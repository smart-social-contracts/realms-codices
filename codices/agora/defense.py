"""
Defense Codex
A community defense fund for security, audits, and infrastructure protection.

How it works:
  1. A configurable percentage of total income goes to the Defense Fund.
  2. Active members can voluntarily enlist as defenders.
  3. The community proposes defense missions via governance (type "defense_mission").
  4. Approved missions are funded from the Defense Fund.
  5. Enlisted defenders who participate in missions receive compensation.

In a digital realm, "defense" means things like security audits, bug bounties,
infrastructure monitoring, and protecting the realm from attacks.
"""

from _cdk import ic
from ggg import Proposal, Vote, User, Member, Transfer, Notification
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json

import budget
import governance


# ---------------------------------------------------------------------------
# Configuration (can be changed via governance proposals)
# ---------------------------------------------------------------------------

DEFENSE_PERCENT_OF_BUDGET = 10   # % of total income allocated to defense
MISSION_VOTE_DAYS = 7            # days to vote on a defense mission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso():
    return epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")


def _get_enlisted_ids() -> list:
    """Return user IDs of all currently enlisted defenders."""
    ids = []
    for p in Proposal.instances():
        try:
            meta = json.loads(p.metadata) if p.metadata else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if meta.get("type") == "defense_enlistment" and p.status == "enlisted":
            uid = meta.get("user_id")
            if uid and governance._is_active_member(uid):
                ids.append(uid)
    return ids


# ---------------------------------------------------------------------------
# Enlistment
# ---------------------------------------------------------------------------

def enlist(user_id: str) -> dict:
    """Voluntarily enlist as a defender. Only active members can enlist."""
    if not governance._is_active_member(user_id):
        return {"enlisted": False, "reason": "Only active members can enlist."}

    # Check if already enlisted
    if user_id in _get_enlisted_ids():
        return {"enlisted": False, "reason": "You are already enlisted."}

    metadata = json.dumps({
        "type": "defense_enlistment",
        "user_id": user_id,
        "enlisted_at": _now_iso(),
    })

    user = User[user_id]
    record = Proposal(
        title=f"Enlistment: {user_id}",
        description=f"Voluntary defense enlistment for {user_id}",
        status="enlisted",
        proposer=user,
        metadata=metadata,
    )

    ic.print(f"Member {user_id} enlisted as defender (record #{record.id})")

    return {
        "enlisted": True,
        "user_id": user_id,
        "record_id": record.id,
    }


def resign(user_id: str) -> dict:
    """Resign from defense duty."""
    for p in Proposal.instances():
        try:
            meta = json.loads(p.metadata) if p.metadata else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if (meta.get("type") == "defense_enlistment"
                and meta.get("user_id") == user_id
                and p.status == "enlisted"):
            p.status = "resigned"
            ic.print(f"Member {user_id} resigned from defense duty")
            return {"resigned": True, "user_id": user_id}

    return {"resigned": False, "reason": "You are not currently enlisted."}


# ---------------------------------------------------------------------------
# Defense Missions
# ---------------------------------------------------------------------------

def propose_mission(user_id: str, title: str, description: str,
                    budget_satoshis: int) -> dict:
    """Propose a defense mission for community vote.

    Examples of missions: security audit, bug bounty program,
    infrastructure monitoring, emergency response.
    """
    if not governance._is_active_member(user_id):
        return {"proposed": False, "reason": "Only active members can propose missions."}

    if budget_satoshis <= 0:
        return {"proposed": False, "reason": "Mission budget must be greater than zero."}

    # Check that the requested budget doesn't exceed the defense fund
    status = get_defense_status()
    if budget_satoshis > status["available_satoshis"]:
        return {
            "proposed": False,
            "reason": f"Budget exceeds available defense funds "
                      f"({status['available_satoshis']} satoshis available).",
        }

    now_epoch = ic_time_to_epoch(ic.time())
    vote_deadline = epoch_to_datetime_str(
        now_epoch + MISSION_VOTE_DAYS * 86400
    ).replace(" ", "T")

    metadata = json.dumps({
        "type": "defense_mission",
        "budget_satoshis": budget_satoshis,
        "proposed_by": user_id,
        "proposed_at": _now_iso(),
    })

    user = User[user_id]
    mission = Proposal(
        title=f"Mission: {title}",
        description=description,
        status="voting",
        deadline=vote_deadline,
        proposer=user,
        metadata=metadata,
    )

    ic.print(f"Defense mission #{mission.id} proposed: {title} ({budget_satoshis} sat)")

    # Notify all members
    for member in Member.instances():
        if member.identity_verification == "verified" and member.user:
            Notification(
                topic="defense",
                title=f"Defense Mission Proposed: {title}",
                message=f"A defense mission has been proposed with a budget of "
                        f"{budget_satoshis} satoshis. Vote before {vote_deadline[:10]}.",
                user=member.user,
                read=False,
                icon="shield",
                href="/extensions/voting",
                color="blue",
                metadata=f"mission_id:{mission.id}"
            )

    return {
        "proposed": True,
        "mission_id": mission.id,
        "title": title,
        "budget_satoshis": budget_satoshis,
        "vote_deadline": vote_deadline,
    }


# ---------------------------------------------------------------------------
# Mission Processing (Scheduled Task)
# ---------------------------------------------------------------------------

def process_missions() -> dict:
    """Tally votes on defense missions whose deadline has passed.

    Approved missions have their budget allocated from the defense fund.
    """
    now_str = _now_iso()
    processed = 0
    approved = 0
    rejected = 0

    active_members = governance._count_active_members()

    for mission in Proposal.instances():
        if mission.status != "voting":
            continue

        try:
            meta = json.loads(mission.metadata) if mission.metadata else {}
        except (json.JSONDecodeError, TypeError):
            continue

        if meta.get("type") != "defense_mission":
            continue

        try:
            if mission.deadline and mission.deadline > now_str:
                continue
        except (ValueError, TypeError):
            continue

        # Tally votes
        yes_votes = 0
        no_votes = 0
        for v in Vote.instances():
            if v.proposal and v.proposal.id == mission.id:
                if v.vote == "yes":
                    yes_votes += 1
                elif v.vote == "no":
                    no_votes += 1

        total_votes = yes_votes + no_votes
        processed += 1

        # Check quorum
        quorum_needed = max(1, int(active_members * governance.QUORUM_PERCENT / 100))
        if total_votes < quorum_needed:
            mission.status = "no_quorum"
            ic.print(f"Mission #{mission.id} — no quorum ({total_votes}/{quorum_needed})")
            continue

        # Simple majority
        if total_votes > 0 and (yes_votes / total_votes) > governance.APPROVAL_THRESHOLD:
            mission.status = "approved"
            approved += 1
            _fund_mission(mission, meta)
        else:
            mission.status = "rejected"
            rejected += 1
            ic.print(f"Mission #{mission.id} rejected ({yes_votes}/{total_votes})")

    return {"processed": processed, "approved": approved, "rejected": rejected}


def _fund_mission(mission, meta: dict):
    """Allocate funds for an approved defense mission."""
    budget_sat = meta.get("budget_satoshis", 0)
    amount_btc = budget_sat / budget.SATOSHIS_PER_BTC

    budget.record_service_payment(
        recipient="defense_fund",
        amount_btc=amount_btc,
        currency="ckBTC",
        description=f"Defense mission — {mission.title}"
    )

    ic.print(f"Mission #{mission.id} approved and funded: {budget_sat} sat")

    if mission.proposer:
        Notification(
            topic="defense",
            title=f"Mission Approved: {mission.title}",
            message=f"The defense mission has been approved with {budget_sat} satoshis.",
            user=mission.proposer,
            read=False,
            icon="shield",
            href="/extensions/voting",
            color="green",
            metadata=f"mission_id:{mission.id}"
        )


# ---------------------------------------------------------------------------
# Scheduled Task Entry Point
# ---------------------------------------------------------------------------

def async_task():
    """Entry point for the Task Manager scheduled execution."""
    return process_missions()


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_defense_status() -> dict:
    """Return current defense fund status."""
    income = budget.calculate_total_income()
    total_income_sat = income["total_income_satoshis"]

    defense_budget_sat = int(total_income_sat * DEFENSE_PERCENT_OF_BUDGET / 100)

    # Calculate how much has already been spent on defense
    defense_spent_sat = 0
    from ggg import LedgerEntry, EntryType
    for entry in LedgerEntry.instances():
        if (entry.entry_type == EntryType.EXPENSE
                and entry.debit and entry.debit > 0):
            desc = entry.description or ""
            if "defense" in desc.lower() or "Defense" in desc:
                defense_spent_sat += entry.debit

    available_sat = max(0, defense_budget_sat - defense_spent_sat)

    enlisted = _get_enlisted_ids()

    return {
        "defense_percent_of_budget": DEFENSE_PERCENT_OF_BUDGET,
        "defense_budget_satoshis": defense_budget_sat,
        "defense_spent_satoshis": defense_spent_sat,
        "available_satoshis": available_sat,
        "enlisted_defenders": len(enlisted),
    }


def get_mission_summary(mission_id: str) -> dict:
    """Get details about a defense mission."""
    mission = Proposal[mission_id]
    if not mission:
        return {"error": "Mission not found"}

    try:
        meta = json.loads(mission.metadata) if mission.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    yes_votes = 0
    no_votes = 0
    for v in Vote.instances():
        if v.proposal and v.proposal.id == mission_id:
            if v.vote == "yes":
                yes_votes += 1
            elif v.vote == "no":
                no_votes += 1

    return {
        "mission_id": mission.id,
        "title": mission.title,
        "status": mission.status,
        "deadline": mission.deadline,
        "budget_satoshis": meta.get("budget_satoshis"),
        "proposed_by": meta.get("proposed_by"),
        "yes_votes": yes_votes,
        "no_votes": no_votes,
    }


if __name__ == "__main__":
    print(json.dumps(get_defense_status(), indent=2))
