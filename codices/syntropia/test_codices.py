# Test: Fiscal period, funds, budgets, ledger entries, billing, procurement,
#       realm lifecycle, land & zones, justice system
from ggg import (
    Proposal, User, Member, Invoice, Notification, Transfer, Instrument,
    FiscalPeriod, FiscalPeriodStatus, Fund, FundType,
    Budget, BudgetStatus, LedgerEntry, EntryType, Category,
    Realm, RealmStatus, Codex,
    Land, LandStatus, LandType, Zone,
    JusticeSystem, JusticeSystemType, Court, CourtLevel,
    Judge, Case, CaseStatus, Verdict, Penalty, PenaltyType,
    Appeal, AppealStatus,
)
from datetime import datetime
import json

now = datetime.now()
fy = now.year
today = now.strftime("%Y-%m-%d")
deadline = today + "T23:59:59"

# ── TEST 1: Fiscal Period ─────────────────────────────────────────────────
print("=== TEST 1: FISCAL PERIOD ===")
fp = FiscalPeriod(
    id="FY" + str(fy),
    name="Fiscal Year " + str(fy),
    start_date=str(fy) + "-01-01",
    end_date=str(fy) + "-12-31",
    status=FiscalPeriodStatus.OPEN,
)
print("FiscalPeriod " + fp.id + " status=" + fp.status)
assert fp.is_open(), "Fiscal period should be open"

# ── TEST 2: Funds ─────────────────────────────────────────────────────────
print("=== TEST 2: FUNDS ===")
gen_fund = Fund(code="GEN", name="General Fund", fund_type=FundType.GENERAL, description="Main operating fund")
ss_fund = Fund(code="SS", name="Social Security Fund", fund_type=FundType.SPECIAL_REVENUE, description="Welfare and social benefits")
proc_fund = Fund(code="PROC", name="Procurement Fund", fund_type=FundType.CAPITAL_PROJECTS, description="Capital projects and procurement")
sav_fund = Fund(code="SAV", name="Treasury Savings Fund", fund_type=FundType.TRUST, description="Long-term treasury savings")
print("Created funds: " + ", ".join(f.code for f in Fund.instances()))

# ── TEST 3: Budget Proposal + Budget Line Items ──────────────────────────
print("=== TEST 3: BUDGET PROPOSAL & BUDGETS ===")
bp = Proposal(
    proposal_id="budget_fy" + str(fy),
    title="Annual Budget FY " + str(fy),
    description="Allocates 1M revenue: 30% savings, 40% procurement, 30% social security",
    status="debate",
    voting_deadline=deadline,
    metadata="branch:budget",
)
print("Proposal " + bp.proposal_id + " status=" + bp.status)

# Revenue budget
rev_budget = Budget(
    id="FY" + str(fy) + "_GEN_tax",
    name="Tax Revenue FY" + str(fy),
    category="tax_revenue",
    budget_type="revenue",
    planned_amount=1000000,
    status=BudgetStatus.DRAFT,
    description="Projected membership dues and tax revenue",
)
print("  Revenue budget: " + rev_budget.id + " planned=" + str(rev_budget.planned_amount))

# Expense budgets per fund
savings_budget = Budget(
    id="FY" + str(fy) + "_SAV_savings",
    name="Treasury Savings",
    category="savings",
    budget_type="expense",
    planned_amount=300000,
    status=BudgetStatus.DRAFT,
    description="30% allocation to treasury savings",
)
procurement_budget = Budget(
    id="FY" + str(fy) + "_PROC_capital",
    name="Procurement & Capital",
    category="capital",
    budget_type="expense",
    planned_amount=400000,
    status=BudgetStatus.DRAFT,
    description="40% allocation to capital projects",
)
welfare_budget = Budget(
    id="FY" + str(fy) + "_SS_welfare",
    name="Social Security & Welfare",
    category="welfare",
    budget_type="expense",
    planned_amount=300000,
    status=BudgetStatus.DRAFT,
    description="30% allocation to social security",
)
print("  Expense budgets: " + ", ".join(b.id for b in Budget.instances() if b.budget_type == "expense"))

# Approve the budget proposal
bp.status = "enacted"
for b in Budget.instances():
    b.status = BudgetStatus.ADOPTED
print("Budget proposal enacted, all budgets adopted")

# ── TEST 4: Ledger Entries (double-entry) ────────────────────────────────
print("=== TEST 4: LEDGER ENTRIES ===")

# Record tax revenue received: debit Cash, credit Revenue
tax_entries = LedgerEntry.create_transaction(
    transaction_id="txn_tax_" + str(fy) + "_001",
    entries=[
        {
            "entry_type": EntryType.ASSET,
            "category": Category.CASH,
            "debit": 100000,
            "credit": 0,
            "entry_date": today,
            "description": "Membership dues received",
        },
        {
            "entry_type": EntryType.REVENUE,
            "category": Category.TAX,
            "debit": 0,
            "credit": 100000,
            "entry_date": today,
            "description": "Membership dues revenue",
        },
    ],
)
print("Tax revenue transaction: " + str(len(tax_entries)) + " entries, balanced=" + str(LedgerEntry.validate_transaction("txn_tax_" + str(fy) + "_001")))

# Update actual on the revenue budget
rev_budget.update_actual(100000)
print("Revenue budget actual=" + str(rev_budget.actual_amount) + " variance=" + str(rev_budget.variance()))

# Record a procurement expense: debit Expense, credit Cash
proc_entries = LedgerEntry.create_transaction(
    transaction_id="txn_proc_001",
    entries=[
        {
            "entry_type": EntryType.EXPENSE,
            "category": Category.CAPITAL,
            "debit": 50000,
            "credit": 0,
            "entry_date": today,
            "description": "Community Center construction",
        },
        {
            "entry_type": EntryType.ASSET,
            "category": Category.CASH,
            "debit": 0,
            "credit": 50000,
            "entry_date": today,
            "description": "Cash outflow for Community Center",
        },
    ],
)
print("Procurement transaction: balanced=" + str(LedgerEntry.validate_transaction("txn_proc_001")))
procurement_budget.update_actual(50000)
print("Procurement budget actual=" + str(procurement_budget.actual_amount) + " of " + str(procurement_budget.planned_amount))

# Check net balances
cash_balance = LedgerEntry.get_balance(EntryType.ASSET, Category.CASH)
revenue_balance = LedgerEntry.get_balance(EntryType.REVENUE, Category.TAX)
expense_balance = LedgerEntry.get_balance(EntryType.EXPENSE, Category.CAPITAL)
print("Balances: cash=" + str(cash_balance) + " revenue=" + str(revenue_balance) + " expense=" + str(expense_balance))

# ── TEST 5: Monthly Invoice ──────────────────────────────────────────────
print("=== TEST 5: MONTHLY INVOICE ===")
verified = [m for m in Member.instances() if m.identity_verification == "verified" and m.user]
print("Verified members: " + str(len(verified)))
inv_count = 0
for m in verified[:2]:
    due = today + "T23:59:59"
    inv = Invoice(
        amount=0.00001,
        currency="ckBTC",
        due_date=due,
        status="Pending",
        user=m.user,
        metadata="monthly_dues|" + str(m.user.id) + "|" + now.strftime("%Y-%m"),
    )
    print("  Invoice " + str(inv.id) + " for user " + str(m.user.id))
    inv_count += 1
print("Invoices created: " + str(inv_count))

# ── TEST 6: Procurement Proposal ─────────────────────────────────────────
print("=== TEST 6: PROCUREMENT PROPOSAL ===")
pp = Proposal(
    proposal_id="proc_001",
    title="Procurement: Community Center",
    description="Build a community center. Cost: 50000 sats. Contractor: aaaaa-aa",
    status="debate",
    voting_deadline=deadline,
    metadata="branch:procurement",
)
print("Procurement proposal " + pp.proposal_id)

# ── TEST 7: Notification ─────────────────────────────────────────────────
print("=== TEST 7: NOTIFICATION ===")
notif_user = verified[0].user if verified else None
n = Notification(
    topic="billing",
    title="Monthly Dues Reminder",
    message="Your monthly dues invoice has been created. Please pay within 30 days.",
    user=notif_user,
    read=False,
    icon="bell",
    href="/invoices",
    color="blue",
    metadata="test",
)
print("Notification created: " + str(n.title))

# ── TEST 8: Transfer + Ledger Entry ──────────────────────────────────────
print("=== TEST 8: TRANSFER + LEDGER ===")
target_uid = str(verified[0].user.id) if verified else "unknown"
t = Transfer(
    id="txn_ss_001",
    principal_from="system",
    principal_to=target_uid,
    instrument="ckBTC",
    amount=1000,
    status="completed",
    tags="social_security",
    timestamp=now.isoformat(),
)
print("Transfer " + str(t.id) + " to=" + target_uid)

# Record the welfare payment in the ledger
welfare_entries = LedgerEntry.create_transaction(
    transaction_id="txn_welfare_001",
    entries=[
        {
            "entry_type": EntryType.EXPENSE,
            "category": Category.TRANSFER_OUT,
            "debit": 1000,
            "credit": 0,
            "entry_date": today,
            "description": "Social security payment to " + target_uid,
        },
        {
            "entry_type": EntryType.ASSET,
            "category": Category.CASH,
            "debit": 0,
            "credit": 1000,
            "entry_date": today,
            "description": "Cash outflow for social security",
        },
    ],
)
welfare_budget.update_actual(1000)
print("Welfare ledger recorded, budget actual=" + str(welfare_budget.actual_amount))

# ── TEST 9: Realm Lifecycle Stages ────────────────────────────────────────
print("=== TEST 9: REALM LIFECYCLE ===")

# Create a new realm for lifecycle testing
realm = Realm(
    name="Syntropia Lifecycle Test",
    description="A digital realm for smart social contracts",
    status=RealmStatus.ALPHA,
)
print("Realm: " + realm.name + " status=" + realm.status)

# Initialize lifecycle metadata
lifecycle = {
    "critical_mass": 10000,
    "deposit_amount": 100,
    "registered_users": 0,
    "total_deposits": 0,
    "deposits_locked": False,
    "land_acquired": False,
    "infrastructure_ready": False,
    "providers_ready": False,
    "history": [
        {"stage": RealmStatus.ALPHA, "at": now.isoformat(), "reason": "Realm created"}
    ],
}
realm.manifest_data = json.dumps({"lifecycle": lifecycle})

# Simulate alpha stage: ZK proof + deposit, gathering interest
assert realm.status == RealmStatus.ALPHA, "Realm should start in alpha"
lifecycle["registered_users"] = 150
lifecycle["total_deposits"] = 15000
lifecycle["history"].append({
    "stage": RealmStatus.ALPHA,
    "at": now.isoformat(),
    "reason": "150 users registered with ZK proof (Rarimo)",
})
print("  Registered users: " + str(lifecycle["registered_users"]) + " deposits: " + str(lifecycle["total_deposits"]))

# Advance to beta (deposits locked, auctions & land bidding)
realm.status = RealmStatus.BETA
lifecycle["deposits_locked"] = True
lifecycle["history"].append({
    "stage": RealmStatus.BETA,
    "at": now.isoformat(),
    "reason": "Critical mass reached — deposits locked, land bidding begins",
})
assert realm.status == RealmStatus.BETA
print("  Advanced to: " + realm.status + " deposits_locked=" + str(lifecycle["deposits_locked"]))

# Mark infrastructure ready (electricity, roads, buildings, hospitals)
lifecycle["infrastructure_ready"] = True
lifecycle["infrastructure_details"] = "Electricity grid, road network, hospital, school"
lifecycle["land_acquired"] = True
lifecycle["land_details"] = "40 hectares acquired in Zone A"
lifecycle["providers_ready"] = True
lifecycle["providers_details"] = "Power, water, telecom, healthcare contracted"
print("  Infrastructure: ready | Land: acquired | Providers: ready")

# Advance to production (fully operational)
realm.status = RealmStatus.PRODUCTION
lifecycle["history"].append({
    "stage": RealmStatus.PRODUCTION,
    "at": now.isoformat(),
    "reason": "Infrastructure ready — citizens moving in, fully operational",
})
assert realm.status == RealmStatus.PRODUCTION
print("  Advanced to: " + realm.status)

# Simulate deprecation and termination lifecycle
realm_copy_status = realm.status
print("  Production realm status: " + realm_copy_status)
realm.manifest_data = json.dumps({"lifecycle": lifecycle})
print("  Lifecycle history: " + str(len(lifecycle["history"])) + " entries")

# ── TEST 10: Land & Zones ────────────────────────────────────────────────
print("=== TEST 10: LAND & ZONES ===")

# Register land parcels
land_hq = Land(
    id="LAND-001",
    x_coordinate=100,
    y_coordinate=200,
    land_type=LandType.COMMERCIAL,
    size_width=10,
    size_height=10,
    status=LandStatus.ACTIVE,
    registered_by="Syntropia Land Authority",
    nft_token_id="NFT-LAND-001",
    metadata=json.dumps({"use": "Realm HQ", "floor_area_sqm": 2500}),
)
land_res = Land(
    id="LAND-002",
    x_coordinate=120,
    y_coordinate=210,
    land_type=LandType.RESIDENTIAL,
    size_width=5,
    size_height=8,
    status=LandStatus.ACTIVE,
    registered_by="Syntropia Land Authority",
    nft_token_id="NFT-LAND-002",
    metadata=json.dumps({"use": "Residential Block A", "units": 40}),
)
land_farm = Land(
    id="LAND-003",
    x_coordinate=80,
    y_coordinate=250,
    land_type=LandType.AGRICULTURAL,
    size_width=20,
    size_height=30,
    status=LandStatus.ACTIVE,
    registered_by="Syntropia Land Authority",
)
print("Land parcels: " + str(Land.count()))
for l in Land.instances():
    print("  " + l.id + " type=" + l.land_type + " status=" + l.status + " size=" + str(l.size_width) + "x" + str(l.size_height))

# Create zones with H3 indices
zone_central = Zone(
    h3_index="861203a4fffffff",
    name="Central District",
    description="Main commercial and administrative zone",
    latitude=34.0522,
    longitude=-118.2437,
    resolution=6.0,
)
zone_residential = Zone(
    h3_index="861203a5fffffff",
    name="Residential Quarter",
    description="Primary residential area",
    latitude=34.0550,
    longitude=-118.2400,
    resolution=6.0,
    land=land_res,
)
print("Zones: " + str(Zone.count()))
for z in Zone.instances():
    print("  " + z.h3_index + " name=" + z.name)

# ── TEST 11: Justice System ──────────────────────────────────────────────
print("=== TEST 11: JUSTICE SYSTEM ===")

# Create justice system
justice = JusticeSystem(
    name="Syntropia Justice",
    description="Public justice system for Syntropia realm",
    system_type=JusticeSystemType.PUBLIC,
    status="active",
    realm=realm,
)
assert justice.is_active(), "Justice system should be active"
print("JusticeSystem: " + justice.name + " type=" + justice.system_type)

# Create courts (first instance + appellate)
district_court = Court(
    name="District Court",
    description="First instance court for civil and commercial matters",
    jurisdiction="Syntropia",
    level=CourtLevel.FIRST_INSTANCE,
    status="active",
    justice_system=justice,
)
appeals_court = Court(
    name="Court of Appeals",
    description="Appellate court for reviewing district court decisions",
    jurisdiction="Syntropia",
    level=CourtLevel.APPELLATE,
    status="active",
    justice_system=justice,
)
assert district_court.is_active()
assert appeals_court.can_hear_appeal(), "Appellate court should hear appeals"
assert not district_court.can_hear_appeal(), "District court should not hear appeals"
print("Courts: " + str(Court.count()))

# Appoint judges
judge_a = Judge(
    id="judge_alpha",
    status="active",
    specialization="contract_law",
    appointment_date=today,
    court=district_court,
)
judge_b = Judge(
    id="judge_beta",
    status="active",
    specialization="land_disputes",
    appointment_date=today,
    court=district_court,
)
assert judge_a.is_active()
print("Judges: " + str(Judge.count()))

# Create test users for case parties
users = list(User.instances())
if len(users) >= 2:
    plaintiff_user = users[0]
    defendant_user = users[1]
else:
    plaintiff_user = User(id="plaintiff_01", name="Alice Plaintiff")
    defendant_user = User(id="defendant_01", name="Bob Defendant")

# File a case
case = Case(
    case_number="DC-" + str(fy) + "-001",
    title="Land Boundary Dispute",
    description="Plaintiff alleges defendant encroached on LAND-002 residential parcel boundary",
    status=CaseStatus.FILED,
    filed_date=today,
    court=district_court,
    plaintiff=plaintiff_user,
    defendant=defendant_user,
)
assert case.is_open(), "Case should be open after filing"
assert not case.has_verdict(), "No verdict yet"
print("Case filed: " + case.case_number + " title=" + case.title)

# Assign judges
case.status = CaseStatus.ASSIGNED
print("  Assigned judges: " + judge_a.id + ", " + judge_b.id)

# Issue verdict
case.status = CaseStatus.VERDICT_ISSUED
verdict = Verdict(
    id="VRD-" + str(fy) + "-001",
    decision="liable",
    reasoning="Defendant found to have encroached 2m into plaintiff parcel. Survey evidence conclusive.",
    issued_date=today,
    case=case,
    issued_by=judge_a,
)
print("Verdict: " + verdict.id + " decision=" + verdict.decision)

# Create financial penalty (fine)
fine = Penalty(
    id="PEN-" + str(fy) + "-001",
    penalty_type=PenaltyType.FINE,
    amount=5000.0,
    currency="ckBTC",
    description="Fine for boundary encroachment",
    status="pending",
    due_date=today + "T23:59:59",
    verdict=verdict,
    target_user=defendant_user,
)
assert fine.is_financial(), "Fine should be financial"
assert fine.is_pending(), "Fine should be pending"
print("Penalty: " + fine.id + " type=" + fine.penalty_type + " amount=" + str(fine.amount))

# Record fine revenue in the ledger (double-entry: debit receivable, credit revenue)
fine_entries = LedgerEntry.create_transaction(
    transaction_id="txn_fine_" + str(fy) + "_001",
    entries=[
        {
            "entry_type": EntryType.ASSET,
            "category": Category.RECEIVABLE,
            "debit": 5000,
            "credit": 0,
            "entry_date": today,
            "description": "Fine receivable from " + str(defendant_user.id),
        },
        {
            "entry_type": EntryType.REVENUE,
            "category": Category.FEE,
            "debit": 0,
            "credit": 5000,
            "entry_date": today,
            "description": "Court fine revenue — case " + case.case_number,
        },
    ],
)
print("Fine ledger: " + str(len(fine_entries)) + " entries, balanced=" + str(LedgerEntry.validate_transaction("txn_fine_" + str(fy) + "_001")))

# File an appeal
assert case.can_appeal(), "Case with verdict should be appealable"
case.status = CaseStatus.APPEALED
appeal = Appeal(
    id="APL-" + str(fy) + "-001",
    grounds="Procedural error: defendant was not given adequate time to present survey counter-evidence",
    status=AppealStatus.FILED,
    filed_date=today,
    original_case=case,
    original_verdict=verdict,
    appellate_court=appeals_court,
    appellant=defendant_user,
)
assert appeal.is_pending(), "Appeal should be pending"
print("Appeal filed: " + appeal.id + " at " + appeals_court.name)

# Decide appeal — denied (upheld)
appeal.status = AppealStatus.DENIED
appeal.decision = "upheld"
appeal.decision_reasoning = "Procedural review found adequate notice was given. Original verdict stands."
appeal.decided_date = today
assert not appeal.is_pending()
assert not appeal.was_granted()
print("Appeal decided: " + appeal.decision + " — " + appeal.decision_reasoning[:60] + "...")

# Execute the penalty
fine.status = "executed"
fine.executed_date = today
assert not fine.is_pending()
print("Penalty executed: " + fine.id)

# ── STATE SUMMARY ─────────────────────────────────────────────────────────
print("=== STATE SUMMARY ===")
print("Realms: " + str(Realm.count()) + " (status=" + realm.status + ")")
print("FiscalPeriods: " + str(FiscalPeriod.count()))
print("Funds: " + str(Fund.count()))
print("Budgets: " + str(Budget.count()))
print("LedgerEntries: " + str(LedgerEntry.count()))
print("Proposals: " + str(Proposal.count()))
print("Invoices: " + str(Invoice.count()))
print("Notifications: " + str(Notification.count()))
print("Transfers: " + str(Transfer.count()))
print("Land: " + str(Land.count()))
print("Zones: " + str(Zone.count()))
print("JusticeSystems: " + str(JusticeSystem.count()))
print("Courts: " + str(Court.count()))
print("Judges: " + str(Judge.count()))
print("Cases: " + str(Case.count()))
print("Verdicts: " + str(Verdict.count()))
print("Penalties: " + str(Penalty.count()))
print("Appeals: " + str(Appeal.count()))
for b in Budget.instances():
    pct = str(round(b.variance_percent(), 1)) if b.planned_amount else "n/a"
    print("  Budget: " + str(b.id) + " type=" + str(b.budget_type) + " planned=" + str(b.planned_amount) + " actual=" + str(b.actual_amount) + " var%=" + pct)
for p in Proposal.instances():
    print("  Proposal: " + str(p.proposal_id) + " status=" + str(p.status))
print("Net cash: " + str(LedgerEntry.get_balance(EntryType.ASSET, Category.CASH)))
print("=== ALL TESTS PASSED ===")
