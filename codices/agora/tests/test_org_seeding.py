"""Tests for the init/seed hooks' organization seeding — Agora incumbent
migration (issues #241/#244).

departments.json is seeded as real Department organizations: policy defaults,
Fund budget envelope, permissions, staff profiles, Position seats (headcount +
salary line), and one multi-use invite code per position. Seeding must be
idempotent so upgrades and reinstalls never duplicate entities or reset
creator edits.
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
    Position,
    Realm,
    RegistrationCode,
    UserProfile,
    department_personnel_cost,
)

_CODEX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(_CODEX_DIR, "backend", "data", "departments.json")) as f:
    DEPT_DATA = json.load(f)

SPEC_DEPTS = DEPT_DATA["departments"]
SPEC_POSITIONS = [
    (d["name"], p) for d in SPEC_DEPTS for p in d.get("positions", [])
]
SPEC_PROFILE_PAIRS = [(name, p["profile"]) for name, p in SPEC_POSITIONS]
SPEC_POSITION_KEYS = {f"{name}/{p['title']}" for name, p in SPEC_POSITIONS}

# A realm must exist before init runs.
realm = Realm(name="Agoria Test")

# The init hook (issue #244) writes manifest_data and seeds orgs.
import entry
import org_seeding

init_result = json.loads(entry.init("{}"))
assert init_result["success"], f"init hook failed: {init_result}"


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


# ── Position seats: headcount + salary line per (department, title) ──────────
print("Testing position seeding...")

assert Position.count() == len(SPEC_POSITIONS), (
    f"expected {len(SPEC_POSITIONS)} positions, got {Position.count()}"
)

for dept_name, pspec in SPEC_POSITIONS:
    key = f"{dept_name}/{pspec['title']}"
    pos = Position[key]
    assert pos is not None, f"position '{key}' not seeded"
    assert pos.title == pspec["title"]
    assert pos.headcount == pspec.get("headcount", 1)
    assert pos.salary_amount == pspec.get("salary_amount", 0)
    assert pos.status == "open"
    assert pos.department is Department[dept_name]
    assert pos.profile is UserProfile[pspec["profile"]]
    # Nobody appointed yet.
    assert pos.filled_count() == 0
    assert pos.vacancies() == pos.headcount

# Personnel budget line = sum(headcount x salary) over the org's open seats.
justice_spec = next(d for d in SPEC_DEPTS if d["name"] == "Justice")
expected_cost = sum(
    p.get("headcount", 1) * p.get("salary_amount", 0)
    for p in justice_spec["positions"]
)
assert department_personnel_cost("Justice") == expected_cost

print("  position seeding: OK")


# ── Invite codes: one multi-use code per position ────────────────────────────
print("Testing staff invite codes...")

codes = RegistrationCode.instances()
assert len(codes) == len(SPEC_POSITIONS)

pairs = {(c.department, c.profile) for c in codes}
assert pairs == set(SPEC_PROFILE_PAIRS)

# Each invite carries the position key so redemption appoints to the seat.
assert {c.position for c in codes} == SPEC_POSITION_KEYS

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
    Position.count(),
    RegistrationCode.count(),
)

org_seeding.seed_organizations(DEPT_DATA, realm)

after = (
    Department.count(),
    Fund.count(),
    Permission.count(),
    UserProfile.count(),
    Position.count(),
    RegistrationCode.count(),
)
assert before == after, f"seeding is not idempotent: {before} -> {after}"

print("  idempotency: OK")


# ── Legacy invite backfill: pre-position codes gain the position key ─────────
print("Testing legacy invite backfill...")

legacy = RegistrationCode.create(
    user_id="",
    created_by="codex:agora",
    frontend_url="",
    profile="judge",
    max_uses=100,
    department="Justice",
)
assert legacy.position == ""
# Remove the position-linked judge invite so the legacy one is "the" invite.
for c in RegistrationCode.find_by_department("Justice"):
    if c.profile == "judge" and c.position:
        c.delete()

org_seeding.seed_organizations(DEPT_DATA, realm)
assert legacy.position == "Justice/judge", (
    f"legacy invite not backfilled: {legacy.position!r}"
)

print("  legacy invite backfill: OK")

print("All org seeding tests passed.")
