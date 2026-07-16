"""Syntropia codex — hook API entry point (codex_api_version 1, issue #244).

Syntropia is a *greenfield* sovereign smart city built from scratch. New
citizens are onboarded with a ZK passport, pay a deposit (a house in a zone),
and submit Know-Your-Citizen data before go-live. Until the realm reaches
production, member voting is not executable — only admins can make
fundamental changes.

The codex integrates with the core exclusively through the hooks defined
here — no ``entity_method_overrides``, no exec'd ``init.py``.

Hooks implemented:
  get_config          — manifest config blocks (single source of realm policy)
  init                — post-install realm setup: manifest_data, server-side
                        registration-policy enforcement, org seeding
  seed                — idempotent org-chart re-seed (admin re-run)
  on_user_register    — greenfield onboarding: deposit invoice + welcome steps
"""

import json
import os

from _cdk import ic

REALM_NAME = "Syntropia"

_DIR = os.path.dirname(__file__)

# Manifest keys that are packaging metadata, not realm configuration.
_NON_CONFIG_KEYS = {
    "id", "name", "version", "kind", "codex_api_version", "description",
    "author", "dependencies", "extension_overrides", "data_files",
    "profiles", "categories", "icon", "show_in_sidebar", "sidebar_label",
    "doc_url", "permissions",
}


def _manifest() -> dict:
    # Installed layout: manifest.json next to entry.py (backend/ prefix is
    # stripped at install). Source layout (local tests): one level up.
    for candidate in (
        os.path.join(_DIR, "manifest.json"),
        os.path.join(os.path.dirname(_DIR), "manifest.json"),
    ):
        try:
            with open(candidate, "r") as f:
                return json.loads(f.read())
        except FileNotFoundError:
            continue
        except Exception as e:
            ic.print(f"⚠️  Syntropia: could not load manifest.json: {e}")
            return {}
    ic.print("⚠️  Syntropia: manifest.json not found")
    return {}


def _load_data(filename):
    path = os.path.join(_DIR, filename)
    try:
        with open(path, "r") as f:
            return json.loads(f.read())
    except Exception as e:
        ic.print(f"⚠️  Syntropia: could not load {filename}: {e}")
        return None


def _realm():
    from ggg import Realm

    realms = Realm.instances()
    return realms[0] if realms else None


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def get_config(args: str) -> str:
    """Realm configuration blocks declared by this codex."""
    manifest = _manifest()
    config = {k: v for k, v in manifest.items() if k not in _NON_CONFIG_KEYS}
    return json.dumps(config)


def init(args: str) -> str:
    """Post-install realm setup (idempotent).

    Writes the lean config summary into ``Realm.manifest_data`` (legacy
    readers), enforces the codex's registration policy server-side, fills
    empty identity fields, and seeds the org chart.
    """
    realm = _realm()
    if not realm:
        return json.dumps({"success": False, "error": "No Realm found"})

    manifest = _manifest()
    departments = _load_data(
        manifest.get("data_files", {}).get("departments", "data/departments.json")
    )

    # Lifecycle: seed the metrics the public dashboard reads
    # (countdown, citizen counter, critical-mass threshold).
    lifecycle = dict(manifest.get("lifecycle", {}))
    lifecycle.setdefault("total_deposits", 0)
    lifecycle.setdefault("deposits_locked", False)
    lifecycle.setdefault("land_acquired", False)
    lifecycle.setdefault("infrastructure_ready", False)
    lifecycle.setdefault("providers_ready", False)

    # Keep manifest_data lean (Realm.manifest_data is capped at 4096 chars).
    department_names = [
        d.get("name", "") for d in (departments or {}).get("departments", [])
    ]

    realm_manifest = {
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
        ic.print(
            f"✅ Registration policy enforced: open_registration={realm.open_registration}"
        )

    # Identity fields are the creator's, not the codex's: fill them only
    # when the wizard left them empty — never overwrite a chosen realm name.
    if manifest.get("name") and not getattr(realm, "name", ""):
        realm.name = manifest["name"]
    if manifest.get("manifesto") and not getattr(realm, "manifesto", ""):
        realm.manifesto = manifest["manifesto"]
    if manifest.get("welcome_message") and not getattr(realm, "welcome_message", ""):
        realm.welcome_message = manifest["welcome_message"]

    seed_result = json.loads(seed(args))

    ic.print("✅ Syntropia (greenfield) init complete")
    return json.dumps({
        "success": True,
        "codex": "syntropia",
        "seeded": seed_result.get("success", False),
    })


def seed(args: str) -> str:
    """Seed the org chart as real organizations (idempotent, issues #241/#244)."""
    realm = _realm()
    if not realm:
        return json.dumps({"success": False, "error": "No Realm found"})

    manifest = _manifest()
    departments = _load_data(
        manifest.get("data_files", {}).get("departments", "data/departments.json")
    )
    if not departments:
        return json.dumps({"success": False, "error": "departments data file missing"})

    try:
        try:
            from .org_seeding import seed_organizations  # installed (package)
        except ImportError:
            from org_seeding import seed_organizations  # local test (flat path)

        seed_organizations(departments, realm)
        return json.dumps({"success": True})
    except Exception as e:
        import traceback

        ic.print(f"❌ Organization seeding failed: {e}\n{traceback.format_exc()}")
        return json.dumps({"success": False, "error": str(e)})


def on_user_register(args: str) -> str:
    """Greenfield onboarding — deposit invoice (*a house in a zone*) plus the
    three-step welcome message (passport, deposit, Know-Your-Citizen)."""
    from ggg import Invoice, Notification, User
    from ic_basilisk_toolkit.date_utils import epoch_to_datetime_str, ic_time_to_epoch

    try:
        params = json.loads(args) if args else {}
        user = User[params.get("user_id", "")]
        if not user:
            return json.dumps({"success": False, "error": "user not found"})

        manifest = _manifest()
        currency = manifest.get("currency", {}).get("symbol", "ckBTC")
        lifecycle = manifest.get("lifecycle", {})
        deposit = manifest.get("fees", {}).get(
            "deposit", lifecycle.get("deposit_amount", 0.01)
        )
        deposit_label = lifecycle.get("deposit_label", "a house in a zone")
        validity_days = manifest.get("membership", {}).get("invoice_validity_days", 30)

        now_epoch = ic_time_to_epoch(ic.time())
        due_date = epoch_to_datetime_str(
            now_epoch + validity_days * 86400
        ).replace(" ", "T")

        # Deposit invoice — secures the citizen's house in a zone.
        invoice = Invoice(
            amount=deposit,
            currency=currency,
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="deposit invoice - a house in a zone",
        )

        Notification(
            topic="welcome",
            title=f"Welcome to {REALM_NAME}!",
            message=(
                f"Welcome to **{REALM_NAME}**, a brand-new sovereign smart city. "
                f"To become an active citizen, complete three steps:\n\n"
                f"1. **Verify your identity** via ZK Passport (*Passport Verification* extension)\n"
                f"2. **Pay your deposit** — {deposit_label} — `{deposit} {currency}` from the *Invoices* section\n"
                f"3. **Submit your Know-Your-Citizen data** before the city goes live\n\n"
                f"The **AI Assistant** can guide you through every step."
            ),
            sender="Administration",
            recipient=user.id,
            user=user,
            read=False,
            icon="shield_check",
            href="/extensions/member_dashboard",
            color="green",
            metadata=f"invoice_id:{invoice.id}",
            timestamp_created=epoch_to_datetime_str(now_epoch)[:16],
        )

        ic.print(
            f"Syntropia: created deposit invoice #{invoice.id} "
            f"({deposit} {currency}) for new citizen {user.id}"
        )
        return json.dumps({"success": True, "invoice_id": invoice.id})

    except Exception as e:
        ic.print(f"Error in Syntropia on_user_register: {e}")
        return json.dumps({"success": False, "error": str(e)})
