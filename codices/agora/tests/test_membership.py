"""Tests for membership.py — Agora incumbent migration model.

Citizens are imported from an existing census and become active members
immediately (no ZK passport). Activation is idempotent. Members can be
suspended for non-payment and reactivated.
"""

from realms.testing import setup_test_env, reset_registry

setup_test_env()
reset_registry()

import membership
from ggg import User, Member


# ── activate_member: active on registration, idempotent ───────────────────────
print("Testing activate_member...")

User(id="alice", name="Alice")
res = membership.activate_member("alice")
assert res["accepted"] is True
member = Member.for_user("alice")
assert member is not None
assert member.identity_verification == "verified", "Incumbent members are active immediately"
assert member.voting_eligibility == "eligible"
assert membership.is_registered_member("alice") is True

# Idempotent — calling again does not create a second member
res2 = membership.activate_member("alice")
assert res2["accepted"] is True
assert res2.get("already_member") is True
assert sum(1 for m in Member.instances() if m.user and m.user.id == "alice") == 1

# Unknown user
assert membership.activate_member("ghost")["accepted"] is False

print("  activate_member: OK")


# ── check_membership_status ───────────────────────────────────────────────────
print("Testing check_membership_status...")

status = membership.check_membership_status("alice")
assert status["is_member"] is True
assert status["active"] is True

User(id="bob", name="Bob")
status_bob = membership.check_membership_status("bob")
assert status_bob["is_member"] is False
assert membership.is_registered_member("bob") is False

print("  check_membership_status: OK")


# ── deactivate / reactivate ───────────────────────────────────────────────────
print("Testing deactivate/reactivate...")

deact = membership.deactivate_member("alice", "Non-payment of dues")
assert deact["deactivated"] is True
member = Member.for_user("alice")
assert member.identity_verification == "suspended"
assert member.voting_eligibility == "ineligible"
assert membership.is_registered_member("alice") is False

# Cannot reactivate a non-suspended member
membership.activate_member("bob")
not_suspended = membership.reactivate_member("bob")
assert not_suspended["reactivated"] is False

react = membership.reactivate_member("alice")
assert react["reactivated"] is True
assert Member.for_user("alice").identity_verification == "verified"
assert membership.is_registered_member("alice") is True

print("  deactivate/reactivate: OK")


print("\n✅ All membership tests passed!")
