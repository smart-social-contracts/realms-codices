"""
Monthly Billing Codex
Handles recurring monthly invoices for all active members of the Agora realm.

Accepted currencies:
  - ckBTC (Bitcoin on IC)
  - AGO (Agora realm token, ic-tokens) at fixed rate 1 AGO = 0.5 BTC

Lifecycle:
  1. New user registers → user_registration_hook creates the FIRST invoice.
     User must pay this invoice AND verify passport to become active.
  2. Each billing cycle (scheduled task), new monthly invoices are created
     for active members whose previous invoice period has elapsed.
  3. Overdue invoices → warning notification after GRACE_PERIOD_DAYS.
  4. Still unpaid after SUSPENSION_AFTER_DAYS → membership.deactivate_member().
  5. When an invoice is paid, a double-entry LedgerEntry is recorded so the
     metrics extension shows accurate real-time finances.
  6. If a suspended member pays all overdue invoices → membership.reactivate_member().

Uses icw (ICP Wallet CLI) externally to move ckBTC / AGO tokens.
"""

from _cdk import ic
from ggg import User, Member, Invoice, Notification, Transfer
from ic_basilisk_toolkit.date_utils import (
    ic_time_to_epoch, epoch_to_datetime_str, epoch_to_date_str,
    date_str_to_epoch,
)
import json

# Accounting entities for accurate metrics
from ggg import LedgerEntry, Fund, FiscalPeriod, Budget
from ggg import EntryType, Category

# Import sibling codex for membership operations
import membership
# Import budget module for recording transactions
import budget


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Monthly fee: 0.00001000 ckBTC (1000 satoshis) or equivalent in AGO
MONTHLY_FEE_CKBTC = 0.00001000         # ckBTC (8 decimals)
MONTHLY_FEE_SATOSHIS = 1000            # raw satoshis

# AGO equivalent: 1 AGO = 0.5 BTC, so 1000 sat = 0.00001 BTC = 0.00002 AGO
AGO_PER_BTC = 2.0                      # 1 AGO = 0.5 BTC → 2 AGO per BTC
MONTHLY_FEE_AGO = MONTHLY_FEE_CKBTC * AGO_PER_BTC   # 0.00002 AGO

GRACE_PERIOD_DAYS = 7                  # days before warning
SUSPENSION_AFTER_DAYS = 30             # days before suspension (after due date)
INVOICE_VALIDITY_DAYS = 30             # each invoice is due in 30 days


# ---------------------------------------------------------------------------
# Invoice Creation
# ---------------------------------------------------------------------------

def create_monthly_invoice(user_id: str) -> dict:
    """Create monthly invoices (ckBTC + AGO) for a member.

    Two invoices are created — one in each accepted currency.
    The user only needs to pay ONE of them.
    """
    user = User[user_id]
    if not user:
        return {"created": False, "reason": "User not found"}

    now_epoch = ic_time_to_epoch(ic.time())
    due_date = epoch_to_datetime_str(now_epoch + INVOICE_VALIDITY_DAYS * 86400).replace(" ", "T")
    period = epoch_to_date_str(now_epoch)[:7]

    # Create ckBTC invoice
    inv_ckbtc = Invoice(
        amount=MONTHLY_FEE_CKBTC,
        currency="ckBTC",
        due_date=due_date,
        status="Pending",
        user=user,
        metadata=f"Monthly dues {period} - ckBTC"
    )

    # Create AGO invoice
    inv_ago = Invoice(
        amount=MONTHLY_FEE_AGO,
        currency="AGO",
        due_date=due_date,
        status="Pending",
        user=user,
        metadata=f"Monthly dues {period} - AGO"
    )

    # Deposit address info
    vault_principal = ic.id().to_str()
    sub_ckbtc = inv_ckbtc.get_subaccount_hex()
    sub_ago = inv_ago.get_subaccount_hex()

    ic.print(f"Created monthly invoices for user {user_id}: "
             f"ckBTC #{inv_ckbtc.id} ({MONTHLY_FEE_CKBTC}), "
             f"AGO #{inv_ago.id} ({MONTHLY_FEE_AGO})")

    Notification(
        topic="billing",
        title=f"Monthly Dues — {period}",
        message=(
            f"Your monthly dues invoice is ready. "
            f"Pay {MONTHLY_FEE_CKBTC} ckBTC to {vault_principal} "
            f"(subaccount: {sub_ckbtc[:16]}...) "
            f"OR {MONTHLY_FEE_AGO} AGO to {vault_principal} "
            f"(subaccount: {sub_ago[:16]}...). "
            f"Due in {INVOICE_VALIDITY_DAYS} days."
        ),
        user=user,
        read=False,
        icon="receipt",
        href="/extensions/member_dashboard#my_taxes",
        color="blue",
        metadata=f"invoice_id:{inv_ckbtc.id},invoice_id:{inv_ago.id}"
    )

    return {
        "created": True,
        "invoice_ckbtc_id": inv_ckbtc.id,
        "invoice_ago_id": inv_ago.id,
        "period": period,
        "due_date": due_date,
    }


# ---------------------------------------------------------------------------
# Invoice Payment Processing
# ---------------------------------------------------------------------------

def record_invoice_payment(invoice_id: str) -> dict:
    """Record a paid invoice and create proper LedgerEntry for metrics.

    This is called when the vault extension confirms payment receipt.
    It also checks if a suspended member should be reactivated.
    """
    inv = Invoice[invoice_id]
    if not inv:
        return {"recorded": False, "reason": "Invoice not found"}

    if inv.status == "Paid":
        return {"recorded": False, "reason": "Invoice already paid"}

    inv.status = "Paid"
    user = inv.user
    currency = inv.currency or "ckBTC"
    amount = inv.amount or 0

    ic.print(f"Invoice #{invoice_id} paid: {amount} {currency} by user {user.id if user else '?'}")

    # Convert amount to satoshi-equivalent for consistent LedgerEntry amounts
    if currency == "AGO":
        btc_equivalent = amount / AGO_PER_BTC
    else:
        btc_equivalent = amount

    # Record double-entry: debit Cash (asset), credit Revenue
    budget.record_bill_payment(
        user_id=user.id if user else "unknown",
        amount_btc=btc_equivalent,
        currency=currency,
        description=f"Monthly dues payment — invoice #{invoice_id}"
    )

    # Mark the sibling invoice (other currency) as cancelled if it exists
    meta = inv.metadata or ""
    period_tag = ""
    if "Monthly dues" in meta:
        period_tag = meta.split(" - ")[0]  # "Monthly dues YYYY-MM"
    if period_tag and user:
        for other_inv in Invoice.instances():
            if (other_inv.id != invoice_id
                    and other_inv.user and other_inv.user.id == user.id
                    and other_inv.status == "Pending"
                    and period_tag in (other_inv.metadata or "")):
                other_inv.status = "Cancelled"
                ic.print(f"Cancelled sibling invoice #{other_inv.id}")

    # Check if a suspended member can be reactivated
    if user:
        member = membership._find_member_for_user(user.id)
        if member and member.identity_verification == "suspended":
            # Check if ALL overdue invoices are now paid/cancelled
            has_overdue = False
            now_str = epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")
            for check_inv in Invoice.instances():
                if (check_inv.user and check_inv.user.id == user.id
                        and check_inv.status == "Pending"):
                    try:
                        if check_inv.due_date and check_inv.due_date < now_str:
                            has_overdue = True
                            break
                    except (ValueError, TypeError):
                        pass
            if not has_overdue:
                membership.reactivate_member(user.id)

    return {"recorded": True, "invoice_id": invoice_id, "currency": currency, "amount": amount}


# ---------------------------------------------------------------------------
# Billing Cycle (Scheduled Task)
# ---------------------------------------------------------------------------

def run_billing_cycle():
    """Main billing cycle — issue new invoices, warn or suspend overdue users.

    Designed to run as a scheduled task (e.g. daily or weekly).
    """
    now_epoch = ic_time_to_epoch(ic.time())
    now_str = epoch_to_datetime_str(now_epoch).replace(" ", "T")
    ic.print(f"=== Billing cycle started at {now_str} ===")

    members_billed = 0
    members_warned = 0
    members_suspended = 0

    for member in Member.instances():
        if not member.user:
            continue

        user = member.user
        user_id = user.id

        # Skip suspended members (they need to pay overdue bills first)
        if member.identity_verification == "suspended":
            continue

        # Check existing pending invoices for this user
        has_current_invoice = False
        overdue_invoices = []

        for inv in Invoice.instances():
            if not (inv.user and inv.user.id == user_id):
                continue
            if inv.status == "Pending":
                try:
                    if inv.due_date and inv.due_date >= now_str:
                        has_current_invoice = True
                    elif inv.due_date:
                        overdue_invoices.append(inv)
                except (ValueError, TypeError):
                    pass

        # Process overdue invoices
        for inv in overdue_invoices:
            try:
                due_epoch = date_str_to_epoch(inv.due_date[:10])
                days_overdue = (now_epoch - due_epoch) // 86400
            except (ValueError, TypeError, IndexError):
                days_overdue = 0

            if days_overdue >= SUSPENSION_AFTER_DAYS:
                # Suspend the member
                inv.status = "Defaulted"
                membership.deactivate_member(user_id, "Non-payment of monthly dues")
                members_suspended += 1
                ic.print(f"SUSPENDED user {user_id} — invoice #{inv.id} {days_overdue}d overdue")
                break  # no need to process further once suspended

            elif days_overdue >= GRACE_PERIOD_DAYS:
                if inv.status != "Warned":
                    inv.status = "Warned"
                    members_warned += 1
                    Notification(
                        topic="billing",
                        title="Payment Overdue",
                        message=(
                            f"Your invoice #{inv.id} is {days_overdue} days overdue. "
                            f"Please pay within {SUSPENSION_AFTER_DAYS - days_overdue} days "
                            f"to avoid suspension."
                        ),
                        user=user,
                        read=False,
                        icon="alert_triangle",
                        href="/extensions/member_dashboard#my_taxes",
                        color="orange",
                        metadata=f"invoice_id:{inv.id}"
                    )
                    ic.print(f"WARNED user {user_id} — invoice #{inv.id} {days_overdue}d overdue")

        # Issue new invoice if member has no current one and is still active
        if (not has_current_invoice
                and member.identity_verification == "verified"):
            result = create_monthly_invoice(user_id)
            if result.get("created"):
                members_billed += 1

    ic.print(f"=== Billing cycle complete: "
             f"{members_billed} billed, {members_warned} warned, "
             f"{members_suspended} suspended ===")

    return {
        "members_billed": members_billed,
        "members_warned": members_warned,
        "members_suspended": members_suspended,
        "cycle_time": now_str,
    }


# ---------------------------------------------------------------------------
# Scheduled Task Entry Point
# ---------------------------------------------------------------------------

def async_task():
    """Entry point for the Task Manager scheduled execution."""
    return run_billing_cycle()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def get_billing_status(user_id: str) -> dict:
    """Get the billing status for a user."""
    invoices = []
    for inv in Invoice.instances():
        if inv.user and inv.user.id == user_id:
            invoices.append({
                "id": inv.id,
                "amount": inv.amount,
                "currency": inv.currency,
                "status": inv.status,
                "due_date": inv.due_date,
                "metadata": inv.metadata,
            })
    return {
        "user_id": user_id,
        "invoices": invoices,
        "monthly_fee_ckbtc": MONTHLY_FEE_CKBTC,
        "monthly_fee_ago": MONTHLY_FEE_AGO,
        "grace_period_days": GRACE_PERIOD_DAYS,
        "suspension_after_days": SUSPENSION_AFTER_DAYS,
    }


if __name__ == "__main__":
    print(json.dumps(get_billing_status("test_user"), indent=2))
