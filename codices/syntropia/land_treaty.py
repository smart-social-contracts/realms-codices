"""
Land Treaty Codex
Manages land lease treaties between the Realm and host states.

A treaty formalises the terms under which a realm leases territory from an
existing sovereign state. Treaties go through a lifecycle:

  draft       — Being negotiated, not yet binding
  signed      — Both parties signed, awaiting ratification
  ratified    — Ratified by Realm parliament and Host State authority
  active      — In force, land is available to the Realm
  suspended   — Temporarily suspended (e.g. dispute, force majeure)
  terminated  — Treaty ended, wind-down complete

This codex ties into the realm lifecycle: marking a treaty as "active"
satisfies the land_acquired precondition for advancing from beta to production.
"""

from ggg import Proposal, User, Land, LandType, Zone
from datetime import datetime, timedelta
import json


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TREATY_STAGES = ["draft", "signed", "ratified", "active", "suspended", "terminated"]

DEFAULT_TERM_YEARS = 50
DEFAULT_WIND_DOWN_MONTHS = 24


# ---------------------------------------------------------------------------
# Treaty CRUD
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Helpers — treaty data stored in Proposal.description (max 2048 chars)
# ---------------------------------------------------------------------------

def _load_treaty(proposal) -> dict:
    """Load treaty dict from proposal.description (JSON)."""
    try:
        return json.loads(proposal.description) if proposal.description else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _save_treaty(proposal, treaty: dict):
    """Save treaty dict to proposal.description."""
    proposal.description = json.dumps(treaty, separators=(",", ":"))


def _find_treaty_proposal(treaty_id: str):
    """Find a treaty Proposal by proposal_id."""
    return Proposal[treaty_id]


def create_treaty(host_state_name: str, territory_description: str,
                  term_years: int = DEFAULT_TERM_YEARS,
                  annual_fee: int = 0, fee_currency: str = "USD",
                  revenue_share_pct: float = 0.0,
                  security_deposit: int = 0,
                  territory_area_km2: float = 0.0,
                  coordinates: dict = None,
                  reserved_powers: list = None,
                  criminal_offences_annex: list = None,
                  notes: str = "") -> dict:
    """Create a new treaty in draft status.

    The treaty is stored as a Proposal with branch='treaty'.
    """
    now = datetime.now()

    treaty_data = {
        "hs": host_state_name,
        "td": territory_description,
        "km2": territory_area_km2,
        "st": "draft",
        "ty": term_years,
        "af": annual_fee,
        "fc": fee_currency,
        "rsp": revenue_share_pct,
        "sd": security_deposit,
        "pay": [],
        "hist": [{"ev": "created", "at": now.isoformat()}],
    }

    existing = Proposal.instances()
    num = len([p for p in existing if p.metadata == "branch:treaty"]) + 1
    pid = "treaty_" + str(num).zfill(3)

    proposal = Proposal(
        proposal_id=pid,
        title="Land Lease Treaty: " + host_state_name,
        description=json.dumps(treaty_data, separators=(",", ":")),
        status="draft",
        metadata="branch:treaty",
    )

    return {
        "treaty_id": pid,
        "host_state": host_state_name,
        "territory_description": territory_description,
        "territory_area_km2": territory_area_km2,
        "status": "draft",
        "term_years": term_years,
        "annual_fee": annual_fee,
    }


def get_treaty(treaty_id: str) -> dict:
    """Retrieve full treaty details."""
    proposal = _find_treaty_proposal(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    if proposal.metadata != "branch:treaty":
        return {"error": "Proposal is not a treaty"}

    treaty = _load_treaty(proposal)
    treaty["treaty_id"] = treaty_id
    return treaty


# ---------------------------------------------------------------------------
# Treaty Lifecycle
# ---------------------------------------------------------------------------

def sign_treaty(treaty_id: str, host_state_signatory: str,
                realm_signatory: str) -> dict:
    """Record signatures from both parties. Advances draft → signed."""
    proposal = _find_treaty_proposal(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    treaty = _load_treaty(proposal)

    if treaty.get("st") != "draft":
        return {"error": f"Treaty must be in draft to sign (current: {treaty.get('st')})"}

    now = datetime.now()
    treaty["st"] = "signed"
    treaty["hist"].append({"ev": "signed", "at": now.isoformat()})
    _save_treaty(proposal, treaty)
    proposal.status = "signed"

    return {"treaty_id": treaty_id, "status": "signed"}


def ratify_treaty(treaty_id: str, ratified_by: str = "parliament") -> dict:
    """Ratify a signed treaty. Advances signed → ratified."""
    proposal = _find_treaty_proposal(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    treaty = _load_treaty(proposal)

    if treaty.get("st") != "signed":
        return {"error": f"Treaty must be signed before ratification (current: {treaty.get('st')})"}

    now = datetime.now()
    treaty["st"] = "ratified"
    treaty["hist"].append({"ev": "ratified", "at": now.isoformat()})
    _save_treaty(proposal, treaty)
    proposal.status = "ratified"

    return {"treaty_id": treaty_id, "status": "ratified"}


def activate_treaty(treaty_id: str) -> dict:
    """Activate a ratified treaty. Advances ratified → active.

    Also marks land as acquired in the realm lifecycle so the realm can
    advance from beta to production.
    """
    proposal = _find_treaty_proposal(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    treaty = _load_treaty(proposal)

    if treaty.get("st") != "ratified":
        return {"error": f"Treaty must be ratified before activation (current: {treaty.get('st')})"}

    now = datetime.now()
    term_years = treaty.get("ty", DEFAULT_TERM_YEARS)
    treaty["st"] = "active"
    treaty["hist"].append({"ev": "activated", "at": now.isoformat()})
    _save_treaty(proposal, treaty)
    proposal.status = "active"

    # Mark land as acquired in realm lifecycle
    try:
        from . import realm_lifecycle
        realm_lifecycle.mark_land_acquired(
            details=f"Treaty {treaty_id} with {treaty.get('hs', 'unknown')} — "
                    f"{treaty.get('km2', 0)} km²"
        )
    except Exception:
        pass  # lifecycle codex may not be loaded

    end_date = (now + timedelta(days=term_years * 365)).isoformat()
    return {
        "treaty_id": treaty_id,
        "status": "active",
        "start_date": now.isoformat(),
        "end_date": end_date,
    }


def suspend_treaty(treaty_id: str, reason: str = "") -> dict:
    """Suspend an active treaty (e.g. dispute, force majeure)."""
    proposal = _find_treaty_proposal(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    treaty = _load_treaty(proposal)

    if treaty.get("st") != "active":
        return {"error": "Only active treaties can be suspended"}

    now = datetime.now()
    treaty["st"] = "suspended"
    treaty["hist"].append({"ev": "suspended", "at": now.isoformat()})
    _save_treaty(proposal, treaty)
    proposal.status = "suspended"

    return {"treaty_id": treaty_id, "status": "suspended", "reason": reason}


def reactivate_treaty(treaty_id: str, reason: str = "") -> dict:
    """Reactivate a suspended treaty."""
    proposal = _find_treaty_proposal(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    treaty = _load_treaty(proposal)

    if treaty.get("st") != "suspended":
        return {"error": "Only suspended treaties can be reactivated"}

    now = datetime.now()
    treaty["st"] = "active"
    treaty["hist"].append({"ev": "reactivated", "at": now.isoformat()})
    _save_treaty(proposal, treaty)
    proposal.status = "active"

    return {"treaty_id": treaty_id, "status": "active"}


def terminate_treaty(treaty_id: str, reason: str = "",
                     immediate: bool = False) -> dict:
    """Terminate a treaty. Triggers wind-down unless immediate."""
    proposal = _find_treaty_proposal(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    treaty = _load_treaty(proposal)

    if treaty.get("st") in ("draft", "terminated"):
        return {"error": f"Cannot terminate a treaty in '{treaty.get('st')}' status"}

    now = datetime.now()
    treaty["st"] = "terminated"
    treaty["hist"].append({"ev": "terminated", "at": now.isoformat()})
    _save_treaty(proposal, treaty)
    proposal.status = "terminated"

    return {
        "treaty_id": treaty_id,
        "status": "terminated",
    }


# ---------------------------------------------------------------------------
# Financial — Payment Tracking
# ---------------------------------------------------------------------------

def record_payment(treaty_id: str, amount: int, currency: str = "",
                   period: str = "", notes: str = "") -> dict:
    """Record a lease fee payment against the treaty."""
    proposal = _find_treaty_proposal(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    treaty = _load_treaty(proposal)

    payment = {
        "a": amount,
        "c": currency or treaty.get("fc", "USD"),
        "p": period,
        "at": datetime.now().isoformat(),
    }
    treaty.setdefault("pay", []).append(payment)
    _save_treaty(proposal, treaty)

    return {
        "treaty_id": treaty_id,
        "payment_index": len(treaty["pay"]) - 1,
        "amount": amount,
    }


def get_payment_summary(treaty_id: str) -> dict:
    """Return payment history and balance for a treaty."""
    proposal = _find_treaty_proposal(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    treaty = _load_treaty(proposal)
    payments = treaty.get("pay", [])
    total_paid = sum(p.get("a", 0) for p in payments)

    return {
        "treaty_id": treaty_id,
        "annual_fee": treaty.get("af", 0),
        "total_paid": total_paid,
        "payment_count": len(payments),
    }


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def list_treaties(status: str = None) -> list:
    """List all treaties, optionally filtered by status."""
    results = []
    for proposal in Proposal.instances():
        if proposal.metadata != "branch:treaty":
            continue
        treaty = _load_treaty(proposal)
        if status and treaty.get("st") != status:
            continue
        results.append({
            "treaty_id": proposal.proposal_id,
            "host_state": treaty.get("hs"),
            "status": treaty.get("st"),
            "territory_area_km2": treaty.get("km2"),
            "annual_fee": treaty.get("af"),
        })
    return results


def get_active_treaty() -> dict:
    """Return the first active treaty (convenience for single-treaty realms)."""
    active = list_treaties(status="active")
    if not active:
        return {"error": "No active treaty found"}
    return get_treaty(active[0]["treaty_id"])


# Main execution
if __name__ == "__main__":
    treaty = create_treaty(
        host_state_name="Republic of Example",
        territory_description="50 km² coastal zone in the southern province",
        term_years=50,
        annual_fee=500_000,
        fee_currency="USD",
        revenue_share_pct=5.0,
        security_deposit=2_000_000,
        territory_area_km2=50.0,
    )
    print(json.dumps(treaty, indent=2))
