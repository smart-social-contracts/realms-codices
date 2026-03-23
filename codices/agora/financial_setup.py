"""
Financial Setup
Sets up the accounting structure for the Agora realm: Funds, Fiscal Periods,
and Budget allocations. Ledger entries are created organically when real
transactions occur (via Transfer.record_accounting).
"""

from ggg import Fund, FiscalPeriod, Budget
from ggg import FundType, FiscalPeriodStatus, BudgetStatus
from datetime import datetime


def seed_funds():
    """Create the realm's fund structure."""
    general_fund = Fund(
        code="GF001",
        name="General Fund",
        fund_type=FundType.GENERAL,
        description="Primary operating fund for general government activities"
    )

    infra_fund = Fund(
        code="SF001",
        name="Infrastructure Fund",
        fund_type=FundType.SPECIAL_REVENUE,
        description="Dedicated fund for infrastructure projects"
    )

    capital_fund = Fund(
        code="CF001",
        name="Capital Projects Fund",
        fund_type=FundType.CAPITAL_PROJECTS,
        description="Fund for major capital acquisitions and construction"
    )

    return general_fund, infra_fund, capital_fund


def seed_fiscal_period():
    """Create the current fiscal period."""
    current_year = datetime.now().year
    return FiscalPeriod(
        id=f"FY{current_year}",
        name=f"Fiscal Year {current_year}",
        start_date=f"{current_year}-01-01",
        end_date=f"{current_year}-12-31",
        status=FiscalPeriodStatus.OPEN
    )


def seed_budgets(general_fund, infra_fund, fiscal_period):
    """Create budget allocations for the fiscal period."""
    current_year = datetime.now().year

    Budget(
        id=f"BUD-TAX-{current_year}",
        name="Tax Revenue",
        fund=general_fund,
        fiscal_period=fiscal_period,
        category="tax",
        budget_type="revenue",
        planned_amount=500000,
        actual_amount=0,
        status=BudgetStatus.ADOPTED,
        description="Projected tax revenue from members"
    )

    Budget(
        id=f"BUD-FEE-{current_year}",
        name="Service Fees",
        fund=general_fund,
        fiscal_period=fiscal_period,
        category="fee",
        budget_type="revenue",
        planned_amount=150000,
        actual_amount=0,
        status=BudgetStatus.ADOPTED,
        description="Revenue from service fees and licenses"
    )

    Budget(
        id=f"BUD-PERS-{current_year}",
        name="Personnel Expenses",
        fund=general_fund,
        fiscal_period=fiscal_period,
        category="personnel",
        budget_type="expense",
        planned_amount=300000,
        actual_amount=0,
        status=BudgetStatus.ADOPTED,
        description="Salaries and benefits"
    )

    Budget(
        id=f"BUD-INFRA-{current_year}",
        name="Infrastructure",
        fund=infra_fund,
        fiscal_period=fiscal_period,
        category="capital",
        budget_type="expense",
        planned_amount=200000,
        actual_amount=0,
        status=BudgetStatus.ADOPTED,
        description="Infrastructure maintenance and improvements"
    )


def setup_accounting():
    """Set up the accounting structure if not already present."""
    existing_funds = list(Fund.instances())
    if existing_funds:
        return "already_setup"

    general_fund, infra_fund, capital_fund = seed_funds()
    fiscal_period = seed_fiscal_period()
    seed_budgets(general_fund, infra_fund, fiscal_period)

    return "setup_complete"


# Top-level execution (runs when codex is loaded)
result = setup_accounting()
ic.print(f"Accounting setup: {result}")
