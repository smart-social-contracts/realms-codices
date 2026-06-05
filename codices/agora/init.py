"""Agora codex initialization.

Agora is an *incumbent migration*: an existing public administration replacing
its IT with Realms GOS. Onboarding is by registration code / bulk import (no ZK
passport). This init writes the codex configuration into ``Realm.manifest_data``
so the backend and the (input-driven) public dashboard can read it.

Entity creation (Zone, License, budget accounting) is intentionally deferred
to avoid hitting the IC 40B-instruction per-message limit on canisters with
large amounts of existing state.
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

    # Reference data files (JSON) shipped with the codex.
    departments = _load_json(manifest.get("data_files", {}).get("departments", "departments.json"))

    # Lifecycle metrics consumed by the public dashboard.
    lifecycle = dict(manifest.get("lifecycle", {}))
    population_target = lifecycle.get("population_target", 0)
    lifecycle.setdefault("critical_mass", population_target)

    # Keep manifest_data lean (Realm.manifest_data is capped at 4096 chars).
    # Store only what the backend and public dashboard read.
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
    if manifest.get("manifesto"):
        realm.manifesto = manifest["manifesto"]
    if manifest.get("welcome_message"):
        realm.welcome_message = manifest["welcome_message"]

    ic.print("✅ Agora (incumbent) manifest_data written")
else:
    ic.print("❌ No Realm found")
