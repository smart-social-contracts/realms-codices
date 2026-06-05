"""Syntropia codex initialization.

Syntropia is a *greenfield* sovereign smart city built from scratch. New
citizens are onboarded with a ZK passport, pay a deposit (a house in a zone),
and submit Know-Your-Citizen data before go-live. Until the realm reaches
production, member voting is not executable — only admins can make fundamental
changes.

This init loads the codex configuration and reference data (departments,
justice license, land zones) into ``Realm.manifest_data`` and sets the realm to
the alpha stage.
"""

from _cdk import ic
from ggg import Realm, Treasury, UserProfile
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

    departments = _load_json(manifest.get("data_files", {}).get("departments", "departments.json"))
    justice_license = _load_json(manifest.get("data_files", {}).get("justice_license", "justice_license.json"))
    zones_data = _load_json(manifest.get("data_files", {}).get("zones", "zones.json"))

    # Lifecycle: start at alpha and seed the metrics the public dashboard reads
    # (countdown, citizen counter, critical-mass threshold).
    lifecycle = dict(manifest.get("lifecycle", {}))
    # registered_users is provided live by get_realm_stage; no need to store it
    lifecycle.setdefault("total_deposits", 0)
    lifecycle.setdefault("deposits_locked", False)
    lifecycle.setdefault("land_acquired", False)
    lifecycle.setdefault("infrastructure_ready", False)
    lifecycle.setdefault("providers_ready", False)

    # Keep manifest_data lean (Realm.manifest_data is capped at 4096 chars).
    department_names = [d.get("name", "") for d in (departments or {}).get("departments", [])]

    realm_manifest = {
        "entity_method_overrides": manifest.get("entity_method_overrides", []),
        "onboarding": manifest.get("onboarding", {}),
        "lifecycle": lifecycle,
        "dashboard": manifest.get("dashboard", {}),
        "dependencies": manifest.get("dependencies", []),
        "governance": manifest.get("governance", {}),
        "departments": department_names,
    }

    realm.manifest_data = json.dumps(realm_manifest)

    # Greenfield realms begin in alpha (gathering founding citizens).
    if not getattr(realm, "status", None):
        realm.status = "alpha"

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

    ic.print("✅ Syntropia (greenfield) manifest_data written")

    # Materialize founding land zones.
    try:
        from ggg import Zone
        existing = {z.name for z in Zone.instances()}
        for i, z in enumerate((zones_data or {}).get("zones", [])):
            if z.get("name") in existing:
                continue
            Zone(
                h3_index=z.get("h3_index") or f"syntropia-zone-{i+1}",
                name=z.get("name", f"Zone {i+1}"),
                description=z.get("description", ""),
                latitude=float(z.get("latitude", 0.0) or 0.0),
                longitude=float(z.get("longitude", 0.0) or 0.0),
                resolution=7.0,
                metadata=json.dumps({"category": "founding", "status": "active"}),
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
