"""
Westminster Licensing Codex
Issues and manages licenses for private service providers.

The central authority outsources public services to private providers through
a licensing system. Providers must meet requirements to obtain and retain a
license. Licensed providers submit invoices which the realm treasury pays.

Uses the native ggg License entity, LicenseType, license_issue() and
license_revoke() functions.

License categories (from ggg.LicenseType):
  - health         — private hospitals, clinics, pharmacies
  - police         — private security, community policing
  - infrastructure — construction, utilities, transport
  - education      — private schools, training centres
  - justice_provider — private courts, arbitration, legal aid
  - other          — catch-all for unlisted provider types
"""

from _cdk import ic
from ggg import (
    License, LicenseType, license_issue, license_revoke,
    Organization, User, Transfer, Instrument, Invoice,
)
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json

# Default license validity in seconds (1 year)
DEFAULT_LICENSE_VALIDITY_SECONDS = 365 * 86400

PROVIDER_CATEGORIES = [
    LicenseType.HEALTH,
    LicenseType.POLICE,
    LicenseType.INFRASTRUCTURE,
    LicenseType.EDUCATION,
    LicenseType.JUSTICE_PROVIDER,
    LicenseType.OTHER,
]


def issue_provider_license(provider_name: str, category: str,
                           organization: "Organization" = None,
                           description: str = "",
                           validity_seconds: int = DEFAULT_LICENSE_VALIDITY_SECONDS,
                           issuing_authority: str = "Westminster Central Authority") -> dict:
    """Issue a new license to a private service provider.

    Uses the native ggg license_issue() function.
    """
    if category not in PROVIDER_CATEGORIES:
        return {"error": f"Invalid category '{category}'. Must be one of {PROVIDER_CATEGORIES}"}

    lic = license_issue(
        name=provider_name,
        license_type=category,
        organization=organization,
        description=description or f"Service provider license for '{category}'",
        validity_seconds=validity_seconds,
        issuing_authority=issuing_authority,
        metadata=json.dumps({
            "bills": [],
            "compliance_checks": [],
        }),
    )

    return {
        "license_id": lic.id,
        "name": lic.name,
        "license_type": lic.license_type,
        "status": lic.status,
        "issued_at": lic.issued_at,
        "expires_at": lic.expires_at,
    }


def check_compliance(license_id: str) -> dict:
    """Verify that a licensed provider still meets requirements."""
    lic = License.load(license_id)
    if not lic:
        return {"error": "License not found"}

    valid = lic.is_valid()

    # Record the check in metadata
    try:
        meta = json.loads(lic.metadata) if lic.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    check = {
        "compliant": valid,
        "checked_at": epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T"),
    }
    meta.setdefault("compliance_checks", []).append(check)
    lic.metadata = json.dumps(meta)

    return {
        "license_id": license_id,
        "compliant": valid,
        "status": lic.status,
        "checked_at": check["checked_at"],
    }


def revoke_provider_license(license_id: str, reason: str = "") -> dict:
    """Revoke an active provider license."""
    lic = License.load(license_id)
    if not lic:
        return {"error": "License not found"}

    license_revoke(lic, reason=reason)

    return {"license_id": license_id, "status": lic.status, "reason": reason}


def renew_provider_license(license_id: str,
                           validity_seconds: int = DEFAULT_LICENSE_VALIDITY_SECONDS) -> dict:
    """Renew an active or expired license for another term."""
    lic = License.load(license_id)
    if not lic:
        return {"error": "License not found"}

    if lic.status == "revoked":
        return {"error": "Cannot renew a revoked license. Apply for a new one."}

    now = ic_time_to_epoch(ic.time())
    lic.status = "active"
    lic.issued_at = now
    lic.expires_at = now + validity_seconds

    return {"license_id": license_id, "status": "active", "expires_at": lic.expires_at}


def submit_bill(license_id: str, amount: int, description: str) -> dict:
    """Provider submits a bill (stored in license metadata) for services rendered."""
    lic = License.load(license_id)
    if not lic:
        return {"error": "License not found"}

    if not lic.is_valid():
        return {"error": "Only active license holders may submit bills"}

    try:
        meta = json.loads(lic.metadata) if lic.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    bill = {
        "amount": amount,
        "description": description,
        "submitted_at": epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T"),
        "status": "pending",
    }
    meta.setdefault("bills", []).append(bill)
    lic.metadata = json.dumps(meta)

    return {
        "license_id": license_id,
        "bill_index": len(meta["bills"]) - 1,
        "amount": amount,
        "status": "pending",
    }


def pay_bill(license_id: str, bill_index: int) -> dict:
    """Realm treasury pays an approved provider bill."""
    lic = License.load(license_id)
    if not lic:
        return {"error": "License not found"}

    try:
        meta = json.loads(lic.metadata) if lic.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    bills = meta.get("bills", [])
    if bill_index < 0 or bill_index >= len(bills):
        return {"error": "Bill not found"}

    bill = bills[bill_index]
    if bill["status"] != "pending":
        return {"error": f"Bill is already {bill['status']}"}

    # Pay via the organization linked to the license, or fall back to system
    system_user = User.get("system")
    instrument = Instrument.get_by_name("Realm Token")

    if not system_user or not instrument:
        return {"error": "Cannot resolve system user or instrument"}

    # If the license is linked to an organization with a user, pay that user
    to_user = None
    if lic.organization and hasattr(lic.organization, "user"):
        to_user = lic.organization.user
    if not to_user:
        to_user = system_user  # fallback: record the transfer to system

    Transfer(
        from_user=system_user,
        to_user=to_user,
        instrument=instrument,
        amount=bill["amount"]
    )

    bill["status"] = "paid"
    bill["paid_at"] = epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")
    lic.metadata = json.dumps(meta)

    return {
        "license_id": license_id,
        "bill_index": bill_index,
        "amount": bill["amount"],
        "status": "paid",
    }


def list_licenses(category: str = None, status: str = "active") -> list:
    """List all licenses, optionally filtered by category and status."""
    results = []
    for lic in License.instances():
        if category and lic.license_type != category:
            continue
        if status and lic.status != status:
            continue
        results.append({
            "license_id": lic.id,
            "name": lic.name,
            "license_type": lic.license_type,
            "status": lic.status,
            "issued_at": lic.issued_at,
            "expires_at": lic.expires_at,
        })
    return results


# Main execution
if __name__ == "__main__":
    lic = issue_provider_license("City Hospital", LicenseType.HEALTH)
    print(json.dumps(lic, indent=2))
