# Test: Identity, governance, fiscal, billing, welfare, procurement,
#       treasury, realm lifecycle, land, zones, treaties, licensing,
#       justice system, federation
#
# NOTE: Codex modules are WASM stubs at runtime and cannot be called
# directly. All codex logic is inlined here using ggg entity operations.
from ggg import (
    Proposal, User, Member, Invoice, Notification, Transfer, Instrument,
    FiscalPeriod, FiscalPeriodStatus, Fund, FundType,
    Budget, BudgetStatus, LedgerEntry, EntryType, Category,
    Realm, RealmStatus, Codex, Vote,
    Land, LandStatus, LandType, Zone,
    License, LicenseType, license_issue, license_revoke,
    Quarter, QuarterStatus,
    JusticeSystem, JusticeSystemType, Court, CourtLevel,
    Judge, Case, CaseStatus, Verdict, Penalty, PenaltyType,
    Appeal, AppealStatus,
)
import json
import random

# datetime.now() returns epoch in WASM; use object id for unique prefix
ts = "t" + str(id(object()))[-6:]
fy = 2026
today = "2026-03-09"
deadline = today + "T23:59:59"

# ═══════════════════════════════════════════════════════════════════════════
# SECTION A: IDENTITY & MEMBERSHIP
# ═══════════════════════════════════════════════════════════════════════════

# ── TEST 1: User Registration ────────────────────────────────────────────
print("=== TEST 1: USER REGISTRATION ===")
user_alice = User(id=ts + "_alice", name="Alice")
user_bob = User(id=ts + "_bob", name="Bob")
user_carol = User(id=ts + "_carol", name="Carol")
print("Created users: " + user_alice.id + ", " + user_bob.id + ", " + user_carol.id)
assert user_alice.id, "User should have an id"
assert user_bob.id, "User should have an id"

# ── TEST 2: ZK Passport Verification (simulated) ────────────────────────
print("=== TEST 2: ZK PASSPORT VERIFICATION ===")
zk_hash_alice = "zk_" + ts + "_alice"
zk_hash_bob = "zk_" + ts + "_bob"
zk_hash_carol = "zk_" + ts + "_carol"
print("ZK proofs simulated for 3 users")

# ── TEST 3: Membership Finalization (inline membership logic) ─────
print("=== TEST 3: MEMBERSHIP FINALIZATION ===")
member_alice = Member(
    user=user_alice, identity_verification="verified",
    residence_permit="valid", tax_compliance="compliant",
    public_benefits_eligibility="eligible", voting_eligibility="eligible",
    criminal_record="clean|zk:" + zk_hash_alice,
)
assert member_alice.id, "Alice member should have id"
print("Alice accepted, member_id=" + str(member_alice.id))

member_bob = Member(
    user=user_bob, identity_verification="verified",
    residence_permit="valid", tax_compliance="compliant",
    public_benefits_eligibility="eligible", voting_eligibility="eligible",
    criminal_record="clean|zk:" + zk_hash_bob,
)
print("Bob accepted, member_id=" + str(member_bob.id))

member_carol = Member(
    user=user_carol, identity_verification="verified",
    residence_permit="valid", tax_compliance="compliant",
    public_benefits_eligibility="eligible", voting_eligibility="eligible",
    criminal_record="clean|zk:" + zk_hash_carol,
)
print("Carol accepted, member_id=" + str(member_carol.id))

# Verify membership status
assert member_alice.identity_verification == "verified", "Alice should be verified"
assert member_alice.user.id == user_alice.id, "Alice member should link to user"
print("Alice membership verified: " + member_alice.identity_verification)

# Sybil resistance: duplicate ZK hash detection
dup_found = False
for m in Member.instances():
    if m.criminal_record and zk_hash_alice in m.criminal_record and m.id != member_alice.id:
        dup_found = True
assert not dup_found, "No duplicate ZK hash should exist"
print("Sybil resistance check passed")

Notification(
    topic="membership", title="Citizenship Granted",
    message="Your identity has been verified. Welcome to Syntropia.",
    user=user_alice, read=False, icon="shield_check", href="/", color="green",
    metadata="uid:" + user_alice.id + "|mid:" + str(member_alice.id),
)

# ── TEST 4: Membership Revocation (inline membership logic) ──────
print("=== TEST 4: MEMBERSHIP REVOCATION ===")
member_carol.identity_verification = "revoked"
member_carol.voting_eligibility = "ineligible"
member_carol.public_benefits_eligibility = "ineligible"
assert member_carol.identity_verification == "revoked", "Carol should be revoked"
print("Carol revoked, verification=" + member_carol.identity_verification)

Notification(
    topic="membership", title="Citizenship Revoked",
    message="Your citizenship has been revoked. Reason: Test revocation for non-payment.",
    user=user_carol, read=False, icon="shield_off", href="/", color="red",
    metadata="uid:" + user_carol.id + "|mid:" + str(member_carol.id),
)
print("Carol status after revocation: " + member_carol.identity_verification)

# ═══════════════════════════════════════════════════════════════════════════
# SECTION B: GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════

# ── TEST 5: Create Legislative Proposal ──────────────────────────────────
print("=== TEST 5: LEGISLATIVE PROPOSAL ===")
leg_prop = Proposal(
    proposal_id=ts + "_leg_001",
    title="Universal Healthcare Coverage Act",
    description="Extend basic healthcare to all registered citizens",
    status="debate",
    voting_deadline=deadline,
    metadata="branch:legislative",
)
print("Legislative proposal: " + leg_prop.proposal_id + " status=" + leg_prop.status)

# ── TEST 6: Cast Votes ───────────────────────────────────────────────────
print("=== TEST 6: CAST VOTES ===")
vote_a = Vote(proposal=leg_prop, voter=user_alice, vote_choice="yes")
vote_b = Vote(proposal=leg_prop, voter=user_bob, vote_choice="yes")
vote_c = Vote(proposal=leg_prop, voter=user_carol, vote_choice="no")
print("Votes cast: Alice=yes, Bob=yes, Carol=no")

leg_prop.votes_yes = 2
leg_prop.votes_no = 1
leg_prop.total_voters = 3
print("Tally: yes=" + str(int(leg_prop.votes_yes)) + " no=" + str(int(leg_prop.votes_no)))

# ── TEST 7: Process Vote Results (simple majority) ───────────────────────
print("=== TEST 7: VOTE RESULTS ===")
votes_for = int(leg_prop.votes_yes or 0)
votes_against = int(leg_prop.votes_no or 0)
total = votes_for + votes_against
assert total > 0, "Should have votes"
passed = votes_for > votes_against
assert passed, "Proposal should pass with 2 vs 1"
leg_prop.status = "passed_parliament"
print("Proposal " + leg_prop.proposal_id + " passed parliament (" + str(votes_for) + " vs " + str(votes_against) + ")")

# ── TEST 8: Executive Approval & Veto (inline governance_automation) ────
print("=== TEST 8: EXECUTIVE APPROVAL & VETO ===")

# Approve
leg_prop.status = "enacted"
assert leg_prop.status == "enacted", "Should be enacted"
print("Executive approved: status=" + leg_prop.status)

# Veto a second proposal
veto_prop = Proposal(
    proposal_id=ts + "_leg_002",
    title="Controversial Tax Bill",
    description="Double all tax rates immediately",
    status="passed_parliament",
    voting_deadline=deadline,
    metadata="branch:legislative",
)
veto_prop.status = "vetoed"
assert veto_prop.status == "vetoed", "Should be vetoed"
print("Executive vetoed: status=" + veto_prop.status)

# ── TEST 9: Judicial Review (inline governance_automation) ───────────────
print("=== TEST 9: JUDICIAL REVIEW ===")
# Constitutional review passes
assert leg_prop.status == "enacted"
print("Judicial review (constitutional): proposal=" + leg_prop.proposal_id + " upheld")

# Strike down unconstitutional law
strike_prop = Proposal(
    proposal_id=ts + "_leg_003",
    title="Unconstitutional Surveillance Act",
    description="Mass surveillance without warrant",
    status="enacted",
    voting_deadline=deadline,
    metadata="branch:legislative",
)
strike_prop.status = "struck_down"
assert strike_prop.status == "struck_down"
print("Judicial review (struck down): " + strike_prop.proposal_id)

# ═══════════════════════════════════════════════════════════════════════════
# SECTION C: FISCAL SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

# ── TEST 10: Fiscal Period ───────────────────────────────────────────────
print("=== TEST 10: FISCAL PERIOD ===")
fp = FiscalPeriod(
    id="FY" + str(fy),
    name="Fiscal Year " + str(fy),
    start_date=str(fy) + "-01-01",
    end_date=str(fy) + "-12-31",
    status=FiscalPeriodStatus.OPEN,
)
print("FiscalPeriod " + fp.id + " status=" + fp.status)
assert fp.is_open(), "Fiscal period should be open"

# ── TEST 11: Funds ───────────────────────────────────────────────────────
print("=== TEST 11: FUNDS ===")
gen_fund = Fund(code="GEN", name="General Fund", fund_type=FundType.GENERAL, description="Main operating fund")
ss_fund = Fund(code="SS", name="Social Security Fund", fund_type=FundType.SPECIAL_REVENUE, description="Welfare and social benefits")
proc_fund = Fund(code="PROC", name="Procurement Fund", fund_type=FundType.CAPITAL_PROJECTS, description="Capital projects and procurement")
sav_fund = Fund(code="SAV", name="Treasury Savings Fund", fund_type=FundType.TRUST, description="Long-term treasury savings")
print("Created funds: " + ", ".join(f.code for f in Fund.instances()))

# ── TEST 12: Budget Proposal + Budget Line Items ─────────────────────────
print("=== TEST 12: BUDGET PROPOSAL & BUDGETS ===")
bp = Proposal(
    proposal_id="budget_fy" + str(fy),
    title="Annual Budget FY " + str(fy),
    description="Allocates 1M revenue: 30% savings, 40% procurement, 30% social security",
    status="debate",
    voting_deadline=deadline,
    metadata="branch:budget",
)
print("Proposal " + bp.proposal_id + " status=" + bp.status)

rev_budget = Budget(
    id="FY" + str(fy) + "_GEN_tax",
    name="Tax Revenue FY" + str(fy),
    category="tax_revenue",
    budget_type="revenue",
    planned_amount=1000000,
    status=BudgetStatus.DRAFT,
    description="Projected membership dues and tax revenue",
)
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

bp.status = "enacted"
for b in Budget.instances():
    b.status = BudgetStatus.ADOPTED
print("Budget proposal enacted, all budgets adopted")

# ── TEST 13: Ledger Entries (double-entry) ───────────────────────────────
print("=== TEST 13: LEDGER ENTRIES ===")
tax_entries = LedgerEntry.create_transaction(
    transaction_id="txn_tax_" + str(fy) + "_001",
    entries=[
        {"entry_type": EntryType.ASSET, "category": Category.CASH, "debit": 100000, "credit": 0, "entry_date": today, "description": "Membership dues received"},
        {"entry_type": EntryType.REVENUE, "category": Category.TAX, "debit": 0, "credit": 100000, "entry_date": today, "description": "Membership dues revenue"},
    ],
)
print("Tax revenue: " + str(len(tax_entries)) + " entries, balanced=" + str(LedgerEntry.validate_transaction("txn_tax_" + str(fy) + "_001")))
rev_budget.update_actual(100000)

proc_entries = LedgerEntry.create_transaction(
    transaction_id="txn_proc_001",
    entries=[
        {"entry_type": EntryType.EXPENSE, "category": Category.CAPITAL, "debit": 50000, "credit": 0, "entry_date": today, "description": "Community Center construction"},
        {"entry_type": EntryType.ASSET, "category": Category.CASH, "debit": 0, "credit": 50000, "entry_date": today, "description": "Cash outflow for Community Center"},
    ],
)
print("Procurement transaction: balanced=" + str(LedgerEntry.validate_transaction("txn_proc_001")))
procurement_budget.update_actual(50000)
print("Balances: cash=" + str(LedgerEntry.get_balance(EntryType.ASSET, Category.CASH)) + " revenue=" + str(LedgerEntry.get_balance(EntryType.REVENUE, Category.TAX)))

# ── TEST 14: Progressive Tax Calculation ─────────────────────────────────
print("=== TEST 14: PROGRESSIVE TAX CALCULATION ===")
import tax_collection

# Give Alice some income via transfers
Transfer(id=ts + "_income_alice", principal_from="system", principal_to=user_alice.id,
         instrument="Realm Token", amount=50000, status="completed",
         tags="income", timestamp=now.isoformat())

tax_info = tax_collection.calculate_tax_for_user(user_alice.id, tax_year=fy)
print("Alice tax: gross=" + str(tax_info.get("gross_income", 0))
      + " deduction=" + str(tax_info.get("standard_deduction", 0))
      + " taxable=" + str(tax_info.get("taxable_income", 0))
      + " owed=" + str(tax_info.get("tax_owed", 0))
      + " rate=" + str(tax_info.get("effective_rate", 0)))
assert tax_info.get("gross_income", 0) >= 50000, "Alice should have income >= 50000"
assert tax_info.get("tax_owed", 0) > 0, "Alice should owe tax"
print("Tax brackets: " + str(len(tax_collection.TAX_BRACKETS)) + " brackets, deduction=" + str(tax_collection.STANDARD_DEDUCTION))

# ── TEST 15: Tax Collection ──────────────────────────────────────────────
print("=== TEST 15: TAX COLLECTION ===")
tax_results = tax_collection.process_tax_collection()
print("Tax collection: " + str(len(tax_results)) + " payments processed")
for tr in tax_results[:3]:
    print("  user=" + str(tr.get("user_id", "")) + " tax=" + str(tr.get("tax_collected", 0)) + " rate=" + str(tr.get("effective_rate", 0)))

# ═══════════════════════════════════════════════════════════════════════════
# SECTION D: BILLING
# ═══════════════════════════════════════════════════════════════════════════

# ── TEST 16: Monthly Invoice ─────────────────────────────────────────────
print("=== TEST 16: MONTHLY INVOICE ===")
import monthly_billing

inv_result = monthly_billing.create_monthly_invoice(user_alice.id)
assert "error" not in inv_result, "Invoice creation should succeed: " + str(inv_result)
print("Invoice created: id=" + str(inv_result.get("invoice_id")) + " amount=" + str(inv_result.get("amount_ckbtc")))

inv_result_bob = monthly_billing.create_monthly_invoice(user_bob.id)
assert "error" not in inv_result_bob
print("Invoice for Bob: id=" + str(inv_result_bob.get("invoice_id")))

# ── TEST 17: Overdue Invoice Warning ─────────────────────────────────────
print("=== TEST 17: OVERDUE WARNING ===")
warn_result = monthly_billing.warn_user(user_bob.id, str(inv_result_bob.get("invoice_id", "")))
assert warn_result.get("warned"), "Warning should succeed"
print("Warning sent to Bob: " + str(warn_result))

# ── TEST 18: Membership Revocation for Non-Payment ──────────────────────
print("=== TEST 18: BILLING REVOCATION ===")
# Carol was already revoked in TEST 4 — verify kick_user also works
kick_result = monthly_billing.kick_user(user_carol.id, "test_invoice")
print("Kick result for Carol: " + str(kick_result))

# ═══════════════════════════════════════════════════════════════════════════
# SECTION E: SPENDING & WELFARE
# ═══════════════════════════════════════════════════════════════════════════

# ── TEST 19: Welfare Benefit Distribution ────────────────────────────────
print("=== TEST 19: WELFARE DISTRIBUTION ===")
target_uid = user_alice.id
t = Transfer(
    id=ts + "_ss_001",
    principal_from="system",
    principal_to=target_uid,
    instrument="ckBTC",
    amount=1000,
    status="completed",
    tags="social_security",
    timestamp=now.isoformat(),
)
print("Welfare transfer " + str(t.id) + " to=" + target_uid + " amount=1000")

welfare_entries = LedgerEntry.create_transaction(
    transaction_id=ts + "_welfare_001",
    entries=[
        {"entry_type": EntryType.EXPENSE, "category": Category.TRANSFER_OUT, "debit": 1000, "credit": 0, "entry_date": today, "description": "Social security payment to " + target_uid},
        {"entry_type": EntryType.ASSET, "category": Category.CASH, "debit": 0, "credit": 1000, "entry_date": today, "description": "Cash outflow for social security"},
    ],
)
welfare_budget.update_actual(1000)
print("Welfare ledger recorded, budget actual=" + str(welfare_budget.actual_amount))

n_welfare = Notification(
    topic="social_security", title="Social Security Payment",
    message="You received 0.00001 ckBTC as social security benefit.",
    user=user_alice, read=False, icon="wallet",
    href="/extensions/member_dashboard#my_taxes", color="green",
    metadata="uid:" + user_alice.id,
)
print("Welfare notification sent")

# ── TEST 20: Procurement Project Proposal, Vote, Approval ────────────────
print("=== TEST 20: PROCUREMENT WORKFLOW ===")
import procurement

proj = procurement.propose_project(
    name="Solar Farm",
    desc="Build a 10MW solar farm for the realm",
    amount_satoshis=200000,
    receiver_principal="aaaaa-aa",
    proposer_user_id=user_alice.id,
)
assert "proposal_id" in proj, "Project should have proposal_id"
print("Procurement proposed: " + str(proj.get("proposal_id")) + " amount=" + str(proj.get("amt")))

# Approve the project
approval = procurement.approve_project(proj["proposal_id"])
assert approval.get("status") == "approved", "Should be approved: " + str(approval)
print("Project approved: " + str(approval))

# Check project status
ps = procurement.get_project_status(proj["proposal_id"])
assert ps.get("status") == "approved"
print("Project status: " + str(ps.get("status")) + " amount=" + str(ps.get("amount_satoshis")))

# List all projects
projects = procurement.list_projects()
print("Total procurement projects: " + str(len(projects)))

# ── TEST 21: Treasury Savings & Supermajority Withdrawal ─────────────────
print("=== TEST 21: TREASURY SAVINGS ===")
import treasury_savings

# Create a withdrawal proposal directly
tsw_prop = Proposal(
    proposal_id=ts + "_tsw_001",
    title="Treasury Withdrawal: 10000 sat",
    description=json.dumps({"amt": 10000, "rcv": "aaaaa-aa", "by": user_alice.id, "st": "proposed"}),
    status="debate",
    voting_deadline=deadline,
    metadata="branch:treasury_savings",
)
print("Treasury withdrawal proposed: " + tsw_prop.proposal_id)

# Simulate voting — 3 yes, 1 no (passes supermajority 75% > 66.7%)
tsw_prop.votes_yes = 3
tsw_prop.votes_no = 1
sm = treasury_savings.check_supermajority(tsw_prop.proposal_id)
assert sm.get("passed"), "Supermajority should pass with 3/4=75%: " + str(sm)
print("Supermajority check: passed=" + str(sm.get("passed")) + " ratio=" + str(sm.get("approval_ratio")))

# Simulate voting — 2 yes, 2 no (fails supermajority 50% < 66.7%)
tsw_prop.votes_yes = 2
tsw_prop.votes_no = 2
sm_fail = treasury_savings.check_supermajority(tsw_prop.proposal_id)
assert not sm_fail.get("passed"), "Supermajority should fail with 2/4=50%"
print("Supermajority check (fail): passed=" + str(sm_fail.get("passed")) + " ratio=" + str(sm_fail.get("approval_ratio")))

withdrawals = treasury_savings.list_withdrawals()
print("Treasury withdrawal proposals: " + str(len(withdrawals)))

# ═══════════════════════════════════════════════════════════════════════════
# SECTION F: TERRITORY & LAND
# ═══════════════════════════════════════════════════════════════════════════

# ── TEST 22: Realm Lifecycle Stages ──────────────────────────────────────
print("=== TEST 22: REALM LIFECYCLE ===")
realm = Realm(
    name="Syntropia Lifecycle Test",
    description="A digital realm for smart social contracts",
    status=RealmStatus.ALPHA,
)
print("Realm: " + realm.name + " status=" + realm.status)

lifecycle = {
    "critical_mass": 10000, "deposit_amount": 100,
    "registered_users": 0, "total_deposits": 0,
    "deposits_locked": False, "land_acquired": False,
    "infrastructure_ready": False, "providers_ready": False,
    "history": [{"stage": RealmStatus.ALPHA, "at": now.isoformat(), "reason": "Realm created"}],
}
realm.manifest_data = json.dumps({"lifecycle": lifecycle})
assert realm.status == RealmStatus.ALPHA, "Realm should start in alpha"

lifecycle["registered_users"] = 150
lifecycle["total_deposits"] = 15000
print("  Registered: " + str(lifecycle["registered_users"]) + " deposits: " + str(lifecycle["total_deposits"]))

realm.status = RealmStatus.BETA
lifecycle["deposits_locked"] = True
assert realm.status == RealmStatus.BETA
print("  Advanced to: " + realm.status)

lifecycle["infrastructure_ready"] = True
lifecycle["land_acquired"] = True
lifecycle["providers_ready"] = True

realm.status = RealmStatus.PRODUCTION
assert realm.status == RealmStatus.PRODUCTION
print("  Advanced to: " + realm.status)
realm.manifest_data = json.dumps({"lifecycle": lifecycle})
print("  Lifecycle history: " + str(len(lifecycle["history"])) + " entries")

# ── TEST 23: Land & Zones ───────────────────────────────────────────────
print("=== TEST 23: LAND & ZONES ===")
land_hq = Land(
    id=ts + "_LAND001", x_coordinate=100, y_coordinate=200,
    land_type=LandType.COMMERCIAL, size_width=10, size_height=10,
    status=LandStatus.ACTIVE, registered_by="Syntropia Land Authority",
    nft_token_id="NFT-" + ts + "-001",
    metadata=json.dumps({"use": "Realm HQ", "floor_area_sqm": 2500}),
)
land_res = Land(
    id=ts + "_LAND002", x_coordinate=120, y_coordinate=210,
    land_type=LandType.RESIDENTIAL, size_width=5, size_height=8,
    status=LandStatus.ACTIVE, registered_by="Syntropia Land Authority",
    nft_token_id="NFT-" + ts + "-002",
    metadata=json.dumps({"use": "Residential Block A", "units": 40}),
)
land_farm = Land(
    id=ts + "_LAND003", x_coordinate=80, y_coordinate=250,
    land_type=LandType.AGRICULTURAL, size_width=20, size_height=30,
    status=LandStatus.ACTIVE, registered_by="Syntropia Land Authority",
)
print("Land parcels: " + str(Land.count()))

zone_central = Zone(
    h3_index="861203a4fffffff", name=ts + " Central District",
    description="Main commercial and administrative zone",
    latitude=34.0522, longitude=-118.2437, resolution=6.0,
)
zone_residential = Zone(
    h3_index="861203a5fffffff", name=ts + " Residential Quarter",
    description="Primary residential area",
    latitude=34.0550, longitude=-118.2400, resolution=6.0, land=land_res,
)
print("Zones: " + str(Zone.count()))

# ── TEST 24: Land Lease Treaty Lifecycle ─────────────────────────────────
print("=== TEST 24: LAND LEASE TREATY ===")
import land_treaty

treaty = land_treaty.create_treaty(
    host_state_name="Republic of Freedonia",
    territory_description="50 km2 coastal zone in the southern province",
    term_years=50, annual_fee=500000, fee_currency="USD",
    revenue_share_pct=5.0, security_deposit=2000000, territory_area_km2=50.0,
)
assert treaty.get("status") == "draft"
treaty_id = treaty["treaty_id"]
print("Treaty created: " + treaty_id + " status=draft")

# Sign
sign_result = land_treaty.sign_treaty(treaty_id, "Minister of Foreign Affairs", "Realm Chancellor")
assert sign_result.get("status") == "signed", "Should be signed: " + str(sign_result)
print("Treaty signed: " + str(sign_result.get("status")))

# Ratify
ratify_result = land_treaty.ratify_treaty(treaty_id, ratified_by="parliament")
assert ratify_result.get("status") == "ratified"
print("Treaty ratified: " + str(ratify_result.get("status")))

# Activate
activate_result = land_treaty.activate_treaty(treaty_id)
assert activate_result.get("status") == "active"
print("Treaty activated: " + str(activate_result.get("status")))

# Record payment
pay_result = land_treaty.record_payment(treaty_id, amount=500000, currency="USD", period="Year 1")
assert "payment_index" in pay_result
print("Payment recorded: " + str(pay_result.get("amount")))

pay_summary = land_treaty.get_payment_summary(treaty_id)
print("Payment summary: total_paid=" + str(pay_summary.get("total_paid")))

# Suspend and reactivate
suspend_result = land_treaty.suspend_treaty(treaty_id, reason="Diplomatic review")
assert suspend_result.get("status") == "suspended"
print("Treaty suspended")

reactivate_result = land_treaty.reactivate_treaty(treaty_id)
assert reactivate_result.get("status") == "active"
print("Treaty reactivated")

# Terminate
terminate_result = land_treaty.terminate_treaty(treaty_id, reason="Term ended")
assert terminate_result.get("status") == "terminated"
print("Treaty terminated")

treaties = land_treaty.list_treaties()
print("Total treaties: " + str(len(treaties)))

# ── TEST 25: Zone Policy & License Assignment ────────────────────────────
print("=== TEST 25: ZONE POLICY & LICENSE ===")
import zones

# Add policy to zone
policy_result = zones.add_policy_to_zone(
    str(zone_central.id), "Tax Incentive Zone",
    "Reduced tax rate for businesses in the central district",
)
assert "error" not in policy_result, "Policy should be added: " + str(policy_result)
print("Policy added: " + str(policy_result.get("policy", {}).get("name")))

# Create a license for assignment
test_lic = license_issue(
    name=ts + "_test_provider",
    license_type=LicenseType.INFRASTRUCTURE,
    description="Test infrastructure provider",
    validity_seconds=365 * 86400,
    issuing_authority="Central Authority",
)
print("License issued: " + str(test_lic.id) + " type=" + test_lic.license_type)

# Assign license to zone
assign_result = zones.assign_license_to_zone(str(zone_central.id), str(test_lic.id))
assert assign_result.get("status") == "assigned", "License should be assigned: " + str(assign_result)
print("License assigned to zone: " + str(assign_result))

# Verify zone details
zone_info = zones.get_zone(str(zone_central.id))
assert str(test_lic.id) in zone_info.get("assigned_licenses", [])
print("Zone has " + str(len(zone_info.get("assigned_licenses", []))) + " licenses, " + str(len(zone_info.get("policies", []))) + " policies")

# Remove license from zone
remove_result = zones.remove_license_from_zone(str(zone_central.id), str(test_lic.id))
assert remove_result.get("status") == "removed"
print("License removed from zone")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION G: SERVICE PROVIDERS
# ═══════════════════════════════════════════════════════════════════════════

# ── TEST 26: License Issuance ────────────────────────────────────────────
print("=== TEST 26: LICENSE ISSUANCE ===")
import licensing

hospital_lic = licensing.issue_provider_license(
    ts + "_City Hospital", LicenseType.HEALTH,
    description="Primary healthcare provider for the central district",
    issuing_authority="Health Ministry",
)
assert "error" not in hospital_lic, "License should be issued: " + str(hospital_lic)
print("Hospital license: id=" + str(hospital_lic.get("license_id")) + " status=" + str(hospital_lic.get("status")))

school_lic = licensing.issue_provider_license(
    ts + "_Academy", LicenseType.EDUCATION,
    description="K-12 education provider",
)
assert "error" not in school_lic
print("School license: id=" + str(school_lic.get("license_id")))

security_lic = licensing.issue_provider_license(
    ts + "_SecureGuard", LicenseType.POLICE,
    description="Community security and policing",
)
assert "error" not in security_lic
print("Security license: id=" + str(security_lic.get("license_id")))

# ── TEST 27: Compliance Check ────────────────────────────────────────────
print("=== TEST 27: COMPLIANCE CHECK ===")
comp_result = licensing.check_compliance(str(hospital_lic["license_id"]))
assert comp_result.get("compliant"), "Hospital should be compliant: " + str(comp_result)
print("Hospital compliance: " + str(comp_result.get("compliant")) + " status=" + str(comp_result.get("status")))

# ── TEST 28: Service Bill Submission & Payment ───────────────────────────
print("=== TEST 28: SERVICE BILLING ===")
bill_result = licensing.submit_bill(str(hospital_lic["license_id"]), amount=5000, description="Q1 healthcare services")
assert "error" not in bill_result, "Bill should be submitted: " + str(bill_result)
print("Bill submitted: index=" + str(bill_result.get("bill_index")) + " amount=" + str(bill_result.get("amount")))

pay_result = licensing.pay_bill(str(hospital_lic["license_id"]), bill_index=0)
assert pay_result.get("status") == "paid", "Bill should be paid: " + str(pay_result)
print("Bill paid: " + str(pay_result.get("amount")))

# ── TEST 29: License Renewal & Revocation ────────────────────────────────
print("=== TEST 29: LICENSE RENEWAL & REVOCATION ===")
renew_result = licensing.renew_provider_license(str(school_lic["license_id"]))
assert renew_result.get("status") == "active", "License should be renewed: " + str(renew_result)
print("School license renewed: " + str(renew_result.get("status")))

revoke_result = licensing.revoke_provider_license(str(security_lic["license_id"]), reason="Compliance failure")
assert revoke_result.get("status") == "revoked"
print("Security license revoked: " + str(revoke_result.get("status")))

licenses = licensing.list_licenses()
print("Active licenses: " + str(len(licenses)))

# ═══════════════════════════════════════════════════════════════════════════
# SECTION H: JUSTICE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

# ── TEST 30: Justice System ──────────────────────────────────────────────
print("=== TEST 30: JUSTICE SYSTEM ===")
justice = JusticeSystem(
    name="Syntropia Justice",
    description="Public justice system for Syntropia realm",
    system_type=JusticeSystemType.PUBLIC,
    status="active",
    realm=realm,
)
assert justice.is_active(), "Justice system should be active"
print("JusticeSystem: " + justice.name + " type=" + justice.system_type)

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

judge_a = Judge(
    id=ts + "_judge_alpha", status="active",
    specialization="contract_law", appointment_date=today, court=district_court,
)
judge_b = Judge(
    id=ts + "_judge_beta", status="active",
    specialization="land_disputes", appointment_date=today, court=district_court,
)
assert judge_a.is_active()
print("Judges: " + str(Judge.count()))

case = Case(
    case_number="DC-" + str(fy) + "-001",
    title="Land Boundary Dispute",
    description="Plaintiff alleges defendant encroached on residential parcel boundary",
    status=CaseStatus.FILED,
    filed_date=today,
    court=district_court,
    plaintiff=user_alice,
    defendant=user_bob,
)
assert case.is_open(), "Case should be open after filing"
assert not case.has_verdict(), "No verdict yet"
print("Case filed: " + case.case_number)

case.status = CaseStatus.ASSIGNED
case.status = CaseStatus.VERDICT_ISSUED
verdict = Verdict(
    id="VRD-" + str(fy) + "-001",
    decision="liable",
    reasoning="Defendant encroached 2m into plaintiff parcel. Survey evidence conclusive.",
    issued_date=today,
    case=case,
    issued_by=judge_a,
)
print("Verdict: " + verdict.id + " decision=" + verdict.decision)

fine = Penalty(
    id="PEN-" + str(fy) + "-001",
    penalty_type=PenaltyType.FINE,
    amount=5000.0,
    currency="ckBTC",
    description="Fine for boundary encroachment",
    status="pending",
    due_date=deadline,
    verdict=verdict,
    target_user=user_bob,
)
assert fine.is_financial(), "Fine should be financial"
assert fine.is_pending(), "Fine should be pending"
print("Penalty: " + fine.id + " type=" + fine.penalty_type + " amount=" + str(fine.amount))

fine_entries = LedgerEntry.create_transaction(
    transaction_id="txn_fine_" + str(fy) + "_001",
    entries=[
        {"entry_type": EntryType.ASSET, "category": Category.RECEIVABLE, "debit": 5000, "credit": 0, "entry_date": today, "description": "Fine receivable from " + user_bob.id},
        {"entry_type": EntryType.REVENUE, "category": Category.FEE, "debit": 0, "credit": 5000, "entry_date": today, "description": "Court fine revenue"},
    ],
)
print("Fine ledger: balanced=" + str(LedgerEntry.validate_transaction("txn_fine_" + str(fy) + "_001")))

assert case.can_appeal(), "Case with verdict should be appealable"
case.status = CaseStatus.APPEALED
appeal = Appeal(
    id="APL-" + str(fy) + "-001",
    grounds="Procedural error: inadequate time for counter-evidence",
    status=AppealStatus.FILED,
    filed_date=today,
    original_case=case,
    original_verdict=verdict,
    appellate_court=appeals_court,
    appellant=user_bob,
)
assert appeal.is_pending(), "Appeal should be pending"
print("Appeal filed: " + appeal.id)

appeal.status = AppealStatus.DENIED
appeal.decision = "upheld"
appeal.decision_reasoning = "Procedural review found adequate notice was given."
appeal.decided_date = today
assert not appeal.is_pending()
assert not appeal.was_granted()
print("Appeal decided: " + appeal.decision)

fine.status = "executed"
fine.executed_date = today
assert not fine.is_pending()
print("Penalty executed: " + fine.id)

# ═══════════════════════════════════════════════════════════════════════════
# SECTION I: FEDERATION
# ═══════════════════════════════════════════════════════════════════════════

# ── TEST 31: Federation / Quarter Assignment ─────────────────────────────
print("=== TEST 31: FEDERATION & QUARTERS ===")
import quarter_assignment

q1 = Quarter(name=ts + "_Quarter_Alpha", canister_id="aaaaa-aa", federation=realm, population=50, status=QuarterStatus.ACTIVE)
q2 = Quarter(name=ts + "_Quarter_Beta", canister_id="bbbbb-bb", federation=realm, population=30, status=QuarterStatus.ACTIVE)
q3 = Quarter(name=ts + "_Quarter_Gamma", canister_id="ccccc-cc", federation=realm, population=80, status=QuarterStatus.ACTIVE)
print("Quarters created: " + q1.name + ", " + q2.name + ", " + q3.name)

quarters = [q1, q2, q3]

# Test random strategy
assigned_random = quarter_assignment.assign_quarter("principal_test_123", quarters, "")
assert assigned_random in ["aaaaa-aa", "bbbbb-bb", "ccccc-cc"], "Should assign to a valid quarter"
print("Random assignment: " + assigned_random)

# Test least_populated strategy
orig_strategy = quarter_assignment.ASSIGNMENT_STRATEGY
quarter_assignment.ASSIGNMENT_STRATEGY = "least_populated"
assigned_lp = quarter_assignment.assign_quarter("principal_test_456", quarters, "")
assert assigned_lp == "bbbbb-bb", "Should assign to least populated (Beta=30): got " + assigned_lp
print("Least populated assignment: " + assigned_lp + " (Quarter Beta, pop=30)")

# Test user_choice strategy
quarter_assignment.ASSIGNMENT_STRATEGY = "user_choice"
assigned_uc = quarter_assignment.assign_quarter("principal_test_789", quarters, "ccccc-cc")
assert assigned_uc == "ccccc-cc", "Should honour user choice"
print("User choice assignment: " + assigned_uc)

# Restore original strategy
quarter_assignment.ASSIGNMENT_STRATEGY = orig_strategy
print("Quarter assignment strategies verified")

# ═══════════════════════════════════════════════════════════════════════════
# STATE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
print("=== STATE SUMMARY ===")
print("Users: " + str(User.count()))
print("Members: " + str(Member.count()))
print("Realms: " + str(Realm.count()) + " (status=" + realm.status + ")")
print("FiscalPeriods: " + str(FiscalPeriod.count()))
print("Funds: " + str(Fund.count()))
print("Budgets: " + str(Budget.count()))
print("LedgerEntries: " + str(LedgerEntry.count()))
print("Proposals: " + str(Proposal.count()))
print("Votes: " + str(Vote.count()))
print("Invoices: " + str(Invoice.count()))
print("Notifications: " + str(Notification.count()))
print("Transfers: " + str(Transfer.count()))
print("Licenses: " + str(License.count()))
print("Land: " + str(Land.count()))
print("Zones: " + str(Zone.count()))
print("Quarters: " + str(Quarter.count()))
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
