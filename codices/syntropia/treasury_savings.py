"""
Treasury Savings Codex
Manages the treasury_savings portion of the annual budget.

The savings pool is locked by default. Withdrawals require a supermajority
vote (2/3 of votes cast). This provides a financial safety net for the realm.

Workflow:
  1. Savings are automatically allocated when the annual budget is approved
  2. propose_withdrawal() — create a proposal to withdraw from savings
  3. Members vote (supermajority required: 2/3)
  4. execute_withdrawal() — after vote passes, transfers ckBTC out
  5. get_savings_status() — inspect current savings balance

Note: The savings pool can only be drawn from via this codex. The
budget_plan.record_expenditure() will reject direct draws from
treasury_savings unless called through here.
"""

from ggg import Proposal, Treasury, Transfer, User, Notification
from datetime import datetime, timedelta
import json

try:
    from core.extensions import extension_async_call
except ImportError:
    from ..core.extensions import extension_async_call


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUPERMAJORITY_THRESHOLD = 2 / 3  # 66.7% of votes must be in favour


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_proposal(proposal_id: str):
    """Find a Proposal by proposal_id."""
    return next(
        (p for p in Proposal.instances() if p.proposal_id == proposal_id),
        None,
    )


def _load_withdrawal(proposal) -> dict:
    """Load withdrawal dict from proposal.description (JSON)."""
    try:
        return json.loads(proposal.description) if proposal.description else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _save_withdrawal(proposal, data: dict):
    """Save withdrawal dict to proposal.description."""
    proposal.description = json.dumps(data, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Savings Query
# ---------------------------------------------------------------------------

def get_savings_status() -> dict:
    """Return the current treasury savings balance from the approved budget."""
    try:
        from codices.syntropia.budget_plan import (
            get_approved_budget_proposal_id, get_budget_summary,
        )
    except ImportError:
        return {"error": "budget_plan not available"}

    pid = get_approved_budget_proposal_id()
    if not pid:
        return {"error": "No approved budget found"}

    summary = get_budget_summary(pid)
    if "error" in summary:
        return summary

    ts_cat = summary.get("categories", {}).get("treasury_savings", {})

    return {
        "budget_proposal_id": pid,
        "fiscal_year": summary.get("fiscal_year"),
        "allocated_satoshis": ts_cat.get("allocated", 0),
        "spent_satoshis": ts_cat.get("spent", 0),
        "remaining_satoshis": ts_cat.get("remaining", 0),
        "remaining_ckbtc": ts_cat.get("remaining", 0) / 1e8,
        "locked": True,
        "unlock_requires": "supermajority (2/3) vote",
    }


# ---------------------------------------------------------------------------
# Withdrawal Proposal
# ---------------------------------------------------------------------------

def propose_withdrawal(amount_satoshis: int, justification: str,
                       receiver_principal: str,
                       proposer_user_id: str = "system",
                       voting_days: int = 14) -> dict:
    """Propose a withdrawal from the treasury savings (requires supermajority).

    Args:
        amount_satoshis: Amount to withdraw in ckBTC satoshis.
        justification: Why the withdrawal is needed.
        receiver_principal: IC principal that will receive the funds.
        proposer_user_id: User ID of the proposer.
        voting_days: How long the vote stays open.

    Returns:
        Proposal dict with proposal_id.
    """
    # Verify savings have enough balance
    status = get_savings_status()
    if "error" in status:
        return status

    if amount_satoshis > status["remaining_satoshis"]:
        return {
            "error": f"Insufficient savings: requested {amount_satoshis}, "
                     f"available {status['remaining_satoshis']}"
        }

    deadline = (datetime.now() + timedelta(days=voting_days)).isoformat()

    withdrawal = {
        "amt": amount_satoshis,
        "rcv": receiver_principal,
        "by": proposer_user_id,
        "st": "proposed",
    }

    existing = Proposal.instances()
    num = len([p for p in existing if p.metadata == "branch:treasury_savings"]) + 1
    pid = "tsw_" + str(num).zfill(3)

    proposal = Proposal(
        proposal_id=pid,
        title="Treasury Withdrawal: " + str(amount_satoshis) + " sat",
        description=json.dumps(withdrawal, separators=(",", ":")),
        status="debate",
        voting_deadline=deadline,
        metadata="branch:treasury_savings",
    )

    withdrawal["proposal_id"] = pid
    return withdrawal


# ---------------------------------------------------------------------------
# Vote Checking (supermajority)
# ---------------------------------------------------------------------------

def check_supermajority(proposal_id: str) -> dict:
    """Check if a treasury withdrawal proposal has achieved supermajority.

    Returns:
        Dict with passed (bool), votes_for, votes_against, threshold.
    """
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    if proposal.metadata != "branch:treasury_savings":
        return {"error": "Not a treasury savings proposal"}

    votes_for = proposal.votes_yes or 0
    votes_against = proposal.votes_no or 0
    total = votes_for + votes_against

    if total == 0:
        return {
            "passed": False,
            "reason": "No votes cast",
            "votes_for": 0,
            "votes_against": 0,
            "threshold": SUPERMAJORITY_THRESHOLD,
        }

    ratio = votes_for / total
    passed = ratio >= SUPERMAJORITY_THRESHOLD

    return {
        "passed": passed,
        "votes_for": votes_for,
        "votes_against": votes_against,
        "total_votes": total,
        "approval_ratio": round(ratio, 4),
        "threshold": SUPERMAJORITY_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def execute_withdrawal(proposal_id: str) -> "Async[str]":
    """Execute an approved treasury savings withdrawal.

    Requires supermajority vote to have passed.

    Args:
        proposal_id: The withdrawal proposal ID.

    Returns:
        JSON result string (async generator for vault call).
    """
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return json.dumps({"error": "Proposal not found"})

    if proposal.metadata != "branch:treasury_savings":
        return json.dumps({"error": "Not a treasury savings proposal"})

    withdrawal = _load_withdrawal(proposal)
    if withdrawal.get("st") != "proposed":
        return json.dumps({"error": "Withdrawal already in status: " + str(withdrawal.get("st"))})

    # Verify supermajority
    sm = check_supermajority(proposal_id)
    if not sm.get("passed"):
        return json.dumps({
            "error": "Supermajority not achieved",
            "details": sm,
        })

    amount = withdrawal["amt"]
    receiver = withdrawal["rcv"]

    # Record expenditure against the budget savings pool
    try:
        from codices.syntropia.budget_plan import record_expenditure
        budget_pid = get_savings_status().get("budget_proposal_id", "")
        if budget_pid:
            budget_result = record_expenditure(
                budget_pid, "treasury_savings", amount,
                description="Savings withdrawal"
            )
            if "error" in budget_result:
                return json.dumps(budget_result)
    except ImportError:
        pass

    # Transfer via vault extension
    args = json.dumps({
        "to_principal": receiver,
        "amount": amount,
    })
    result = yield extension_async_call("vault", "transfer", args)

    # Update withdrawal status
    withdrawal["st"] = "executed"
    _save_withdrawal(proposal, withdrawal)
    proposal.status = "enacted"

    return json.dumps({
        "proposal_id": proposal_id,
        "status": "executed",
        "amount_satoshis": amount,
        "receiver": receiver,
    })


# ---------------------------------------------------------------------------
# List Withdrawals
# ---------------------------------------------------------------------------

def list_withdrawals() -> list:
    """List all treasury savings withdrawal proposals."""
    withdrawals = []
    for p in Proposal.instances():
        if p.metadata != "branch:treasury_savings":
            continue
        w = _load_withdrawal(p)
        withdrawals.append({
            "proposal_id": p.proposal_id,
            "amount_satoshis": w.get("amt"),
            "status": w.get("st"),
            "receiver": w.get("rcv"),
            "vote_status": p.status,
            "votes_for": p.votes_yes or 0,
            "votes_against": p.votes_no or 0,
        })
    return withdrawals


# Main execution
if __name__ == "__main__":
    status = get_savings_status()
    print(json.dumps(status, indent=2))
