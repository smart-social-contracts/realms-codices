# Test: Federation
# Covers: quarter assignment strategies (random, least_populated, user_choice)
import quarter_assignment
from ggg import Realm, RealmStatus, Quarter, QuarterStatus

ts = "q" + str(id(object()))[-6:]

realm = Realm(name="Federation Test " + ts, manifesto="Test", status=RealmStatus.PRODUCTION)

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

# ── TEST 2: Auto-scaling hook (should_deploy_quarter) ────────────────────
print("=== TEST 2: AUTO-SCALING HOOK ===")

# test network => N=10, threshold = ceil(0.9 * 10) = 9
assert quarter_mod._effective_n("test") == 10, "test network N should be 10"
assert quarter_mod._effective_n("ic") == 2000, "prod network N should be 2000"

# Below threshold: all quarters under 9 => no scale
assert quarter_mod.should_deploy_quarter([5, 8, 3], "test") is False, "8/10 should not scale"
# One quarter full but another has headroom => no scale (min semantics:
# max() here re-minted forever — the fullest quarter stays above threshold
# after the fresh one opens, so every join re-triggered provisioning)
assert quarter_mod.should_deploy_quarter([2, 9], "test") is False, "headroom quarter should suppress scale"
# All joinable quarters at threshold => scale
assert quarter_mod.should_deploy_quarter([9, 9], "test") is True, "all full should scale"
# Production: 1799 < 1800 no scale, 1800 >= 1800 scale
assert quarter_mod.should_deploy_quarter([1799], "ic") is False, "1799/2000 should not scale"
assert quarter_mod.should_deploy_quarter([1800], "ic") is True, "1800/2000 should scale"
# Realm manifest override beats the network default
class _FakeRealm:
    manifest_data = '{"scaling": {"quarter_capacity": 2000}}'
assert quarter_mod.should_deploy_quarter([9], "test", realm=_FakeRealm()) is False, "override 2000: 9 joins must not scale"
assert quarter_mod.should_deploy_quarter([1800], "test", realm=_FakeRealm()) is True, "override 2000: 1800 should scale"
# Empty / disabled
assert quarter_mod.should_deploy_quarter([], "test") is False, "empty should not scale"
print("Auto-scaling hook thresholds verified (test N=10, prod N=2000, 90% rule, min semantics, manifest override)")

# Summary
print("=== FEDERATION TESTS PASSED ===")
print("Quarters: " + str(Quarter.count()) + " Realms: " + str(Realm.count()))
