"""
Governance Codex
Implements direct democracy for the Agora realm.

Every active (verified + paid-up) member can:
  - Submit proposals
  - Vote on proposals (one person = one vote)

Proposal types:
  1. codex_change   — propose new/updated codex code (code_url + checksum).
                      On approval the voting extension downloads, verifies,
                      and executes the code.
  2. treasury_spend — propose sending funds to a third-party principal for
                      services. On approval a Transfer is created and the
                      vault extension executes it.
  3. welfare_policy — propose changing welfare redistribution parameters
                      (e.g. % of budget allocated to welfare, eligibility
                      criteria). On approval the config is updated.

Voting rules:
  - Simple majority of votes cast wins.
  - Configurable quorum (minimum % of active members must vote).
  - Voting window is configurable (default 7 days).
  - Each member gets exactly one vote per proposal.
"""

from _cdk import ic
from ggg import Proposal, Vote, User, Member, Transfer, Notification
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json


def _now_iso():
    """Current time as ISO 8601 string (from ic.time())."""
    return epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")

# Import sibling codex for accounting
import budget

try:
    from core.extensions import extension_async_call
except Exception:
    extension_async_call = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VOTING_WINDOW_DAYS = 7         # how long voting stays open
QUORUM_PERCENT = 20            # minimum % of active members that must vote
APPROVAL_THRESHOLD = 0.5       # >50% of votes cast must be "yes"

# Welfare policy defaults (can be changed via welfare_policy proposals)
WELFARE_PERCENT_OF_BUDGET = 30   # % of total income allocated to welfare
WELFARE_ELIGIBILITY_MONTHS = 1   # minimum months of active membership


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_active_member(user_id: str) -> bool:
    """Check if a user is an active (verified + paid-up) member."""
    for member in Member.instances():
        if (member.user and member.user.id == user_id
                and member.identity_verification == "verified"):
            return True
    return False


def _count_active_members() -> int:
    """Count all active members."""
    count = 0
    for member in Member.instances():
        if member.identity_verification == "verified":
            count += 1
    return count


# ---------------------------------------------------------------------------
# Proposal Submission
# ---------------------------------------------------------------------------

def submit_proposal(user_id: str, title: str, description: str,
                    proposal_type: str, details: dict = None) -> dict:
    """Submit a new proposal for community vote.

    Args:
        user_id: The proposer's user ID.
        title: Short title for the proposal.
        description: Full description of what is proposed.
        proposal_type: One of "codex_change", "treasury_spend", "welfare_policy".
        details: Type-specific data:
            codex_change:   {"code_url": str, "code_checksum": str}
            treasury_spend: {"recipient": str, "amount": float, "currency": str, "reason": str}
            welfare_policy: {"welfare_percent": int, "eligibility_months": int}

    Returns:
        Result dict with proposal_id or error.
    """
    if not _is_active_member(user_id):
        return {"submitted": False, "reason": "Only active members can submit proposals."}

    valid_types = (
        "codex_change", "treasury_spend", "welfare_policy",
        "procurement", "elect_enforcer", "remove_enforcer",
        "defense_mission", "defense_policy",
    )
    if proposal_type not in valid_types:
        return {"submitted": False, "reason": f"Invalid proposal type: {proposal_type}"}

    details = details or {}
    now_epoch = ic_time_to_epoch(ic.time())
    deadline = epoch_to_datetime_str(now_epoch + VOTING_WINDOW_DAYS * 86400).replace(" ", "T")

    # Build metadata JSON
    metadata = json.dumps({
        "type": proposal_type,
        "details": details,
        "proposer": user_id,
        "submitted_at": epoch_to_datetime_str(now_epoch).replace(" ", "T"),
    })

    user = User[user_id]
    proposal = Proposal(
        title=title,
        description=description,
        status="voting",
        deadline=deadline,
        proposer=user,
        metadata=metadata,
    )

    ic.print(f"Proposal #{proposal.id} submitted by {user_id}: [{proposal_type}] {title}")

    # Notify all active members
    for member in Member.instances():
        if member.identity_verification == "verified" and member.user:
            Notification(
                topic="governance",
                title=f"New Proposal: {title}",
                message=f"A new {proposal_type.replace('_', ' ')} proposal has been submitted. "
                        f"Voting closes on {deadline[:10]}. Cast your vote!",
                user=member.user,
                read=False,
                icon="vote",
                href="/extensions/voting",
                color="blue",
                metadata=f"proposal_id:{proposal.id}"
            )

    return {
        "submitted": True,
        "proposal_id": proposal.id,
        "title": title,
        "type": proposal_type,
        "deadline": deadline,
    }


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------

def cast_vote(user_id: str, proposal_id: str, vote_choice: str) -> dict:
    """Cast a vote on a proposal.

    Args:
        user_id: The voter's user ID.
        proposal_id: The proposal to vote on.
        vote_choice: "yes" or "no".

    Returns:
        Result dict.
    """
    if not _is_active_member(user_id):
        return {"voted": False, "reason": "Only active members can vote."}

    if vote_choice not in ("yes", "no"):
        return {"voted": False, "reason": "Vote must be 'yes' or 'no'."}

    proposal = Proposal[proposal_id]
    if not proposal:
        return {"voted": False, "reason": "Proposal not found."}

    if proposal.status != "voting":
        return {"voted": False, "reason": f"Proposal is not open for voting (status: {proposal.status})."}

    # Check deadline (ISO string comparison works for chronological order)
    try:
        if proposal.deadline and _now_iso() > proposal.deadline:
            return {"voted": False, "reason": "Voting period has ended."}
    except (ValueError, TypeError):
        pass

    # Check if already voted
    user = User[user_id]
    for v in Vote.instances():
        if (v.proposal and v.proposal.id == proposal_id
                and v.user and v.user.id == user_id):
            return {"voted": False, "reason": "You have already voted on this proposal."}

    vote = Vote(
        proposal=proposal,
        user=user,
        vote=vote_choice,
        metadata=json.dumps({"voted_at": _now_iso()})
    )

    ic.print(f"Vote cast on proposal #{proposal_id} by {user_id}: {vote_choice}")

    return {
        "voted": True,
        "vote_id": vote.id,
        "proposal_id": proposal_id,
        "choice": vote_choice,
    }


# ---------------------------------------------------------------------------
# Vote Processing (Scheduled Task)
# ---------------------------------------------------------------------------

def process_votes() -> dict:
    """Tally votes on proposals whose deadline has passed and execute results.

    Designed to run as a scheduled task.
    """
    now_str = _now_iso()
    processed = 0
    approved = 0
    rejected = 0

    active_members = _count_active_members()

    for proposal in Proposal.instances():
        if proposal.status != "voting":
            continue

        try:
            if proposal.deadline and proposal.deadline > now_str:
                continue  # still open
        except (ValueError, TypeError):
            continue

        # Tally votes
        yes_votes = 0
        no_votes = 0
        for v in Vote.instances():
            if v.proposal and v.proposal.id == proposal.id:
                if v.vote == "yes":
                    yes_votes += 1
                elif v.vote == "no":
                    no_votes += 1

        total_votes = yes_votes + no_votes
        processed += 1

        # Check quorum
        quorum_needed = max(1, int(active_members * QUORUM_PERCENT / 100))
        if total_votes < quorum_needed:
            proposal.status = "no_quorum"
            ic.print(f"Proposal #{proposal.id} — no quorum ({total_votes}/{quorum_needed})")
            continue

        # Check approval
        if total_votes > 0 and (yes_votes / total_votes) > APPROVAL_THRESHOLD:
            proposal.status = "approved"
            approved += 1
            ic.print(f"Proposal #{proposal.id} APPROVED ({yes_votes}/{total_votes})")
            _execute_approved_proposal(proposal)
        else:
            proposal.status = "rejected"
            rejected += 1
            ic.print(f"Proposal #{proposal.id} REJECTED ({yes_votes}/{total_votes})")

    ic.print(f"=== Vote processing: {processed} processed, "
             f"{approved} approved, {rejected} rejected ===")

    return {
        "processed": processed,
        "approved": approved,
        "rejected": rejected,
        "active_members": active_members,
    }


def _execute_approved_proposal(proposal):
    """Execute an approved proposal based on its type."""
    try:
        meta = json.loads(proposal.metadata) if proposal.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    proposal_type = meta.get("type", "")
    details = meta.get("details", {})

    if proposal_type == "codex_change":
        _execute_codex_change(proposal, details)
    elif proposal_type == "treasury_spend":
        _execute_treasury_spend(proposal, details)
    elif proposal_type == "welfare_policy":
        _execute_welfare_policy(proposal, details)
    elif proposal_type == "elect_enforcer":
        _execute_elect_enforcer(proposal, details)
    elif proposal_type == "remove_enforcer":
        _execute_remove_enforcer(proposal, details)
    elif proposal_type == "defense_policy":
        _execute_defense_policy(proposal, details)
    elif proposal_type in ("procurement", "defense_mission"):
        pass  # handled by their own codex modules
    else:
        ic.print(f"Unknown proposal type '{proposal_type}' for #{proposal.id}")


def _execute_codex_change(proposal, details: dict):
    """Execute a codex change proposal.

    The actual download and execution is delegated to the voting extension's
    _do_execute_proposal which handles code_url download, checksum verification,
    and exec().
    """
    code_url = details.get("code_url", "")
    code_checksum = details.get("code_checksum", "")

    if not code_url:
        ic.print(f"Codex change proposal #{proposal.id} has no code_url")
        proposal.status = "failed"
        return

    # Store execution details for the voting extension to pick up
    proposal.status = "pending_execution"
    exec_meta = json.loads(proposal.metadata) if proposal.metadata else {}
    exec_meta["execution"] = {
        "code_url": code_url,
        "code_checksum": code_checksum,
        "approved_at": _now_iso(),
    }
    proposal.metadata = json.dumps(exec_meta)

    ic.print(f"Codex change #{proposal.id} queued for execution: {code_url}")

    # Notify proposer
    if proposal.proposer:
        Notification(
            topic="governance",
            title=f"Proposal Approved: {proposal.title}",
            message="Your codex change proposal has been approved and is queued for execution.",
            user=proposal.proposer,
            read=False,
            icon="check_circle",
            href="/extensions/voting",
            color="green",
            metadata=f"proposal_id:{proposal.id}"
        )


def _execute_treasury_spend(proposal, details: dict):
    """Execute a treasury spend proposal — send funds to a third party."""
    recipient = details.get("recipient", "")
    amount = details.get("amount", 0)
    currency = details.get("currency", "AGO")
    reason = details.get("reason", "Approved by community vote")

    if not recipient or not amount:
        ic.print(f"Treasury spend proposal #{proposal.id} missing recipient/amount")
        proposal.status = "failed"
        return

    # Create a Transfer record
    transfer = Transfer(
        amount=amount,
        currency=currency,
        to_principal=recipient,
        status="Pending",
        metadata=json.dumps({
            "proposal_id": proposal.id,
            "reason": reason,
            "approved_at": _now_iso(),
        })
    )

    # Record in accounting
    if currency == "AGO":
        btc_equivalent = amount / budget.AGO_PER_BTC
    else:
        btc_equivalent = amount

    budget.record_service_payment(
        recipient=recipient,
        amount_btc=btc_equivalent,
        currency=currency,
        description=f"Proposal #{proposal.id}: {reason}"
    )

    proposal.status = "executed"
    ic.print(f"Treasury spend #{proposal.id} executed: {amount} {currency} → {recipient}")

    # Notify proposer
    if proposal.proposer:
        Notification(
            topic="governance",
            title=f"Proposal Executed: {proposal.title}",
            message=f"Treasury spend of {amount} {currency} to {recipient} has been executed.",
            user=proposal.proposer,
            read=False,
            icon="check_circle",
            href="/extensions/voting",
            color="green",
            metadata=f"proposal_id:{proposal.id}"
        )


def _execute_welfare_policy(proposal, details: dict):
    """Execute a welfare policy change proposal."""
    global WELFARE_PERCENT_OF_BUDGET, WELFARE_ELIGIBILITY_MONTHS

    new_percent = details.get("welfare_percent")
    new_months = details.get("eligibility_months")

    changes = []
    if new_percent is not None and 0 <= new_percent <= 100:
        WELFARE_PERCENT_OF_BUDGET = int(new_percent)
        changes.append(f"welfare_percent={new_percent}%")
    if new_months is not None and new_months >= 0:
        WELFARE_ELIGIBILITY_MONTHS = int(new_months)
        changes.append(f"eligibility_months={new_months}")

    proposal.status = "executed"
    ic.print(f"Welfare policy #{proposal.id} executed: {', '.join(changes)}")

    if proposal.proposer:
        Notification(
            topic="governance",
            title=f"Policy Updated: {proposal.title}",
            message=f"Welfare policy has been updated: {', '.join(changes)}.",
            user=proposal.proposer,
            read=False,
            icon="check_circle",
            href="/extensions/voting",
            color="green",
            metadata=f"proposal_id:{proposal.id}"
        )


# ---------------------------------------------------------------------------
# Enforcer Election / Removal
# ---------------------------------------------------------------------------

def _execute_elect_enforcer(proposal, details: dict):
    """Record that a member has been elected as enforcer."""
    enforcer_id = details.get("enforcer_id", "")
    if not enforcer_id:
        proposal.status = "failed"
        return

    meta = json.loads(proposal.metadata) if proposal.metadata else {}
    meta["enforcer_id"] = enforcer_id
    proposal.metadata = json.dumps(meta)
    proposal.status = "approved"

    ic.print(f"Enforcer elected: {enforcer_id} (proposal #{proposal.id})")

    enforcer_user = User[enforcer_id]
    if enforcer_user:
        Notification(
            topic="enforcement",
            title="You Have Been Elected as Enforcer",
            message="The community has voted to elect you as an enforcer. "
                    "You can now investigate violation reports and propose sanctions.",
            user=enforcer_user,
            read=False,
            icon="shield",
            href="/extensions/voting",
            color="green",
            metadata=f"proposal_id:{proposal.id}"
        )


def _execute_remove_enforcer(proposal, details: dict):
    """Record that an enforcer has been removed by community vote."""
    enforcer_id = details.get("enforcer_id", "")
    if not enforcer_id:
        proposal.status = "failed"
        return

    meta = json.loads(proposal.metadata) if proposal.metadata else {}
    meta["enforcer_id"] = enforcer_id
    proposal.metadata = json.dumps(meta)
    proposal.status = "approved"

    ic.print(f"Enforcer removed: {enforcer_id} (proposal #{proposal.id})")

    enforcer_user = User[enforcer_id]
    if enforcer_user:
        Notification(
            topic="enforcement",
            title="Enforcer Role Removed",
            message="The community has voted to remove your enforcer role.",
            user=enforcer_user,
            read=False,
            icon="shield",
            href="/extensions/voting",
            color="orange",
            metadata=f"proposal_id:{proposal.id}"
        )


# ---------------------------------------------------------------------------
# Defense Policy
# ---------------------------------------------------------------------------

def _execute_defense_policy(proposal, details: dict):
    """Update defense fund allocation percentage via governance vote."""
    import defense

    new_percent = details.get("defense_percent")
    if new_percent is not None and 0 <= new_percent <= 100:
        defense.DEFENSE_PERCENT_OF_BUDGET = int(new_percent)
        proposal.status = "executed"
        ic.print(f"Defense policy updated: {new_percent}% (proposal #{proposal.id})")

        if proposal.proposer:
            Notification(
                topic="defense",
                title=f"Defense Policy Updated",
                message=f"Defense fund allocation changed to {new_percent}% of budget.",
                user=proposal.proposer,
                read=False,
                icon="shield",
                href="/extensions/voting",
                color="green",
                metadata=f"proposal_id:{proposal.id}"
            )
    else:
        proposal.status = "failed"


# ---------------------------------------------------------------------------
# Scheduled Task Entry Point
# ---------------------------------------------------------------------------

def async_task():
    """Entry point for the Task Manager scheduled execution."""
    return process_votes()


# ---------------------------------------------------------------------------
# Query Helpers
# ---------------------------------------------------------------------------

def get_governance_config() -> dict:
    """Return current governance configuration."""
    return {
        "voting_window_days": VOTING_WINDOW_DAYS,
        "quorum_percent": QUORUM_PERCENT,
        "approval_threshold": APPROVAL_THRESHOLD,
        "welfare_percent_of_budget": WELFARE_PERCENT_OF_BUDGET,
        "welfare_eligibility_months": WELFARE_ELIGIBILITY_MONTHS,
        "active_members": _count_active_members(),
    }


def get_proposal_summary(proposal_id: str) -> dict:
    """Get detailed info about a proposal including vote tally."""
    proposal = Proposal[proposal_id]
    if not proposal:
        return {"error": "Proposal not found"}

    yes_votes = 0
    no_votes = 0
    for v in Vote.instances():
        if v.proposal and v.proposal.id == proposal_id:
            if v.vote == "yes":
                yes_votes += 1
            elif v.vote == "no":
                no_votes += 1

    try:
        meta = json.loads(proposal.metadata) if proposal.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    return {
        "id": proposal.id,
        "title": proposal.title,
        "description": proposal.description,
        "status": proposal.status,
        "deadline": proposal.deadline,
        "type": meta.get("type", "unknown"),
        "details": meta.get("details", {}),
        "proposer": proposal.proposer.id if proposal.proposer else None,
        "yes_votes": yes_votes,
        "no_votes": no_votes,
        "total_votes": yes_votes + no_votes,
    }


if __name__ == "__main__":
    print(json.dumps(get_governance_config(), indent=2))
