# Test: Billing
# Covers: monthly invoice creation, overdue warning, membership revocation
#         for non-payment
import json
import monthly_billing_codex
from ggg import User, Member, Invoice, Notification

ts = "b" + str(id(object()))[-6:]

# Setup: users with membership
user_alice = User(id=ts + "_alice", name="Alice")
user_bob = User(id=ts + "_bob", name="Bob")
user_carol = User(id=ts + "_carol", name="Carol")
member_alice = Member(
    user=user_alice, identity_verification="verified",
    residence_permit="valid", tax_compliance="compliant",
    public_benefits_eligibility="eligible", voting_eligibility="eligible",
    criminal_record="clean|zk:" + ts + "_alice",
)
member_bob = Member(
    user=user_bob, identity_verification="verified",
    residence_permit="valid", tax_compliance="compliant",
    public_benefits_eligibility="eligible", voting_eligibility="eligible",
    criminal_record="clean|zk:" + ts + "_bob",
)
member_carol = Member(
    user=user_carol, identity_verification="verified",
    residence_permit="valid", tax_compliance="compliant",
    public_benefits_eligibility="eligible", voting_eligibility="eligible",
    criminal_record="clean|zk:" + ts + "_carol",
)

billing_codex = monthly_billing_codex

# ── TEST 1: Monthly Invoice ─────────────────────────────────────────────
print("=== TEST 1: MONTHLY INVOICE ===")
inv_result = billing_codex.create_monthly_invoice(user_alice.id)
assert "error" not in inv_result, "Invoice creation should succeed: " + str(inv_result)
print("Invoice created: id=" + str(inv_result.get("invoice_id")) + " amount=" + str(inv_result.get("amount_ckbtc")))

inv_result_bob = billing_codex.create_monthly_invoice(user_bob.id)
assert "error" not in inv_result_bob
print("Invoice for Bob: id=" + str(inv_result_bob.get("invoice_id")))

# ── TEST 2: Overdue Invoice Warning ──────────────────────────────────────
print("=== TEST 2: OVERDUE WARNING ===")
warn_result = billing_codex.warn_user(user_bob.id, str(inv_result_bob.get("invoice_id", "")))
assert warn_result.get("warned"), "Warning should succeed"
print("Warning sent to Bob: " + str(warn_result))

# ── TEST 3: Membership Revocation for Non-Payment ───────────────────────
print("=== TEST 3: BILLING REVOCATION ===")
kick_result = billing_codex.kick_user(user_carol.id, "test_invoice")
print("Kick result for Carol: " + str(kick_result))

# Verify Carol's membership was revoked
carol_member = None
for m in Member.instances():
    if m.user and m.user.id == user_carol.id:
        carol_member = m
        break
if carol_member:
    assert carol_member.identity_verification == "revoked", "Carol should be revoked after kick"
    print("Carol membership revoked via billing: " + carol_member.identity_verification)

# Summary
print("=== BILLING TESTS PASSED ===")
print("Invoices: " + str(Invoice.count()) + " Notifications: " + str(Notification.count()))
