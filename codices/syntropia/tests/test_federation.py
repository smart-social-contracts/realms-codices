# Test: Federation
# Covers: quarter assignment strategies (random, least_populated, user_choice)
import quarter_assignment
from ggg import Realm, RealmStatus, Quarter, QuarterStatus

ts = "q" + str(id(object()))[-6:]

realm = Realm(name="Federation Test " + ts, description="Test", status=RealmStatus.PRODUCTION)

quarter_mod = quarter_assignment

# ── TEST 1: Quarter Assignment ───────────────────────────────────────────
print("=== TEST 1: FEDERATION & QUARTERS ===")
q1 = Quarter(name=ts + "_Quarter_Alpha", canister_id="aaaaa-aa", federation=realm, population=50, status=QuarterStatus.ACTIVE)
q2 = Quarter(name=ts + "_Quarter_Beta", canister_id="bbbbb-bb", federation=realm, population=30, status=QuarterStatus.ACTIVE)
q3 = Quarter(name=ts + "_Quarter_Gamma", canister_id="ccccc-cc", federation=realm, population=80, status=QuarterStatus.ACTIVE)
print("Quarters created: " + q1.name + ", " + q2.name + ", " + q3.name)

quarters = [q1, q2, q3]

# Test random strategy
assigned_random = quarter_mod.assign_quarter("principal_test_123", quarters, "")
assert assigned_random in ["aaaaa-aa", "bbbbb-bb", "ccccc-cc"], "Should assign to a valid quarter"
print("Random assignment: " + assigned_random)

# Test least_populated strategy
orig_strategy = quarter_mod.ASSIGNMENT_STRATEGY
quarter_mod.ASSIGNMENT_STRATEGY = "least_populated"
assigned_lp = quarter_mod.assign_quarter("principal_test_456", quarters, "")
assert assigned_lp == "bbbbb-bb", "Should assign to least populated (Beta=30): got " + assigned_lp
print("Least populated assignment: " + assigned_lp + " (Quarter Beta, pop=30)")

# Test user_choice strategy
quarter_mod.ASSIGNMENT_STRATEGY = "user_choice"
assigned_uc = quarter_mod.assign_quarter("principal_test_789", quarters, "ccccc-cc")
assert assigned_uc == "ccccc-cc", "Should honour user choice"
print("User choice assignment: " + assigned_uc)

# Restore original strategy
quarter_mod.ASSIGNMENT_STRATEGY = orig_strategy
print("Quarter assignment strategies verified")

# Summary
print("=== FEDERATION TESTS PASSED ===")
print("Quarters: " + str(Quarter.count()) + " Realms: " + str(Realm.count()))
