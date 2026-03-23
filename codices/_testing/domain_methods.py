"""
Domain-specific methods that have real logic beyond simple CRUD.

These get attached to the appropriate entity classes in ggg_module.py.
"""


# ---------------------------------------------------------------------------
# LedgerEntry
# ---------------------------------------------------------------------------

def ledger_create_transaction(cls, transaction_id, entries, validate=True):
    """Create a balanced double-entry transaction.

    Args:
        transaction_id: Unique ID grouping the entries.
        entries: List of dicts with entry_type, category, debit/credit, etc.
        validate: If True, raise ValueError when debits != credits.

    Returns:
        List of created LedgerEntry instances.
    """
    total_debit = sum(e.get("debit", 0) or 0 for e in entries)
    total_credit = sum(e.get("credit", 0) or 0 for e in entries)
    if validate and total_debit != total_credit:
        raise ValueError(
            f"Unbalanced transaction {transaction_id}: "
            f"debit={total_debit} credit={total_credit}"
        )
    result = []
    for e in entries:
        entry = cls(transaction_id=transaction_id, **e)
        result.append(entry)
    return result


def ledger_validate_transaction(cls, transaction_id):
    """Check that debits == credits for a given transaction_id."""
    entries = [e for e in cls.instances() if getattr(e, "transaction_id", None) == transaction_id]
    total_debit = sum(getattr(e, "debit", 0) or 0 for e in entries)
    total_credit = sum(getattr(e, "credit", 0) or 0 for e in entries)
    return total_debit == total_credit


def ledger_get_balance(cls, entry_type, category=None, fund=None):
    """Calculate net balance (debit - credit) for an entry type."""
    total = 0
    for e in cls.instances():
        if getattr(e, "entry_type", None) != entry_type:
            continue
        if category and getattr(e, "category", None) != category:
            continue
        if fund and getattr(e, "fund", None) is not fund:
            continue
        total += (getattr(e, "debit", 0) or 0) - (getattr(e, "credit", 0) or 0)
    return total


def ledger_amount(self):
    """Return the non-zero amount (debit or credit)."""
    d = getattr(self, "debit", 0) or 0
    c = getattr(self, "credit", 0) or 0
    return d if d else c


def ledger_is_debit(self):
    return (getattr(self, "debit", 0) or 0) > 0


def ledger_is_credit(self):
    return (getattr(self, "credit", 0) or 0) > 0


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

def budget_variance(self):
    """Calculate budget variance (actual - planned)."""
    return (getattr(self, "actual_amount", 0) or 0) - (getattr(self, "planned_amount", 0) or 0)


def budget_variance_percent(self):
    """Calculate variance as percentage of planned."""
    planned = getattr(self, "planned_amount", 0) or 0
    if planned == 0:
        return 0.0
    return (self.variance() / planned) * 100.0


def budget_update_actual(self, amount):
    """Add to actual amount."""
    self.actual_amount = (getattr(self, "actual_amount", 0) or 0) + amount


# ---------------------------------------------------------------------------
# FiscalPeriod
# ---------------------------------------------------------------------------

def fiscal_period_is_open(self):
    return getattr(self, "status", None) == "open"


def fiscal_period_close(self):
    self.status = "closed"


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

def invoice_mark_paid(self):
    """Mark this invoice as paid with current timestamp."""
    from datetime import datetime, timezone
    self.status = "Paid"
    self.paid_on = datetime.now(timezone.utc).isoformat()


def invoice_get_amount_raw(self):
    """Get the invoice amount in raw satoshis."""
    amount = getattr(self, "amount", 0) or 0
    return int(amount * 100_000_000)


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

def token_is_enabled(self):
    return getattr(self, "enabled", "true") == "true"


# ---------------------------------------------------------------------------
# JusticeSystem / Court / Case helpers
# ---------------------------------------------------------------------------

def is_active(self):
    return getattr(self, "status", None) == "active"


def case_is_open(self):
    return getattr(self, "status", None) in ("filed", "assigned", "in_progress")


def case_has_verdict(self):
    return getattr(self, "verdict", None) is not None


def case_can_appeal(self):
    return self.has_verdict() and getattr(self, "status", None) != "appealed"


def verdict_is_appealed(self):
    return getattr(self, "appeal", None) is not None


def verdict_total_penalty_amount(self):
    total = 0.0
    for p in getattr(self, "penalties", []):
        total += getattr(p, "amount", 0) or 0
    return total


def penalty_is_financial(self):
    return getattr(self, "penalty_type", None) in ("fine", "restitution")


def penalty_is_pending(self):
    return getattr(self, "status", None) == "pending"


def appeal_is_pending(self):
    return getattr(self, "status", None) in ("filed", "under_review")


def appeal_was_granted(self):
    return getattr(self, "status", None) == "granted"


def court_can_hear_appeal(self):
    level = getattr(self, "level", None)
    return level in ("appellate", "supreme") and self.is_active()


# ---------------------------------------------------------------------------
# UserProfile
# ---------------------------------------------------------------------------

def userprofile_add(self, operation):
    current = getattr(self, "allowed_to", "") or ""
    ops = [o.strip() for o in current.split(",") if o.strip()]
    if operation not in ops:
        ops.append(operation)
    self.allowed_to = ",".join(ops)


def userprofile_remove(self, operation):
    current = getattr(self, "allowed_to", "") or ""
    ops = [o.strip() for o in current.split(",") if o.strip()]
    if operation in ops:
        ops.remove(operation)
    self.allowed_to = ",".join(ops)


def userprofile_is_allowed(self, operation):
    current = getattr(self, "allowed_to", "") or ""
    ops = [o.strip() for o in current.split(",") if o.strip()]
    return "ALL" in ops or operation in ops


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

def task_new_task_execution(self):
    """Create a new TaskExecution for this task."""
    # Import here to avoid circular ref at module level
    from . import ggg_module
    te = ggg_module.TaskExecution(name=f"exec_{self._id}", task=self, status="idle")
    return te
