"""Tests for init.py organization seeding — Agora incumbent migration (issue #241).

departments.json is seeded as real Department organizations: policy defaults,
Fund budget envelope, permissions, staff profiles, and one multi-use invite
code per (department, profile). Seeding must be idempotent so upgrades and
reinstalls never duplicate entities or reset creator edits.
"""

import json
import os

from realms.testing import setup_test_env, reset_registry

setup_test_env()
reset_registry()

from ggg import (
    Department,
    Fund,
    Permission,
    Realm,
    RegistrationCode,
    UserProfile,
)

_CODEX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(_CODEX_DIR, "departments.json")) as f:
    DEPT_DATA = json.load(f)

SPEC_DEPTS = DEPT_DATA["departments"]
SPEC_PROFILE_PAIRS = [
    (d["name"], p) for d in SPEC_DEPTS for p in d.get("profiles", [])
]

# A realm must exist before init runs.
realm = Realm(name="Agoria Test")

# Running init.py (module import executes it) writes manifest_data and seeds orgs.
import init  # noqa: F401  (import side effect is the point)


# ── manifest_data still written as before ────────────────────────────────────
print("Testing manifest_data...")

manifest_data = json.loads(realm.manifest_data)
assert manifest_data["departments"] == [d["name"] for d in SPEC_DEPTS]
assert "lifecycle" in manifest_data

print("  manifest_data: OK")


# ── Departments seeded with policy defaults ──────────────────────────────────
print("Testing department seeding...")

assert Department.count() == len(SPEC_DEPTS), (
    f"expected {len(SPEC_DEPTS)} departments, got {Department.count()}"
)

for spec in SPEC_DEPTS:
    dept = Department[spec["name"]]
    assert dept is not None, f"department '{spec['name']}' not seeded"
    policy = spec.get("policy", {})
    assert dept.policy_threshold_m == policy.get("threshold_m", 1)
    assert dept.policy_threshold_n == policy.get("threshold_n", 1)
    assert dept.is_root is False

treasury = Department["Treasury & Tax Office"]
assert treasury.policy_threshold_m == 2 and treasury.policy_threshold_n == 3

print("  department seeding: OK")


# ── Funds linked as budget envelopes ─────────────────────────────────────────
print("Testing fund envelopes...")

for spec in SPEC_DEPTS:
    dept = Department[spec["name"]]
    assert dept.fund is not None, f"'{spec['name']}' has no fund"
    assert dept.fund.code == spec["fund_code"][:16]
    assert Fund[spec["fund_code"][:16]] is dept.fund

print("  fund envelopes: OK")


# ── Permissions granted to the org ───────────────────────────────────────────
print("Testing department permissions...")

for spec in SPEC_DEPTS:
    dept = Department[spec["name"]]
    have = {p.name for p in dept.permissions}
    assert have == set(spec["permissions"]), (
        f"'{spec['name']}' permissions {have} != {set(spec['permissions'])}"
    )

# Shared permission names must reuse one Permission entity, not duplicate.
all_perm_names = [p for d in SPEC_DEPTS for p in d["permissions"]]
assert Permission.count() == len(set(all_perm_names))

print("  department permissions: OK")


# ── Staff profiles created with baseline ops ─────────────────────────────────
print("Testing staff profiles...")

for _, pname in SPEC_PROFILE_PAIRS:
    prof = UserProfile[pname]
    assert prof is not None, f"profile '{pname}' not seeded"
    assert "extension.sync_call" in prof.allowed_to

print("  staff profiles: OK")


# ── Invite codes: one multi-use code per (department, profile) ───────────────
print("Testing staff invite codes...")

codes = RegistrationCode.instances()
assert len(codes) == len(SPEC_PROFILE_PAIRS)

pairs = {(c.department, c.profile) for c in codes}
assert pairs == set(SPEC_PROFILE_PAIRS)

invite_cfg = DEPT_DATA["invite"]
for c in codes:
    assert c.code, "staff invites need a plaintext code to build the URL"
    assert c.max_uses == invite_cfg["max_uses"]
    assert c.created_by == "codex:agora"

civreg_codes = RegistrationCode.find_by_department("Civil Registry")
assert {c.profile for c in civreg_codes} == {"registrar", "clerk"}

print("  staff invite codes: OK")


# ── Idempotency: re-running seeding changes nothing ──────────────────────────
print("Testing idempotency...")

before = (
    Department.count(),
    Fund.count(),
    Permission.count(),
    UserProfile.count(),
    RegistrationCode.count(),
)

init.seed_organizations(DEPT_DATA, realm)

after = (
    Department.count(),
    Fund.count(),
    Permission.count(),
    UserProfile.count(),
    RegistrationCode.count(),
)
assert before == after, f"seeding is not idempotent: {before} -> {after}"

print("  idempotency: OK")

print("All org seeding tests passed.")
