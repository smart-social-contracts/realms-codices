"""
Syntropia Realm Lifecycle Codex
Manages the realm through its full lifecycle stages:

  alpha        — Realm announced. Users register interest with ZK proof of
                 unique personhood (Rarimo passport extension) and a refundable
                 deposit. Goal: reach critical mass (e.g. 10 000 users).
                 Deposits can be withdrawn at any time.

  beta         — Critical mass reached. Deposits are now locked.
                 Infrastructure built: electricity, roads, buildings, hospitals.
                 Service-provider licenses auctioned, land allocated.
                 New users can still join (their deposits lock immediately).

  production   — Infrastructure ready. Citizens move in. Taxes, welfare,
                 budgets, and governance run normally. Realm fully operational
                 and self-sustaining.

  deprecation  — Realm is winding down. No new members accepted.
                 Services continue for existing citizens while migration or
                 shutdown is organised. Providers fulfill remaining contracts.

  terminated   — Realm is closed. Remaining treasury funds are distributed
                 back to citizens. All licenses revoked. Read-only archive.

Transitions:
  alpha → beta           (auto when critical mass reached, or by governance vote)
  beta → production      (governance vote after land, infrastructure & providers secured)
  production → deprecation (governance vote)
  deprecation → terminated (governance vote after wind-down complete)
"""

from ggg import Realm, RealmStatus, Proposal, User, Member, Transfer, Instrument, Notification
from datetime import datetime
import json

# NOTE: Registration requires ZK proof of unique personhood via Rarimo passport
# extension. The ZK proof hash is stored in Member.criminal_record field for
# deduplication (see membership.py).

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAGES = [
    RealmStatus.ALPHA,
    RealmStatus.BETA,
    RealmStatus.PRODUCTION,
    RealmStatus.DEPRECATION,
    RealmStatus.TERMINATED,
]

STAGE_DESCRIPTIONS = {
    RealmStatus.ALPHA:        "Gathering interest — ZK proof + deposit, refundable",
    RealmStatus.BETA:         "Deposits locked — infrastructure, auctions & land",
    RealmStatus.PRODUCTION:   "Fully operational and self-sustaining",
    RealmStatus.DEPRECATION:  "Winding down — no new members",
    RealmStatus.TERMINATED:   "Closed — read-only archive",
}

DEFAULT_CRITICAL_MASS = 10_000  # users needed to auto-advance from alpha → beta
DEFAULT_DEPOSIT_AMOUNT = 100    # refundable deposit in realm token units


# ---------------------------------------------------------------------------
# State Helpers
# ---------------------------------------------------------------------------

def _get_realm():
    """Return the first (and usually only) Realm instance."""
    instances = Realm.instances()
    return list(instances)[0] if instances else None


def _get_lifecycle_data(realm) -> dict:
    """Read lifecycle metadata from realm.manifest_data (extra fields beyond status)."""
    try:
        meta = json.loads(realm.manifest_data) if realm.manifest_data else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}
    return meta.get("lifecycle", {})


def _save_lifecycle_data(realm, lifecycle: dict):
    """Write lifecycle metadata back to realm.manifest_data."""
    try:
        meta = json.loads(realm.manifest_data) if realm.manifest_data else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}
    meta["lifecycle"] = lifecycle
    realm.manifest_data = json.dumps(meta)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def initialize_lifecycle(critical_mass: int = DEFAULT_CRITICAL_MASS,
                         deposit_amount: int = DEFAULT_DEPOSIT_AMOUNT) -> dict:
    """Set the realm to alpha stage. Call once at realm creation."""
    realm = _get_realm()
    if not realm:
        return {"error": "No realm found"}

    realm.status = RealmStatus.ALPHA

    lifecycle = {
        "critical_mass": critical_mass,
        "deposit_amount": deposit_amount,
        "registered_users": 0,
        "total_deposits": 0,
        "deposits_locked": False,
        "land_acquired": False,
        "infrastructure_ready": False,
        "providers_ready": False,
        "history": [
            {"stage": RealmStatus.ALPHA, "at": datetime.now().isoformat(), "reason": "Realm created"}
        ],
    }
    _save_lifecycle_data(realm, lifecycle)

    return {"stage": realm.status, **lifecycle}


# ---------------------------------------------------------------------------
# Alpha Stage — interest registration & refundable deposits
# ---------------------------------------------------------------------------

def register_interest(user_id: str) -> dict:
    """A user registers interest and pays the refundable deposit."""
    realm = _get_realm()
    if not realm:
        return {"error": "No realm found"}

    if realm.status in (RealmStatus.DEPRECATION, RealmStatus.TERMINATED):
        return {"error": f"Realm is in '{realm.status}' — no new registrations accepted"}

    lc = _get_lifecycle_data(realm)
    deposit = lc.get("deposit_amount", DEFAULT_DEPOSIT_AMOUNT)

    user = User[user_id]
    if not user:
        return {"error": "User not found"}

    system_user = User["system"]
    instrument = Instrument["Realm Token"]
    if not system_user or not instrument:
        return {"error": "System user or instrument not found"}

    # Collect deposit
    Transfer(
        from_user=user,
        to_user=system_user,
        instrument=instrument,
        amount=deposit
    )

    lc["registered_users"] = lc.get("registered_users", 0) + 1
    lc["total_deposits"] = lc.get("total_deposits", 0) + deposit

    result = {
        "user_id": user_id,
        "deposit": deposit,
        "refundable": not lc.get("deposits_locked", False),
        "registered_users": lc["registered_users"],
        "critical_mass": lc.get("critical_mass", DEFAULT_CRITICAL_MASS),
    }

    # Check critical mass auto-transition
    if realm.status == RealmStatus.ALPHA and lc["registered_users"] >= lc.get("critical_mass", DEFAULT_CRITICAL_MASS):
        lc = _advance_to_beta(realm, lc)
        result["stage_advanced"] = RealmStatus.BETA

    _save_lifecycle_data(realm, lc)
    return result


def withdraw_deposit(user_id: str) -> dict:
    """Withdraw the refundable deposit (only allowed in alpha stage)."""
    realm = _get_realm()
    if not realm:
        return {"error": "No realm found"}

    lc = _get_lifecycle_data(realm)

    if lc.get("deposits_locked", False):
        return {"error": "Deposits are locked — withdrawal not allowed"}

    if realm.status != RealmStatus.ALPHA:
        return {"error": f"Withdrawals only allowed in alpha stage (current: {realm.status})"}

    deposit = lc.get("deposit_amount", DEFAULT_DEPOSIT_AMOUNT)
    user = User[user_id]
    system_user = User["system"]
    instrument = Instrument["Realm Token"]

    if not all([user, system_user, instrument]):
        return {"error": "Cannot resolve user, system, or instrument"}

    Transfer(
        from_user=system_user,
        to_user=user,
        instrument=instrument,
        amount=deposit
    )

    lc["registered_users"] = max(0, lc.get("registered_users", 0) - 1)
    lc["total_deposits"] = max(0, lc.get("total_deposits", 0) - deposit)
    _save_lifecycle_data(realm, lc)

    return {"user_id": user_id, "refunded": deposit, "stage": realm.status}


# ---------------------------------------------------------------------------
# Stage Transitions
# ---------------------------------------------------------------------------

def _advance_to_beta(realm, lc: dict) -> dict:
    """Internal: transition from alpha to beta."""
    realm.status = RealmStatus.BETA
    lc["deposits_locked"] = True
    lc["history"].append({
        "stage": RealmStatus.BETA,
        "at": datetime.now().isoformat(),
        "reason": f"Critical mass reached ({lc['registered_users']} users)",
    })
    return lc


def advance_stage(reason: str = "") -> dict:
    """Advance the realm to the next lifecycle stage (governance-triggered).

    Allowed transitions:
      alpha → beta, beta → production, production → deprecation,
      deprecation → terminated.
    """
    realm = _get_realm()
    if not realm:
        return {"error": "No realm found"}

    current = realm.status or RealmStatus.ALPHA
    lc = _get_lifecycle_data(realm)

    idx = STAGES.index(current) if current in STAGES else -1
    if idx < 0 or idx >= len(STAGES) - 1:
        return {"error": f"Cannot advance from '{current}' — already at final stage or unknown"}

    next_stage = STAGES[idx + 1]

    # Stage-specific pre-conditions
    if next_stage == RealmStatus.BETA:
        lc["deposits_locked"] = True

    if next_stage == RealmStatus.PRODUCTION:
        if not lc.get("land_acquired"):
            return {"error": "Cannot enter production — land has not been acquired"}
        if not lc.get("infrastructure_ready"):
            return {"error": "Cannot enter production — infrastructure not ready"}
        if not lc.get("providers_ready"):
            return {"error": "Cannot enter production — service providers not ready"}

    realm.status = next_stage
    lc["history"].append({
        "stage": next_stage,
        "at": datetime.now().isoformat(),
        "reason": reason or "Advanced by governance vote",
    })

    if next_stage == RealmStatus.TERMINATED:
        lc["terminated_at"] = datetime.now().isoformat()

    _save_lifecycle_data(realm, lc)

    return {"previous": current, "current": next_stage, "reason": reason}


# ---------------------------------------------------------------------------
# Beta Stage — land & provider readiness flags
# ---------------------------------------------------------------------------

def mark_land_acquired(details: str = "") -> dict:
    """Mark that the realm has acquired its physical/virtual land."""
    realm = _get_realm()
    if not realm:
        return {"error": "No realm found"}

    lc = _get_lifecycle_data(realm)
    lc["land_acquired"] = True
    lc["land_details"] = details
    lc["land_acquired_at"] = datetime.now().isoformat()
    _save_lifecycle_data(realm, lc)

    return {"land_acquired": True, "details": details}


def mark_infrastructure_ready(details: str = "") -> dict:
    """Mark that infrastructure is built (electricity, roads, buildings, hospitals)."""
    realm = _get_realm()
    if not realm:
        return {"error": "No realm found"}

    lc = _get_lifecycle_data(realm)
    lc["infrastructure_ready"] = True
    lc["infrastructure_details"] = details
    lc["infrastructure_ready_at"] = datetime.now().isoformat()
    _save_lifecycle_data(realm, lc)

    return {"infrastructure_ready": True, "details": details}


def mark_providers_ready(details: str = "") -> dict:
    """Mark that essential service providers have been contracted."""
    realm = _get_realm()
    if not realm:
        return {"error": "No realm found"}

    lc = _get_lifecycle_data(realm)
    lc["providers_ready"] = True
    lc["providers_details"] = details
    lc["providers_ready_at"] = datetime.now().isoformat()
    _save_lifecycle_data(realm, lc)

    return {"providers_ready": True, "details": details}


# ---------------------------------------------------------------------------
# Deprecation & Termination
# ---------------------------------------------------------------------------

def distribute_remaining_funds() -> dict:
    """Distribute remaining treasury funds back to citizens (termination step)."""
    realm = _get_realm()
    if not realm:
        return {"error": "No realm found"}

    if realm.status not in (RealmStatus.DEPRECATION, RealmStatus.TERMINATED):
        return {"error": "Fund distribution only allowed during deprecation or termination"}

    members = Member.instances()
    system_user = User["system"]
    instrument = Instrument["Realm Token"]

    if not system_user or not instrument:
        return {"error": "System user or instrument not found"}

    member_list = list(members)
    member_count = len(member_list)
    if member_count == 0:
        return {"error": "No members to distribute to"}

    lc = _get_lifecycle_data(realm)
    total_deposits = lc.get("total_deposits", 0)
    per_member = total_deposits // member_count if member_count > 0 else 0

    distributed = 0
    for member in member_list:
        if member.user:
            Transfer(
                from_user=system_user,
                to_user=member.user,
                instrument=instrument,
                amount=per_member
            )
            distributed += 1

    return {
        "total_distributed": per_member * distributed,
        "per_member": per_member,
        "members_paid": distributed,
    }


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_lifecycle_status() -> dict:
    """Return current lifecycle state."""
    realm = _get_realm()
    if not realm:
        return {"error": "No realm found"}

    lc = _get_lifecycle_data(realm)

    return {
        "stage": realm.status,
        "description": STAGE_DESCRIPTIONS.get(realm.status, ""),
        "registered_users": lc.get("registered_users", 0),
        "critical_mass": lc.get("critical_mass", DEFAULT_CRITICAL_MASS),
        "deposits_locked": lc.get("deposits_locked", False),
        "land_acquired": lc.get("land_acquired", False),
        "infrastructure_ready": lc.get("infrastructure_ready", False),
        "providers_ready": lc.get("providers_ready", False),
        "history": lc.get("history", []),
    }


def get_stage() -> str:
    """Return just the current stage name."""
    realm = _get_realm()
    if not realm:
        return "unknown"
    return realm.status or "unknown"


# Main execution
if __name__ == "__main__":
    lc = initialize_lifecycle(critical_mass=10_000, deposit_amount=100)
    print(json.dumps(lc, indent=2))
