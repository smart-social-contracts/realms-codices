"""Syntropia — sandboxed codex hooks (issue #265).

This module is spawned inside the Basilisk subinterpreter (manifest
``sandbox_module``). It is intentionally self-contained: it imports **only**
``ggg_sdk`` (the in-sandbox SDK) and the standard library, so its module body
executes cleanly inside the sandbox — no ``_cdk``, no ``ggg``, no sibling
modules, no filesystem access. The sandbox is pure compute: reads (``realm.config``,
``realm.users.get``, ...) are served from the host-injected context and writes
(``realm.invoices.create``, ...) are recorded as effects the host authorizes
against the manifest ``capabilities`` and applies via the public ``ggg`` API.

``entry.py`` keeps an equivalent in-process implementation as the fallback used
when the sandbox is unavailable; this module is the sandboxed path.

Greenfield onboarding: on registration a new citizen receives a deposit invoice
(*a house in a zone*) and a three-step welcome notification (passport, deposit,
Know-Your-Citizen). Mirrors ``entry.py::on_user_register``.
"""

from ggg_sdk import hook, iso_days_from, realm

REALM_NAME = "Syntropia"


@hook
def on_user_register(args):
    user = realm.users.get(args.get("user_id", ""))
    if not user:
        return {"success": False, "error": "user not found"}

    config = realm.config() or {}
    currency = realm.currency()
    lifecycle = config.get("lifecycle", {}) or {}
    deposit = (config.get("fees", {}) or {}).get(
        "deposit", lifecycle.get("deposit_amount", 0.01)
    )
    deposit_label = lifecycle.get("deposit_label", "a house in a zone")
    validity_days = (config.get("membership", {}) or {}).get(
        "invoice_validity_days", 30
    )

    now_epoch = realm.now()["epoch"]
    due_date = iso_days_from(now_epoch, validity_days)
    created_at = iso_days_from(now_epoch, 0)[:16]

    invoice = realm.invoices.create(
        amount=deposit,
        currency=currency,
        due_date=due_date,
        status="Pending",
        user_id=user["id"],
        metadata="deposit invoice - a house in a zone",
    )

    realm.notifications.create(
        topic="welcome",
        title="Welcome to " + REALM_NAME + "!",
        message=(
            "Welcome to **" + REALM_NAME + "**, a brand-new sovereign smart "
            "city. To become an active citizen, complete three steps:\n\n"
            "1. **Verify your identity** via ZK Passport (*Passport "
            "Verification* extension)\n"
            "2. **Pay your deposit** — " + str(deposit_label) + " — `"
            + str(deposit) + " " + str(currency) + "` from the *Invoices* "
            "section\n"
            "3. **Submit your Know-Your-Citizen data** before the city goes "
            "live\n\n"
            "The **AI Assistant** can guide you through every step."
        ),
        user_id=user["id"],
        sender="Administration",
        recipient=user["id"],
        read=False,
        icon="shield_check",
        href="/extensions/member_dashboard",
        color="green",
        metadata="invoice_id:" + str(invoice["id"]),
        timestamp_created=created_at,
    )

    return {"success": True, "invoice_id": invoice["id"]}
