"""Comprehensive tests for citizen_lifecycle.py codex.

Tests the full citizen journey:
  1. Registration — create user, member, invoice
  2. Passport verification — sybil detection, activation conditions
  3. Invoice payment — ledger entries, auto-activation
  4. Governance — proposal submission, voting, tallying
  5. Financial statements — auto-updated from ledger entries
  6. Periodic payments — welfare distribution to eligible members
  7. Edge cases — duplicates, invalid states, unauthorized actions
"""

import sys
import os
import json

from realms.testing import setup_test_env, reset_registry

# ── Setup ────────────────────────────────────────────────────────────────────

setup_test_env()

# Patch manifest loading to use the real manifest from parent dir
import citizen_lifecycle

_manifest_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "manifest.json"
)
def _patched_load_manifest():
    with open(_manifest_path) as f:
        return json.load(f)

citizen_lifecycle._load_manifest = _patched_load_manifest

from ggg import (
    User, Member, Invoice, Proposal, Vote, Transfer,
    LedgerEntry, Fund, FiscalPeriod, Budget,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def fresh_env():
    """Reset registry and re-import citizen_lifecycle for a clean state."""
    reset_registry()
    # Re-patch after reset since module may be cached
    citizen_lifecycle._load_manifest = _patched_load_manifest


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Registration
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing registration...")
fresh_env()

# Register Alice
result = citizen_lifecycle.register_citizen("alice")
assert result["user_id"] == "alice", f"Expected user_id 'alice', got {result['user_id']}"
assert result["member_id"] == "member_alice"
assert result["fee"] == 10.00, f"Expected fee 10.00, got {result['fee']}"
assert result["currency"] == "ckUSDC"
assert "due_date" in result

# Verify entities were created
assert User["alice"] is not None, "User alice should exist"
assert Member.for_user("alice") is not None, "Member for alice should exist"
member = Member.for_user("alice")
assert member.identity_verification == "pending", "Should be pending before activation"
assert member.voting_eligibility == "ineligible"

# Verify invoice was created
invoices = [i for i in Invoice.instances() if i.user and i.user.id == "alice"]
assert len(invoices) == 1, f"Expected 1 invoice, got {len(invoices)}"
assert invoices[0].status == "Pending"
assert invoices[0].amount == 10.00

# Duplicate registration should fail
dup = citizen_lifecycle.register_citizen("alice")
assert dup["error"] == "already_registered"

print("  registration: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Passport Verification
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing passport verification...")

# Verify passport (invoice not yet paid → should NOT activate)
result = citizen_lifecycle.verify_passport("alice", "hash_alice_passport")
assert result["verified"] is True
assert result["activated"] is False, "Should not activate without paid invoice"

member = Member.for_user("alice")
assert member.residence_permit == "hash_alice_passport"
assert member.identity_verification == "pending", "Still pending — invoice not paid"

# Sybil detection: register Bob, try same passport hash
citizen_lifecycle.register_citizen("bob")
sybil = citizen_lifecycle.verify_passport("bob", "hash_alice_passport")
assert sybil["error"] == "sybil_detected", f"Expected sybil_detected, got {sybil}"

# Verify passport for non-existent user
missing = citizen_lifecycle.verify_passport("nobody", "hash_xxx")
assert missing["error"] == "user_not_found"

# Already active member
member_alice = Member.for_user("alice")
member_alice.activate()  # force activate for this test
already = citizen_lifecycle.verify_passport("alice", "hash_alice_passport")
assert already["error"] == "already_active"
member_alice.identity_verification = "pending"  # reset for next tests

print("  passport verification: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Invoice Payment + Auto-activation
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing invoice payment...")
fresh_env()

# Register + verify passport first
citizen_lifecycle.register_citizen("charlie")
citizen_lifecycle.verify_passport("charlie", "hash_charlie")

# Get invoice ID
invoices = [i for i in Invoice.instances() if i.user and i.user.id == "charlie"]
inv_id = invoices[0]._id

# Pay the invoice → should auto-activate (both conditions met)
result = citizen_lifecycle.pay_registration_invoice("charlie", inv_id)
assert result["paid"] is True
assert result["activated"] is True, "Should activate: passport verified + invoice paid"

# Check member is now active
member = Member.for_user("charlie")
assert member.is_active(), "Member should be active after payment + passport"
assert member.voting_eligibility == "eligible"
assert member.public_benefits_eligibility == "eligible"

# Check invoice marked paid
invoice = Invoice.load(inv_id)
assert invoice.status == "Paid"
assert invoice.paid_at is not None

# Check ledger entries created (2 entries: debit Cash, credit Revenue)
entries = LedgerEntry.instances()
assert len(entries) == 2, f"Expected 2 ledger entries, got {len(entries)}"
debits = [e for e in entries if (e.debit or 0) > 0]
credits = [e for e in entries if (e.credit or 0) > 0]
assert len(debits) == 1 and len(credits) == 1
assert debits[0].debit == credits[0].credit, "Double-entry must balance"

# Payment without passport → should NOT activate
citizen_lifecycle.register_citizen("dave")
inv_dave = [i for i in Invoice.instances() if i.user and i.user.id == "dave"]
result_dave = citizen_lifecycle.pay_registration_invoice("dave", inv_dave[0]._id)
assert result_dave["paid"] is True
assert result_dave["activated"] is False, "Dave has no passport → should not activate"

# Already paid
dup_pay = citizen_lifecycle.pay_registration_invoice("charlie", inv_id)
assert dup_pay["error"] == "already_paid"

print("  invoice payment: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: Governance — Proposal Submission
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing proposal submission...")
fresh_env()

# Set up 3 active members
for name in ["alice", "bob", "carol"]:
    citizen_lifecycle.register_citizen(name)
    citizen_lifecycle.verify_passport(name, f"hash_{name}")
    inv = [i for i in Invoice.instances() if i.user and i.user.id == name][0]
    citizen_lifecycle.pay_registration_invoice(name, inv._id)

# Verify all 3 are active
assert Member.count_active() == 3

# Active member submits proposal
result = citizen_lifecycle.submit_proposal(
    "alice", "Increase welfare", "Raise welfare to 40%", "welfare_policy"
)
assert result["proposal_id"] == "prop_1"
assert result["status"] == "voting"
assert "voting_deadline" in result

# Verify proposal entity
prop = Proposal["prop_1"]
assert prop is not None
assert prop.title == "Increase welfare"
assert prop.proposer.id == "alice"
assert prop.required_threshold == 0.5

# Inactive member cannot submit
citizen_lifecycle.register_citizen("eve")  # registered but not active
inactive_result = citizen_lifecycle.submit_proposal("eve", "Bad", "Nope", "codex_change")
assert inactive_result["error"] == "not_active_member"

# Invalid proposal type
bad_type = citizen_lifecycle.submit_proposal("alice", "X", "Y", "invalid_type")
assert bad_type["error"] == "invalid_proposal_type"

print("  proposal submission: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: Governance — Voting
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing voting...")

# Alice, Bob, Carol vote on prop_1
r1 = citizen_lifecycle.cast_vote("alice", "prop_1", "yes")
assert r1["voted"] is True
assert r1["choice"] == "yes"

r2 = citizen_lifecycle.cast_vote("bob", "prop_1", "yes")
assert r2["voted"] is True

r3 = citizen_lifecycle.cast_vote("carol", "prop_1", "no")
assert r3["voted"] is True

# Duplicate vote should fail
dup_vote = citizen_lifecycle.cast_vote("alice", "prop_1", "no")
assert dup_vote["error"] == "already_voted"

# Inactive member cannot vote
eve_vote = citizen_lifecycle.cast_vote("eve", "prop_1", "yes")
assert eve_vote["error"] == "not_active_member"

# Invalid vote choice
bad_choice = citizen_lifecycle.cast_vote("bob", "prop_1", "maybe")
assert bad_choice["error"] == "invalid_vote_choice"

# Verify vote entities (check Vote instances linked to this proposal)
votes_for_prop1 = [v for v in Vote.instances() if v.proposal is Proposal["prop_1"]]
assert len(votes_for_prop1) == 3, f"Expected 3 votes, got {len(votes_for_prop1)}"

print("  voting: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 6: Governance — Tallying
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing proposal tallying...")

# Tally prop_1 (2 yes, 1 no, 3 active members → quorum 100% >= 20%, 2/3 > 50%)
result = citizen_lifecycle.tally_proposal("prop_1")
assert result["status"] == "approved", f"Expected approved, got {result['status']}"
assert result["votes_yes"] == 2.0
assert result["votes_no"] == 1.0
assert result["total_voters"] == 3.0
assert result["quorum_met"] is True

# Submit and tally a proposal with no votes → no_quorum
citizen_lifecycle.submit_proposal("bob", "Empty proposal", "Nobody votes", "codex_change")
no_vote_result = citizen_lifecycle.tally_proposal("prop_2")
assert no_vote_result["status"] == "no_quorum"

# Submit a proposal that gets rejected (majority no)
citizen_lifecycle.submit_proposal("carol", "Bad idea", "Should fail", "treasury_spend")
citizen_lifecycle.cast_vote("alice", "prop_3", "no")
citizen_lifecycle.cast_vote("bob", "prop_3", "no")
citizen_lifecycle.cast_vote("carol", "prop_3", "yes")
rejected = citizen_lifecycle.tally_proposal("prop_3")
assert rejected["status"] == "rejected", f"Expected rejected, got {rejected['status']}"

# Cannot vote on closed proposal
closed_vote = citizen_lifecycle.cast_vote("alice", "prop_1", "yes")
assert closed_vote["error"] == "voting_closed"

print("  proposal tallying: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 7: Financial Statements
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing financial statements...")

# We have 3 paid registration invoices (10.00 each → 10_000_000 raw units each)
summary = citizen_lifecycle.get_financial_summary()

balance_sheet = summary["balance_sheet"]
income_stmt = summary["income_statement"]

# Revenue should be 3 * 10_000_000 = 30_000_000
assert income_stmt["revenues"]["total"] == 30_000_000, \
    f"Expected 30M revenue, got {income_stmt['revenues']['total']}"
assert income_stmt["revenues"]["items"].get("fee") == 30_000_000

# Assets (cash) should be 30_000_000
assert balance_sheet["assets"]["items"].get("cash") == 30_000_000, \
    f"Expected 30M cash, got {balance_sheet['assets']}"

print("  financial statements: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 8: Periodic Payments (Welfare Distribution)
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing periodic payments...")

# Distribute welfare: 30% of 30_000_000 revenue = 9_000_000 pool, 3 members → 3_000_000 each
result = citizen_lifecycle.distribute_periodic_payments()
assert result["distributed"] is True
assert result["total_pool"] == 9_000_000, f"Expected 9M pool, got {result['total_pool']}"
assert result["per_member"] == 3_000_000
assert result["count"] == 3

# Verify transfers created
transfers = [t for t in Transfer.instances() if t.tags == "welfare"]
assert len(transfers) == 3, f"Expected 3 welfare transfers, got {len(transfers)}"

# Verify ledger entries (3 members × 2 entries each = 6 new entries)
# Plus 6 existing from registrations = 12 total
all_entries = LedgerEntry.instances()
welfare_entries = [e for e in all_entries if "Welfare" in (e.description or "")]
assert len(welfare_entries) == 6, f"Expected 6 welfare entries, got {len(welfare_entries)}"

# Income statement should now show expenses
summary2 = citizen_lifecycle.get_financial_summary()
income2 = summary2["income_statement"]
assert income2["expenses"]["total"] == 9_000_000, \
    f"Expected 9M expenses, got {income2['expenses']['total']}"
assert income2["net_income"] == 30_000_000 - 9_000_000, \
    f"Expected 21M net income, got {income2['net_income']}"

# Updated balance sheet: cash should be 30M - 9M = 21M
bs2 = summary2["balance_sheet"]
assert bs2["assets"]["items"].get("cash") == 21_000_000, \
    f"Expected 21M cash after welfare, got {bs2['assets']['items'].get('cash')}"

print("  periodic payments: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 9: Citizen Status Query
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing citizen status...")

status = citizen_lifecycle.get_citizen_status("alice")
assert status["user_id"] == "alice"
assert status["is_member"] is True
assert status["is_active"] is True
assert status["invoices"] == 1
assert status["invoices_paid"] == 1
assert status["proposals_submitted"] == 1  # alice submitted prop_1

# Non-existent user
missing = citizen_lifecycle.get_citizen_status("nobody")
assert missing["error"] == "user_not_found"

print("  citizen status: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 10: Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing edge cases...")

# Payment for non-existent user
bad_pay = citizen_lifecycle.pay_registration_invoice("nobody", "999")
assert bad_pay["error"] == "user_not_found"

# Payment for non-existent invoice
bad_inv = citizen_lifecycle.pay_registration_invoice("alice", "999")
assert bad_inv["error"] == "invoice_not_found"

# Vote on non-existent proposal
bad_prop = citizen_lifecycle.cast_vote("alice", "prop_999", "yes")
assert bad_prop["error"] == "proposal_not_found"

# Tally non-existent proposal
bad_tally = citizen_lifecycle.tally_proposal("prop_999")
assert bad_tally["error"] == "proposal_not_found"

# Welfare with no eligible members
fresh_env()
no_welfare = citizen_lifecycle.distribute_periodic_payments()
assert no_welfare["distributed"] is False

print("  edge cases: OK")


print("\n✅ All citizen_lifecycle tests passed!")
