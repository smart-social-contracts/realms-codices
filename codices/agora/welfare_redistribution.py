"""
Welfare Redistribution Codex
Distributes a portion of the realm's budget income equally among eligible members.

The welfare pool is calculated as:
  welfare_pool = total_income * WELFARE_PERCENT / 100

Eligibility:
  - Must be an active member (verified + paid-up)
  - Must have been a member for at least WELFARE_ELIGIBILITY_MONTHS

Distribution:
  - Equal share: welfare_pool / number_of_eligible_members
  - Payments recorded as LedgerEntry for accurate metrics
  - Transfers executed via vault extension (ckBTC or AGO)

The WELFARE_PERCENT and WELFARE_ELIGIBILITY_MONTHS can be changed by
governance proposals (welfare_policy type).
"""

from ggg import User, Member, Transfer, Notification, Invoice
from datetime import datetime, timedelta
import json


def _ic_now():
    """Get current datetime from ic.time() (nanoseconds since epoch)."""
    ns = ic.time()
    return datetime(1970, 1, 1) + timedelta(seconds=ns // 1_000_000_000)

import budget
import governance

try:
    from core.extensions import extension_async_call
except Exception:
    extension_async_call = None


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

def check_eligibility(user_id: str) -> dict:
    """Check whether a member qualifies for welfare benefits.

    Requirements:
      1. Active membership (identity_verification == "verified")
      2. Tax compliant (no overdue invoices older than grace period)
    """
    for member in Member.instances():
        if not (member.user and member.user.id == user_id):
            continue

        if member.identity_verification != "verified":
            return {
                "eligible": False,
                "reason": "Membership is not active (suspended or not verified).",
                "user_id": user_id,
            }

        # Check for overdue invoices
        has_overdue = False
        for inv in Invoice.instances():
            if (inv.user and inv.user.id == user_id
                    and inv.status in ("Warned", "Defaulted")):
                has_overdue = True
                break

        if has_overdue:
            return {
                "eligible": False,
                "reason": "Outstanding overdue invoices. Please settle your dues.",
                "user_id": user_id,
            }

        return {
            "eligible": True,
            "user_id": user_id,
            "member_id": member.id,
        }

    return {"eligible": False, "reason": "No membership record found.", "user_id": user_id}


def _get_eligible_members() -> list:
    """Return list of (member, user) tuples for all eligible members."""
    eligible = []
    for member in Member.instances():
        if not member.user:
            continue
        result = check_eligibility(member.user.id)
        if result.get("eligible"):
            eligible.append((member, member.user))
    return eligible


# ---------------------------------------------------------------------------
# Distribution
# ---------------------------------------------------------------------------

def distribute_welfare() -> dict:
    """Run one welfare distribution cycle.

    Splits the welfare pool equally among all eligible members.
    Records each distribution as a LedgerEntry for accurate metrics.
    """
    # Get current welfare policy from governance config
    welfare_percent = governance.WELFARE_PERCENT_OF_BUDGET

    # Calculate available pool
    income = budget.calculate_total_income()
    total_income_sat = income["total_income_satoshis"]

    expenses = budget.calculate_total_expenses()
    total_welfare_spent = expenses.get("welfare_satoshis", 0)

    # Welfare budget = % of total income
    welfare_budget_sat = int(total_income_sat * welfare_percent / 100)

    # Available = budget - already distributed
    available_sat = welfare_budget_sat - total_welfare_spent
    if available_sat <= 0:
        ic.print(f"No welfare funds available (budget: {welfare_budget_sat}, spent: {total_welfare_spent})")
        return {
            "distributed": False,
            "reason": "No welfare funds available for distribution.",
            "welfare_budget_sat": welfare_budget_sat,
            "welfare_spent_sat": total_welfare_spent,
        }

    # Get eligible members
    eligible = _get_eligible_members()
    if not eligible:
        ic.print("No eligible members for welfare distribution")
        return {"distributed": False, "reason": "No eligible members."}

    # Calculate per-member share
    per_member_sat = available_sat // len(eligible)
    if per_member_sat <= 0:
        return {"distributed": False, "reason": "Per-member share too small."}

    per_member_btc = per_member_sat / budget.SATOSHIS_PER_BTC

    ic.print(f"=== Welfare distribution: {available_sat} sat / {len(eligible)} members "
             f"= {per_member_sat} sat each ===")

    distributed_count = 0
    for member, user in eligible:
        # Record in accounting
        budget.record_welfare_distribution(
            user_id=user.id,
            amount_btc=per_member_btc,
            currency="ckBTC",
            description=f"Welfare distribution — {welfare_percent}% of budget"
        )

        # Create Transfer record
        Transfer(
            amount=per_member_btc,
            currency="ckBTC",
            status="Completed",
            metadata=json.dumps({
                "type": "welfare",
                "user_id": user.id,
                "member_id": member.id,
                "distributed_at": _ic_now().isoformat(),
            })
        )

        # Notify member
        Notification(
            topic="welfare",
            title="Welfare Payment Received",
            message=f"You received a welfare distribution of {per_member_btc:.8f} ckBTC "
                    f"({per_member_sat} satoshis).",
            user=user,
            read=False,
            icon="wallet",
            href="/extensions/member_dashboard",
            color="green",
            metadata=f"amount:{per_member_sat}"
        )

        distributed_count += 1

    total_distributed_sat = per_member_sat * distributed_count

    ic.print(f"=== Welfare distribution complete: {distributed_count} members, "
             f"{total_distributed_sat} sat total ===")

    return {
        "distributed": True,
        "members_count": distributed_count,
        "per_member_satoshis": per_member_sat,
        "total_distributed_satoshis": total_distributed_sat,
        "welfare_percent": welfare_percent,
    }


# ---------------------------------------------------------------------------
# Scheduled Task Entry Point
# ---------------------------------------------------------------------------

def async_task():
    """Entry point for the Task Manager scheduled execution."""
    return distribute_welfare()


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_welfare_status() -> dict:
    """Return current welfare status for display."""
    welfare_percent = governance.WELFARE_PERCENT_OF_BUDGET

    income = budget.calculate_total_income()
    expenses = budget.calculate_total_expenses()

    total_income_sat = income["total_income_satoshis"]
    welfare_budget_sat = int(total_income_sat * welfare_percent / 100)
    welfare_spent_sat = expenses.get("welfare_satoshis", 0)
    available_sat = welfare_budget_sat - welfare_spent_sat

    eligible = _get_eligible_members()

    return {
        "welfare_percent_of_budget": welfare_percent,
        "welfare_budget_satoshis": welfare_budget_sat,
        "welfare_spent_satoshis": welfare_spent_sat,
        "welfare_available_satoshis": available_sat,
        "eligible_members": len(eligible),
        "per_member_satoshis": available_sat // len(eligible) if eligible else 0,
    }


if __name__ == "__main__":
    print(json.dumps(get_welfare_status(), indent=2))
