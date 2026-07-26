"""Agora — sandboxed codex hooks (issue #265).

This module is spawned inside the Basilisk subinterpreter (manifest
``sandbox_module``). It is intentionally self-contained: it imports **only**
``ggg_sdk`` (the in-sandbox SDK) and the standard library, so its module body
executes cleanly inside the sandbox — no ``_cdk``, no ``ggg``, no sibling
modules, no filesystem access. All realm access goes through the capability
bridge via ``realm.*`` (authorized against the manifest ``capabilities``).

``entry.py`` keeps an equivalent in-process implementation as the fallback used
when the sandbox is unavailable; this module is the sandboxed path.

Incumbent migration: registered/imported citizens are activated immediately
(no ZK passport). No payment during alpha; a registration invoice is issued at
beta/production if a registration fee is configured. Mirrors
``entry.py::on_user_register``.
"""

from ggg_sdk import hook, iso_days_from, realm

REALM_NAME = "Agora"


@hook
def on_user_register(args):
    user = realm.users.get(args.get("user_id", ""))
    if not user:
        return {"success": False, "error": "user not found"}

    config = realm.config() or {}
    currency = realm.currency()
    fee = (config.get("fees", {}) or {}).get("registration", 0.0)
    validity_days = (config.get("membership", {}) or {}).get(
        "invoice_validity_days", 30
    )
    info = realm.info() or {}
    stage = info.get("status") or "alpha"

    now_epoch = realm.now()["epoch"]
    created_at = iso_days_from(now_epoch, 0)[:16]

    # Incumbent migration: imported/registered citizens are active
    # immediately. Idempotent; non-fatal if it fails (mirrors entry.py).
    try:
        realm.members.activate(
            user["id"],
            identity_verification="verified",
            residence_permit="valid",
            tax_compliance="compliant",
            public_benefits_eligibility="eligible",
            voting_eligibility="eligible",
            criminal_record="clean",
        )
    except Exception:
        pass

    # Beta or live realm with a real fee: issue a registration invoice
    # (payments start at the Beta transition, issue #253).
    if stage in ("beta", "production") and fee and fee > 0:
        due_date = iso_days_from(now_epoch, validity_days)
        invoice = realm.invoices.create(
            amount=fee,
            currency=currency,
            due_date=due_date,
            status="Pending",
            user_id=user["id"],
            metadata="registration invoice",
        )
        realm.notifications.create(
            topic="welcome",
            title="Welcome to " + REALM_NAME,
            message=(
                "Your account has been migrated into **" + REALM_NAME + "**. "
                "Please settle your registration invoice (`" + str(fee) + " "
                + str(currency) + "`) in the *Invoices* section. The **AI "
                "Assistant** can help you at any time."
            ),
            user_id=user["id"],
            sender="Administration",
            recipient=user["id"],
            read=False,
            icon="wallet",
            href="/extensions/member_dashboard",
            color="green",
            metadata="invoice_id:" + str(invoice["id"]),
            timestamp_created=created_at,
        )
        return {"success": True, "invoice_id": invoice["id"]}

    # Alpha (migration preparation): no payment, informational only.
    realm.notifications.create(
        topic="welcome",
        title="Welcome to " + REALM_NAME,
        message=(
            "Your account has been migrated into **" + REALM_NAME + "** during "
            "the **" + str(stage) + "** phase. **Nothing to pay for now.** Your "
            "member dashboard shows your declaration and any *potential future* "
            "tax deadlines so you can prepare ahead of the beta transition. "
            "Questions? Ask the **AI Assistant** — it knows everything about "
            "this realm."
        ),
        user_id=user["id"],
        sender="Administration",
        recipient=user["id"],
        read=False,
        icon="information_circle",
        href="/extensions/member_dashboard",
        color="blue",
        metadata="stage:" + str(stage),
        timestamp_created=created_at,
    )
    return {"success": True, "stage": stage}
