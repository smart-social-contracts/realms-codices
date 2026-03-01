"""
Budget Plan Codex
Manages the annual government budget with allocated departments and a
reserve fund for procurement and exceptional urgencies.

Budget categories:
  - Healthcare
  - Education
  - Infrastructure
  - Defence
  - Justice & Public Safety
  - Social Welfare
  - Procurement & Emergency Reserve
"""

from ggg import Proposal, Treasury, Transfer, User, Instrument
from datetime import datetime
import json

# Default annual budget allocation (percentages of total revenue)
DEFAULT_BUDGET_ALLOCATION = {
    "healthcare":          0.20,
    "education":           0.18,
    "infrastructure":      0.15,
    "defence":             0.10,
    "justice_public_safety": 0.10,
    "social_welfare":      0.15,
    "procurement_emergency": 0.12,
}


def create_budget_plan(total_revenue: int, fiscal_year: int = None,
                       allocations: dict = None) -> dict:
    """Create an annual budget plan from projected total revenue.

    Args:
        total_revenue: Total projected revenue for the fiscal year.
        fiscal_year: Year the budget applies to (defaults to current year).
        allocations: Optional dict overriding DEFAULT_BUDGET_ALLOCATION.

    Returns:
        Budget plan dict with per-category amounts.
    """
    if fiscal_year is None:
        fiscal_year = datetime.now().year

    alloc = allocations or DEFAULT_BUDGET_ALLOCATION

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

    # Any rounding remainder goes to procurement_emergency
    remainder = total_revenue - allocated_total
    if "procurement_emergency" in plan:
        plan["procurement_emergency"]["amount"] += remainder
        plan["procurement_emergency"]["remaining"] += remainder

    budget = {
        "fiscal_year": fiscal_year,
        "total_revenue": total_revenue,
        "allocated_total": allocated_total + remainder,
        "categories": plan,
        "status": "draft",
        "created_at": datetime.now().isoformat(),
    }

    # Store as a governance proposal so parliament can vote on it
    proposal = Proposal(
        metadata=json.dumps({
            "title": f"Budget Plan — Fiscal Year {fiscal_year}",
            "description": "Annual budget appropriations for all government departments.",
            "branch": "budget",
            "status": "debate",
            "budget": budget,
        })
    )

    budget["proposal_id"] = proposal.id
    return budget


def approve_budget(proposal_id: str) -> dict:
    """Mark a budget plan as approved after parliamentary vote."""
    proposal = Proposal.get(proposal_id)
    if not proposal:
        return {"error": "Budget proposal not found"}

    metadata = json.loads(proposal.metadata)
    if metadata.get("branch") != "budget":
        return {"error": "Proposal is not a budget plan"}

    metadata["budget"]["status"] = "approved"
    metadata["status"] = "enacted"
    metadata["budget"]["approved_at"] = datetime.now().isoformat()
    proposal.metadata = json.dumps(metadata)

    return {"proposal_id": proposal_id, "status": "approved"}


def record_expenditure(proposal_id: str, category: str, amount: int,
                       description: str = "") -> dict:
    """Record spending against an approved budget category.

    Returns updated remaining balance for the category.
    """
    proposal = Proposal.get(proposal_id)
    if not proposal:
        return {"error": "Budget proposal not found"}

    metadata = json.loads(proposal.metadata)
    budget = metadata.get("budget", {})

    if budget.get("status") != "approved":
        return {"error": "Budget has not been approved yet"}

    if category not in budget.get("categories", {}):
        return {"error": f"Unknown budget category: {category}"}

    cat = budget["categories"][category]
    if amount > cat["remaining"]:
        return {"error": f"Insufficient budget in {category}: requested {amount}, remaining {cat['remaining']}"}

    cat["spent"] += amount
    cat["remaining"] -= amount
    proposal.metadata = json.dumps(metadata)

    return {
        "category": category,
        "amount_spent": amount,
        "description": description,
        "remaining": cat["remaining"],
        "recorded_at": datetime.now().isoformat(),
    }


def request_emergency_funds(proposal_id: str, amount: int,
                            justification: str) -> dict:
    """Draw from the procurement / emergency reserve."""
    return record_expenditure(
        proposal_id,
        category="procurement_emergency",
        amount=amount,
        description=f"[EMERGENCY] {justification}",
    )


def get_budget_summary(proposal_id: str) -> dict:
    """Return a summary of current budget status."""
    proposal = Proposal.get(proposal_id)
    if not proposal:
        return {"error": "Budget proposal not found"}

    metadata = json.loads(proposal.metadata)
    budget = metadata.get("budget", {})
    categories = budget.get("categories", {})

    summary = {
        "fiscal_year": budget.get("fiscal_year"),
        "status": budget.get("status"),
        "total_revenue": budget.get("total_revenue", 0),
        "total_spent": sum(c["spent"] for c in categories.values()),
        "total_remaining": sum(c["remaining"] for c in categories.values()),
        "categories": {
            k: {"spent": v["spent"], "remaining": v["remaining"], "pct_used": round(v["spent"] / v["amount"], 2) if v["amount"] else 0}
            for k, v in categories.items()
        },
    }
    return summary


# Main execution
if __name__ == "__main__":
    budget = create_budget_plan(total_revenue=1_000_000)
    print(json.dumps(budget, indent=2))
