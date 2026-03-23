# Test: Territory & Land
# Covers: realm lifecycle stages, land & zones, land lease treaty lifecycle,
#         zone policy & license assignment
import json
import land_treaty
import zones
from ggg import (
    Realm, RealmStatus,
    Land, LandStatus, LandType, Zone,
    License, LicenseType, license_issue,
)

ts = "r" + str(id(object()))[-6:]

# ── TEST 1: Realm Lifecycle Stages ───────────────────────────────────────
print("=== TEST 1: REALM LIFECYCLE ===")
realm = Realm(
    name="Syntropia Lifecycle Test " + ts,
    description="A digital realm for smart social contracts",
    status=RealmStatus.ALPHA,
)
print("Realm: " + realm.name + " status=" + realm.status)

lifecycle = {
    "critical_mass": 10000, "deposit_amount": 100,
    "registered_users": 0, "total_deposits": 0,
    "deposits_locked": False, "land_acquired": False,
    "infrastructure_ready": False, "providers_ready": False,
    "history": [{"stage": RealmStatus.ALPHA, "at": "2026-03-09", "reason": "Realm created"}],
}
realm.manifest_data = json.dumps({"lifecycle": lifecycle})
assert realm.status == RealmStatus.ALPHA, "Realm should start in alpha"

lifecycle["registered_users"] = 150
lifecycle["total_deposits"] = 15000
print("  Registered: " + str(lifecycle["registered_users"]) + " deposits: " + str(lifecycle["total_deposits"]))

realm.status = RealmStatus.BETA
lifecycle["deposits_locked"] = True
assert realm.status == RealmStatus.BETA
print("  Advanced to: " + realm.status)

lifecycle["infrastructure_ready"] = True
lifecycle["land_acquired"] = True
lifecycle["providers_ready"] = True

realm.status = RealmStatus.PRODUCTION
assert realm.status == RealmStatus.PRODUCTION
print("  Advanced to: " + realm.status)
realm.manifest_data = json.dumps({"lifecycle": lifecycle})

# ── TEST 2: Land & Zones ────────────────────────────────────────────────
print("=== TEST 2: LAND & ZONES ===")
land_hq = Land(
    id=ts + "_LAND001", x_coordinate=100, y_coordinate=200,
    land_type=LandType.COMMERCIAL, size_width=10, size_height=10,
    status=LandStatus.ACTIVE, registered_by="Syntropia Land Authority",
    nft_token_id="NFT-" + ts + "-001",
    metadata=json.dumps({"use": "Realm HQ", "floor_area_sqm": 2500}),
)
land_res = Land(
    id=ts + "_LAND002", x_coordinate=120, y_coordinate=210,
    land_type=LandType.RESIDENTIAL, size_width=5, size_height=8,
    status=LandStatus.ACTIVE, registered_by="Syntropia Land Authority",
    nft_token_id="NFT-" + ts + "-002",
    metadata=json.dumps({"use": "Residential Block A", "units": 40}),
)
land_farm = Land(
    id=ts + "_LAND003", x_coordinate=80, y_coordinate=250,
    land_type=LandType.AGRICULTURAL, size_width=20, size_height=30,
    status=LandStatus.ACTIVE, registered_by="Syntropia Land Authority",
)
print("Land parcels: " + str(Land.count()))

zone_central = Zone(
    h3_index="861203a4fffffff", name=ts + " Central District",
    description="Main commercial and administrative zone",
    latitude=34.0522, longitude=-118.2437, resolution=6.0,
)
zone_residential = Zone(
    h3_index="861203a5fffffff", name=ts + " Residential Quarter",
    description="Primary residential area",
    latitude=34.0550, longitude=-118.2400, resolution=6.0, land=land_res,
)
print("Zones: " + str(Zone.count()))

# ── TEST 3: Land Lease Treaty Lifecycle ──────────────────────────────────
print("=== TEST 3: LAND LEASE TREATY ===")
treaty_mod = land_treaty

treaty = treaty_mod.create_treaty(
    host_state_name="Republic of Freedonia",
    territory_description="50 km2 coastal zone in the southern province",
    term_years=50, annual_fee=500000, fee_currency="USD",
    revenue_share_pct=5.0, security_deposit=2000000, territory_area_km2=50.0,
)
assert treaty.get("status") == "draft"
treaty_id = treaty["treaty_id"]
print("Treaty created: " + treaty_id + " status=draft")

sign_result = treaty_mod.sign_treaty(treaty_id, "Minister of Foreign Affairs", "Realm Chancellor")
assert sign_result.get("status") == "signed", "Should be signed: " + str(sign_result)
print("Treaty signed")

ratify_result = treaty_mod.ratify_treaty(treaty_id, ratified_by="parliament")
assert ratify_result.get("status") == "ratified"
print("Treaty ratified")

activate_result = treaty_mod.activate_treaty(treaty_id)
assert activate_result.get("status") == "active"
print("Treaty activated")

pay_result = treaty_mod.record_payment(treaty_id, amount=500000, currency="USD", period="Year 1")
assert "payment_index" in pay_result
print("Payment recorded: " + str(pay_result.get("amount")))

pay_summary = treaty_mod.get_payment_summary(treaty_id)
print("Payment summary: total_paid=" + str(pay_summary.get("total_paid")))

suspend_result = treaty_mod.suspend_treaty(treaty_id, reason="Diplomatic review")
assert suspend_result.get("status") == "suspended"
print("Treaty suspended")

reactivate_result = treaty_mod.reactivate_treaty(treaty_id)
assert reactivate_result.get("status") == "active"
print("Treaty reactivated")

terminate_result = treaty_mod.terminate_treaty(treaty_id, reason="Term ended")
assert terminate_result.get("status") == "terminated"
print("Treaty terminated")

treaties = treaty_mod.list_treaties()
print("Total treaties: " + str(len(treaties)))

# ── TEST 4: Zone Policy & License Assignment ─────────────────────────────
print("=== TEST 4: ZONE POLICY & LICENSE ===")
policy_result = zones.add_policy_to_zone(
    str(zone_central._id), "Tax Incentive Zone",
    "Reduced tax rate for businesses in the central district",
)
assert "error" not in policy_result, "Policy should be added: " + str(policy_result)
print("Policy added: " + str(policy_result.get("policy", {}).get("name")))

test_lic = license_issue(
    name=ts + "_test_provider",
    license_type=LicenseType.INFRASTRUCTURE,
    description="Test infrastructure provider",
    validity_seconds=365 * 86400,
    issuing_authority="Central Authority",
)
print("License issued: " + str(test_lic._id) + " type=" + test_lic.license_type)

assign_result = zones.assign_license_to_zone(str(zone_central._id), str(test_lic._id))
assert assign_result.get("status") == "assigned", "License should be assigned: " + str(assign_result)
print("License assigned to zone")

zone_info = zones.get_zone(str(zone_central._id))
assert str(test_lic._id) in zone_info.get("assigned_licenses", [])
print("Zone has " + str(len(zone_info.get("assigned_licenses", []))) + " licenses, " + str(len(zone_info.get("policies", []))) + " policies")

remove_result = zones.remove_license_from_zone(str(zone_central._id), str(test_lic._id))
assert remove_result.get("status") == "removed"
print("License removed from zone")

# Summary
print("=== TERRITORY TESTS PASSED ===")
print("Realms: " + str(Realm.count()) + " Land: " + str(Land.count()) + " Zones: " + str(Zone.count()))
