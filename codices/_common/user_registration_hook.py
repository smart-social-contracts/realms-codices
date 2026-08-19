"""
User Registration Hook Codex
Overrides user_register_posthook to add custom logic after user registration.
Creates a 1 satoshi invoice expiring in 1 day for new users.
"""

from _cdk import ic
from ggg import Invoice, Notification
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str

from invoice_currency import invoice_currency, no_treasury_token_error


def user_register_posthook(user):
    """Custom user registration hook - creates welcome invoice."""
    currency = invoice_currency({})
    if not currency:
        err = no_treasury_token_error()
        ic.print(f"❌ Welcome invoice skipped: {err['error']}")
        return

    try:
        now_epoch = ic_time_to_epoch(ic.time())
        due_date = epoch_to_datetime_str(now_epoch + 86400).replace(" ", "T")

        invoice = Invoice(
            amount=0.00000001,
            currency=currency,
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="Welcome fee - registration invoice",
        )

        vault_principal = ic.id().to_str()
        subaccount_hex = invoice.get_subaccount_hex()

        ic.print(
            f"✅ Created welcome invoice {invoice.id} for user {user.id}"
        )
        ic.print(
            f"   Deposit to: {vault_principal} "
            f"(subaccount: {subaccount_hex[:16]}...)"
        )
        ic.print(f"   Amount: 0.00000001 {currency}, expires in 1 day")

        Notification(
            topic="welcome",
            title="Welcome! Please complete your registration",
            message=(
                f"Please pay your welcome invoice to complete your registration. "
                f"Deposit {invoice.amount} {currency} to: {vault_principal} "
                f"(subaccount: {subaccount_hex[:16]}...). Expires in 1 day."
            ),
            sender="Administration",
            recipient=user.id,
            user=user,
            read=False,
            icon="wallet",
            href="/extensions/member_dashboard#my_taxes",
            color="green",
            metadata=f"invoice_id:{invoice.id}",
        )

    except Exception as e:
        ic.print(f"❌ Error creating invoice: {e}")

    return
