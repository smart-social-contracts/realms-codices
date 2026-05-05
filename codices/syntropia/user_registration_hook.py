"""
User Registration Hook — Syntropia

Creates a registration invoice in ckBTC upon user signup.
"""

from datetime import datetime, timedelta

CURRENCY = "ckBTC"
REGISTRATION_FEE = 0.00001
INVOICE_VALIDITY_DAYS = 30
REALM_NAME = "Syntropia"


def _ic_now():
    ns = ic.time()
    return datetime(1970, 1, 1) + timedelta(seconds=ns // 1_000_000_000)


def user_register_posthook(user):
    try:
        now = _ic_now()
        due_date = (now + timedelta(days=INVOICE_VALIDITY_DAYS)).isoformat()

        invoice = ggg.Invoice(
            amount=REGISTRATION_FEE,
            currency=CURRENCY,
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="Welcome fee - registration invoice",
        )

        ic.print(
            f"Created registration invoice #{invoice.id} for user {user.id}: "
            f"{REGISTRATION_FEE} {CURRENCY}"
        )

        ggg.Notification(
            topic="welcome",
            title=f"Welcome to {REALM_NAME}!",
            message=(
                f"Welcome to **{REALM_NAME}**! To become an active citizen you need to complete two steps:\n\n"
                f"- **Pay your registration invoice** — `{REGISTRATION_FEE} {CURRENCY}` from the *Invoices* section below\n"
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
            timestamp_created=now.strftime("%Y-%m-%d %H:%M"),
        )

    except Exception as e:
        ic.print(f"Error creating registration invoice: {e}")

    return
