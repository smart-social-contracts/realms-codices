"""
Welfare Benefits Codex
Distributes basic universal welfare services typical of a western state:
  - Healthcare subsidy
  - Unemployment benefit
  - Pension
"""

from ggg import User, Member, Transfer, Treasury, Instrument
from datetime import datetime
import json

# Monthly benefit amounts (in realm token units)
HEALTHCARE_BENEFIT = 200
UNEMPLOYMENT_BENEFIT = 400
PENSION_BENEFIT = 350


def check_eligibility(member_id: str) -> dict:
    """Check whether a citizen qualifies for welfare benefits"""
    member = Member.get(member_id)
    if not member:
        return {"eligible": False, "reason": "Member not found"}

    criteria = {
        "identity_verified": member.identity_verification == "verified",
        "resident": member.residence_permit == "valid",
        "tax_compliant": member.tax_compliance in ["compliant", "under_review"],
    }

    return {
        "member_id": member_id,
        "eligible": all(criteria.values()),
        "criteria_met": criteria,
        "checked_at": datetime.now().isoformat()
    }


def calculate_benefits(member_id: str) -> dict:
    """Calculate total welfare entitlement for a citizen"""
    member = Member.get(member_id)
    if not member:
        return {"total": 0, "breakdown": {}}

    breakdown = {}

    # Healthcare — every eligible citizen
    breakdown["healthcare"] = HEALTHCARE_BENEFIT

    # Unemployment — only citizens flagged as benefits-eligible
    if member.public_benefits_eligibility == "eligible":
        breakdown["unemployment"] = UNEMPLOYMENT_BENEFIT

    # Pension — citizens with voting eligibility (proxy for seniority)
    if member.voting_eligibility == "eligible":
        breakdown["pension"] = PENSION_BENEFIT

    return {
        "member_id": member_id,
        "breakdown": breakdown,
        "total": sum(breakdown.values())
    }


def distribute_welfare():
    """Run welfare distribution cycle for all eligible citizens"""
    results = []
    members = Member.get_all()

    for member in members:
        elig = check_eligibility(member.id)
        if not elig["eligible"]:
            continue

        benefits = calculate_benefits(member.id)
        if benefits["total"] <= 0:
            continue

        benefit_instrument = Instrument.get_by_name("Service Credit")
        system_user = User.get("system")

        if benefit_instrument and system_user and member.user:
            transfer = Transfer(
                from_user=system_user,
                to_user=member.user,
                instrument=benefit_instrument,
                amount=benefits["total"]
            )
            results.append({
                "member_id": member.id,
                "total": benefits["total"],
                "breakdown": benefits["breakdown"],
                "status": "distributed"
            })

    return results


# Main execution
if __name__ == "__main__":
    results = distribute_welfare()
    print(f"Welfare distribution completed: {len(results)} payments processed")
