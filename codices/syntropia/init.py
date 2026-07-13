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


def _load_module(filename):
    """Exec a sibling codex .py file into a namespace (init runs in a bare
    exec namespace, so plain ``import`` cannot see package siblings)."""
    path = os.path.join(_DIR, filename)
    try:
        with open(path, "r") as f:
            code = f.read()
        ns = {"__file__": path, "__name__": f"codex_syntropia_{filename[:-3]}"}
        exec(compile(code, path, "exec"), ns)
        return ns
    except Exception as e:
        ic.print(f"⚠️  Could not load module {filename}: {e}")
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

    # The registration model is part of the codex's governance design —
    # enforce it server-side so a stale or broken wizard can never produce
    # a realm that contradicts its codex (issue #244).
    registration = (manifest.get("onboarding", {}) or {}).get("registration", {}) or {}
    if "open_registration" in registration:
        realm.open_registration = bool(registration["open_registration"])
        ic.print(f"✅ Registration policy enforced: open_registration={realm.open_registration}")

    # Identity fields are the creator's, not the codex's: fill them only
    # when the wizard left them empty — never overwrite a chosen realm name.
    if manifest.get("name") and not getattr(realm, "name", ""):
        realm.name = manifest["name"]
    if manifest.get("manifesto") and not getattr(realm, "manifesto", ""):
        realm.manifesto = manifest["manifesto"]
    if manifest.get("welcome_message") and not getattr(realm, "welcome_message", ""):
        realm.welcome_message = manifest["welcome_message"]

    # Seed the org chart as real organizations (issues #241/#244).
    if departments:
        seeding = _load_module("org_seeding.py")
        if seeding and "seed_organizations" in seeding:
            try:
                seeding["seed_organizations"](departments, realm)
            except Exception as e:
                import traceback

                ic.print(f"❌ Organization seeding failed: {e}\n{traceback.format_exc()}")

    ic.print("✅ Syntropia (greenfield) manifest_data written")
else:
    ic.print("❌ No Realm found")
