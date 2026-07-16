"""
Syntropia Tax Collection Codex
Progressive income tax with standard deductions and multiple brackets.
"""

from ggg import User, Transfer
from datetime import datetime

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

    user = User[user_id]
    if not user:
        return {"error": "User not found"}

    # Calculate gross income from transfers received during the tax year
    gross_income = 0
    for t in Transfer.instances():
        if t.principal_to != user_id:
            continue
        try:
            ts = t.timestamp or t.created_at or ""
            if ts and datetime.fromisoformat(ts).year == tax_year:
                gross_income += (t.amount or 0)
        except (ValueError, TypeError):
            pass
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

    for user in User.instances():
        if user.id == "system":
            continue

        tax_info = calculate_tax_for_user(user.id)

        if "error" not in tax_info and tax_info["tax_owed"] > 0:
            transfer = Transfer(
                id=f"tax_{user.id}_{datetime.now().year}",
                principal_from=user.id,
                principal_to="system",
                instrument="Realm Token",
                amount=tax_info["tax_owed"],
                timestamp=datetime.now().isoformat(),
                status="completed",
                tags="tax_collection",
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
