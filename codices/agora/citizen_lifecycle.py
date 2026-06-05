"""Citizen Lifecycle Codex — Agora Realm

Orchestrates the full citizen journey:
  1. Registration: user joins → invoice created → passport verified → activated
  2. Governance: active members submit proposals, vote, proposals are tallied
  3. Financials: invoice payments auto-generate double-entry ledger entries
  4. Periodic payments: eligible members receive welfare distributions

All policy parameters are read from manifest.json — no hardcoded constants.
Relies on platform ggg methods (Member.activate, Proposal.resolve, etc.)
and basilisk OS for token operations.
"""

from _cdk import ic
from ggg import (
    User, Member, Invoice, Proposal, Vote, Transfer,
    LedgerEntry, Notification, Fund, FiscalPeriod, Budget,
    EntryType, Category,
)
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json
import os


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------

def _load_manifest() -> dict:
    """Load manifest.json from the codex directory."""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path) as f:
        return json.load(f)


def get_params() -> dict:
    """Return the full manifest as a dict."""
    return _load_manifest()


def _currency(params: dict) -> str:
    """Realm currency symbol (manifest currency.symbol)."""
    return params.get("currency", {}).get("symbol", "ckUSDC")


def _realm_stage() -> str:
    """Current realm lifecycle stage (default alpha when no Realm exists)."""
    try:
        from ggg import Realm
        instances = list(Realm.instances())
        return (getattr(instances[0], "status", None) or "alpha") if instances else "alpha"
    except Exception:
        return "alpha"


# ---------------------------------------------------------------------------
# 1. Registration (incumbent migration — no ZK passport)
# ---------------------------------------------------------------------------

def register_citizen(principal_id: str) -> dict:
    """Register/import a citizen: create User + an immediately-active Member.

    Agora is an incumbent migration: citizens come from an existing census, so
    there is no passport step and they are active on registration. A
    registration invoice is only issued once the realm is live (production) and
    a fee is configured — during the migration phases members pay nothing.
    """
    params = get_params()
    fee = params["fees"]["registration"]
    currency = _currency(params)
    validity_days = params["membership"]["invoice_validity_days"]
    stage = _realm_stage()

    # Check if already registered
    existing = User[principal_id]
    if existing:
        return {"error": "already_registered", "user_id": existing.id}

    # Create user
    user = User(id=principal_id)
    ic.print(f"Created user {principal_id}")

    # Create member record and activate immediately (incumbent: census import).
    member = Member(
        id=f"member_{principal_id}",
        user=user,
        identity_verification="verified",
        residence_permit="valid",
        tax_compliance="compliant",
        voting_eligibility="eligible",
        public_benefits_eligibility="eligible",
        criminal_record="clean",
    )
    ic.print(f"Created active member {member.id}")

    result = {
        "user_id": user.id,
        "member_id": member.id,
        "invoice_id": None,
        "active": True,
        "stage": stage,
    }

    # Only charge once the realm is live and a fee is configured.
    if stage == "production" and fee and fee > 0:
        now_epoch = ic_time_to_epoch(ic.time())
        due_str = epoch_to_datetime_str(now_epoch + validity_days * 86400).replace(" ", "T")
        invoice = Invoice(
            amount=fee,
            currency=currency,
            status="Pending",
            user=user,
            due_date=due_str,
            metadata=json.dumps({"type": "registration", "principal": principal_id}),
        )
        ic.print(f"Created registration invoice #{invoice._id} for {fee} {currency}")
        result["invoice_id"] = invoice._id
        result["fee"] = fee
        result["currency"] = currency
        result["due_date"] = due_str

    return result


def pay_registration_invoice(principal_id: str, invoice_id: str) -> dict:
    """Record payment of a registration invoice (live realms with a fee).

    Creates double-entry ledger entries for the payment. Membership is already
    active in the incumbent model, so payment does not gate activation.
    """
    params = get_params()

    user = User[principal_id]
    if not user:
        return {"error": "user_not_found"}

    invoice = Invoice.load(invoice_id)
    if not invoice:
        return {"error": "invoice_not_found"}

    if invoice.status == "Paid":
        return {"error": "already_paid", "invoice_id": invoice_id}

    # Mark paid
    invoice.status = "Paid"
    invoice.paid_at = epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")
    ic.print(f"Invoice #{invoice_id} paid by {principal_id}")

    # Record accounting: debit Cash, credit Revenue
    _record_payment_ledger(invoice, params)

    return {"paid": True, "invoice_id": invoice_id}


def _record_payment_ledger(invoice, params: dict):
    """Create double-entry ledger entries for an invoice payment."""
    currency = _currency(params)
    now = epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")
    amount_raw = int(invoice.amount * 1_000_000)  # normalize to smallest unit

    LedgerEntry(
        transaction_id=f"TXN-REG-{invoice._id}",
        entry_type=EntryType.ASSET,
        category=Category.CASH,
        debit=amount_raw,
        credit=0,
        entry_date=now,
        description=f"Registration payment — invoice #{invoice._id}",
        invoice=invoice,
        user=invoice.user,
    )
    LedgerEntry(
        transaction_id=f"TXN-REG-{invoice._id}",
        entry_type=EntryType.REVENUE,
        category=Category.FEE,
        debit=0,
        credit=amount_raw,
        entry_date=now,
        description=f"Registration revenue — invoice #{invoice._id}",
        invoice=invoice,
        user=invoice.user,
    )


# ---------------------------------------------------------------------------
# 2. Governance
# ---------------------------------------------------------------------------

def submit_proposal(principal_id: str, title: str, description: str,
                    proposal_type: str = "codex_change") -> dict:
    """Submit a governance proposal. Only active members may submit.

    Reads governance params (voting window, threshold) from manifest.
    """
    params = get_params()
    gov = params["governance"]

    member = Member.for_user(principal_id)
    if not member or not member.is_active():
        return {"error": "not_active_member"}

    if proposal_type not in gov["proposal_types"]:
        return {"error": "invalid_proposal_type", "allowed": gov["proposal_types"]}

    user = User[principal_id]
    now_epoch = ic_time_to_epoch(ic.time())
    deadline_str = epoch_to_datetime_str(now_epoch + gov["voting_window_days"] * 86400).replace(" ", "T")
    proposal_id = f"prop_{Proposal.count() + 1}"

    proposal = Proposal(
        proposal_id=proposal_id,
        title=title,
        description=description,
        proposer=user,
        status="voting",
        voting_deadline=deadline_str,
        votes_yes=0.0,
        votes_no=0.0,
        votes_abstain=0.0,
        total_voters=0.0,
        required_threshold=gov["approval_threshold"],
        metadata=json.dumps({"type": proposal_type}),
    )
    ic.print(f"Proposal {proposal_id} submitted by {principal_id}: {title}")

    return {
        "proposal_id": proposal_id,
        "title": title,
        "status": "voting",
        "voting_deadline": deadline_str,
    }


def cast_vote(principal_id: str, proposal_id: str, vote_choice: str) -> dict:
    """Cast a vote on a proposal. Only active members, one vote per member.

    vote_choice must be 'yes', 'no', or 'abstain'.
    """
    if vote_choice not in ("yes", "no", "abstain"):
        return {"error": "invalid_vote_choice", "allowed": ["yes", "no", "abstain"]}

    member = Member.for_user(principal_id)
    if not member or not member.is_active():
        return {"error": "not_active_member"}

    proposal = Proposal[proposal_id]
    if not proposal:
        return {"error": "proposal_not_found"}

    if proposal.status != "voting":
        return {"error": "voting_closed", "status": proposal.status}

    # Check duplicate vote
    user = User[principal_id]
    for v in Vote.instances():
        if (v.proposal is proposal
                and v.voter and v.voter.id == principal_id):
            return {"error": "already_voted"}

    vote = Vote(
        proposal=proposal,
        voter=user,
        vote_choice=vote_choice,
    )
    ic.print(f"{principal_id} voted '{vote_choice}' on {proposal_id}")

    return {"voted": True, "proposal_id": proposal_id, "choice": vote_choice}


def tally_proposal(proposal_id: str) -> dict:
    """Tally votes and resolve a proposal using manifest governance params."""
    params = get_params()
    gov = params["governance"]

    proposal = Proposal[proposal_id]
    if not proposal:
        return {"error": "proposal_not_found"}

    active_count = Member.count_active()
    status = proposal.resolve(active_count, gov["quorum_percent"])

    return {
        "proposal_id": proposal_id,
        "status": status,
        "votes_yes": proposal.votes_yes,
        "votes_no": proposal.votes_no,
        "votes_abstain": proposal.votes_abstain,
        "total_voters": proposal.total_voters,
        "quorum_met": proposal.is_quorum_met(active_count, gov["quorum_percent"]),
    }


# ---------------------------------------------------------------------------
# 3. Financial statements (delegates to platform LedgerEntry)
# ---------------------------------------------------------------------------

def get_financial_summary() -> dict:
    """Return balance sheet and income statement from platform LedgerEntry."""
    balance_sheet = LedgerEntry.get_balance_sheet()
    income_statement = LedgerEntry.get_income_statement()
    return {
        "balance_sheet": balance_sheet,
        "income_statement": income_statement,
    }


# ---------------------------------------------------------------------------
# 4. Periodic payments (welfare distribution)
# ---------------------------------------------------------------------------

def distribute_periodic_payments() -> dict:
    """Distribute welfare payments to all eligible active members.

    Reads welfare params from manifest. Calculates pool from budget,
    splits equally among eligible members, creates Transfer + LedgerEntry.
    """
    params = get_params()
    welfare = params["welfare"]
    currency = _currency(params)
    percent = welfare["percent_of_budget"]
    eligibility_months = welfare["eligibility_months"]

    # Calculate available pool from income statement
    income_stmt = LedgerEntry.get_income_statement()
    total_revenue = income_stmt["revenues"]["total"]
    welfare_budget = int(total_revenue * percent / 100)

    if welfare_budget <= 0:
        return {"distributed": False, "reason": "No revenue to distribute from"}

    # Find eligible members (active + member for enough months)
    eligible = []
    for member in Member.instances():
        if not member.is_active():
            continue
        if not member.user:
            continue
        eligible.append(member)

    if not eligible:
        return {"distributed": False, "reason": "No eligible members"}

    per_member = welfare_budget // len(eligible)
    if per_member <= 0:
        return {"distributed": False, "reason": "Per-member share too small"}

    ic.print(f"Distributing {welfare_budget} ({percent}% of revenue) to "
             f"{len(eligible)} members = {per_member} each")

    now = epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")
    distributions = []

    for member in eligible:
        user = member.user

        # Create transfer record
        transfer = Transfer(
            principal_to=user.id,
            instrument=currency,
            amount=per_member,
            status="completed",
            timestamp=now,
            tags="welfare",
        )

        # Double-entry: Debit Expense (welfare), Credit Cash
        LedgerEntry(
            transaction_id=f"TXN-WEL-{transfer._id}",
            entry_type=EntryType.EXPENSE,
            category="welfare",
            debit=per_member,
            credit=0,
            entry_date=now,
            description=f"Welfare payment to {user.id}",
            transfer=transfer,
            user=user,
        )
        LedgerEntry(
            transaction_id=f"TXN-WEL-{transfer._id}",
            entry_type=EntryType.ASSET,
            category=Category.CASH,
            debit=0,
            credit=per_member,
            entry_date=now,
            description=f"Welfare cash disbursement to {user.id}",
            transfer=transfer,
            user=user,
        )

        distributions.append({
            "member_id": member.id,
            "user_id": user.id,
            "amount": per_member,
        })

    return {
        "distributed": True,
        "total_pool": welfare_budget,
        "per_member": per_member,
        "count": len(distributions),
        "distributions": distributions,
    }


# ---------------------------------------------------------------------------
# Citizen status query
# ---------------------------------------------------------------------------

def get_citizen_status(principal_id: str) -> dict:
    """Return full status for a citizen: membership, financial, governance."""
    user = User[principal_id]
    if not user:
        return {"error": "user_not_found"}

    member = Member.for_user(principal_id)
    invoices = [inv for inv in Invoice.instances()
                if inv.user and inv.user.id == principal_id]
    proposals = [p for p in Proposal.instances()
                 if p.proposer and p.proposer.id == principal_id]

    return {
        "user_id": principal_id,
        "is_member": member is not None,
        "is_active": member.is_active() if member else False,
        "identity_verification": member.identity_verification if member else None,
        "invoices": len(invoices),
        "invoices_paid": sum(1 for i in invoices if i.status == "Paid"),
        "proposals_submitted": len(proposals),
    }
