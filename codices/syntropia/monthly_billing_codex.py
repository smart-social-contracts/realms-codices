"""
Monthly Billing Codex
Issues monthly ckBTC invoices to all active members.

Lifecycle per member each billing cycle:
  1. Create a ckBTC invoice (status: Pending)
  2. If already warned last cycle and still unpaid → kick (revoke membership)
  3. If unpaid from previous cycle and not yet warned → warn
  4. Paid invoices are left as-is

Designed to run as a scheduled task via:
    realms run --file monthly_billing_codex.py --every 300 --after 5
"""

from ggg import User, Member, Invoice, Notification, Transfer
from datetime import datetime, timedelta
import json

try:
    from core.extensions import extension_async_call
except ImportError:
    from ..core.extensions import extension_async_call


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MONTHLY_FEE_SATOSHIS = 1000          # 1000 satoshis = 0.00001 ckBTC
INVOICE_CURRENCY = "ckBTC"
GRACE_PERIOD_DAYS = 30               # days before warning
KICK_AFTER_DAYS = 60                 # days before revocation


# ---------------------------------------------------------------------------
# Invoice Creation
# ---------------------------------------------------------------------------

def create_monthly_invoice(user_id: str) -> dict:
    """Create a monthly ckBTC invoice for a member."""
    user = User[user_id]
    if not user:
        return {"error": "User not found"}

    due_date = (datetime.now() + timedelta(days=GRACE_PERIOD_DAYS)).isoformat()

    invoice = Invoice(
        amount=MONTHLY_FEE_SATOSHIS / 1e8,  # convert satoshis to ckBTC
        currency=INVOICE_CURRENCY,
        due_date=due_date,
        status="Pending",
        user=user,
        metadata="monthly_dues|" + user_id + "|" + datetime.now().strftime("%Y-%m"),
    )

    return {
        "invoice_id": invoice.id,
        "user_id": user_id,
        "amount_ckbtc": MONTHLY_FEE_SATOSHIS / 1e8,
        "due_date": due_date,
        "status": "Pending",
    }


# ---------------------------------------------------------------------------
# Overdue Processing
# ---------------------------------------------------------------------------

def _get_active_members() -> list:
    """Return members whose identity_verification is 'verified'."""
    return [m for m in Member.instances()
            if m.identity_verification == "verified" and m.user]


def _get_monthly_invoices(user_id: str) -> list:
    """Return all monthly-dues invoices for a user, newest first."""
    invoices = []
    for inv in Invoice.instances():
        meta = inv.metadata or ""
        if meta.startswith("monthly_dues|"):
            parts = meta.split("|")
            inv_uid = parts[1] if len(parts) > 1 else ""
            if inv_uid == user_id:
                invoices.append(inv)
    # Sort by due_date descending
    invoices.sort(key=lambda i: i.due_date or "", reverse=True)
    return invoices


def _days_overdue(invoice) -> int:
    """How many days past due_date an invoice is. Returns 0 if not overdue."""
    if not invoice.due_date:
        return 0
    try:
        due = datetime.fromisoformat(invoice.due_date)
        delta = int((datetime.now() - due).total_seconds() // 86400)
        return max(0, delta)
    except (ValueError, TypeError):
        return 0


def warn_user(user_id: str, invoice_id: str) -> dict:
    """Send a warning notification about an overdue invoice."""
    user = User[user_id]
    if not user:
        return {"warned": False, "reason": "User not found"}

    Notification(
        topic="billing",
        title="Overdue Invoice Warning",
        message="Your monthly dues invoice " + invoice_id + " is overdue. Please pay within the next billing cycle or your citizenship will be revoked.",
        user=user,
        read=False,
        icon="alert_triangle",
        href="/extensions/member_dashboard#my_taxes",
        color="orange",
        metadata="uid:" + user_id + "|inv:" + invoice_id
    )

    return {
        "warned": True,
        "user_id": user_id,
        "invoice_id": invoice_id,
        "warned_at": datetime.now().isoformat(),
    }


def kick_user(user_id: str, invoice_id: str) -> dict:
    """Revoke membership due to persistent non-payment.

    Delegates to membership_codex.revoke_membership.
    """
    try:
        from codices.syntropia.membership_codex import revoke_membership
    except ImportError:
        # Fallback: inline minimal revocation
        user = User[user_id]
        if not user:
            return {"kicked": False, "reason": "User not found"}
        for member in Member.instances():
            if member.user and member.user.id == user_id:
                member.identity_verification = "revoked"
                member.voting_eligibility = "ineligible"
                member.public_benefits_eligibility = "ineligible"
                Notification(
                    topic="membership",
                    title="Citizenship Revoked",
                    message="Your citizenship has been revoked due to non-payment of invoice " + invoice_id + ".",
                    user=user,
                    read=False, icon="shield_off",
                    href="/", color="red",
                    metadata="uid:" + user_id + "|inv:" + invoice_id
                )
                return {"kicked": True, "user_id": user_id,
                        "member_id": member.id,
                        "kicked_at": datetime.now().isoformat()}
        return {"kicked": False, "reason": "No membership found"}

    return revoke_membership(
        user_id,
        reason=f"Non-payment of monthly dues (invoice {invoice_id})"
    )


# ---------------------------------------------------------------------------
# Billing Cycle (scheduled task entry point)
# ---------------------------------------------------------------------------

def run_billing_cycle():
    """Main billing cycle — issue new invoices, warn or kick overdue users.

    For each active member:
      1. Check previous invoices for overdue status
      2. If overdue > KICK_AFTER_DAYS and already warned → kick
      3. If overdue > GRACE_PERIOD_DAYS and not warned → warn
      4. Issue a new invoice for the current cycle
    """
    results = {
        "invoices_created": [],
        "warnings_sent": [],
        "members_kicked": [],
        "cycle": datetime.now().strftime("%Y-%m"),
    }

    members = _get_active_members()

    for member in members:
        user_id = member.user.id
        past_invoices = _get_monthly_invoices(user_id)

        # Check for overdue invoices
        already_warned = False
        for inv in past_invoices:
            if inv.status == "Pending":
                overdue = _days_overdue(inv)

                # Check if user was already warned (status flag)
                was_warned = inv.status == "Warned"

                if overdue >= KICK_AFTER_DAYS and was_warned:
                    # Kick
                    kick_result = kick_user(user_id, inv.id)
                    results["members_kicked"].append(kick_result)
                    inv.status = "Defaulted"
                    already_warned = True
                    break  # no new invoice for kicked user

                elif overdue >= GRACE_PERIOD_DAYS and not was_warned:
                    # Warn
                    warn_result = warn_user(user_id, inv.id)
                    results["warnings_sent"].append(warn_result)
                    # Mark invoice as warned via status
                    inv.status = "Warned"
                    already_warned = True

        # Don't create new invoice if member was just kicked
        kicked_ids = [k.get("user_id") for k in results["members_kicked"]]
        if user_id in kicked_ids:
            continue

        # Issue new monthly invoice
        invoice_result = create_monthly_invoice(user_id)
        if "error" not in invoice_result:
            results["invoices_created"].append(invoice_result)

    return results


# Scheduled task entry point
def async_task():
    """Entry point for scheduled execution via `realms run --every`."""
    print("Monthly Billing Cycle starting...")
    results = run_billing_cycle()
    print("Cycle complete: " + str(len(results["invoices_created"])) + " invoices, "
          + str(len(results["warnings_sent"])) + " warnings, "
          + str(len(results["members_kicked"])) + " kicked")
    return json.dumps(results)


# Main execution
if __name__ == "__main__":
    results = run_billing_cycle()
    print(json.dumps(results, indent=2))
