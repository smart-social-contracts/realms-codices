"""User Registration Hook — Agora (incumbent migration).

Agora migrates an existing population into the realm via registration codes /
bulk import. During the migration phases (alpha/beta) members pay nothing — the
member dashboard only shows their declaration and *potential future* tax
deadlines. A registration invoice is created only once the realm is live
(production) and only if a registration fee is configured.
"""

from _cdk import ic
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json
import os

REALM_NAME = "Agora"


def _manifest():
    path = os.path.join(os.path.dirname(__file__), "manifest.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _realm_stage():
    try:
        realm = list(ggg.Realm.instances())[0]
        return getattr(realm, "status", None) or "alpha"
    except Exception:
        return "alpha"


def user_register_posthook(user):
    try:
        manifest = _manifest()
        currency = manifest.get("currency", {}).get("symbol", "ckUSDC")
        fee = manifest.get("fees", {}).get("registration", 0.0)
        validity_days = manifest.get("membership", {}).get("invoice_validity_days", 30)
        stage = _realm_stage()

        now_epoch = ic_time_to_epoch(ic.time())

        # Incumbent migration: imported/registered citizens are active immediately
        # (no ZK passport step). Activation is idempotent.
        try:
            import membership
            membership.activate_member(user.id)
        except Exception as e:
            ic.print(f"Agora: could not activate member {user.id}: {e}")

        # Live realm with a real fee: issue a registration invoice.
        if stage == "production" and fee and fee > 0:
            due_date = epoch_to_datetime_str(now_epoch + validity_days * 86400).replace(" ", "T")
            invoice = ggg.Invoice(
                amount=fee,
                currency=currency,
                due_date=due_date,
                status="Pending",
                user=user,
                metadata="registration invoice",
            )
            ggg.Notification(
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
            ic.print(f"Created registration invoice #{invoice.id} for migrated user {user.id}")
            return

        # Migration phases (alpha/beta): no payment, informational only.
        ggg.Notification(
            topic="welcome",
            title=f"Welcome to {REALM_NAME}",
            message=(
                f"Your account has been migrated into **{REALM_NAME}** during the **{stage}** phase. "
                f"**Nothing to pay for now.** Your member dashboard shows your declaration and any "
                f"*potential future* tax deadlines so you can prepare ahead of go-live. "
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

    except Exception as e:
        ic.print(f"Error in Agora user_register_posthook: {e}")

    return
