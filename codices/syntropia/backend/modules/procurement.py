"""
Procurement Codex
Manages procurement projects funded from the budget's procurement pool.

Workflow:
  1. propose_project()   — any member can propose a project (creates Proposal)
  2. Members vote via governance_automation / voting extension
  3. approve_project()   — after vote passes, marks project as approved
  4. disburse_project()  — transfers ckBTC to the receiver principal
  5. get_project_status() — inspect a single project
  6. list_projects()     — list all procurement proposals

The procurement pool is managed by budget_plan.record_expenditure().
"""

from ggg import Proposal, Transfer, User, Member, Notification, Treasury
from datetime import datetime, timedelta
import json
import os

from ggg import extension_call as extension_async_call

try:
    from invoice_currency import invoice_currency, no_treasury_token_error
except ImportError:
    from ..invoice_currency import invoice_currency, no_treasury_token_error


def _manifest() -> dict:
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(3):
        candidate = os.path.join(d, "manifest.json")
        if os.path.exists(candidate):
            with open(candidate) as f:
                return json.load(f)
        d = os.path.dirname(d)
    return {}


def _treasury_currency() -> str:
    return invoice_currency(_manifest())


# ---------------------------------------------------------------------------
# Helpers — project data stored in Proposal.description (max 2048 chars)
# ---------------------------------------------------------------------------

def _load_project(proposal) -> dict:
    """Load project dict from proposal.description (JSON)."""
    try:
        return json.loads(proposal.description) if proposal.description else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _save_project(proposal, project: dict):
    """Save project dict to proposal.description."""
    proposal.description = json.dumps(project, separators=(",", ":"))


def _find_proposal(proposal_id: str):
    """Find a Proposal by proposal_id."""
    return next(
        (p for p in Proposal.instances() if p.proposal_id == proposal_id),
        None,
    )


# ---------------------------------------------------------------------------
# Project Proposal
# ---------------------------------------------------------------------------

def propose_project(name: str, desc: str, amount_satoshis: int,
                    receiver_principal: str, proposer_user_id: str = "system",
                    voting_days: int = 14) -> dict:
    """Propose a new procurement project for voting.

    Args:
        name: Short project name.
        desc: What the project delivers.
        amount_satoshis: Cost in ckBTC satoshis.
        receiver_principal: IC principal that will receive the funds.
        proposer_user_id: User ID of the proposer.
        voting_days: How long the vote stays open.

    Returns:
        Project proposal dict with proposal_id.
    """
    deadline = (datetime.now() + timedelta(days=voting_days)).isoformat()

    project = {
        "name": name,
        "amt": amount_satoshis,
        "rcv": receiver_principal,
        "by": proposer_user_id,
        "st": "proposed",
    }

    existing = Proposal.instances()
    num = len([p for p in existing if p.metadata == "branch:procurement"]) + 1
    pid = "proc_" + str(num).zfill(3)

    proposal = Proposal(
        proposal_id=pid,
        title="Procurement: " + name,
        description=json.dumps(project, separators=(",", ":")),
        status="debate",
        voting_deadline=deadline,
        metadata="branch:procurement",
    )

    project["proposal_id"] = pid
    return project


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

def approve_project(proposal_id: str) -> dict:
    """Mark a procurement project as approved after the vote passes."""
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    if proposal.metadata != "branch:procurement":
        return {"error": "Proposal is not a procurement project"}

    if proposal.status not in ("debate", "passed_parliament"):
        return {"error": f"Cannot approve proposal in status '{proposal.status}'"}

    project = _load_project(proposal)
    project["st"] = "approved"
    _save_project(proposal, project)
    proposal.status = "enacted"

    return {"proposal_id": proposal_id, "status": "approved"}


# ---------------------------------------------------------------------------
# Disbursement
# ---------------------------------------------------------------------------

def disburse_project(proposal_id: str, budget_proposal_id: str) -> "Async[str]":
    """Disburse ckBTC for an approved procurement project.

    Steps:
      1. Verify project is approved
      2. Draw from the budget procurement pool via budget_plan
      3. Transfer ckBTC to the receiver principal via vault extension
      4. Record the expense in the fund ledger (Financial Reports, issue #260)

    Args:
        proposal_id: The procurement proposal ID.
        budget_proposal_id: The approved annual budget proposal ID.

    Returns:
        JSON result string (async generator for vault call).
    """
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return json.dumps({"error": "Proposal not found"})

    project = _load_project(proposal)

    if project.get("st") != "approved":
        return json.dumps({"error": "Project must be approved before disbursement"})

    amount = project["amt"]
    receiver = project["rcv"]

    # Record expenditure against the budget procurement pool
    try:
        from codices.syntropia.budget_plan import record_expenditure
        budget_result = record_expenditure(
            budget_proposal_id, "procurement", amount,
            description="Procurement: " + project.get("name", "")
        )
        if "error" in budget_result:
            return json.dumps(budget_result)
    except ImportError:
        pass  # budget tracking unavailable, proceed anyway

    # Transfer via vault extension
    args = json.dumps({
        "to_principal": receiver,
        "amount": amount,
    })
    result = yield extension_async_call("vault", "transfer", args)

    # Only mark disbursed (and book the expense) if the transfer succeeded.
    try:
        result_dict = json.loads(result) if isinstance(result, str) else (result or {})
    except (json.JSONDecodeError, TypeError):
        result_dict = {}
    if isinstance(result_dict, dict) and result_dict.get("success") is False:
        return json.dumps({
            "error": f"Vault transfer failed: {result_dict.get('error', 'unknown')}",
            "proposal_id": proposal_id,
        })

    _record_disbursement_accounting(proposal_id, project, amount, receiver)

    # Update project status
    project["st"] = "disbursed"
    _save_project(proposal, project)

    return json.dumps({
        "proposal_id": proposal_id,
        "status": "disbursed",
        "amount_satoshis": amount,
        "receiver": receiver,
    })


def _record_disbursement_accounting(proposal_id: str, project: dict,
                                    amount: int, receiver: str):
    """Book a procurement disbursement in the fund ledger (issue #260).

    Creates a Transfer record plus balanced double-entry ledger lines
    (capital expense / cash) against the realm's general fund, so procurement
    spending shows up in Financial Reports instead of bypassing accounting.
    """
    try:
        from ggg import Fund

        general_fund = next(
            (f for f in Fund.instances() if (f.fund_type or "") == "general"),
            None,
        )

        currency = _treasury_currency()
        if not currency:
            print("procurement: accounting skipped — no treasury token resolved")
            return

        transfer_id = "PROC-" + proposal_id
        transfer = Transfer(
            id=transfer_id,
            principal_from="vault",
            principal_to=receiver,
            instrument=currency,
            amount=amount,
            timestamp=datetime.now().isoformat(),
            tags="procurement",
            status="completed",
        )
        transfer.record_accounting(
            fund=general_fund,
            expense_category="capital",
            description="Procurement: " + project.get("name", proposal_id),
        )
    except Exception as e:
        # Accounting must never block a successful disbursement.
        print(f"procurement: accounting for {proposal_id} failed: {e}")


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_project_status(proposal_id: str) -> dict:
    """Get the status of a procurement project."""
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    if proposal.metadata != "branch:procurement":
        return {"error": "Not a procurement proposal"}

    project = _load_project(proposal)
    return {
        "proposal_id": proposal_id,
        "name": project.get("name"),
        "status": project.get("st"),
        "amount_satoshis": project.get("amt"),
        "receiver": project.get("rcv"),
        "proposer": project.get("by"),
        "vote_status": proposal.status,
    }


def list_projects() -> list:
    """List all procurement proposals with their status."""
    projects = []
    for p in Proposal.instances():
        if p.metadata != "branch:procurement":
            continue
        project = _load_project(p)
        projects.append({
            "proposal_id": p.proposal_id,
            "name": project.get("name"),
            "status": project.get("st"),
            "amount_satoshis": project.get("amt"),
            "receiver": project.get("rcv"),
            "vote_status": p.status,
        })
    return projects


# Main execution
if __name__ == "__main__":
    project = propose_project(
        name="Community Center",
        desc="Build a community center for member gatherings",
        amount_satoshis=50000,
        receiver_principal="aaaaa-aa",
    )
    print(json.dumps(project, indent=2))
