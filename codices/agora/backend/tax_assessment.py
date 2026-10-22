"""Tax assessment: the realm's adopted tax policy, turned into invoices.

The parameters come from the tax policy adopted in the realm (edited in the
Tax extension, stored as ``ggg.TaxPolicy``). This module decides who pays and
how much, using ``ggg_sdk.tax_breakdown`` for the arithmetic.

Two passes, each one page per call, addressed by an opaque cursor:

  ``members:<id>``  flat taxes, one invoice per member per period;
  ``parcels:<id>``  land taxes, one invoice per parcel per period, billed to
                    the parcel's owner and valued at area × ``unit_value``.

An invoice id is derived from (tax, member or parcel, period), so assessing
the same period again skips what is already invoiced instead of billing twice.
"""

import hashlib
import json

from _cdk import ic

PHASES = ("members", "parcels")
MAX_BATCH = 100


def _parse_cursor(cursor: str):
    if not cursor:
        return PHASES[0], 1
    phase, _, from_id = str(cursor).partition(":")
    if phase not in PHASES:
        raise ValueError(f"unknown assessment cursor '{cursor}'")
    try:
        return phase, max(1, int(from_id or 1))
    except ValueError:
        raise ValueError(f"unknown assessment cursor '{cursor}'")


def invoice_id(code: str, subject: str, period: str) -> str:
    """32 characters, the most an invoice id may have."""
    digest = hashlib.sha256(f"{code}|{subject}|{period}".encode()).hexdigest()
    return "tax_" + digest[:28]


def _eligible(user, tax) -> bool:
    from ggg import user_has_profile

    if not any(user_has_profile(user, p) for p in tax.get("applies_to") or []):
        return False
    return not any(user_has_profile(user, p) for p in tax.get("exempt_profiles") or [])


class _Run:
    def __init__(self, policy_id: str, currency: str, now: int, codex_label: str):
        self.policy_id = policy_id
        self.currency = currency
        self.now = now
        self.codex_label = codex_label
        self.created = 0
        self.already_invoiced = 0
        self.nothing_due = 0
        self.not_eligible = 0
        self.total = 0.0

    def bill(self, tax, user, subject: str, quantity: float, parcel: str = ""):
        from ggg import Invoice, Notification
        from ggg_sdk import iso_days_from, tax_breakdown, tax_period

        if not _eligible(user, tax):
            self.not_eligible += 1
            return
        breakdown = tax_breakdown(tax, quantity)
        amount = breakdown["amount"]
        if amount <= 0:
            self.nothing_due += 1
            return

        period = tax_period(tax["period"], self.now)
        inv_id = invoice_id(tax["code"], subject, period)
        if Invoice[inv_id] is not None:
            self.already_invoiced += 1
            return

        meta = {"type": "tax", "tax": tax["code"], "period": period,
                "policy": self.policy_id}
        if parcel:
            meta["parcel"] = parcel[:64]
        invoice = Invoice(
            id=inv_id,
            amount=amount,
            currency=self.currency,
            due_date=iso_days_from(self.now, tax.get("due_days", 30)),
            status="Pending",
            user=user,
            metadata=json.dumps(meta, separators=(",", ":"))[:256],
        )
        label = tax.get("label") or tax["code"]
        Notification(
            topic="billing",
            title=f"{label} due",
            message=(
                f"{label} for {period}: `{amount:g} {self.currency}`. "
                f"Settle it in the *Invoices* section."
            ),
            sender="Taxes",
            recipient=str(user.id),
            user=user,
            read=False,
            icon="wallet",
            href="/extensions/member_dashboard",
            color="yellow",
            metadata=f"invoice_id:{invoice.id}",
            timestamp_created=iso_days_from(self.now, 0)[:16].replace("T", " "),
        )
        self.created += 1
        self.total += amount

    def result(self, phase: str, next_cursor: str) -> dict:
        return {
            "success": True,
            "phase": phase,
            "next_cursor": next_cursor,
            "invoices_created": self.created,
            "already_invoiced": self.already_invoiced,
            "nothing_due": self.nothing_due,
            "not_eligible": self.not_eligible,
            "total_amount": round(self.total, 6),
            "currency": self.currency,
            "policy_id": self.policy_id,
        }


def assess(params: dict, manifest: dict, codex_label: str) -> dict:
    """Assess one page. Returns counts and ``next_cursor`` ("" when done)."""
    from ggg import Land, LandStatus, TaxPolicy, User
    from invoice_currency import invoice_currency, no_treasury_token_error

    policy = TaxPolicy.adopted()
    if policy is None:
        return {"success": False, "error": "No tax policy is adopted"}
    taxes = [t for t in policy.taxes() if t.get("enabled", True)]
    flat = [t for t in taxes if t.get("base") == "flat"]
    land = [t for t in taxes if t.get("base") == "land_area"]
    if not taxes:
        return {"success": False, "error": "The adopted tax policy has no enabled taxes"}

    currency = invoice_currency(manifest)
    if not currency:
        return {"success": False, **no_treasury_token_error()}

    count = max(1, min(int(params.get("count") or 25), MAX_BATCH))
    phase, from_id = _parse_cursor(params.get("cursor") or "")
    if phase == "members" and not flat:
        phase, from_id = "parcels", 1

    run = _Run(policy.id, currency, int(ic.time()) // 1_000_000_000, codex_label)
    nxt = from_id + count

    if phase == "members":
        for user in User.load_some(from_id=from_id, count=count) or []:
            if str(user.id) == "system":
                continue
            for tax in flat:
                run.bill(tax, user, subject=str(user.id), quantity=1)
        if nxt <= User.max_id():
            next_cursor = f"members:{nxt}"
        else:
            next_cursor = "parcels:1" if land else ""
    else:
        for parcel in Land.load_some(from_id=from_id, count=count) or []:
            owner = parcel.owner_user
            if owner is None or (parcel.status or LandStatus.ACTIVE) != LandStatus.ACTIVE:
                continue
            area = int(parcel.size_width or 0) * int(parcel.size_height or 0)
            for tax in land:
                run.bill(tax, owner, subject=f"land:{parcel.id}", quantity=area,
                         parcel=str(parcel.id))
        next_cursor = f"parcels:{nxt}" if land and nxt <= Land.max_id() else ""

    ic.print(
        f"{codex_label}: tax assessment {phase} from {from_id} — "
        f"{run.created} invoice(s), next '{next_cursor}'"
    )
    return run.result(phase, next_cursor)
