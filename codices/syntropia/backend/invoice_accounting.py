"""Syntropia invoice-accounting policy.

Core emits invoice lifecycle events. This module decides how those events are
booked for Syntropia: citizen deposits remain liabilities, membership invoices
become tax revenue, and other invoices become fee revenue.
"""


DEPOSIT_CATEGORY = "citizen_deposit"


def _entry_date(invoice) -> str:
    paid_at = getattr(invoice, "paid_at", "") or ""
    if paid_at and not paid_at.startswith("1970-01-01T00:00:00"):
        return paid_at
    try:
        from _cdk import ic
        from ic_basilisk_toolkit.date_utils import (
            epoch_to_datetime_str,
            ic_time_to_epoch,
        )

        return epoch_to_datetime_str(
            ic_time_to_epoch(int(ic.time()))
        ).replace(" ", "T")
    except Exception:
        return ""


def _root_fund():
    from ggg import Fund, FundType

    fund = Fund["ROOT"]
    if fund:
        return fund
    return Fund(
        code="ROOT",
        name="Root Department Fund",
        fund_type=FundType.GENERAL,
        description="Budget envelope for the quarter root department",
    )


def _common(invoice, fund, entry_date: str, description: str) -> dict:
    entry = {
        "currency": invoice.currency or "",
        "entry_date": entry_date,
        "description": description,
        "fund": fund,
        "invoice": invoice,
    }
    if getattr(invoice, "user", None):
        entry["user"] = invoice.user
    return entry


def _create_invoice_entries(invoice, fund, amount_raw: int, entry_date: str) -> list:
    from ggg import Category, EntryType, LedgerEntry

    metadata = (getattr(invoice, "metadata", "") or "").lower()
    liability_category = (
        DEPOSIT_CATEGORY if "deposit" in metadata else Category.DEFERRED_REVENUE
    )
    transaction_id = f"TXN-INV-{invoice.id}"
    if LedgerEntry.find({"transaction_id": transaction_id}):
        return []

    desc = f"Invoice {invoice.id}"
    receivable = _common(
        invoice, fund, entry_date, f"{desc} - Receivable ({invoice.currency})"
    )
    receivable.update({
        "entry_type": EntryType.ASSET,
        "category": Category.RECEIVABLE,
        "debit": amount_raw,
        "credit": 0,
    })
    liability = _common(
        invoice,
        fund,
        entry_date,
        f"{desc} - {'Citizen deposit' if 'deposit' in metadata else 'Deferred revenue'} "
        f"({invoice.currency})",
    )
    liability.update({
        "entry_type": EntryType.LIABILITY,
        "category": liability_category,
        "debit": 0,
        "credit": amount_raw,
    })
    return LedgerEntry.create_transaction(
        transaction_id, [receivable, liability]
    )


def _create_payment_entries(invoice, fund, amount_raw: int, entry_date: str) -> list:
    from ggg import Category, EntryType, LedgerEntry

    transaction_id = f"TXN-INV-PAY-{invoice.id}"
    if LedgerEntry.find({"transaction_id": transaction_id}):
        return []

    metadata = (getattr(invoice, "metadata", "") or "").lower()
    desc = f"Invoice {invoice.id} payment"
    cash = _common(
        invoice, fund, entry_date, f"{desc} - Cash received ({invoice.currency})"
    )
    cash.update({
        "entry_type": EntryType.ASSET,
        "category": Category.CASH,
        "debit": amount_raw,
        "credit": 0,
    })
    receivable = _common(
        invoice, fund, entry_date, f"{desc} - Receivable cleared ({invoice.currency})"
    )
    receivable.update({
        "entry_type": EntryType.ASSET,
        "category": Category.RECEIVABLE,
        "debit": 0,
        "credit": amount_raw,
    })
    entries = [cash, receivable]

    # A citizen deposit is held by the realm, not earned income. Its original
    # liability remains on the balance sheet after cash is received.
    if "deposit" not in metadata:
        revenue_category = Category.TAX if "membership_tax" in metadata else Category.FEE
        deferred = _common(
            invoice,
            fund,
            entry_date,
            f"{desc} - Deferred revenue cleared ({invoice.currency})",
        )
        deferred.update({
            "entry_type": EntryType.LIABILITY,
            "category": Category.DEFERRED_REVENUE,
            "debit": amount_raw,
            "credit": 0,
        })
        revenue = _common(
            invoice,
            fund,
            entry_date,
            f"{desc} - Revenue recognised ({invoice.currency})",
        )
        revenue.update({
            "entry_type": EntryType.REVENUE,
            "category": revenue_category,
            "debit": 0,
            "credit": amount_raw,
        })
        entries.extend([deferred, revenue])

    return LedgerEntry.create_transaction(transaction_id, entries)


def book_invoice_event(invoice_id: str, event: str) -> dict:
    """Book one invoice event according to Syntropia policy."""
    from ggg import Invoice

    invoice = Invoice[invoice_id]
    if not invoice:
        return {"success": False, "error": "invoice not found"}
    if event != "paid":
        return {"success": True, "skipped": f"unsupported event: {event}"}

    fund = _root_fund()
    entry_date = _entry_date(invoice)
    amount_raw = invoice.get_amount_raw(invoice._get_token_decimals())
    created = _create_invoice_entries(invoice, fund, amount_raw, entry_date)
    paid = _create_payment_entries(invoice, fund, amount_raw, entry_date)
    return {
        "success": True,
        "invoice_id": invoice.id,
        "creation_entries": len(created),
        "payment_entries": len(paid),
    }
