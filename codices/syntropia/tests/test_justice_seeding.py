"""Tests for the init hook's justice seeding — template court hierarchy.

``data/justice.json`` declares Syntropia's judiciary (Community Courts on
every quarter under one Constitutional Court on the capital) and
``data/justice_license.json`` the license authorizing it. Seeding must be
idempotent and quarter-aware.
"""

import json
import os

from realms.testing import setup_test_env, reset_registry

setup_test_env()
reset_registry()

from ggg import Court, JusticeSystem, License, Realm

_CODEX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(_CODEX_DIR, "backend", "data", "justice.json")) as f:
    JUSTICE_DATA = json.load(f)
with open(os.path.join(_CODEX_DIR, "backend", "data", "justice_license.json")) as f:
    LICENSE_DATA = json.load(f)

SPEC_COURTS = JUSTICE_DATA["courts"]
SPEC_BY_NAME = {c["name"]: c for c in SPEC_COURTS}
QUARTER_COURTS = [c for c in SPEC_COURTS if c.get("scope", "quarter") == "quarter"]
CAPITAL_COURTS = [c for c in SPEC_COURTS if c.get("scope") == "capital"]

# ── Standalone realm (capital-like): full hierarchy seeded via init ─────────
print("Testing justice seeding on a standalone realm...")

realm = Realm(name="Syntropia Test")

import entry

init_result = json.loads(entry.init("{}"))
assert init_result["success"], f"init hook failed: {init_result}"
assert init_result.get("justice_seeded") is True, f"justice not seeded: {init_result}"

assert Court.count() == len(SPEC_COURTS), (
    f"expected {len(SPEC_COURTS)} courts, got {Court.count()}"
)
for spec in SPEC_COURTS:
    court = Court[spec["name"]]
    assert court is not None, f"court '{spec['name']}' not seeded"
    assert court.level == spec["level"]
    assert court.status == "active"
    assert court.justice_system is not None
    parent_name = spec.get("parent")
    if parent_name:
        assert court.parent_court is not None, f"{spec['name']} has no parent court"
        assert court.parent_court.name == parent_name

js = JusticeSystem[JUSTICE_DATA["justice_system"]["name"]]
assert js is not None, "justice system not seeded"
assert js.status == "active"

license_name = LICENSE_DATA["license"]["name"]
lic = License[license_name]
assert lic is not None, "justice license not seeded"
assert lic.status == "active"
assert lic.justice_system is js, "license not attached to the justice system"

print("  standalone seeding: OK")

# ── Idempotency: re-running never duplicates or resets ───────────────────────
print("Testing idempotency...")

before_courts = Court.count()
before_systems = JusticeSystem.count()
before_licenses = License.count()

rerun = json.loads(entry.seed_justice("{}"))
assert rerun["success"], f"seed_justice re-run failed: {rerun}"
assert rerun["data"]["created"] == [], f"re-run created courts: {rerun['data']}"
assert sorted(rerun["data"]["existing"]) == sorted(SPEC_BY_NAME.keys())

assert Court.count() == before_courts
assert JusticeSystem.count() == before_systems
assert License.count() == before_licenses

print("  idempotency: OK")

# ── Quarter scoping: capital-scoped courts skipped, appeal routing recorded ──
print("Testing quarter scoping...")

reset_registry()
CAPITAL_CANISTER_ID = "capital-canister-id"
quarter_realm = Realm(
    name="Syntropia Quarter",
    is_quarter=True,
    is_capital=False,
    federation_realm_id=CAPITAL_CANISTER_ID,
)

quarter_result = json.loads(entry.seed_justice("{}"))
assert quarter_result["success"], f"quarter seed_justice failed: {quarter_result}"
data = quarter_result["data"]
assert sorted(data["created"]) == sorted(c["name"] for c in QUARTER_COURTS)
assert sorted(data["skipped"]) == sorted(c["name"] for c in CAPITAL_COURTS)

assert Court.count() == len(QUARTER_COURTS)
for spec in QUARTER_COURTS:
    court = Court[spec["name"]]
    assert court is not None
    parent_name = spec.get("parent")
    if parent_name and SPEC_BY_NAME[parent_name].get("scope") == "capital":
        # Parent lives on the capital: no local link, routing via metadata.
        assert court.parent_court is None
        meta = json.loads(court.metadata)
        assert meta["appellate_court"] == parent_name
        assert meta["appellate_quarter_id"] == CAPITAL_CANISTER_ID

print("  quarter scoping: OK")

print("\n✅ All justice seeding tests passed!")
