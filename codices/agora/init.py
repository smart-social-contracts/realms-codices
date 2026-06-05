"""Agora codex initialization.

Agora is an *incumbent migration*: an existing public administration replacing
its IT with Realms GOS. Onboarding is by registration code / bulk import (no ZK
passport). This init loads the codex configuration and reference data
(departments, justice license, land zones) into ``Realm.manifest_data`` so the
backend and the (input-driven) public dashboard can read it.
"""

from _cdk import ic
from ggg import Realm, Treasury, UserProfile, User, Codex, Instrument, Transfer
import json
import os

_DIR = os.path.dirname(__file__)


def _load_json(filename):
    path = os.path.join(_DIR, filename)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        ic.print(f"⚠️  Could not load {filename}: {e}")
        return None


realm = list(Realm.instances())[0] if Realm.instances() else None
if realm:
    manifest = _load_json("manifest.json") or {}

    # Reference data files (JSON) shipped with the codex.
    departments = _load_json(manifest.get("data_files", {}).get("departments", "departments.json"))
    justice_license = _load_json(manifest.get("data_files", {}).get("justice_license", "justice_license.json"))
    zones_data = _load_json(manifest.get("data_files", {}).get("zones", "zones.json"))

    # Lifecycle metrics consumed by the public dashboard. For an incumbent
    # migration "critical_mass" is the population to be migrated.
    lifecycle = dict(manifest.get("lifecycle", {}))
    population_target = lifecycle.get("population_target", 0)
    lifecycle.setdefault("critical_mass", population_target)
    lifecycle.setdefault("registered_users", User.count())

    # Keep manifest_data lean (Realm.manifest_data is capped at 4096 chars):
    # store only what the backend and public dashboard read. Department *names*
    # are enough for the dashboard; full department/license records are
    # materialized as entities below.
    department_names = [d.get("name", "") for d in (departments or {}).get("departments", [])]

    realm_manifest = {
        "entity_method_overrides": manifest.get("entity_method_overrides", []),
        "onboarding": manifest.get("onboarding", {}),
        "lifecycle": lifecycle,
        "dashboard": manifest.get("dashboard", {}),
        "dependencies": manifest.get("dependencies", []),
        "departments": department_names,
    }

    realm.manifest_data = json.dumps(realm_manifest)

    if manifest.get("name"):
        realm.name = manifest["name"]
        ic.print(f"✅ Realm name set to: {manifest['name']}")
    if manifest.get("manifesto"):
        realm.manifesto = manifest["manifesto"]
    if manifest.get("logo"):
        realm.logo = manifest["logo"]
    if manifest.get("welcome_image"):
        realm.welcome_image = manifest["welcome_image"]
    if manifest.get("welcome_message"):
        realm.welcome_message = manifest["welcome_message"]

    ic.print("✅ Agora (incumbent) manifest_data written")

    # Materialize initial land zones (quarters are predefined with fixed zones).
    try:
        from ggg import Zone
        existing = {z.name for z in Zone.instances()}
        for i, z in enumerate((zones_data or {}).get("zones", [])):
            if z.get("name") in existing:
                continue
            Zone(
                h3_index=z.get("h3_index") or f"agora-zone-{i+1}",
                name=z.get("name", f"Zone {i+1}"),
                description=z.get("description", ""),
                latitude=float(z.get("latitude", 0.0) or 0.0),
                longitude=float(z.get("longitude", 0.0) or 0.0),
                resolution=7.0,
                metadata=json.dumps({"category": "administrative", "status": "active"}),
            )
        ic.print(f"🗺️  Zones ensured: {len((zones_data or {}).get('zones', []))}")
    except Exception as e:
        ic.print(f"⚠️  Zone initialization skipped: {e}")

    # Materialize the license for justice from justice_license.json.
    try:
        from ggg import License
        lic = (justice_license or {}).get("license", {})
        if lic.get("name") and not any(l.name == lic["name"] for l in License.instances()):
            License(
                name=lic.get("name", "Justice License"),
                license_type=lic.get("license_type", "justice_provider"),
                description=lic.get("terms", ""),
                status=lic.get("status", "active"),
                issuing_authority=lic.get("issuing_authority", ""),
                metadata=json.dumps({"scope": lic.get("scope", [])}),
            )
            ic.print(f"⚖️  Justice license created: {lic.get('name')}")
    except Exception as e:
        ic.print(f"⚠️  Justice license initialization skipped: {e}")
else:
    ic.print("❌ No Realm found")

# Initialize accounting entities (Fund, FiscalPeriod, Budget) for real-time metrics
try:
    import budget
    result = budget.ensure_accounting_entities()
    ic.print(f"📊 Accounting entities: {result.get('status', 'unknown')}")
except Exception as e:
    ic.print(f"⚠️  Accounting entity initialization: {e}")

# Print entity counts
ic.print("len(Realm.instances()) = %d" % len(Realm.instances()))
ic.print("len(Treasury.instances()) = %d" % len(Treasury.instances()))
ic.print("len(UserProfile.instances()) = %d" % len(UserProfile.instances()))
ic.print("len(User.instances()) = %d" % len(User.instances()))
ic.print("len(Codex.instances()) = %d" % len(Codex.instances()))
ic.print("len(Instrument.instances()) = %d" % len(Instrument.instances()))
ic.print("len(Transfer.instances()) = %d" % len(Transfer.instances()))

for codex in Codex.instances():
    ic.print(f"{codex.name}: {len(codex.code)}")
