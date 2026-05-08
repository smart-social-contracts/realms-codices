"""
Budget Codex
Manages the realm's financial accounting with accurate, real-time tracking.

The total budget income of the realm is calculated by summing all bill
payments from users. Every financial event (bill payment, welfare payout,
treasury spend from governance proposals) creates proper double-entry
LedgerEntry records so the metrics extension displays accurate finances.

Entities used:
  - Fund          : grouping of financial resources (General Fund, Welfare Fund)
  - FiscalPeriod  : time window for accounting (auto-created yearly)
  - Budget        : planned vs actual tracking per category
  - LedgerEntry   : double-entry bookkeeping records (debit/credit)

Accepted currencies and conversion:
  - ckBTC : 1 ckBTC = 1 BTC
  - AGO   : 1 AGO = 0.5 BTC (fixed rate)
  All LedgerEntry amounts are stored in satoshis (1 BTC = 100_000_000 sat).
"""

from _cdk import ic
from ggg import LedgerEntry, Fund, FiscalPeriod, Budget
from ggg import EntryType, Category, FundType, FiscalPeriodStatus, BudgetStatus
from ic_basilisk_toolkit.date_utils import (
    ic_time_to_epoch, epoch_to_date_str, _date_from_epoch_days,
)
import json
import uuid as _uuid


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SATOSHIS_PER_BTC = 100_000_000
AGO_PER_BTC = 2.0  # 1 AGO = 0.5 BTC → 2 AGO per BTC


def _current_epoch():
    """Current time as epoch seconds (from ic.time() nanoseconds)."""
    return ic_time_to_epoch(ic.time())


def _current_year():
    """Current calendar year on the IC."""
    return _date_from_epoch_days(_current_epoch() // 86400)[0]


def _today_str():
    """Current date as 'YYYY-MM-DD' string."""
    return epoch_to_date_str(_current_epoch())


# ---------------------------------------------------------------------------
# Initialization (called from adjustments.py on deploy)
# ---------------------------------------------------------------------------

def ensure_accounting_entities():
    """Create the core Fund, FiscalPeriod and Budget entities if missing.

    This is idempotent — safe to call multiple times.
    """
    # Check if already initialized
    existing_funds = list(Fund.instances())
    if existing_funds:
        return {"status": "already_initialized"}

    current_year = _current_year()

    # --- Funds ---
    general_fund = Fund(
        code="GF001",
        name="General Fund",
        fund_type=FundType.GENERAL,
        description="Primary operating fund — membership dues revenue"
    )

    welfare_fund = Fund(
        code="WF001",
        name="Welfare Fund",
        fund_type=FundType.SPECIAL_REVENUE,
        description="Dedicated fund for social welfare redistribution"
    )

    services_fund = Fund(
        code="SF001",
        name="Services Fund",
        fund_type=FundType.SPECIAL_REVENUE,
        description="Fund for proposal-approved third-party service payments"
    )

    # --- Fiscal Period ---
    fiscal_period = FiscalPeriod(
        id=f"FY{current_year}",
        name=f"Fiscal Year {current_year}",
        start_date=f"{current_year}-01-01",
        end_date=f"{current_year}-12-31",
        status=FiscalPeriodStatus.OPEN
    )

    # --- Budgets (start at 0, updated in real-time) ---
    Budget(
        id=f"BUD-DUES-{current_year}",
        name="Membership Dues Revenue",
        fund=general_fund,
        fiscal_period=fiscal_period,
        category="fee",
        budget_type="revenue",
        planned_amount=0,
        actual_amount=0,
        status=BudgetStatus.ADOPTED,
        description="Revenue from monthly membership bill payments"
    )

    Budget(
        id=f"BUD-WELFARE-{current_year}",
        name="Welfare Expenditure",
        fund=welfare_fund,
        fiscal_period=fiscal_period,
        category="services",
        budget_type="expense",
        planned_amount=0,
        actual_amount=0,
        status=BudgetStatus.ADOPTED,
        description="Social welfare distributions to eligible members"
    )

    Budget(
        id=f"BUD-SERVICES-{current_year}",
        name="Services Expenditure",
        fund=services_fund,
        fiscal_period=fiscal_period,
        category="services",
        budget_type="expense",
        planned_amount=0,
        actual_amount=0,
        status=BudgetStatus.ADOPTED,
        description="Proposal-approved payments to third parties"
    )

    return {"status": "initialized", "year": current_year}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_current_fiscal_period():
    """Return the current open FiscalPeriod."""
    for fp in FiscalPeriod.instances():
        if fp.status == FiscalPeriodStatus.OPEN:
            return fp
    return None


def _get_fund(code: str):
    """Lookup a Fund by code."""
    for f in Fund.instances():
        if f.code == code:
            return f
    return None


def _get_budget(budget_id_prefix: str):
    """Lookup a Budget whose id starts with the given prefix (for current year)."""
    current_year = _current_year()
    target_id = f"{budget_id_prefix}-{current_year}"
    for b in Budget.instances():
        if b.id == target_id:
            return b
    return None


def _btc_to_satoshis(btc_amount: float) -> int:
    """Convert BTC amount to satoshis."""
    return int(round(btc_amount * SATOSHIS_PER_BTC))


# ---------------------------------------------------------------------------
# Recording Transactions (called by other codices)
# ---------------------------------------------------------------------------

def record_bill_payment(user_id: str, amount_btc: float, currency: str,
                        description: str = "Bill payment") -> dict:
    """Record a bill payment as a double-entry LedgerEntry.

    Creates:
      - Debit to Cash (Asset) — money received
      - Credit to Fee Revenue — income recognized

    Also updates the Membership Dues Revenue budget's actual_amount.
    """
    fp = _get_current_fiscal_period()
    fund = _get_fund("GF001")
    if not fp or not fund:
        ic.print("WARNING: Accounting entities not initialized, skipping LedgerEntry")
        return {"recorded": False, "reason": "Accounting not initialized"}

    sat_amount = _btc_to_satoshis(amount_btc)
    today = _today_str()
    tx_id = str(_uuid.uuid4())[:8]

    # Debit Cash (asset increases)
    LedgerEntry(
        id=f"LE-{tx_id}-1",
        transaction_id=tx_id,
        entry_type=EntryType.ASSET,
        category=Category.CASH,
        debit=sat_amount,
        credit=0,
        entry_date=today,
        fund=fund,
        fiscal_period=fp,
        description=f"{description} ({currency}) — user {user_id}",
        tags="operating,dues"
    )

    # Credit Revenue (income recognized)
    LedgerEntry(
        id=f"LE-{tx_id}-2",
        transaction_id=tx_id,
        entry_type=EntryType.REVENUE,
        category=Category.FEE,
        debit=0,
        credit=sat_amount,
        entry_date=today,
        fund=fund,
        fiscal_period=fp,
        description=f"{description} ({currency}) — user {user_id}",
        tags="operating,dues"
    )

    # Update budget actual_amount
    budget = _get_budget("BUD-DUES")
    if budget:
        budget.actual_amount = (budget.actual_amount or 0) + sat_amount

    ic.print(f"Recorded bill payment: {sat_amount} sat from user {user_id}")
    return {"recorded": True, "transaction_id": tx_id, "satoshis": sat_amount}


def record_welfare_distribution(user_id: str, amount_btc: float, currency: str,
                                 description: str = "Welfare distribution") -> dict:
    """Record a welfare distribution as a double-entry LedgerEntry.

    Creates:
      - Debit to Services Expense — money spent
      - Credit to Cash (Asset) — money leaving treasury
    """
    fp = _get_current_fiscal_period()
    fund = _get_fund("WF001")
    if not fp or not fund:
        return {"recorded": False, "reason": "Accounting not initialized"}

    sat_amount = _btc_to_satoshis(amount_btc)
    today = _today_str()
    tx_id = str(_uuid.uuid4())[:8]

    # Debit Expense
    LedgerEntry(
        id=f"LE-{tx_id}-1",
        transaction_id=tx_id,
        entry_type=EntryType.EXPENSE,
        category=Category.SERVICES,
        debit=sat_amount,
        credit=0,
        entry_date=today,
        fund=fund,
        fiscal_period=fp,
        description=f"{description} ({currency}) — user {user_id}",
        tags="operating,welfare"
    )

    # Credit Cash (asset decreases)
    LedgerEntry(
        id=f"LE-{tx_id}-2",
        transaction_id=tx_id,
        entry_type=EntryType.ASSET,
        category=Category.CASH,
        debit=0,
        credit=sat_amount,
        entry_date=today,
        fund=fund,
        fiscal_period=fp,
        description=f"{description} ({currency}) — user {user_id}",
        tags="operating,welfare"
    )

    # Update budget actual_amount
    budget = _get_budget("BUD-WELFARE")
    if budget:
        budget.actual_amount = (budget.actual_amount or 0) + sat_amount

    return {"recorded": True, "transaction_id": tx_id, "satoshis": sat_amount}


def record_service_payment(recipient: str, amount_btc: float, currency: str,
                           description: str = "Service payment") -> dict:
    """Record a proposal-approved service payment as a double-entry LedgerEntry.

    Creates:
      - Debit to Services Expense — money spent
      - Credit to Cash (Asset) — money leaving treasury
    """
    fp = _get_current_fiscal_period()
    fund = _get_fund("SF001")
    if not fp or not fund:
        return {"recorded": False, "reason": "Accounting not initialized"}

    sat_amount = _btc_to_satoshis(amount_btc)
    today = _today_str()
    tx_id = str(_uuid.uuid4())[:8]

    # Debit Expense
    LedgerEntry(
        id=f"LE-{tx_id}-1",
        transaction_id=tx_id,
        entry_type=EntryType.EXPENSE,
        category=Category.SERVICES,
        debit=sat_amount,
        credit=0,
        entry_date=today,
        fund=fund,
        fiscal_period=fp,
        description=f"{description} — to {recipient}",
        tags="operating,services"
    )

    # Credit Cash
    LedgerEntry(
        id=f"LE-{tx_id}-2",
        transaction_id=tx_id,
        entry_type=EntryType.ASSET,
        category=Category.CASH,
        debit=0,
        credit=sat_amount,
        entry_date=today,
        fund=fund,
        fiscal_period=fp,
        description=f"{description} — to {recipient}",
        tags="operating,services"
    )

    # Update budget actual_amount
    budget = _get_budget("BUD-SERVICES")
    if budget:
        budget.actual_amount = (budget.actual_amount or 0) + sat_amount

    return {"recorded": True, "transaction_id": tx_id, "satoshis": sat_amount}


# ---------------------------------------------------------------------------
# Budget Queries
# ---------------------------------------------------------------------------

def calculate_total_income() -> dict:
    """Calculate total budget income = sum of all paid bill payments.

    Reads directly from LedgerEntry (revenue entries with fee category)
    so the number is always accurate and real-time.
    """
    total_satoshis = 0
    payment_count = 0

    for entry in LedgerEntry.instances():
        if (entry.entry_type == EntryType.REVENUE
                and entry.category == Category.FEE
                and entry.credit and entry.credit > 0):
            total_satoshis += entry.credit
            payment_count += 1

    return {
        "total_income_satoshis": total_satoshis,
        "total_income_btc": total_satoshis / SATOSHIS_PER_BTC,
        "payment_count": payment_count,
    }


def calculate_total_expenses() -> dict:
    """Calculate total expenses (welfare + services)."""
    welfare_sat = 0
    services_sat = 0

    for entry in LedgerEntry.instances():
        if entry.entry_type == EntryType.EXPENSE and entry.debit and entry.debit > 0:
            tags = entry.tags or ""
            if "welfare" in tags:
                welfare_sat += entry.debit
            elif "services" in tags:
                services_sat += entry.debit

    total = welfare_sat + services_sat
    return {
        "total_expenses_satoshis": total,
        "total_expenses_btc": total / SATOSHIS_PER_BTC,
        "welfare_satoshis": welfare_sat,
        "services_satoshis": services_sat,
    }


def get_budget_summary() -> dict:
    """Return a complete budget summary for display."""
    income = calculate_total_income()
    expenses = calculate_total_expenses()
    net = income["total_income_satoshis"] - expenses["total_expenses_satoshis"]

    return {
        "income": income,
        "expenses": expenses,
        "net_balance_satoshis": net,
        "net_balance_btc": net / SATOSHIS_PER_BTC,
    }


if __name__ == "__main__":
    print(json.dumps(get_budget_summary(), indent=2))
