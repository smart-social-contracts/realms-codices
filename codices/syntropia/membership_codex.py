"""
Membership Codex
Defines join criteria for the realm.

To become a citizen a user must:
  1. Be verified via the Rarimo ZK Passport verification (passport_verification
     extension) — proving age >= 18, uniqueness, and valid passport — all
     without revealing personal data.
  2. Pay the initial registration invoice (handled by the common
     user_registration_hook).

This codex provides helpers that the realm can call during onboarding to
enforce these requirements.
"""

from ggg import User, Member, Notification
from datetime import datetime
import json

try:
    from core.extensions import extension_async_call
except ImportError:
    from ..core.extensions import extension_async_call


# ---------------------------------------------------------------------------
# Verification Requirements
# ---------------------------------------------------------------------------

JOIN_REQUIREMENTS = {
    "passport_zk_verified": {
        "description": "Identity verified via Rarimo ZK Passport (rarime app)",
        "required": True,
    },
    "minimum_age": {
        "description": "Must be at least 18 years old (proven via ZK proof)",
        "value": 18,
        "required": True,
    },
    "uniqueness": {
        "description": "One person = one membership (Sybil resistance)",
        "required": True,
    },
}


def get_join_requirements() -> dict:
    """Return the current join requirements for display to prospective members."""
    return {
        "requirements": JOIN_REQUIREMENTS,
        "verification_method": "Rarimo ZK Passport (rarime mobile app)",
        "steps": [
            "Install the RariMe mobile app",
            "Scan your passport via NFC",
            "Generate zero-knowledge proof on your device",
            "Submit proof to the realm for verification",
        ],
    }


# ---------------------------------------------------------------------------
# Verification Flow
# ---------------------------------------------------------------------------

def request_verification(user_id: str) -> "Async[str]":
    """Start the passport verification flow for a prospective member.

    Calls the passport_verification extension to generate a verification
    link / QR code that the user scans with the RariMe app.
    """
    args = json.dumps({"user_id": user_id})
    result = yield extension_async_call(
        "passport_verification", "get_verification_link", args
    )
    return result


def check_verification(user_id: str) -> "Async[str]":
    """Poll verification status from the passport_verification extension."""
    args = json.dumps({"user_id": user_id})
    result = yield extension_async_call(
        "passport_verification", "check_verification_status", args
    )
    return result


def finalize_membership(user_id: str, verification_result: str) -> dict:
    """Grant membership after successful passport verification.

    Args:
        user_id: The user requesting membership.
        verification_result: JSON string returned by check_verification
                             when status is verified.

    Returns:
        Membership decision dict.
    """
    user = User.get(user_id)
    if not user:
        return {"accepted": False, "reason": "User not found"}

    try:
        vdata = json.loads(verification_result) if isinstance(verification_result, str) else verification_result
    except (json.JSONDecodeError, TypeError):
        vdata = {}

    # Check proof was successful
    verified = vdata.get("data", {}).get("attributes", {}).get("status") == "verified"
    if not verified:
        return {
            "accepted": False,
            "reason": "Passport verification not completed or failed. "
                      "Please use the RariMe app to verify your identity.",
        }

    # Create membership record
    member = Member(
        user=user,
        identity_verification="verified",
        residence_permit="valid",
        tax_compliance="compliant",
        public_benefits_eligibility="eligible",
        voting_eligibility="eligible",
        criminal_record="clean",
    )

    # Notify user
    Notification(
        topic="membership",
        title="Citizenship Granted",
        message="Your identity has been verified and citizenship has been granted. "
                "Welcome to the Realm.",
        user=user,
        read=False,
        icon="shield_check",
        href="/",
        color="green",
        metadata=f"member_id:{member.id}"
    )

    return {
        "accepted": True,
        "member_id": member.id,
        "user_id": user_id,
        "granted_at": datetime.now().isoformat(),
    }


def check_membership_status(user_id: str) -> dict:
    """Check whether a user is already a verified member."""
    user = User.get(user_id)
    if not user:
        return {"is_member": False, "reason": "User not found"}

    members = Member.get_all()
    for member in members:
        if member.user and member.user.id == user_id:
            return {
                "is_member": True,
                "member_id": member.id,
                "identity_verification": member.identity_verification,
            }

    return {"is_member": False, "reason": "No membership record found. Please verify your passport."}


# Main execution
if __name__ == "__main__":
    reqs = get_join_requirements()
    print(json.dumps(reqs, indent=2))
