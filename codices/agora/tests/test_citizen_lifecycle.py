"""Tests for citizen_lifecycle.py — Agora incumbent migration model.

Agora migrates an existing population (census), so:
  1. Registration activates citizens immediately — no ZK passport step.
  2. During migration phases (alpha/beta) citizens pay nothing.
  3. Once live (production) a registration fee is charged and recorded as
     double-entry ledger entries.
  4. Governance, financial statements, and welfare distribution work for
     active members.
"""

import sys
import os
import json

from realms.testing import setup_test_env, reset_registry

setup_test_env()

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
    LedgerEntry, Fund, FiscalPeriod, Budget, Realm,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def fresh_env():
    """Reset registry and re-patch manifest loading for a clean state."""
    reset_registry()
    citizen_lifecycle._load_manifest = _patched_load_manifest


def make_realm(stage):
    """Create the single Realm at a given lifecycle stage."""
    return Realm(name="Agora", status=stage, accounting_currency="ckUSDC")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Incumbent registration — active immediately, no payment in alpha
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing incumbent registration...")
fresh_env()

result = citizen_lifecycle.register_citizen("alice")
assert result["user_id"] == "alice", f"Expected user_id 'alice', got {result['user_id']}"
assert result["member_id"] == "member_alice"
assert result["active"] is True, "Incumbent citizens are active on registration"
assert result["invoice_id"] is None, "No invoice during migration phases"

assert User["alice"] is not None, "User alice should exist"
member = Member.for_user("alice")
assert member is not None, "Member for alice should exist"
assert member.identity_verification == "verified", "Should be active (verified) immediately"
assert member.voting_eligibility == "eligible"
assert member.is_active()

# No invoice issued during migration phases
invoices = [i for i in Invoice.instances() if i.user and i.user.id == "alice"]
assert len(invoices) == 0, f"Expected 0 invoices in alpha, got {len(invoices)}"

# Duplicate registration should fail
dup = citizen_lifecycle.register_citizen("alice")
assert dup["error"] == "already_registered"

print("  incumbent registration: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: No payment during beta migration phase
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing no payment during beta...")
fresh_env()
make_realm("beta")

result = citizen_lifecycle.register_citizen("bob")
assert result["active"] is True
assert result["invoice_id"] is None, "Beta migration: members pay nothing"
assert len([i for i in Invoice.instances() if i.user and i.user.id == "bob"]) == 0

print("  no payment during beta: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Production billing + payment ledger
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing production billing + payment ledger...")
fresh_env()
make_realm("production")

result = citizen_lifecycle.register_citizen("charlie")
assert result["active"] is True
assert result["invoice_id"] is not None, "Production: a registration invoice is issued"
assert result["fee"] == 1.0, f"Expected fee 1.0, got {result.get('fee')}"
assert result["currency"] == "ckUSDC"

inv_id = result["invoice_id"]
pay = citizen_lifecycle.pay_registration_invoice("charlie", inv_id)
assert pay["paid"] is True

invoice = Invoice.load(inv_id)
assert invoice.status == "Paid"
assert invoice.paid_at is not None

# Double-entry ledger: debit Cash, credit Revenue
entries = LedgerEntry.instances()
assert len(entries) == 2, f"Expected 2 ledger entries, got {len(entries)}"
debits = [e for e in entries if (e.debit or 0) > 0]
credits = [e for e in entries if (e.credit or 0) > 0]
assert len(debits) == 1 and len(credits) == 1
assert debits[0].debit == credits[0].credit, "Double-entry must balance"

# Already paid
dup_pay = citizen_lifecycle.pay_registration_invoice("charlie", inv_id)
assert dup_pay["error"] == "already_paid"

print("  production billing + payment ledger: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: Governance — proposal submission
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing proposal submission...")
fresh_env()

# Register 3 citizens — all active on registration (incumbent)
for name in ["alice", "bob", "carol"]:
    citizen_lifecycle.register_citizen(name)
assert Member.count_active() == 3

result = citizen_lifecycle.submit_proposal(
    "alice", "Increase welfare", "Raise welfare to 40%", "welfare_policy"
)
assert result["proposal_id"] == "prop_1"
assert result["status"] == "voting"
assert "voting_deadline" in result

prop = Proposal["prop_1"]
assert prop is not None
assert prop.title == "Increase welfare"
assert prop.proposer.id == "alice"
assert prop.required_threshold == 0.5

# A deactivated (suspended) member cannot submit
citizen_lifecycle.register_citizen("eve")
Member.for_user("eve").deactivate()
inactive_result = citizen_lifecycle.submit_proposal("eve", "Bad", "Nope", "codex_change")
assert inactive_result["error"] == "not_active_member"

# Invalid proposal type
bad_type = citizen_lifecycle.submit_proposal("alice", "X", "Y", "invalid_type")
assert bad_type["error"] == "invalid_proposal_type"

print("  proposal submission: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: Governance — voting
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing voting...")

r1 = citizen_lifecycle.cast_vote("alice", "prop_1", "yes")
assert r1["voted"] is True and r1["choice"] == "yes"
r2 = citizen_lifecycle.cast_vote("bob", "prop_1", "yes")
assert r2["voted"] is True
r3 = citizen_lifecycle.cast_vote("carol", "prop_1", "no")
assert r3["voted"] is True

dup_vote = citizen_lifecycle.cast_vote("alice", "prop_1", "no")
assert dup_vote["error"] == "already_voted"

eve_vote = citizen_lifecycle.cast_vote("eve", "prop_1", "yes")
assert eve_vote["error"] == "not_active_member"

bad_choice = citizen_lifecycle.cast_vote("bob", "prop_1", "maybe")
assert bad_choice["error"] == "invalid_vote_choice"

votes_for_prop1 = [v for v in Vote.instances() if v.proposal is Proposal["prop_1"]]
assert len(votes_for_prop1) == 3, f"Expected 3 votes, got {len(votes_for_prop1)}"

print("  voting: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 6: Governance — tallying
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing proposal tallying...")

result = citizen_lifecycle.tally_proposal("prop_1")
assert result["status"] == "approved", f"Expected approved, got {result['status']}"
assert result["votes_yes"] == 2.0
assert result["votes_no"] == 1.0
assert result["quorum_met"] is True

citizen_lifecycle.submit_proposal("bob", "Empty proposal", "Nobody votes", "codex_change")
no_vote_result = citizen_lifecycle.tally_proposal("prop_2")
assert no_vote_result["status"] == "no_quorum"

citizen_lifecycle.submit_proposal("carol", "Bad idea", "Should fail", "treasury_spend")
citizen_lifecycle.cast_vote("alice", "prop_3", "no")
citizen_lifecycle.cast_vote("bob", "prop_3", "no")
citizen_lifecycle.cast_vote("carol", "prop_3", "yes")
rejected = citizen_lifecycle.tally_proposal("prop_3")
assert rejected["status"] == "rejected", f"Expected rejected, got {rejected['status']}"

closed_vote = citizen_lifecycle.cast_vote("alice", "prop_1", "yes")
assert closed_vote["error"] == "voting_closed"

print("  proposal tallying: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 7: Financial statements (production revenue)
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing financial statements...")
fresh_env()
make_realm("production")

# Register + pay 3 citizens → 3 paid registration invoices (1.0 each → 1_000_000 raw)
for name in ["alice", "bob", "carol"]:
    res = citizen_lifecycle.register_citizen(name)
    citizen_lifecycle.pay_registration_invoice(name, res["invoice_id"])

summary = citizen_lifecycle.get_financial_summary()
income_stmt = summary["income_statement"]
balance_sheet = summary["balance_sheet"]

assert income_stmt["revenues"]["total"] == 3_000_000, \
    f"Expected 3M revenue, got {income_stmt['revenues']['total']}"
assert income_stmt["revenues"]["items"].get("fee") == 3_000_000
assert balance_sheet["assets"]["items"].get("cash") == 3_000_000, \
    f"Expected 3M cash, got {balance_sheet['assets']}"

print("  financial statements: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 8: Periodic payments (welfare distribution)
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing periodic payments...")

# 30% of 3_000_000 = 900_000 pool, 3 members → 300_000 each
result = citizen_lifecycle.distribute_periodic_payments()
assert result["distributed"] is True
assert result["total_pool"] == 900_000, f"Expected 900K pool, got {result['total_pool']}"
assert result["per_member"] == 300_000
assert result["count"] == 3

transfers = [t for t in Transfer.instances() if t.tags == "welfare"]
assert len(transfers) == 3, f"Expected 3 welfare transfers, got {len(transfers)}"

welfare_entries = [e for e in LedgerEntry.instances() if "Welfare" in (e.description or "")]
assert len(welfare_entries) == 6, f"Expected 6 welfare entries, got {len(welfare_entries)}"

summary2 = citizen_lifecycle.get_financial_summary()
income2 = summary2["income_statement"]
assert income2["expenses"]["total"] == 900_000
assert income2["net_income"] == 3_000_000 - 900_000
bs2 = summary2["balance_sheet"]
assert bs2["assets"]["items"].get("cash") == 2_100_000, \
    f"Expected 2.1M cash after welfare, got {bs2['assets']['items'].get('cash')}"

print("  periodic payments: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 9: Citizen status query
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing citizen status...")

status = citizen_lifecycle.get_citizen_status("alice")
assert status["user_id"] == "alice"
assert status["is_member"] is True
assert status["is_active"] is True
assert status["invoices"] == 1
assert status["invoices_paid"] == 1

missing = citizen_lifecycle.get_citizen_status("nobody")
assert missing["error"] == "user_not_found"

print("  citizen status: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 10: Edge cases
# ═══════════════════════════════════════════════════════════════════════════════

print("Testing edge cases...")

bad_pay = citizen_lifecycle.pay_registration_invoice("nobody", "999")
assert bad_pay["error"] == "user_not_found"

bad_inv = citizen_lifecycle.pay_registration_invoice("alice", "999")
assert bad_inv["error"] == "invoice_not_found"

bad_prop = citizen_lifecycle.cast_vote("alice", "prop_999", "yes")
assert bad_prop["error"] == "proposal_not_found"

bad_tally = citizen_lifecycle.tally_proposal("prop_999")
assert bad_tally["error"] == "proposal_not_found"

fresh_env()
no_welfare = citizen_lifecycle.distribute_periodic_payments()
assert no_welfare["distributed"] is False

print("  edge cases: OK")


print("\n✅ All citizen_lifecycle tests passed!")
