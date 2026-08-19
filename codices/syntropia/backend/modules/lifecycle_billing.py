"""Beta-stage billing and payroll (issue #253).

At the Beta transition money starts flowing:

  - ``issue_membership_invoices`` — every citizen (holder of the ``member``
    profile) receives a tax/membership invoice.
  - ``run_payroll`` — every filled Position seat with a salary line produces
    a salary Transfer recorded against the department's fund (double-entry
    ``personnel`` expense).

Payroll transfers are *recorded* (bookkeeping + audit trail); actual ICRC
settlement happens through the vault/treasury flows and is out of scope
here.
"""

import json

from _cdk import ic


def issue_membership_invoices(manifest: dict, codex_label: str) -> dict:
    """Create a membership/tax invoice for every citizen without one.

    Idempotent per stage: users that already have a pending invoice tagged
    ``membership_tax`` are skipped.
    """
    from ggg import Invoice, Notification, User
    from ic_basilisk_toolkit.date_utils import epoch_to_datetime_str, ic_time_to_epoch

    try:
        from invoice_currency import invoice_currency
    except ImportError:
        from ..invoice_currency import invoice_currency

    currency = invoice_currency(manifest)
    if not currency:
        try:
            from invoice_currency import no_treasury_token_error
        except ImportError:
            from ..invoice_currency import no_treasury_token_error

        return {"success": False, **no_treasury_token_error()}

    fees = manifest.get("fees", {}) or {}
    amount = fees.get("monthly_membership") or fees.get("registration") or 0
    validity_days = manifest.get("membership", {}).get("invoice_validity_days", 30)

    if not amount or amount <= 0:
        return {"success": True, "invoiced": 0, "detail": "no membership fee configured"}

    now_epoch = ic_time_to_epoch(ic.time())
    due_date = epoch_to_datetime_str(now_epoch + validity_days * 86400).replace(" ", "T")

    # Users that already hold a membership_tax invoice (idempotency).
    already = set()
    for inv in Invoice.instances():
        if "membership_tax" in (getattr(inv, "metadata", "") or ""):
            user = getattr(inv, "user", None)
            if user is not None:
                already.add(str(getattr(user, "id", "")))

    from ggg import iter_users, user_has_profile

    invoiced = 0
    for user in iter_users():
        uid = str(getattr(user, "id", ""))
        if uid in already:
            continue
        if not user_has_profile(user, "member"):
            continue
        if user_has_profile(user, "admin"):
            continue

        invoice = Invoice(
            amount=amount,
            currency=currency,
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="membership_tax invoice - beta stage",
        )
        Notification(
            topic="billing",
            title="Tax / membership fee due",
            message=(
                f"The realm has entered **beta** — taxes and fees are now "
                f"active. Please settle your membership invoice "
                f"(`{amount} {currency}`) in the *Invoices* section."
            ),
            sender="Economy",
            recipient=uid,
            user=user,
            read=False,
            icon="wallet",
            href="/extensions/member_dashboard",
            color="yellow",
            metadata=f"invoice_id:{invoice.id}",
            timestamp_created=epoch_to_datetime_str(now_epoch)[:16],
        )
        invoiced += 1

    ic.print(f"{codex_label}: issued {invoiced} membership/tax invoice(s) at beta")
    return {"success": True, "invoiced": invoiced}


def run_payroll(manifest: dict, codex_label: str) -> dict:
    """Record one salary payment per filled Position seat.

    For each active appointment on a salaried position, a Transfer is
    recorded from the department's fund to the seat holder, with balanced
    ``personnel`` expense ledger entries against that fund. Returns the list
    of recorded payments.
    """
    from ggg import Position

    try:
        from invoice_currency import invoice_currency
    except ImportError:
        from ..invoice_currency import invoice_currency

    currency = invoice_currency(manifest)
    if not currency:
        try:
            from invoice_currency import no_treasury_token_error
        except ImportError:
            from ..invoice_currency import no_treasury_token_error

        return {"success": False, **no_treasury_token_error()}

    now = int(ic.time()) // 1_000_000_000

    payments = []
    total = 0
    for position in Position.instances():
        salary = int(getattr(position, "salary_amount", 0) or 0)
        if salary <= 0:
            continue
        dept = getattr(position, "department", None)
        fund = getattr(dept, "fund", None) if dept is not None else None
        fund_code = getattr(fund, "code", "") if fund is not None else ""

        for appointment in position.active_appointments():
            holder = getattr(appointment, "user", None)
            if holder is None:
                continue
            uid = str(getattr(holder, "id", ""))
            payment = _record_salary_transfer(
                position=position,
                fund=fund,
                fund_code=fund_code,
                to_principal=uid,
                amount=salary,
                currency=currency,
                now=now,
            )
            payments.append(payment)
            if not payment.get("skipped"):
                total += salary

    ic.print(
        f"{codex_label}: payroll recorded — {len(payments)} payment(s), "
        f"total {total} {currency}"
    )
    return {"success": True, "payments": payments, "total": total, "currency": currency}


def _record_salary_transfer(
    position, fund, fund_code, to_principal, amount, currency, now
):
    from datetime import datetime

    from ggg import Transfer

    # Period-based id — the idempotency key shared with core.payroll (issue
    # #260): re-running payroll (or settling on-chain later) never duplicates
    # a salary for the same seat and month.
    dt = datetime.fromtimestamp(now)
    period = f"{dt.year:04d}-{dt.month:02d}"
    transfer_id = f"SAL-{position.key}-{to_principal}-{period}"

    existing = Transfer[transfer_id]
    if existing is not None:
        return {
            "transfer_id": transfer_id,
            "position": position.key,
            "to": to_principal,
            "amount": amount,
            "skipped": "already recorded for this period",
        }

    transfer = Transfer(
        id=transfer_id,
        principal_from=fund_code or "treasury",
        principal_to=to_principal,
        instrument=currency,
        amount=amount,
        timestamp=str(now),
        tags="salary",
        status="recorded",
    )
    try:
        transfer.record_accounting(
            fund=fund,
            expense_category="personnel",
            description=f"Salary — {position.key}",
        )
    except Exception as e:
        ic.print(f"⚠️  payroll accounting for {transfer_id} failed: {e}")
    return {
        "transfer_id": transfer_id,
        "position": position.key,
        "to": to_principal,
        "amount": amount,
    }
