"""
Westminster Tax Collection Codex
Progressive income tax with standard deductions and multiple brackets,
typical of western democracies.
"""

from ggg import User, Transfer, Treasury, Instrument
from datetime import datetime
import json

# Standard personal deduction before tax applies
STANDARD_DEDUCTION = 5000

# Progressive tax brackets: (upper_limit, rate)
# Income up to 12000 taxed at 10%, up to 40000 at 22%, etc.
TAX_BRACKETS = [
    (12000, 0.10),
    (40000, 0.22),
    (85000, 0.32),
    (float("inf"), 0.40),
]


def calculate_tax_for_user(user_id: str, tax_year: int = None) -> dict:
    """Calculate progressive income tax owed by a citizen"""
    if tax_year is None:
        tax_year = datetime.now().year

    user = User.get(user_id)
    if not user:
        return {"error": "User not found"}

    # Calculate gross income from transfers received during the tax year
    income_transfers = [
        t for t in user.transfers_to
        if datetime.fromisoformat(t.created_at).year == tax_year
    ]
    gross_income = sum(t.amount for t in income_transfers)
    taxable_income = max(0, gross_income - STANDARD_DEDUCTION)

    # Apply progressive brackets
    tax_owed = 0
    remaining = taxable_income
    for bracket_limit, rate in TAX_BRACKETS:
        taxable_in_bracket = min(remaining, bracket_limit)
        tax_owed += int(taxable_in_bracket * rate)
        remaining -= taxable_in_bracket
        if remaining <= 0:
            break

    effective_rate = round(tax_owed / gross_income, 4) if gross_income > 0 else 0.0

    return {
        "user_id": user_id,
        "tax_year": tax_year,
        "gross_income": gross_income,
        "standard_deduction": STANDARD_DEDUCTION,
        "taxable_income": taxable_income,
        "tax_owed": tax_owed,
        "effective_rate": effective_rate,
        "calculated_at": datetime.now().isoformat()
    }


def process_tax_collection():
    """Collect taxes from all citizens"""
    results = []
    users = User.get_all()

    for user in users:
        if user.id == "system":
            continue

        tax_info = calculate_tax_for_user(user.id)

        if "error" not in tax_info and tax_info["tax_owed"] > 0:
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
                    "effective_rate": tax_info["effective_rate"],
                    "status": "collected"
                })

    return results


# Main execution
if __name__ == "__main__":
    results = process_tax_collection()
    print(f"Tax collection completed: {len(results)} payments processed")
