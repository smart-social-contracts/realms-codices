# Test: Justice System
# Covers: justice system, courts, judges, cases, verdicts, penalties, appeals
import sys as _sys
from ggg import (
    User, Realm, RealmStatus, Codex,
    JusticeSystem, JusticeSystemType, Court, CourtLevel,
    Judge, Case, CaseStatus, Verdict, Penalty, PenaltyType,
    Appeal, AppealStatus,
    LedgerEntry, EntryType, Category,
)

ts = "j" + str(id(object()))[-6:]
fy = 2026
today = "2026-03-09"
deadline = today + "T23:59:59"

# Setup
user_alice = User(id=ts + "_alice", name="Alice")
user_bob = User(id=ts + "_bob", name="Bob")
realm = Realm(name="Justice Test Realm " + ts, description="Test", status=RealmStatus.PRODUCTION)

# ── TEST 1: Justice System, Courts, Judges ───────────────────────────────
print("=== TEST 1: JUSTICE SYSTEM ===")
justice = JusticeSystem(
    name="Syntropia Justice " + ts,
    description="Public justice system for Syntropia realm",
    system_type=JusticeSystemType.PUBLIC,
    status="active",
    realm=realm,
)
assert justice.is_active(), "Justice system should be active"
print("JusticeSystem: " + justice.name + " type=" + justice.system_type)

district_court = Court(
    name="District Court " + ts,
    description="First instance court for civil and commercial matters",
    jurisdiction="Syntropia",
    level=CourtLevel.FIRST_INSTANCE,
    status="active",
    justice_system=justice,
)
appeals_court = Court(
    name="Court of Appeals " + ts,
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

# ── TEST 2: Case Filing ──────────────────────────────────────────────────
print("=== TEST 2: CASE FILING ===")
case = Case(
    case_number="DC-" + ts + "-001",
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

# ── TEST 3: Verdict & Penalty ────────────────────────────────────────────
print("=== TEST 3: VERDICT & PENALTY ===")
case.status = CaseStatus.ASSIGNED
case.status = CaseStatus.VERDICT_ISSUED
verdict = Verdict(
    id="VRD-" + ts + "-001",
    decision="liable",
    reasoning="Defendant encroached 2m into plaintiff parcel. Survey evidence conclusive.",
    issued_date=today,
    case=case,
    issued_by=judge_a,
)
print("Verdict: " + verdict.id + " decision=" + verdict.decision)

fine = Penalty(
    id="PEN-" + ts + "-001",
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
    transaction_id="txn_fine_" + ts + "_001",
    entries=[
        {"entry_type": EntryType.ASSET, "category": Category.RECEIVABLE, "debit": 5000, "credit": 0, "entry_date": today, "description": "Fine receivable from " + user_bob.id},
        {"entry_type": EntryType.REVENUE, "category": Category.FEE, "debit": 0, "credit": 5000, "entry_date": today, "description": "Court fine revenue"},
    ],
)
assert LedgerEntry.validate_transaction("txn_fine_" + ts + "_001"), "Fine transaction should balance"
print("Fine ledger: balanced")

# ── TEST 4: Appeal ───────────────────────────────────────────────────────
print("=== TEST 4: APPEAL ===")
assert case.can_appeal(), "Case with verdict should be appealable"
case.status = CaseStatus.APPEALED
appeal = Appeal(
    id="APL-" + ts + "-001",
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

# Summary
print("=== JUSTICE TESTS PASSED ===")
print("JusticeSystems: " + str(JusticeSystem.count()) + " Courts: " + str(Court.count())
      + " Judges: " + str(Judge.count()) + " Cases: " + str(Case.count())
      + " Verdicts: " + str(Verdict.count()) + " Penalties: " + str(Penalty.count())
      + " Appeals: " + str(Appeal.count()))
