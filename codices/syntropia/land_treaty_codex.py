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
        "host_state": host_state_name,
        "territory_description": territory_description,
        "territory_area_km2": territory_area_km2,
        "coordinates": coordinates or {},
        "status": "draft",

        # Duration
        "term_years": term_years,
        "start_date": None,
        "end_date": None,
        "wind_down_months": DEFAULT_WIND_DOWN_MONTHS,

        # Financial
        "annual_fee": annual_fee,
        "fee_currency": fee_currency,
        "revenue_share_pct": revenue_share_pct,
        "security_deposit": security_deposit,
        "payments": [],

        # Governance
        "reserved_powers": reserved_powers or [
            "national_defence",
            "immigration_border_control",
            "international_treaties",
            "criminal_law_annex_b",
            "environmental_standards",
        ],
        "criminal_offences_annex": criminal_offences_annex or [
            "murder", "trafficking", "terrorism", "money_laundering",
        ],

        # Signatures
        "host_state_signatory": None,
        "realm_signatory": None,
        "signed_at": None,
        "ratified_at": None,
        "activated_at": None,

        # History
        "history": [
            {"event": "created", "at": now.isoformat(), "notes": notes}
        ],
    }

    proposal = Proposal(
        metadata=json.dumps({
            "title": f"Land Lease Treaty — {host_state_name}",
            "description": territory_description,
            "branch": "treaty",
            "status": "draft",
            "treaty": treaty_data,
        })
    )

    treaty_data["treaty_id"] = proposal.id
    return treaty_data


def get_treaty(treaty_id: str) -> dict:
    """Retrieve full treaty details."""
    proposal = Proposal.get(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    metadata = json.loads(proposal.metadata)
    if metadata.get("branch") != "treaty":
        return {"error": "Proposal is not a treaty"}

    treaty = metadata.get("treaty", {})
    treaty["treaty_id"] = treaty_id
    return treaty


# ---------------------------------------------------------------------------
# Treaty Lifecycle
# ---------------------------------------------------------------------------

def sign_treaty(treaty_id: str, host_state_signatory: str,
                realm_signatory: str) -> dict:
    """Record signatures from both parties. Advances draft → signed."""
    proposal = Proposal.get(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    metadata = json.loads(proposal.metadata)
    treaty = metadata.get("treaty", {})

    if treaty.get("status") != "draft":
        return {"error": f"Treaty must be in draft to sign (current: {treaty['status']})"}

    now = datetime.now()
    treaty["status"] = "signed"
    treaty["host_state_signatory"] = host_state_signatory
    treaty["realm_signatory"] = realm_signatory
    treaty["signed_at"] = now.isoformat()
    treaty["history"].append({
        "event": "signed",
        "at": now.isoformat(),
        "notes": f"Signed by {host_state_signatory} (host) and {realm_signatory} (realm)",
    })
    metadata["status"] = "signed"
    proposal.metadata = json.dumps(metadata)

    return {"treaty_id": treaty_id, "status": "signed"}


def ratify_treaty(treaty_id: str, ratified_by: str = "parliament") -> dict:
    """Ratify a signed treaty. Advances signed → ratified."""
    proposal = Proposal.get(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    metadata = json.loads(proposal.metadata)
    treaty = metadata.get("treaty", {})

    if treaty.get("status") != "signed":
        return {"error": f"Treaty must be signed before ratification (current: {treaty['status']})"}

    now = datetime.now()
    treaty["status"] = "ratified"
    treaty["ratified_at"] = now.isoformat()
    treaty["history"].append({
        "event": "ratified", "at": now.isoformat(),
        "notes": f"Ratified by {ratified_by}",
    })
    metadata["status"] = "ratified"
    proposal.metadata = json.dumps(metadata)

    return {"treaty_id": treaty_id, "status": "ratified"}


def activate_treaty(treaty_id: str) -> dict:
    """Activate a ratified treaty. Advances ratified → active.

    Also marks land as acquired in the realm lifecycle so the realm can
    advance from beta to production.
    """
    proposal = Proposal.get(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    metadata = json.loads(proposal.metadata)
    treaty = metadata.get("treaty", {})

    if treaty.get("status") != "ratified":
        return {"error": f"Treaty must be ratified before activation (current: {treaty['status']})"}

    now = datetime.now()
    term_years = treaty.get("term_years", DEFAULT_TERM_YEARS)
    treaty["status"] = "active"
    treaty["activated_at"] = now.isoformat()
    treaty["start_date"] = now.isoformat()
    treaty["end_date"] = (now + timedelta(days=term_years * 365)).isoformat()
    treaty["history"].append({
        "event": "activated", "at": now.isoformat(),
        "notes": f"Treaty active for {term_years} years",
    })
    metadata["status"] = "active"
    proposal.metadata = json.dumps(metadata)

    # Mark land as acquired in realm lifecycle
    try:
        from . import realm_lifecycle_codex
        realm_lifecycle_codex.mark_land_acquired(
            details=f"Treaty {treaty_id} with {treaty.get('host_state', 'unknown')} — "
                    f"{treaty.get('territory_area_km2', 0)} km²"
        )
    except Exception:
        pass  # lifecycle codex may not be loaded

    return {
        "treaty_id": treaty_id,
        "status": "active",
        "start_date": treaty["start_date"],
        "end_date": treaty["end_date"],
    }


def suspend_treaty(treaty_id: str, reason: str = "") -> dict:
    """Suspend an active treaty (e.g. dispute, force majeure)."""
    proposal = Proposal.get(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    metadata = json.loads(proposal.metadata)
    treaty = metadata.get("treaty", {})

    if treaty.get("status") != "active":
        return {"error": "Only active treaties can be suspended"}

    now = datetime.now()
    treaty["status"] = "suspended"
    treaty["history"].append({
        "event": "suspended", "at": now.isoformat(), "notes": reason,
    })
    metadata["status"] = "suspended"
    proposal.metadata = json.dumps(metadata)

    return {"treaty_id": treaty_id, "status": "suspended", "reason": reason}


def reactivate_treaty(treaty_id: str, reason: str = "") -> dict:
    """Reactivate a suspended treaty."""
    proposal = Proposal.get(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    metadata = json.loads(proposal.metadata)
    treaty = metadata.get("treaty", {})

    if treaty.get("status") != "suspended":
        return {"error": "Only suspended treaties can be reactivated"}

    now = datetime.now()
    treaty["status"] = "active"
    treaty["history"].append({
        "event": "reactivated", "at": now.isoformat(), "notes": reason,
    })
    metadata["status"] = "active"
    proposal.metadata = json.dumps(metadata)

    return {"treaty_id": treaty_id, "status": "active"}


def terminate_treaty(treaty_id: str, reason: str = "",
                     immediate: bool = False) -> dict:
    """Terminate a treaty. Triggers wind-down unless immediate."""
    proposal = Proposal.get(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    metadata = json.loads(proposal.metadata)
    treaty = metadata.get("treaty", {})

    if treaty.get("status") in ("draft", "terminated"):
        return {"error": f"Cannot terminate a treaty in '{treaty['status']}' status"}

    now = datetime.now()
    treaty["status"] = "terminated"
    treaty["terminated_at"] = now.isoformat()

    if not immediate:
        wind_down_months = treaty.get("wind_down_months", DEFAULT_WIND_DOWN_MONTHS)
        treaty["wind_down_end"] = (now + timedelta(days=wind_down_months * 30)).isoformat()

    treaty["history"].append({
        "event": "terminated", "at": now.isoformat(),
        "notes": reason or "Treaty terminated",
        "immediate": immediate,
    })
    metadata["status"] = "terminated"
    proposal.metadata = json.dumps(metadata)

    return {
        "treaty_id": treaty_id,
        "status": "terminated",
        "wind_down_end": treaty.get("wind_down_end"),
    }


# ---------------------------------------------------------------------------
# Financial — Payment Tracking
# ---------------------------------------------------------------------------

def record_payment(treaty_id: str, amount: int, currency: str = "",
                   period: str = "", notes: str = "") -> dict:
    """Record a lease fee payment against the treaty."""
    proposal = Proposal.get(treaty_id)
    if not proposal:
        return {"error": "Treaty not found"}

    metadata = json.loads(proposal.metadata)
    treaty = metadata.get("treaty", {})

    payment = {
        "amount": amount,
        "currency": currency or treaty.get("fee_currency", "USD"),
        "period": period,
        "paid_at": datetime.now().isoformat(),
        "notes": notes,
    }
    treaty.setdefault("payments", []).append(payment)
    proposal.metadata = json.dumps(metadata)

    return {
        "treaty_id": treaty_id,
        "payment_index": len(treaty["payments"]) - 1,
        "amount": amount,
    }


def get_payment_summary(treaty_id: str) -> dict:
    """Return payment history and balance for a treaty."""
    treaty = get_treaty(treaty_id)
    if "error" in treaty:
        return treaty

    payments = treaty.get("payments", [])
    total_paid = sum(p["amount"] for p in payments)

    return {
        "treaty_id": treaty_id,
        "annual_fee": treaty.get("annual_fee", 0),
        "total_paid": total_paid,
        "payment_count": len(payments),
        "payments": payments,
    }


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def list_treaties(status: str = None) -> list:
    """List all treaties, optionally filtered by status."""
    results = []
    for proposal in Proposal.get_all():
        metadata = json.loads(proposal.metadata)
        if metadata.get("branch") != "treaty":
            continue
        treaty = metadata.get("treaty", {})
        if status and treaty.get("status") != status:
            continue
        results.append({
            "treaty_id": proposal.id,
            "host_state": treaty.get("host_state"),
            "status": treaty.get("status"),
            "territory_area_km2": treaty.get("territory_area_km2"),
            "annual_fee": treaty.get("annual_fee"),
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
