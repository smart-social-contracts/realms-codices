"""
Tax Collection Automation Codex
Automatically calculates and processes tax payments for citizens
"""

from ggg import User, Transfer, Treasury, Instrument
from datetime import datetime, timedelta
import json

def calculate_tax_for_user(user_id: str, tax_year: int = None) -> dict:
    """Calculate tax owed by a user for a given year"""
    if tax_year is None:
        tax_year = datetime.now().year
    
    # Get user's transfers for the tax year
    user = User.get(user_id)
    if not user:
        return {"error": "User not found"}
    
    # Calculate income from transfers received
    income_transfers = [t for t in user.transfers_to if 
                       datetime.fromisoformat(t.created_at).year == tax_year]
    
    total_income = sum(t.amount for t in income_transfers)
    
    # Progressive tax calculation
    if total_income <= 10000:
        tax_rate = 0.10
    elif total_income <= 50000:
        tax_rate = 0.20
    else:
        tax_rate = 0.30
    
    tax_owed = int(total_income * tax_rate)
    
    return {
        "user_id": user_id,
        "tax_year": tax_year,
        "total_income": total_income,
        "tax_rate": tax_rate,
        "tax_owed": tax_owed,
        "calculated_at": datetime.now().isoformat()
    }

def process_tax_collection():
    """Main tax collection process"""
    results = []
    
    # Get all users
    users = User.get_all()
    
    for user in users:
        if user.id == "system":
            continue
            
        tax_info = calculate_tax_for_user(user.id)
        
        if "error" not in tax_info and tax_info["tax_owed"] > 0:
            # Create tax payment transfer
            tax_instrument = Instrument.get_by_name("Realm Token")
            if tax_instrument:
                transfer = Transfer(
                    from_user=user,
                    to_user=User.get("system"),
                    instrument=tax_instrument,
                    amount=tax_info["tax_owed"]
                )
                results.append({
                    "user_id": user.id,
                    "tax_collected": tax_info["tax_owed"],
                    "status": "collected"
                })
    
    return results

# Main execution
if __name__ == "__main__":
    results = process_tax_collection()
    print(f"Tax collection completed: {len(results)} payments processed")
