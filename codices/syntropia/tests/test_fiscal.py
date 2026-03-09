# Test: Fiscal System
# Covers: fiscal periods, funds, budgets, ledger entries (double-entry),
#         progressive tax calculation, tax collection
import sys as _sys
import json
from ggg import (
    Proposal, User, Member, Transfer, Codex,
    FiscalPeriod, FiscalPeriodStatus, Fund, FundType,
    Budget, BudgetStatus, LedgerEntry, EntryType, Category,
)

def load_codex(name):
    """Load a codex module by exec'ing its source from the Codex entity."""
    mod = _sys.modules.get(name)
    if mod is None:
        mod = type(_sys)(name)
        _sys.modules[name] = mod
    if not getattr(mod, '_codex_loaded', False):
        for c in Codex.instances():
            if c.name == name and c.code:
                exec(compile(c.code, name + '.py', 'exec'), mod.__dict__)
                mod._codex_loaded = True
                return mod
        raise ImportError("Codex not found: " + name)
    return mod

ts = "f" + str(id(object()))[-6:]
fy = 2026
today = "2026-03-09"
deadline = today + "T23:59:59"

# Setup: user with income for tax tests
user_alice = User(id=ts + "_alice", name="Alice")
member_alice = Member(
    user=user_alice, identity_verification="verified",
    residence_permit="valid", tax_compliance="compliant",
    public_benefits_eligibility="eligible", voting_eligibility="eligible",
    criminal_record="clean|zk:" + ts,
)

# ── TEST 1: Fiscal Period ────────────────────────────────────────────────
print("=== TEST 1: FISCAL PERIOD ===")
fp = FiscalPeriod(
    id="FY" + str(fy) + "_" + ts,
    name="Fiscal Year " + str(fy),
    start_date=str(fy) + "-01-01",
    end_date=str(fy) + "-12-31",
    status=FiscalPeriodStatus.OPEN,
)
print("FiscalPeriod " + fp.id + " status=" + fp.status)
assert fp.is_open(), "Fiscal period should be open"

# ── TEST 2: Funds ────────────────────────────────────────────────────────
print("=== TEST 2: FUNDS ===")
gen_fund = Fund(code=ts + "_GEN", name="General Fund", fund_type=FundType.GENERAL, description="Main operating fund")
ss_fund = Fund(code=ts + "_SS", name="Social Security Fund", fund_type=FundType.SPECIAL_REVENUE, description="Welfare and social benefits")
proc_fund = Fund(code=ts + "_PROC", name="Procurement Fund", fund_type=FundType.CAPITAL_PROJECTS, description="Capital projects")
sav_fund = Fund(code=ts + "_SAV", name="Treasury Savings Fund", fund_type=FundType.TRUST, description="Long-term savings")
print("Created 4 funds")

# ── TEST 3: Budget Proposal + Budget Line Items ─────────────────────────
print("=== TEST 3: BUDGET PROPOSAL & BUDGETS ===")
bp = Proposal(
    proposal_id=ts + "_budget_fy" + str(fy),
    title="Annual Budget FY " + str(fy),
    description="Allocates 1M revenue: 30% savings, 40% procurement, 30% welfare",
    status="debate",
    voting_deadline=deadline,
    metadata="branch:budget",
)

rev_budget = Budget(
    id=ts + "_GEN_tax",
    name="Tax Revenue FY" + str(fy),
    category="tax_revenue",
    budget_type="revenue",
    planned_amount=1000000,
    status=BudgetStatus.DRAFT,
    description="Projected membership dues and tax revenue",
)
savings_budget = Budget(
    id=ts + "_SAV_savings",
    name="Treasury Savings",
    category="savings",
    budget_type="expense",
    planned_amount=300000,
    status=BudgetStatus.DRAFT,
    description="30% allocation to treasury savings",
)
procurement_budget = Budget(
    id=ts + "_PROC_capital",
    name="Procurement & Capital",
    category="capital",
    budget_type="expense",
    planned_amount=400000,
    status=BudgetStatus.DRAFT,
    description="40% allocation to capital projects",
)
welfare_budget = Budget(
    id=ts + "_SS_welfare",
    name="Social Security & Welfare",
    category="welfare",
    budget_type="expense",
    planned_amount=300000,
    status=BudgetStatus.DRAFT,
    description="30% allocation to social security",
)

bp.status = "enacted"
rev_budget.status = BudgetStatus.ADOPTED
savings_budget.status = BudgetStatus.ADOPTED
procurement_budget.status = BudgetStatus.ADOPTED
welfare_budget.status = BudgetStatus.ADOPTED
print("Budget proposal enacted, all budgets adopted")

# ── TEST 4: Ledger Entries (double-entry) ────────────────────────────────
print("=== TEST 4: LEDGER ENTRIES ===")
txn1_id = ts + "_txn_tax_001"
tax_entries = LedgerEntry.create_transaction(
    transaction_id=txn1_id,
    entries=[
        {"entry_type": EntryType.ASSET, "category": Category.CASH, "debit": 100000, "credit": 0, "entry_date": today, "description": "Membership dues received"},
        {"entry_type": EntryType.REVENUE, "category": Category.TAX, "debit": 0, "credit": 100000, "entry_date": today, "description": "Membership dues revenue"},
    ],
)
assert LedgerEntry.validate_transaction(txn1_id), "Tax transaction should balance"
print("Tax revenue: balanced=" + str(LedgerEntry.validate_transaction(txn1_id)))
rev_budget.update_actual(100000)

txn2_id = ts + "_txn_proc_001"
proc_entries = LedgerEntry.create_transaction(
    transaction_id=txn2_id,
    entries=[
        {"entry_type": EntryType.EXPENSE, "category": Category.CAPITAL, "debit": 50000, "credit": 0, "entry_date": today, "description": "Community Center construction"},
        {"entry_type": EntryType.ASSET, "category": Category.CASH, "debit": 0, "credit": 50000, "entry_date": today, "description": "Cash outflow for Community Center"},
    ],
)
assert LedgerEntry.validate_transaction(txn2_id), "Procurement transaction should balance"
procurement_budget.update_actual(50000)
print("Cash balance: " + str(LedgerEntry.get_balance(EntryType.ASSET, Category.CASH)))

# ── TEST 5: Progressive Tax Calculation ──────────────────────────────────
print("=== TEST 5: PROGRESSIVE TAX CALCULATION ===")
tax_codex = load_codex("tax_collection_codex")

# Give Alice income via transfers
Transfer(id=ts + "_income_alice", principal_from="system", principal_to=user_alice.id,
         instrument="Realm Token", amount=50000, status="completed",
         tags="income", timestamp=str(fy) + "-06-15T00:00:00")

tax_info = tax_codex.calculate_tax_for_user(user_alice.id, tax_year=fy)
print("Alice tax: gross=" + str(tax_info.get("gross_income", 0))
      + " deduction=" + str(tax_info.get("standard_deduction", 0))
      + " taxable=" + str(tax_info.get("taxable_income", 0))
      + " owed=" + str(tax_info.get("tax_owed", 0))
      + " rate=" + str(tax_info.get("effective_rate", 0)))
assert tax_info.get("gross_income", 0) >= 50000, "Alice should have income >= 50000"
assert tax_info.get("tax_owed", 0) > 0, "Alice should owe tax"
print("Tax brackets: " + str(len(tax_codex.TAX_BRACKETS)) + " brackets, deduction=" + str(tax_codex.STANDARD_DEDUCTION))

# ── TEST 6: Tax Collection ───────────────────────────────────────────────
print("=== TEST 6: TAX COLLECTION ===")
tax_results = tax_codex.process_tax_collection()
print("Tax collection: " + str(len(tax_results)) + " payments processed")
for tr in tax_results[:3]:
    print("  user=" + str(tr.get("user_id", "")) + " tax=" + str(tr.get("tax_collected", 0)))

# Summary
print("=== FISCAL TESTS PASSED ===")
print("FiscalPeriods: " + str(FiscalPeriod.count()) + " Funds: " + str(Fund.count())
      + " Budgets: " + str(Budget.count()) + " LedgerEntries: " + str(LedgerEntry.count()))
for b in [rev_budget, savings_budget, procurement_budget, welfare_budget]:
    pct = str(round(b.variance_percent(), 1)) if b.planned_amount else "n/a"
    print("  Budget: " + str(b.id) + " planned=" + str(b.planned_amount) + " actual=" + str(b.actual_amount) + " var%=" + pct)
