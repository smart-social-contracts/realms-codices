"""
Welfare Benefits / Social Security Codex
Redistributes the social_security portion of the annual budget equally
to all active verified members in ckBTC.

The social security pool is set by the annual budget vote (budget_plan).
Each distribution cycle:
  1. Look up the approved budget and its social_security remaining balance
  2. Divide equally among all active members
  3. Transfer each member's share via the vault extension
  4. Record the expenditure against the budget

Designed to run as a scheduled task via:
    realms run --file welfare_benefits.py --every 300 --after 10
"""

from ggg import User, Member, Transfer, Treasury, Instrument, Notification
from datetime import datetime
import json

from ggg import extension_call as extension_async_call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_active_members() -> list:
    """Return members whose identity_verification is 'verified'."""
    return [m for m in Member.instances()
            if m.identity_verification == "verified" and m.user]


def _get_approved_budget():
    """Return (proposal_id, budget_dict) for the current approved budget."""
    try:
        from codices.syntropia.budget_plan import (
            get_approved_budget_proposal_id, get_budget_summary,
        )
        pid = get_approved_budget_proposal_id()
        if not pid:
            return None, None
        summary = get_budget_summary(pid)
        return pid, summary
    except ImportError:
        return None, None


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

def check_eligibility(member_id: str) -> dict:
    """Check whether a citizen qualifies for social security benefits."""
    member = Member[member_id]
    if not member:
        return {"eligible": False, "reason": "Member not found"}

    criteria = {
        "identity_verified": member.identity_verification == "verified",
        "tax_compliant": member.tax_compliance in ["compliant", "under_review"],
    }

    return {
        "member_id": member_id,
        "eligible": all(criteria.values()),
        "criteria_met": criteria,
        "checked_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Distribution
# ---------------------------------------------------------------------------

def calculate_per_member_share() -> dict:
    """Calculate each member's equal share of the social security pool.

    Returns:
        Dict with per_member_satoshis, total_pool, member_count.
    """
    budget_pid, summary = _get_approved_budget()
    if not summary or "error" in summary:
        return {"error": "No approved budget found"}

    ss_cat = summary.get("categories", {}).get("social_security", {})
    remaining = ss_cat.get("remaining", 0)

    eligible = [m for m in _get_active_members()
                if check_eligibility(m.id).get("eligible")]
    count = len(eligible)
    if count == 0:
        return {"error": "No eligible members"}

    per_member = remaining // count

    return {
        "budget_proposal_id": budget_pid,
        "total_pool_satoshis": remaining,
        "eligible_members": count,
        "per_member_satoshis": per_member,
        "per_member_ckbtc": per_member / 1e8,
    }


def distribute_social_security() -> dict:
    """Run one distribution cycle: split the social_security pool equally.

    For each eligible member, records a Transfer and (optionally) sends
    ckBTC via the vault extension.
    """
    share_info = calculate_per_member_share()
    if "error" in share_info:
        return share_info

    per_member = share_info["per_member_satoshis"]
    if per_member <= 0:
        return {"error": "Per-member share is zero — pool exhausted or too many members"}

    budget_pid = share_info["budget_proposal_id"]
    eligible = [m for m in _get_active_members()
                if check_eligibility(m.id).get("eligible")]

    total_distributed = 0
    results = []
    cycle = datetime.now().strftime("%Y%m")
    for idx, member in enumerate(eligible):
        # Record internal transfer
        txn_id = "ss_" + cycle + "_" + str(idx + 1)
        transfer = Transfer(
            id=txn_id,
            principal_from="system",
            principal_to=member.user.id,
            instrument="ckBTC",
            amount=per_member,
            status="completed",
            tags="social_security",
            timestamp=datetime.now().isoformat(),
        )

        total_distributed += per_member
        results.append({
            "member_id": member.id,
            "user_id": member.user.id,
            "amount_satoshis": per_member,
            "transfer_id": txn_id,
            "status": "distributed",
        })

    # Record total expenditure against the budget
    try:
        from codices.syntropia.budget_plan import record_distribution
        record_distribution(budget_pid, total_distributed,
                            description=f"Social security: {len(results)} members")
    except ImportError:
        pass

    # Notify members
    for member in eligible:
        Notification(
            topic="social_security",
            title="Social Security Payment",
            message="You received " + str(per_member / 1e8) + " ckBTC as your social security benefit.",
            user=member.user,
            read=False,
            icon="wallet",
            href="/extensions/member_dashboard#my_taxes",
            color="green",
            metadata="uid:" + member.user.id + "|sat:" + str(per_member)
        )

    return {
        "cycle": datetime.now().strftime("%Y-%m"),
        "total_distributed_satoshis": total_distributed,
        "members_paid": len(results),
        "per_member_satoshis": per_member,
        "details": results,
    }


# ---------------------------------------------------------------------------
# Scheduled Task Entry Point
# ---------------------------------------------------------------------------

def async_task():
    """Entry point for scheduled execution via `realms run --every`."""
    print("Social Security Distribution starting...")
    results = distribute_social_security()
    if "error" in results:
        print("Distribution skipped: " + results["error"])
    else:
        print("Distributed to " + str(results["members_paid"]) + " members, total " + str(results["total_distributed_satoshis"]) + " satoshis")
    return json.dumps(results)


# Main execution
if __name__ == "__main__":
    results = distribute_social_security()
    print(json.dumps(results, indent=2))
