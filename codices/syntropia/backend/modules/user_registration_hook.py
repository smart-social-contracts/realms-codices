"""User Registration Hook — Syntropia (greenfield smart city).

A new citizen joining Syntropia must complete three steps before becoming an
active citizen:

  1. Verify identity via ZK Passport (passport_verification extension).
  2. Pay a deposit — *a house in a zone* — via the deposit invoice created here.
  3. Submit Know-Your-Citizen (KYC) data before the realm advances to beta/live.

Until the realm reaches production, member voting is not executable; only admins
can make fundamental changes.
"""

from _cdk import ic
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json
import os

REALM_NAME = "Syntropia"


def _manifest():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(3):
        try:
            with open(os.path.join(d, "manifest.json"), "r") as f:
                return json.load(f)
        except Exception:
            d = os.path.dirname(d)
    return {}


def user_register_posthook(user):
    try:
        manifest = _manifest()
        currency = manifest.get("currency", {}).get("symbol", "ckBTC")
        lifecycle = manifest.get("lifecycle", {})
        deposit = manifest.get("fees", {}).get("deposit", lifecycle.get("deposit_amount", 0.01))
        deposit_label = lifecycle.get("deposit_label", "a house in a zone")
        validity_days = manifest.get("membership", {}).get("invoice_validity_days", 30)

        now_epoch = ic_time_to_epoch(ic.time())
        due_date = epoch_to_datetime_str(now_epoch + validity_days * 86400).replace(" ", "T")

        # Deposit invoice — secures the citizen's house in a zone.
        invoice = ggg.Invoice(
            amount=deposit,
            currency=currency,
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="deposit invoice - a house in a zone",
        )

        ggg.Notification(
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
            f"Syntropia: created deposit invoice #{invoice.id} ({deposit} {currency}) for new citizen {user.id}"
        )

    except Exception as e:
        ic.print(f"Error in Syntropia user_register_posthook: {e}")

    return
