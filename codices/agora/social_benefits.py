"""
Social Benefits Distribution Codex
Automatically distributes social benefits to eligible members
"""

from ggg import User, Member, Transfer, Treasury, Instrument
from datetime import datetime
import json

def check_benefit_eligibility(member_id: str) -> dict:
    """Check if a member is eligible for social benefits"""
    member = Member.get(member_id)
    if not member:
        return {"eligible": False, "reason": "Member not found"}
    
    # Eligibility criteria
    criteria = {
        "residence_permit": member.residence_permit == "valid",
        "tax_compliance": member.tax_compliance in ["compliant", "under_review"],
        "identity_verification": member.identity_verification == "verified",
        "benefits_eligibility": member.public_benefits_eligibility == "eligible"
    }
    
    eligible = all(criteria.values())
    
    return {
        "member_id": member_id,
        "eligible": eligible,
        "criteria_met": criteria,
        "checked_at": datetime.now().isoformat()
    }

def calculate_benefit_amount(member_id: str) -> int:
    """Calculate benefit amount based on member status"""
    member = Member.get(member_id)
    if not member:
        return 0
    
    # Base benefit amount
    base_amount = 500
    
    # Adjustments based on status
    if member.criminal_record == "clean":
        base_amount += 100
    
    if member.voting_eligibility == "eligible":
        base_amount += 50
    
    return base_amount

def distribute_social_benefits():
    """Main social benefits distribution process"""
    results = []
    
    # Get all members
    members = Member.get_all()
    
    for member in members:
        eligibility = check_benefit_eligibility(member.id)
        
        if eligibility["eligible"]:
            benefit_amount = calculate_benefit_amount(member.id)
            
            # Create benefit transfer
            benefit_instrument = Instrument.get_by_name("Service Credit")
            system_user = User.get("system")
            
            if benefit_instrument and system_user and member.user:
                transfer = Transfer(
                    from_user=system_user,
                    to_user=member.user,
                    instrument=benefit_instrument,
                    amount=benefit_amount
                )
                
                results.append({
                    "member_id": member.id,
                    "benefit_amount": benefit_amount,
                    "status": "distributed"
                })
    
    return results

# Main execution
if __name__ == "__main__":
    results = distribute_social_benefits()
    print(f"Benefits distribution completed: {len(results)} payments processed")
