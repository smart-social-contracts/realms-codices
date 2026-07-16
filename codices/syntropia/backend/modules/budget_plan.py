"""
Budget Plan Codex
Manages the annual budget allocation voted on by realm members.

All revenue comes from monthly ckBTC dues collected by monthly_billing.
The budget splits collected revenue into three pools:

  - treasury_savings  — locked reserve (no spend without supermajority)
  - procurement       — funds for approved procurement projects
  - social_security   — redistributed equally to all active members

Workflow:
  1. create_budget_proposal() — propose allocation percentages for voting
  2. Members vote via the governance_automation / voting extension
  3. approve_budget()         — enacted after vote passes
  4. record_expenditure()     — procurement draws from procurement pool
  5. record_distribution()    — social_security draws from social pool
  6. get_budget_summary()     — inspect remaining balances
"""

from ggg import Proposal, Treasury, Transfer, User, Instrument
from datetime import datetime, timedelta
import json


# ---------------------------------------------------------------------------
# Default Allocation (percentages of total revenue)
# ---------------------------------------------------------------------------

DEFAULT_BUDGET_ALLOCATION = {
    "treasury_savings": 0.30,   # 30% locked savings
    "procurement":      0.40,   # 40% for approved projects
    "social_security":  0.30,   # 30% redistributed to members
}


# ---------------------------------------------------------------------------
# Helpers — budget data stored in Proposal.description (max 2048 chars)
# ---------------------------------------------------------------------------

def _load_budget(proposal) -> dict:
    """Load budget dict from proposal.description (JSON)."""
    try:
        return json.loads(proposal.description) if proposal.description else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _save_budget(proposal, budget: dict):
    """Save budget dict to proposal.description."""
    proposal.description = json.dumps(budget, separators=(",", ":"))


def _find_proposal(proposal_id: str):
    """Find a Proposal by proposal_id."""
    return next(
        (p for p in Proposal.instances() if p.proposal_id == proposal_id),
        None,
    )


# ---------------------------------------------------------------------------
# Proposal Creation
# ---------------------------------------------------------------------------

def create_budget_proposal(total_revenue: int, fiscal_year: int = None,
                           allocations: dict = None,
                           voting_days: int = 14) -> dict:
    """Create an annual budget proposal for voting.

    Args:
        total_revenue: Total projected ckBTC revenue (in satoshis).
        fiscal_year: Year the budget applies to (defaults to current year).
        allocations: Optional dict overriding DEFAULT_BUDGET_ALLOCATION.
        voting_days: Number of days the vote stays open.

    Returns:
        Budget plan dict including the proposal_id.
    """
    if fiscal_year is None:
        fiscal_year = datetime.now().year

    alloc = allocations or DEFAULT_BUDGET_ALLOCATION

    # Validate percentages sum to 1.0
    total_pct = sum(alloc.values())
    if abs(total_pct - 1.0) > 0.001:
        return {"error": f"Allocation percentages must sum to 1.0, got {total_pct}"}

    plan = {}
    allocated_total = 0
    for category, pct in alloc.items():
        amount = int(total_revenue * pct)
        plan[category] = {
            "percentage": pct,
            "amount": amount,
            "spent": 0,
            "remaining": amount,
        }
        allocated_total += amount

    # Rounding remainder goes to procurement
    remainder = total_revenue - allocated_total
    if "procurement" in plan:
        plan["procurement"]["amount"] += remainder
        plan["procurement"]["remaining"] += remainder

    budget = {
        "fy": fiscal_year,
        "rev": total_revenue,
        "cats": plan,
        "st": "draft",
    }

    deadline = (datetime.now() + timedelta(days=voting_days)).isoformat()

    pid = "budget_fy" + str(fiscal_year)
    ts_pct = int(alloc.get("treasury_savings", 0) * 100)
    pr_pct = int(alloc.get("procurement", 0) * 100)
    ss_pct = int(alloc.get("social_security", 0) * 100)

    proposal = Proposal(
        proposal_id=pid,
        title="Annual Budget FY " + str(fiscal_year),
        description=json.dumps(budget, separators=(",", ":")),
        status="debate",
        voting_deadline=deadline,
        metadata="branch:budget",
    )

    return {
        "proposal_id": pid,
        "fiscal_year": fiscal_year,
        "total_revenue": total_revenue,
        "ts_pct": ts_pct,
        "pr_pct": pr_pct,
        "ss_pct": ss_pct,
        "status": "draft",
    }


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

def approve_budget(proposal_id: str) -> dict:
    """Mark a budget plan as approved after the vote passes."""
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return {"error": "Budget proposal not found"}

    if proposal.metadata != "branch:budget":
        return {"error": "Proposal is not a budget plan"}

    budget = _load_budget(proposal)
    budget["st"] = "approved"
    _save_budget(proposal, budget)
    proposal.status = "enacted"

    return {"proposal_id": proposal_id, "status": "approved"}


# ---------------------------------------------------------------------------
# Expenditure Recording
# ---------------------------------------------------------------------------

def record_expenditure(proposal_id: str, category: str, amount: int,
                       description: str = "") -> dict:
    """Record spending against an approved budget category.

    Used by procurement (category='procurement') and
    social_security (category='social_security').
    """
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return {"error": "Budget proposal not found"}

    budget = _load_budget(proposal)

    if budget.get("st") != "approved":
        return {"error": "Budget has not been approved yet"}

    cats = budget.get("cats", {})
    if category not in cats:
        return {"error": f"Unknown budget category: {category}"}

    cat = cats[category]
    if amount > cat["remaining"]:
        return {"error": f"Insufficient budget in {category}: "
                f"requested {amount}, remaining {cat['remaining']}"}

    cat["spent"] += amount
    cat["remaining"] -= amount
    _save_budget(proposal, budget)

    return {
        "category": category,
        "amount_spent": amount,
        "description": description,
        "remaining": cat["remaining"],
        "recorded_at": datetime.now().isoformat(),
    }


def record_distribution(proposal_id: str, amount: int,
                        description: str = "Social security distribution") -> dict:
    """Convenience wrapper: draw from social_security pool."""
    return record_expenditure(proposal_id, "social_security", amount, description)


# ---------------------------------------------------------------------------
# Budget Query
# ---------------------------------------------------------------------------

def get_approved_budget_proposal_id() -> str:
    """Find the most recent approved budget proposal ID.

    Returns proposal_id or empty string if none found.
    """
    best = None
    best_year = 0
    for p in Proposal.instances():
        if p.metadata != "branch:budget":
            continue
        budget = _load_budget(p)
        if budget.get("st") != "approved":
            continue
        fy = budget.get("fy", 0)
        if fy >= best_year:
            best_year = fy
            best = p.proposal_id
    return best or ""


def get_budget_summary(proposal_id: str) -> dict:
    """Return a summary of current budget status."""
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return {"error": "Budget proposal not found"}

    budget = _load_budget(proposal)
    cats = budget.get("cats", {})

    summary = {
        "fiscal_year": budget.get("fy"),
        "status": budget.get("st"),
        "total_revenue": budget.get("rev", 0),
        "total_spent": sum(c["spent"] for c in cats.values()),
        "total_remaining": sum(c["remaining"] for c in cats.values()),
        "categories": {
            k: {
                "allocated": v["amount"],
                "spent": v["spent"],
                "remaining": v["remaining"],
            }
            for k, v in cats.items()
        },
    }
    return summary


# Main execution
if __name__ == "__main__":
    budget = create_budget_proposal(total_revenue=1_000_000)
    print(json.dumps(budget, indent=2))
