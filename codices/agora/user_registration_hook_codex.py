"""
User Registration Hook Codex (Agora-specific)
Overrides user_register_posthook to add custom logic after user registration.

Creates a single registration invoice for the new user, payable in either
ckBTC or AGO. The user must pay this invoice AND verify their passport
via the passport_verification extension to become an active citizen.

This replaces the _common version which uses REALMS tokens.
"""

from datetime import datetime, timedelta


def _ic_now():
    """Get current datetime from ic.time() (nanoseconds since epoch)."""
    ns = ic.time()
    return datetime(1970, 1, 1) + timedelta(seconds=ns // 1_000_000_000)


# Monthly fee matching monthly_billing_codex config
MONTHLY_FEE_CKBTC = 0.00001000         # 1000 satoshis
AGO_PER_BTC = 2.0                      # 1 AGO = 0.5 BTC
MONTHLY_FEE_AGO = MONTHLY_FEE_CKBTC * AGO_PER_BTC   # 0.00002 AGO
INVOICE_VALIDITY_DAYS = 30


def user_register_posthook(user):
    """Custom user registration hook — creates initial invoice for new Agora users.

    A single invoice is created (denominated in ckBTC). The user can pay in
    either ckBTC or AGO at the equivalent rate. Payment of this invoice is
    one of two requirements for activation (the other being passport
    verification).
    """
    try:
        now = _ic_now()
        due_date = (now + timedelta(days=INVOICE_VALIDITY_DAYS)).isoformat()

        # Create a single registration invoice (payable in ckBTC or AGO)
        invoice = ggg.Invoice(
            amount=MONTHLY_FEE_CKBTC,
            currency="ckBTC",
            due_date=due_date,
            status="Pending",
            user=user,
            metadata=f"Welcome fee - registration invoice | Also payable as {MONTHLY_FEE_AGO} AGO"
        )

        # Get deposit address info
        vault_principal = ic.id().to_str()
        sub_hex = invoice.get_subaccount_hex()

        ic.print(f"Created registration invoice #{invoice.id} for user {user.id}: "
                 f"{MONTHLY_FEE_CKBTC} ckBTC (or {MONTHLY_FEE_AGO} AGO)")

        # Welcome notification with next steps (markdown formatted)
        ggg.Notification(
            topic="welcome",
            title="Welcome to Agora!",
            message=(
                f"Welcome to **Agora**! To become an active citizen you need to complete two steps:\n\n"
                f"- **Pay your registration invoice** — `{MONTHLY_FEE_CKBTC} ckBTC` or `{MONTHLY_FEE_AGO} AGO` from the *Invoices* section below\n"
                f"- **Verify your identity** via ZK Passport using the *Passport Verification* extension\n\n"
                f"If you have any questions, feel free to ask the **AI Assistant** — "
                f"it knows everything about this realm and can guide you through the process."
            ),
            user=user,
            read=False,
            icon="shield_check",
            href="/extensions/member_dashboard",
            color="green",
            metadata=f"invoice_id:{invoice.id}",
            timestamp_created=now.strftime("%Y-%m-%d %H:%M")
        )

    except Exception as e:
        ic.print(f"Error creating registration invoice: {e}")

    return
