# Test: Identity & Membership
# Covers: user registration, ZK passport verification, membership finalization,
#         membership status check, sybil resistance, membership revocation
import json
import membership_codex
from ggg import User, Member, Notification

ts = "t" + str(id(object()))[-6:]

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
zk_result_alice = json.dumps({
    "data": {"attributes": {"status": "verified", "identity_hash": "zk_" + ts + "_alice"}}
})
zk_result_bob = json.dumps({
    "data": {"attributes": {"status": "verified", "identity_hash": "zk_" + ts + "_bob"}}
})
zk_result_carol = json.dumps({
    "data": {"attributes": {"status": "verified", "identity_hash": "zk_" + ts + "_carol"}}
})
print("ZK proofs simulated for 3 users")

# ── TEST 3: Membership Finalization ──────────────────────────────────────
print("=== TEST 3: MEMBERSHIP FINALIZATION ===")
res_alice = membership_codex.finalize_membership(user_alice.id, zk_result_alice)
assert res_alice["accepted"], "Alice should be accepted: " + str(res_alice)
print("Alice accepted, member_id=" + str(res_alice["member_id"]))

res_bob = membership_codex.finalize_membership(user_bob.id, zk_result_bob)
assert res_bob["accepted"], "Bob should be accepted"
print("Bob accepted, member_id=" + str(res_bob["member_id"]))

res_carol = membership_codex.finalize_membership(user_carol.id, zk_result_carol)
assert res_carol["accepted"], "Carol should be accepted"
print("Carol accepted, member_id=" + str(res_carol["member_id"]))

# ── TEST 4: Membership Status ────────────────────────────────────────────
print("=== TEST 4: MEMBERSHIP STATUS ===")
status_alice = membership_codex.check_membership_status(user_alice.id)
assert status_alice["is_member"], "Alice should be a member"
print("Alice membership verified: " + str(status_alice["identity_verification"]))

# ── TEST 5: Sybil Resistance ────────────────────────────────────────────
print("=== TEST 5: SYBIL RESISTANCE ===")
dup_result = membership_codex.finalize_membership(
    user_alice.id,
    json.dumps({"data": {"attributes": {"status": "verified", "identity_hash": "zk_" + ts + "_alice"}}}),
)
assert not dup_result["accepted"], "Duplicate ZK hash should be rejected"
print("Sybil resistance: " + str(dup_result["reason"]))

# ── TEST 6: Membership Revocation ────────────────────────────────────────
print("=== TEST 6: MEMBERSHIP REVOCATION ===")
rev_result = membership_codex.revoke_membership(user_carol.id, reason="Test revocation for non-payment")
assert rev_result["revoked"], "Carol should be revoked"
print("Carol revoked: " + str(rev_result))

status_carol = membership_codex.check_membership_status(user_carol.id)
assert status_carol["identity_verification"] == "revoked", "Carol should be revoked"
print("Carol status after revocation: " + status_carol["identity_verification"])

# Summary
print("=== IDENTITY TESTS PASSED ===")
print("Users: " + str(User.count()) + " Members: " + str(Member.count()) + " Notifications: " + str(Notification.count()))
