"""
Zones Codex
Manages zones of action (jurisdictional areas) for the realm.

Uses the native ggg Zone entity which supports H3 hexagonal indexing
for spatial representation.

Zones are not strict borders but areas where specific policies, services,
or licensed providers operate. A zone can overlap with others.

Examples:
  - "Capital District" — central administrative zone
  - "Northern Health Region" — area served by northern health providers
  - "Industrial Corridor" — zone with special infrastructure licensing
"""

from ggg import Zone, License
from datetime import datetime
import json


def create_zone(name: str, description: str, category: str = "general",
                h3_index: str = "", latitude: float = 0.0,
                longitude: float = 0.0, resolution: float = 7.0,
                parent_zone_id: str = None) -> dict:
    """Create a new zone of action.

    Args:
        name: Human-readable zone name.
        description: Purpose / scope of the zone.
        category: Zone type — e.g. administrative, health, police,
                  infrastructure, judicial, economic, general.
        h3_index: H3 hexagonal cell index for spatial location.
        latitude: Centre latitude of the zone.
        longitude: Centre longitude of the zone.
        resolution: H3 resolution level (0-15).
        parent_zone_id: Optional parent zone for hierarchical nesting.

    Returns:
        Zone data dict including the generated zone_id.
    """
    meta = {
        "category": category,
        "status": "active",
        "parent_zone_id": parent_zone_id,
        "assigned_licenses": [],
        "policies": [],
        "created_at": datetime.now().isoformat(),
    }

    zone = Zone(
        h3_index=h3_index,
        name=name,
        description=description,
        latitude=latitude,
        longitude=longitude,
        resolution=resolution,
        metadata=json.dumps(meta),
    )

    return {
        "zone_id": zone._id,
        "name": zone.name,
        "category": category,
        "h3_index": zone.h3_index,
        "status": "active",
    }


def _get_zone_meta(zone) -> dict:
    """Parse metadata JSON from a Zone entity."""
    try:
        return json.loads(zone.metadata) if zone.metadata else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _save_zone_meta(zone, meta: dict):
    """Save metadata JSON back to a Zone entity."""
    zone.metadata = json.dumps(meta)


def update_zone(zone_id: str, updates: dict) -> dict:
    """Update mutable fields of a zone (name, description, category, status)."""
    zone = Zone.load(zone_id)
    if not zone:
        return {"error": "Zone not found"}

    meta = _get_zone_meta(zone)

    if "name" in updates:
        zone.name = updates["name"]
    if "description" in updates:
        zone.description = updates["description"]
    if "category" in updates:
        meta["category"] = updates["category"]
    if "status" in updates:
        meta["status"] = updates["status"]

    meta["updated_at"] = datetime.now().isoformat()
    _save_zone_meta(zone, meta)

    return {
        "zone_id": zone_id,
        "name": zone.name,
        "category": meta.get("category"),
        "status": meta.get("status"),
    }


def deactivate_zone(zone_id: str, reason: str = "") -> dict:
    """Deactivate a zone (soft-delete)."""
    zone = Zone.load(zone_id)
    if not zone:
        return {"error": "Zone not found"}

    meta = _get_zone_meta(zone)
    meta["status"] = "inactive"
    meta["deactivation_reason"] = reason
    meta["deactivated_at"] = datetime.now().isoformat()
    _save_zone_meta(zone, meta)

    return {"zone_id": zone_id, "status": "inactive", "reason": reason}


def assign_license_to_zone(zone_id: str, license_id: str) -> dict:
    """Link a provider license to a zone so the provider operates within it."""
    zone = Zone.load(zone_id)
    if not zone:
        return {"error": "Zone not found"}

    meta = _get_zone_meta(zone)
    assigned = meta.setdefault("assigned_licenses", [])

    if license_id in assigned:
        return {"error": "License already assigned to this zone"}

    assigned.append(license_id)
    _save_zone_meta(zone, meta)

    return {"zone_id": zone_id, "license_id": license_id, "status": "assigned"}


def remove_license_from_zone(zone_id: str, license_id: str) -> dict:
    """Remove a provider license from a zone."""
    zone = Zone.load(zone_id)
    if not zone:
        return {"error": "Zone not found"}

    meta = _get_zone_meta(zone)
    assigned = meta.get("assigned_licenses", [])

    if license_id not in assigned:
        return {"error": "License not assigned to this zone"}

    assigned.remove(license_id)
    _save_zone_meta(zone, meta)

    return {"zone_id": zone_id, "license_id": license_id, "status": "removed"}


def add_policy_to_zone(zone_id: str, policy_name: str,
                       policy_description: str) -> dict:
    """Attach a policy rule to a zone (e.g. tax incentive, curfew, speed limit)."""
    zone = Zone.load(zone_id)
    if not zone:
        return {"error": "Zone not found"}

    meta = _get_zone_meta(zone)
    policy = {
        "name": policy_name,
        "description": policy_description,
        "added_at": datetime.now().isoformat(),
        "active": True,
    }
    meta.setdefault("policies", []).append(policy)
    _save_zone_meta(zone, meta)

    return {
        "zone_id": zone_id,
        "policy": policy,
        "total_policies": len(meta["policies"]),
    }


def list_zones(category: str = None, status: str = "active") -> list:
    """List all zones, optionally filtered by category and status."""
    results = []
    for zone in Zone.instances():
        meta = _get_zone_meta(zone)
        if category and meta.get("category") != category:
            continue
        if status and meta.get("status") != status:
            continue
        results.append({
            "zone_id": zone._id,
            "name": zone.name,
            "h3_index": zone.h3_index,
            "category": meta.get("category"),
            "status": meta.get("status"),
        })
    return results


def get_zone(zone_id: str) -> dict:
    """Retrieve full zone details."""
    zone = Zone.load(zone_id)
    if not zone:
        return {"error": "Zone not found"}

    meta = _get_zone_meta(zone)
    return {
        "zone_id": zone._id,
        "name": zone.name,
        "description": zone.description,
        "h3_index": zone.h3_index,
        "latitude": zone.latitude,
        "longitude": zone.longitude,
        "resolution": zone.resolution,
        "category": meta.get("category"),
        "status": meta.get("status"),
        "assigned_licenses": meta.get("assigned_licenses", []),
        "policies": meta.get("policies", []),
    }


# ---------------------------------------------------------------------------
# Sample Data
# ---------------------------------------------------------------------------

def create_sample_zones():
    """Create sample zones for a generic western state"""
    zones = [
        {
            "name": "Capital District",
            "description": "Central administrative and governmental zone.",
            "category": "administrative",
            "latitude": 48.8566,
            "longitude": 2.3522,
        },
        {
            "name": "Northern Health Region",
            "description": "Health service delivery area covering the northern territories.",
            "category": "health",
            "latitude": 50.6292,
            "longitude": 3.0573,
        },
        {
            "name": "Southern Industrial Corridor",
            "description": "Zone with special infrastructure and industrial licensing.",
            "category": "infrastructure",
            "latitude": 43.2965,
            "longitude": 5.3698,
        },
        {
            "name": "Eastern Judicial Circuit",
            "description": "Jurisdiction for eastern courts and legal services.",
            "category": "judicial",
            "latitude": 48.5734,
            "longitude": 7.7521,
        },
    ]

    created = []
    for z in zones:
        result = create_zone(**z)
        created.append(result)
    return created


# Main execution
if __name__ == "__main__":
    zones = create_sample_zones()
    print(f"Created {len(zones)} sample zones")
    for z in zones:
        print(f"  - {z['name']} ({z['category']})")
