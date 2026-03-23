"""
Tests for financial_setup.py — accounting structure initialization.

Validates:
  - Fund creation (3 funds with correct types)
  - Fiscal period creation (current year, open status)
  - Budget allocation (4 budgets with correct amounts)
  - Idempotency guard (second run does not duplicate)
"""

from ggg import Fund, FiscalPeriod, Budget
from ggg import FundType, FiscalPeriodStatus, BudgetStatus
from datetime import datetime
from codices._testing import reset_registry
import sys

current_year = datetime.now().year

# ── Test setup_accounting (full run) ───────────────────────────────────────
# financial_setup.py has top-level code that calls setup_accounting() on
# import. We force a fresh import so the test starts from a clean registry.

print("Testing setup_accounting...")

reset_registry()
sys.modules.pop("financial_setup", None)
import financial_setup

# Top-level execution should have run setup_accounting() → "setup_complete"
assert Fund.count() == 3, f"Expected 3 funds after import, got {Fund.count()}"

# Funds
assert Fund.count() == 3, f"Expected 3 funds, got {Fund.count()}"

gf = Fund["GF001"]
assert gf is not None
assert gf.name == "General Fund"
assert gf.fund_type == FundType.GENERAL

infra = Fund["SF001"]
assert infra is not None
assert infra.fund_type == FundType.SPECIAL_REVENUE

cap = Fund["CF001"]
assert cap is not None
assert cap.fund_type == FundType.CAPITAL_PROJECTS

print("  funds: OK")

# Fiscal period
fp = FiscalPeriod[f"FY{current_year}"]
assert fp is not None
assert fp.name == f"Fiscal Year {current_year}"
assert fp.start_date == f"{current_year}-01-01"
assert fp.end_date == f"{current_year}-12-31"
assert fp.status == FiscalPeriodStatus.OPEN

print("  fiscal period: OK")

# Budgets
assert Budget.count() == 4, f"Expected 4 budgets, got {Budget.count()}"

tax_budget = Budget[f"BUD-TAX-{current_year}"]
assert tax_budget is not None
assert tax_budget.name == "Tax Revenue"
assert tax_budget.fund is gf
assert tax_budget.fiscal_period is fp
assert tax_budget.category == "tax"
assert tax_budget.budget_type == "revenue"
assert tax_budget.planned_amount == 500000
assert tax_budget.actual_amount == 0
assert tax_budget.status == BudgetStatus.ADOPTED

fee_budget = Budget[f"BUD-FEE-{current_year}"]
assert fee_budget is not None
assert fee_budget.planned_amount == 150000

pers_budget = Budget[f"BUD-PERS-{current_year}"]
assert pers_budget is not None
assert pers_budget.planned_amount == 300000
assert pers_budget.budget_type == "expense"

infra_budget = Budget[f"BUD-INFRA-{current_year}"]
assert infra_budget is not None
assert infra_budget.planned_amount == 200000
assert infra_budget.fund is infra

print("  budgets: OK")

# ── Test idempotency guard ─────────────────────────────────────────────────

print("Testing idempotency guard...")

result2 = financial_setup.setup_accounting()
assert result2 == "already_setup", f"Expected 'already_setup', got {result2!r}"
assert Fund.count() == 3, "Idempotency failed: funds duplicated"
assert Budget.count() == 4, "Idempotency failed: budgets duplicated"

print("  idempotency: OK")

# ── Test budget domain methods ─────────────────────────────────────────────

print("Testing budget domain methods...")

assert tax_budget.variance() == -500000  # actual(0) - planned(500000)
tax_budget.update_actual(100000)
assert tax_budget.actual_amount == 100000
assert tax_budget.variance() == -400000

print("  budget domain methods: OK")

print("\n\u2705 All financial_setup tests passed!")
