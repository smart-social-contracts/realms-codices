"""Dominion codex — hook API entry point (codex_api_version 1, issue #244).

The codex integrates with the core exclusively through the hooks defined
here — no ``entity_method_overrides``, no exec'd ``init.py``.

Hooks implemented:
  get_config          — manifest config blocks (single source of realm policy)
  init                — post-install realm setup: manifest_data + identity fields
  on_user_register    — registration invoice (welcome fee) + welcome steps
"""

import json
import os

from _cdk import ic

REALM_NAME = "Dominion"

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
            ic.print(f"⚠️  Dominion: could not load manifest.json: {e}")
            return {}
    ic.print("⚠️  Dominion: manifest.json not found")
    return {}


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
    """Post-install realm setup (idempotent): write the config summary into
    ``Realm.manifest_data`` and fill empty identity fields."""
    realm = _realm()
    if not realm:
        return json.dumps({"success": False, "error": "No Realm found"})

    manifest = _manifest()

    realm_manifest = {
        "fees": manifest.get("fees", {}),
        "governance": manifest.get("governance", {}),
        "billing": manifest.get("billing", {}),
        "membership": manifest.get("membership", {}),
    }
    realm.manifest_data = json.dumps(realm_manifest)

    # Identity fields are the creator's, not the codex's: fill them only
    # when the wizard left them empty — never overwrite a chosen realm name.
    if manifest.get("name") and not getattr(realm, "name", ""):
        realm.name = manifest["name"]
    if manifest.get("manifesto") and not getattr(realm, "manifesto", ""):
        realm.manifesto = manifest["manifesto"]
    if manifest.get("welcome_message") and not getattr(realm, "welcome_message", ""):
        realm.welcome_message = manifest["welcome_message"]

    ic.print("✅ Dominion init complete")
    return json.dumps({"success": True, "codex": "dominion"})


def on_user_register(args: str) -> str:
    """Create a registration invoice in DOM upon user signup."""
    from ggg import Invoice, Notification, User
    from ic_basilisk_toolkit.date_utils import epoch_to_datetime_str, ic_time_to_epoch

    try:
        params = json.loads(args) if args else {}
        user = User[params.get("user_id", "")]
        if not user:
            return json.dumps({"success": False, "error": "user not found"})

        manifest = _manifest()
        currency = manifest.get("currency", {}).get("symbol", "DOM")
        fee = manifest.get("fees", {}).get("registration", 1.0)
        validity_days = manifest.get("membership", {}).get("invoice_validity_days", 30)

        now_epoch = ic_time_to_epoch(ic.time())
        due_date = epoch_to_datetime_str(
            now_epoch + validity_days * 86400
        ).replace(" ", "T")

        invoice = Invoice(
            amount=fee,
            currency=currency,
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="Welcome fee - registration invoice",
        )

        ic.print(
            f"Created registration invoice #{invoice.id} for user {user.id}: "
            f"{fee} {currency}"
        )

        Notification(
            topic="welcome",
            title=f"Welcome to {REALM_NAME}!",
            message=(
                f"Welcome to **{REALM_NAME}**! To become an active citizen you need to complete two steps:\n\n"
                f"- **Pay your registration invoice** — `{fee} {currency}` from the *Invoices* section below\n"
                f"- **Verify your identity** via ZK Passport using the *Passport Verification* extension\n\n"
                f"If you have any questions, feel free to ask the **AI Assistant** — "
                f"it knows everything about this realm and can guide you through the process."
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
        return json.dumps({"success": True, "invoice_id": invoice.id})

    except Exception as e:
        ic.print(f"Error in Dominion on_user_register: {e}")
        return json.dumps({"success": False, "error": str(e)})
