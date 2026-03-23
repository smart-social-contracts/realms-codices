"""
Mock ``ggg`` module.

When injected into ``sys.modules["ggg"]``, any codex doing
``from ggg import User, Proposal, Fund`` will get these in-memory classes.

Entity classes are generated from the canonical type stubs in
``realms/typings/ggg/__init__.pyi``.  Enum/constant classes mirror the
real values so that ``FundType.GENERAL == "general"`` etc.
"""

from .entity import MockEntity
from . import domain_methods as _dm


# ═══════════════════════════════════════════════════════════════════════════
# Helper to build entity subclasses concisely
# ═══════════════════════════════════════════════════════════════════════════

def _entity(name, alias=None, methods=None):
    attrs = {"__alias__": alias}
    if methods:
        attrs.update(methods)
    cls = type(name, (MockEntity,), attrs)
    return cls


# ═══════════════════════════════════════════════════════════════════════════
# Enum / Constant classes
# ═══════════════════════════════════════════════════════════════════════════

class RealmStatus:
    REGISTRATION = "registration"
    ACCREDITATION = "accreditation"
    OPERATIONAL = "operational"
    STABLE = "stable"
    DEPRECATION = "deprecation"
    TERMINATED = "terminated"
    # Aliases used in realm.py
    ALPHA = "alpha"
    BETA = "beta"
    PRODUCTION = "production"


class FundType:
    GENERAL = "general"
    SPECIAL_REVENUE = "special_revenue"
    CAPITAL_PROJECTS = "capital_projects"
    DEBT_SERVICE = "debt_service"
    ENTERPRISE = "enterprise"
    INTERNAL_SERVICE = "internal_service"
    TRUST = "trust"
    AGENCY = "agency"


class FiscalPeriodStatus:
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class BudgetStatus:
    DRAFT = "draft"
    PROPOSED = "proposed"
    ADOPTED = "adopted"
    AMENDED = "amended"
    CLOSED = "closed"


class EntryType:
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class Category:
    # Revenues
    TAX = "tax"
    FEE = "fee"
    GRANT = "grant"
    FINE = "fine"
    SERVICE = "service"
    INVESTMENT_INCOME = "investment_income"
    INTERGOVERNMENTAL = "intergovernmental"
    # Expenses
    PERSONNEL = "personnel"
    SUPPLIES = "supplies"
    SERVICES = "services"
    CAPITAL = "capital"
    DEBT = "debt"
    TRANSFER_OUT = "transfer_out"
    # Assets
    CASH = "cash"
    RECEIVABLE = "receivable"
    PROPERTY = "property"
    EQUIPMENT = "equipment"
    INVENTORY = "inventory"
    # Liabilities
    PAYABLE = "payable"
    BOND = "bond"
    LOAN = "loan"
    DEFERRED_REVENUE = "deferred_revenue"
    # Equity
    FUND_BALANCE = "fund_balance"
    RETAINED_EARNINGS = "retained_earnings"


class LandType:
    RESIDENTIAL = "residential"
    AGRICULTURAL = "agricultural"
    INDUSTRIAL = "industrial"
    COMMERCIAL = "commercial"
    UNASSIGNED = "unassigned"


class LandStatus:
    ACTIVE = "active"
    DISPUTED = "disputed"
    TRANSFERRED = "transferred"
    REVOKED = "revoked"


class LicenseType:
    COURT = "court"
    CHURCH = "church"
    JUSTICE_PROVIDER = "justice_provider"


class JusticeSystemType:
    PUBLIC = "public"
    PRIVATE = "private"
    HYBRID = "hybrid"


class CourtLevel:
    FIRST_INSTANCE = "first_instance"
    APPELLATE = "appellate"
    SUPREME = "supreme"
    SPECIALIZED = "specialized"


class CaseStatus:
    FILED = "filed"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    VERDICT_ISSUED = "verdict_issued"
    CLOSED = "closed"
    APPEALED = "appealed"
    DISMISSED = "dismissed"


class PenaltyType:
    FINE = "fine"
    RESTITUTION = "restitution"
    COMMUNITY_SERVICE = "community_service"
    SUSPENSION = "suspension"
    REVOCATION = "revocation"
    INJUNCTION = "injunction"
    OTHER = "other"


class AppealStatus:
    FILED = "filed"
    UNDER_REVIEW = "under_review"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"


class QuarterStatus:
    ACTIVE = "active"
    SUSPENDED = "suspended"
    SPLITTING = "splitting"
    MERGING = "merging"


class Operations:
    ALL = "ALL"
    USER_ADD = "USER_ADD"
    USER_EDIT = "USER_EDIT"
    USER_DELETE = "USER_DELETE"
    ORGANIZATION_ADD = "ORGANIZATION_ADD"
    ORGANIZATION_EDIT = "ORGANIZATION_EDIT"
    ORGANIZATION_DELETE = "ORGANIZATION_DELETE"
    TRANSFER_CREATE = "TRANSFER_CREATE"
    TRANSFER_REVERT = "TRANSFER_REVERT"
    TASK_CREATE = "TASK_CREATE"
    TASK_EDIT = "TASK_EDIT"
    TASK_DELETE = "TASK_DELETE"
    TASK_RUN = "TASK_RUN"
    TASK_SCHEDULE = "TASK_SCHEDULE"
    TASK_CANCEL = "TASK_CANCEL"


class Profiles:
    ADMIN = {"name": "admin", "allowed_to": "ALL"}
    MEMBER = {"name": "member", "allowed_to": ""}


# ═══════════════════════════════════════════════════════════════════════════
# Entity classes
# ═══════════════════════════════════════════════════════════════════════════

# --- System ---
User = _entity("User", alias="id")
Human = _entity("Human", alias="name")
Identity = _entity("Identity")

UserProfile = _entity("UserProfile", alias="name", methods={
    "add": _dm.userprofile_add,
    "remove": _dm.userprofile_remove,
    "is_allowed": _dm.userprofile_is_allowed,
})

# --- Governance ---
Member = _entity("Member", alias="id")
Proposal = _entity("Proposal", alias="proposal_id")
Vote = _entity("Vote")
Notification = _entity("Notification")
Codex = _entity("Codex", alias="name")
Permission = _entity("Permission")

# --- Realm ---
Realm = _entity("Realm", alias="name")
Calendar = _entity("Calendar", alias="name")

# --- Finance ---
Treasury = _entity("Treasury", alias="name")
Instrument = _entity("Instrument", alias="name")
Transfer = _entity("Transfer", alias="id")
Balance = _entity("Balance", alias="id")

Invoice = _entity("Invoice", alias="id", methods={
    "mark_paid": _dm.invoice_mark_paid,
    "get_amount_raw": _dm.invoice_get_amount_raw,
})

PaymentAccount = _entity("PaymentAccount", alias="id")

Token = _entity("Token", alias="id", methods={
    "is_enabled": _dm.token_is_enabled,
})

Fund = _entity("Fund", alias="code", methods={})
FiscalPeriod = _entity("FiscalPeriod", alias="id", methods={
    "is_open": _dm.fiscal_period_is_open,
    "close": _dm.fiscal_period_close,
})
Budget = _entity("Budget", alias="id", methods={
    "variance": _dm.budget_variance,
    "variance_percent": _dm.budget_variance_percent,
    "update_actual": _dm.budget_update_actual,
})
LedgerEntry = _entity("LedgerEntry", alias="id", methods={
    "amount": _dm.ledger_amount,
    "is_debit": _dm.ledger_is_debit,
    "is_credit": _dm.ledger_is_credit,
})
# Attach class methods separately (type() doesn't set classmethods via dict)
LedgerEntry.create_transaction = classmethod(_dm.ledger_create_transaction)
LedgerEntry.validate_transaction = classmethod(_dm.ledger_validate_transaction)
LedgerEntry.get_balance = classmethod(_dm.ledger_get_balance)

# --- Territory ---
Land = _entity("Land", alias="id")
Zone = _entity("Zone", alias="h3_index")
Organization = _entity("Organization", alias="name")
License = _entity("License", alias="name")
Mandate = _entity("Mandate", alias="name")
Contract = _entity("Contract", alias="name")
Registry = _entity("Registry", alias="name")
Trade = _entity("Trade")

# --- Task system ---
Call = _entity("Call")
TaskStep = _entity("TaskStep")
TaskExecution = _entity("TaskExecution", alias="name")
TaskSchedule = _entity("TaskSchedule", alias="name")
Task = _entity("Task", alias="name", methods={
    "new_task_execution": _dm.task_new_task_execution,
})

# --- Justice system ---
JusticeSystem = _entity("JusticeSystem", alias="name", methods={
    "is_active": _dm.is_active,
})
Court = _entity("Court", alias="name", methods={
    "is_active": _dm.is_active,
    "can_hear_appeal": _dm.court_can_hear_appeal,
})
Judge = _entity("Judge", alias="id", methods={
    "is_active": _dm.is_active,
})
Case = _entity("Case", alias="case_number", methods={
    "is_open": _dm.case_is_open,
    "has_verdict": _dm.case_has_verdict,
    "can_appeal": _dm.case_can_appeal,
})
Verdict = _entity("Verdict", alias="id", methods={
    "is_appealed": _dm.verdict_is_appealed,
    "total_penalty_amount": _dm.verdict_total_penalty_amount,
})
Penalty = _entity("Penalty", alias="id", methods={
    "is_financial": _dm.penalty_is_financial,
    "is_pending": _dm.penalty_is_pending,
})
Appeal = _entity("Appeal", alias="id", methods={
    "is_pending": _dm.appeal_is_pending,
    "was_granted": _dm.appeal_was_granted,
})

# --- Federation ---
Quarter = _entity("Quarter", alias="name")

# --- Services ---
Service = _entity("Service", alias="service_id")

# --- Disputes (legacy, kept for backward compat) ---
Dispute = _entity("Dispute", alias="dispute_id")
