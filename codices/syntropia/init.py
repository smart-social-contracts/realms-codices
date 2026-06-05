"""Syntropia codex initialization.

Syntropia is a *greenfield* sovereign smart city built from scratch. New
citizens are onboarded with a ZK passport, pay a deposit (a house in a zone),
and submit Know-Your-Citizen data before go-live. Until the realm reaches
production, member voting is not executable — only admins can make fundamental
changes.

This init writes the codex configuration into ``Realm.manifest_data`` so the
backend and the (input-driven) public dashboard can read it.

Entity creation (Zone, License) is intentionally deferred to avoid hitting
the IC 40B-instruction per-message limit on canisters with existing state.
"""

from _cdk import ic
from ggg import Realm
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

    # Lifecycle: seed the metrics the public dashboard reads
    # (countdown, citizen counter, critical-mass threshold).
    lifecycle = dict(manifest.get("lifecycle", {}))
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
    if manifest.get("manifesto"):
        realm.manifesto = manifest["manifesto"]
    if manifest.get("welcome_message"):
        realm.welcome_message = manifest["welcome_message"]

    ic.print("✅ Syntropia (greenfield) manifest_data written")
else:
    ic.print("❌ No Realm found")
