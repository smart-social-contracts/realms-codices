"""
User Registration Hook Codex (Agora-specific)
Overrides user_register_posthook to add custom logic after user registration.

Creates a single registration invoice denominated in AGO (Agora Token).
The user must pay this invoice AND verify their passport via the
passport_verification extension to become an active citizen.
"""

from datetime import datetime, timedelta


def _ic_now():
    """Get current datetime from ic.time() (nanoseconds since epoch)."""
    ns = ic.time()
    return datetime(1970, 1, 1) + timedelta(seconds=ns // 1_000_000_000)


REGISTRATION_FEE_AGO = 1.0   # 1 AGO (8 decimals → 100_000_000 raw)
INVOICE_VALIDITY_DAYS = 30


def user_register_posthook(user):
    """Custom user registration hook — creates initial invoice for new Agora users.

    A single invoice denominated in AGO is created. Payment of this invoice
    is one of two requirements for activation (the other being passport
    verification).
    """
    try:
        now = _ic_now()
        due_date = (now + timedelta(days=INVOICE_VALIDITY_DAYS)).isoformat()

        invoice = ggg.Invoice(
            amount=REGISTRATION_FEE_AGO,
            currency="AGO",
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="Welcome fee - registration invoice",
        )

        vault_principal = ic.id().to_str()
        sub_hex = invoice.get_subaccount_hex()

        ic.print(
            f"Created registration invoice #{invoice.id} for user {user.id}: "
            f"{REGISTRATION_FEE_AGO} AGO"
        )

        ggg.Notification(
            topic="welcome",
            title="Welcome to Agora!",
            message=(
                f"Welcome to **Agora**! To become an active citizen you need to complete two steps:\n\n"
                f"- **Pay your registration invoice** — `{REGISTRATION_FEE_AGO} AGO` from the *Invoices* section below\n"
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
