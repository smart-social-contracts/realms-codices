"""
Tests for social_benefits.py — benefit eligibility and distribution.

Validates:
  - Benefit eligibility checks (eligible and ineligible members)
  - Benefit amount calculation (base + adjustments)
  - Full distribution flow (end-to-end with transfers)
"""

from ggg import User, Member, Transfer, Treasury, Instrument

import social_benefits

# ── Test check_benefit_eligibility ─────────────────────────────────────────

print("Testing check_benefit_eligibility...")

# Create test data — eligible member
user_alice = User(id="alice")
member_alice = Member(
    id="member_alice",
    user=user_alice,
    residence_permit="valid",
    tax_compliance="compliant",
    identity_verification="verified",
    public_benefits_eligibility="eligible",
    criminal_record="clean",
    voting_eligibility="eligible",
)

result = social_benefits.check_benefit_eligibility("member_alice")
assert result["eligible"] is True, f"Alice should be eligible, got: {result}"
assert result["member_id"] == "member_alice"
assert all(result["criteria_met"].values()), "All criteria should be met for Alice"

# Ineligible member (unverified identity)
user_bob = User(id="bob")
member_bob = Member(
    id="member_bob",
    user=user_bob,
    residence_permit="valid",
    tax_compliance="compliant",
    identity_verification="pending",
    public_benefits_eligibility="eligible",
)

result_bob = social_benefits.check_benefit_eligibility("member_bob")
assert result_bob["eligible"] is False, f"Bob should NOT be eligible, got: {result_bob}"
assert result_bob["criteria_met"]["identity_verification"] is False

# Non-existent member
result_none = social_benefits.check_benefit_eligibility("nonexistent")
assert result_none["eligible"] is False
assert result_none["reason"] == "Member not found"

print("  check_benefit_eligibility: OK")

# ── Test calculate_benefit_amount ──────────────────────────────────────────

print("Testing calculate_benefit_amount...")

# Alice: clean record + voting eligible = 500 + 100 + 50 = 650
amount_alice = social_benefits.calculate_benefit_amount("member_alice")
assert amount_alice == 650, f"Expected 650 for Alice, got {amount_alice}"

# Bob: no criminal_record, no voting_eligibility = 500
amount_bob = social_benefits.calculate_benefit_amount("member_bob")
assert amount_bob == 500, f"Expected 500 for Bob, got {amount_bob}"

# Non-existent member
amount_none = social_benefits.calculate_benefit_amount("nonexistent")
assert amount_none == 0, f"Expected 0 for non-existent member, got {amount_none}"

print("  calculate_benefit_amount: OK")

# ── Test distribute_social_benefits ────────────────────────────────────────

print("Testing distribute_social_benefits...")

# Set up required entities for distribution
system_user = User(id="system")
benefit_instrument = Instrument(name="Service Credit")

results = social_benefits.distribute_social_benefits()
assert isinstance(results, list), f"Expected list, got {type(results)}"

# Only Alice is eligible (Bob has pending identity verification)
assert len(results) == 1, f"Expected 1 distribution, got {len(results)}"
assert results[0]["member_id"] == "member_alice"
assert results[0]["benefit_amount"] == 650
assert results[0]["status"] == "distributed"

# Verify a transfer was created
assert Transfer.count() == 1, f"Expected 1 transfer, got {Transfer.count()}"
t = Transfer.instances()[0]
assert t.from_user is system_user
assert t.to_user is user_alice
assert t.instrument is benefit_instrument
assert t.amount == 650

print("  distribute_social_benefits: OK")

print("\n✅ All social_benefits tests passed!")
