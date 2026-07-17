"""Agora codex — hook API entry point (codex_api_version 1, issue #244).

Agora is an *incumbent migration*: an existing public administration
replacing its IT with Realms GOS. Onboarding is by registration code / bulk
import (no ZK passport). The codex integrates with the core exclusively
through the hooks defined here — no ``entity_method_overrides``, no
exec'd ``init.py``.

Hooks implemented:
  get_config          — manifest config blocks (single source of realm policy),
                        with deploy-time lifecycle overrides (issue #253)
  init                — post-install realm setup: manifest_data, server-side
                        registration-policy enforcement, org seeding
  seed                — idempotent org-chart re-seed (admin re-run)
  on_user_register    — migration onboarding: activation + phase-aware invoice
  on_stage_change     — beta: tax/membership invoicing starts (issue #253)
  on_treasury_send    — treasury transfers through the vault extension

Extension methods (extension_sync_call "agora"):
  run_payroll         — record salary payments for filled positions from
                        department funds (issue #253)
"""

import json
import os

from _cdk import ic

REALM_NAME = "Agora"

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
            ic.print(f"⚠️  Agora: could not load manifest.json: {e}")
            return {}
    ic.print("⚠️  Agora: manifest.json not found")
    return {}


def _load_data(filename):
    path = os.path.join(_DIR, filename)
    try:
        with open(path, "r") as f:
            return json.loads(f.read())
    except Exception as e:
        ic.print(f"⚠️  Agora: could not load {filename}: {e}")
        return None


def _realm():
    from ggg import Realm

    realms = Realm.instances()
    return realms[0] if realms else None


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def get_config(args: str) -> str:
    """Realm configuration blocks declared by this codex.

    Deploy/test-time parameterization (issue #253): a realm admin may patch
    ``lifecycle_overrides`` into ``Realm.manifest_data`` (via realm_settings
    ``patch_manifest_data``); those keys are applied over the codex-declared
    ``lifecycle`` block, so e.g. ``population_target`` or
    ``beta_proving_days`` can be tuned per deployment without republishing
    the codex.
    """
    manifest = _manifest()
    config = {k: v for k, v in manifest.items() if k not in _NON_CONFIG_KEYS}
    try:
        realm = _realm()
        raw = getattr(realm, "manifest_data", "") or "{}" if realm else "{}"
        overrides = (json.loads(raw) or {}).get("lifecycle_overrides") or {}
        if isinstance(overrides, dict) and overrides:
            lifecycle = dict(config.get("lifecycle", {}) or {})
            lifecycle.update(overrides)
            config["lifecycle"] = lifecycle
    except Exception as e:
        ic.print(f"⚠️  Agora: could not apply lifecycle_overrides: {e}")
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

    # Lifecycle metrics consumed by the public dashboard.
    lifecycle = dict(manifest.get("lifecycle", {}))
    population_target = lifecycle.get("population_target", 0)
    lifecycle.setdefault("critical_mass", population_target)

    # Keep manifest_data lean (Realm.manifest_data is capped at 4096 chars).
    department_names = [
        d.get("name", "") for d in (departments or {}).get("departments", [])
    ]

    realm_manifest = {
        "onboarding": manifest.get("onboarding", {}),
        "lifecycle": lifecycle,
        "dashboard": manifest.get("dashboard", {}),
        "dependencies": manifest.get("dependencies", []),
        "departments": department_names,
    }
    realm.manifest_data = json.dumps(realm_manifest)

    # The registration model is part of the codex's governance design —
    # enforce it server-side so a stale or broken wizard can never produce
    # a realm that contradicts its codex (issue #244). Agora is an incumbent
    # migration: invitation/import only, never open registration.
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

    ic.print("✅ Agora (incumbent) init complete")
    return json.dumps({
        "success": True,
        "codex": "agora",
        "seeded": seed_result.get("success", False),
    })


def seed(args: str) -> str:
    """Seed the org chart as real organizations (idempotent, issue #241)."""
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
    """Migration onboarding — no payment during alpha; a registration invoice
    is issued once the realm reaches **beta** (money starts flowing at the
    Beta transition, issue #253) and only if a registration fee is
    configured."""
    from ggg import Invoice, Notification, User
    from ic_basilisk_toolkit.date_utils import epoch_to_datetime_str, ic_time_to_epoch

    try:
        params = json.loads(args) if args else {}
        user = User[params.get("user_id", "")]
        if not user:
            return json.dumps({"success": False, "error": "user not found"})

        manifest = _manifest()
        currency = manifest.get("currency", {}).get("symbol", "ckUSDC")
        fee = manifest.get("fees", {}).get("registration", 0.0)
        validity_days = manifest.get("membership", {}).get("invoice_validity_days", 30)
        realm = _realm()
        stage = (getattr(realm, "status", None) or "alpha") if realm else "alpha"

        now_epoch = ic_time_to_epoch(ic.time())

        # Incumbent migration: imported/registered citizens are active
        # immediately (no ZK passport step). Activation is idempotent.
        try:
            from ggg import Codex

            membership_codex = Codex["membership"]
            if membership_codex and membership_codex.code:
                ns = {"ic": ic, "__builtins__": __builtins__}
                exec(compile(membership_codex.code, "membership.py", "exec"), ns)
                if "activate_member" in ns:
                    ns["activate_member"](user.id)
        except Exception as e:
            ic.print(f"Agora: could not activate member {user.id}: {e}")

        # Beta or live realm with a real fee: issue a registration invoice
        # (payments start at the Beta transition, issue #253).
        if stage in ("beta", "production") and fee and fee > 0:
            due_date = epoch_to_datetime_str(
                now_epoch + validity_days * 86400
            ).replace(" ", "T")
            invoice = Invoice(
                amount=fee,
                currency=currency,
                due_date=due_date,
                status="Pending",
                user=user,
                metadata="registration invoice",
            )
            Notification(
                topic="welcome",
                title=f"Welcome to {REALM_NAME}",
                message=(
                    f"Your account has been migrated into **{REALM_NAME}**. "
                    f"Please settle your registration invoice (`{fee} {currency}`) "
                    f"in the *Invoices* section. The **AI Assistant** can help you at any time."
                ),
                sender="Administration",
                recipient=user.id,
                user=user,
                read=False,
                icon="wallet",
                href="/extensions/member_dashboard",
                color="green",
                metadata=f"invoice_id:{invoice.id}",
                timestamp_created=epoch_to_datetime_str(now_epoch)[:16],
            )
            ic.print(
                f"Created registration invoice #{invoice.id} for migrated user {user.id}"
            )
            return json.dumps({"success": True, "invoice_id": invoice.id})

        # Alpha (migration preparation): no payment, informational only.
        Notification(
            topic="welcome",
            title=f"Welcome to {REALM_NAME}",
            message=(
                f"Your account has been migrated into **{REALM_NAME}** during the **{stage}** phase. "
                f"**Nothing to pay for now.** Your member dashboard shows your declaration and any "
                f"*potential future* tax deadlines so you can prepare ahead of the beta transition. "
                f"Questions? Ask the **AI Assistant** — it knows everything about this realm."
            ),
            sender="Administration",
            recipient=user.id,
            user=user,
            read=False,
            icon="information_circle",
            href="/extensions/member_dashboard",
            color="blue",
            metadata=f"stage:{stage}",
            timestamp_created=epoch_to_datetime_str(now_epoch)[:16],
        )
        ic.print(f"Migrated user {user.id} onboarded in '{stage}' phase (no payment)")
        return json.dumps({"success": True, "stage": stage})

    except Exception as e:
        ic.print(f"Error in Agora on_user_register: {e}")
        return json.dumps({"success": False, "error": str(e)})


def _lifecycle_billing():
    # Prefer the top-level sibling module — the runtime loader only preloads
    # backend/*.py, not backend/modules/*.py (see runtime_extensions._load_module).
    try:
        from . import lifecycle_billing  # installed (package sibling)
    except ImportError:
        try:
            import lifecycle_billing  # local test (flat path)
        except ImportError:
            from modules import lifecycle_billing  # source-tree fallback
    return lifecycle_billing


def on_stage_change(args: str) -> str:
    """React to lifecycle transitions (issue #253).

    Entering **beta** starts the money flow: every citizen receives a
    tax/membership invoice and the payroll baseline is recorded so admin
    salaries begin accruing from department funds.
    """
    try:
        params = json.loads(args) if args else {}
        to_stage = (params.get("to_stage") or "").strip().lower()
        if to_stage != "beta":
            return json.dumps({"success": True, "skipped": f"no action for {to_stage}"})

        manifest = _manifest()
        billing = _lifecycle_billing()
        invoices = billing.issue_membership_invoices(manifest, REALM_NAME)
        payroll = billing.run_payroll(manifest, REALM_NAME)

        return json.dumps({
            "success": True,
            "invoiced": invoices.get("invoiced", 0),
            "payroll_payments": len(payroll.get("payments", [])),
        })
    except Exception as e:
        ic.print(f"Error in Agora on_stage_change: {e}")
        return json.dumps({"success": False, "error": str(e)})


def run_payroll(args: str) -> str:
    """Record salary payments for all filled seats (admin/testing entry point,
    callable via ``extension_sync_call("agora", "run_payroll", "{}")``)."""
    try:
        from core.access import _check_access
        from ggg.system.user_profile import Operations

        caller = ic.caller().to_str()
        if not _check_access(caller, Operations.REALM_ADMIN):
            return json.dumps({
                "success": False,
                "error": f"Access denied: {caller} is not a realm admin",
            })
    except Exception:
        pass

    try:
        result = _lifecycle_billing().run_payroll(_manifest(), REALM_NAME)
        return json.dumps(result)
    except Exception as e:
        ic.print(f"Error in Agora run_payroll: {e}")
        return json.dumps({"success": False, "error": str(e)})


def on_treasury_send(args: str):
    """Treasury transfers go through the vault extension (async generator)."""
    from core.extensions import extension_async_call

    params = json.loads(args) if args else {}
    vault_args = json.dumps({
        "to_principal": params.get("to_principal", ""),
        "amount": params.get("amount", 0),
    })
    result = yield extension_async_call("vault", "transfer", vault_args)
    return result
