"""
Membership Codex
Defines join criteria for the Agora realm.

To become an active citizen a user must:
  1. Be verified as a unique human via the Rarimo ZK Passport verification
     (passport_verification extension) — proving age >= 18, uniqueness, and
     valid passport — all without revealing personal data.
  2. Pay the initial registration invoice (created by user_registration_hook).

Both conditions must be met before the account is activated. Once active,
the user can vote, submit proposals, and receive welfare benefits.

This codex also provides:
  - deactivate_member(): used by monthly_billing_codex to suspend non-payers
  - reactivate_member(): restore membership after paying overdue bills
  - Sybil-resistance: the same ZK identity hash cannot register twice
"""

from ggg import User, Member, Invoice, Notification
from datetime import datetime, timedelta
import json


def _ic_now():
    """Get current datetime from ic.time() (nanoseconds since epoch)."""
    ns = ic.time()
    return datetime(1970, 1, 1) + timedelta(seconds=ns // 1_000_000_000)

try:
    from core.extensions import extension_async_call
except Exception:
    extension_async_call = None


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
    "first_invoice_paid": {
        "description": "Initial registration invoice must be paid",
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
            "Pay the initial registration invoice",
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


def _is_first_invoice_paid(user_id: str) -> bool:
    """Check whether the user's initial registration invoice has been paid."""
    for inv in Invoice.instances():
        meta = inv.metadata or ""
        if inv.user and inv.user.id == user_id:
            if "Welcome fee" in meta or "registration" in meta.lower():
                if inv.status == "Paid":
                    return True
    return False


def _find_member_for_user(user_id: str):
    """Find an existing Member record for this user."""
    for member in Member.instances():
        if member.user and member.user.id == user_id:
            return member
    return None


def finalize_membership(user_id: str, verification_result: str) -> dict:
    """Grant membership after successful passport verification AND first invoice payment.

    Args:
        user_id: The user requesting membership.
        verification_result: JSON string returned by check_verification
                             when status is verified.

    Returns:
        Membership decision dict.
    """
    user = User[user_id]
    if not user:
        return {"accepted": False, "reason": "User not found"}

    try:
        vdata = json.loads(verification_result) if isinstance(verification_result, str) else verification_result
    except (json.JSONDecodeError, TypeError):
        vdata = {}

    # Check proof was successful
    attrs = vdata.get("data", {}).get("attributes", {})
    verified = attrs.get("status") == "verified"
    if not verified:
        return {
            "accepted": False,
            "reason": "Passport verification not completed or failed. "
                      "Please use the RariMe app to verify your identity.",
        }

    # Check first invoice is paid
    if not _is_first_invoice_paid(user_id):
        return {
            "accepted": False,
            "reason": "Your initial registration invoice has not been paid yet. "
                      "Please pay it to complete your membership activation.",
        }

    # Sybil resistance: extract the ZK identity hash and reject duplicates
    zk_identity_hash = attrs.get("identity_hash", "")
    if zk_identity_hash:
        existing_members = Member.instances()
        for m in existing_members:
            if m.criminal_record and zk_identity_hash in m.criminal_record:
                return {
                    "accepted": False,
                    "reason": "This identity has already been used to register. "
                              "One person = one membership.",
                }

    # Create membership record (store zk hash in criminal_record field for dedup)
    member = Member(
        user=user,
        identity_verification="verified",
        residence_permit="valid",
        tax_compliance="compliant",
        public_benefits_eligibility="eligible",
        voting_eligibility="eligible",
        criminal_record="clean|zk:" + zk_identity_hash,
    )

    # Notify user
    Notification(
        topic="membership",
        title="Citizenship Granted",
        message="Your identity has been verified and your registration invoice is paid. "
                "Welcome to Agora! You can now vote, submit proposals, and receive benefits.",
        user=user,
        read=False,
        icon="shield_check",
        href="/",
        color="green",
        metadata="uid:" + user_id + "|mid:" + str(member.id)
    )

    return {
        "accepted": True,
        "member_id": member.id,
        "user_id": user_id,
        "granted_at": _ic_now().isoformat(),
    }


def check_membership_status(user_id: str) -> dict:
    """Check whether a user is already a verified member."""
    user = User[user_id]
    if not user:
        return {"is_member": False, "reason": "User not found"}

    member = _find_member_for_user(user_id)
    if member:
        return {
            "is_member": True,
            "active": member.identity_verification == "verified",
            "member_id": member.id,
            "identity_verification": member.identity_verification,
            "voting_eligibility": member.voting_eligibility,
        }

    return {"is_member": False, "reason": "No membership record found. Please verify your passport and pay your registration invoice."}


# ---------------------------------------------------------------------------
# Membership Suspension / Reactivation (used by monthly_billing_codex)
# ---------------------------------------------------------------------------

def deactivate_member(user_id: str, reason: str = "Non-payment of dues") -> dict:
    """Suspend a member's citizenship due to non-payment.

    Unlike full revocation, a suspended member can reactivate by paying
    their overdue bills.
    """
    user = User[user_id]
    if not user:
        return {"deactivated": False, "reason": "User not found"}

    member = _find_member_for_user(user_id)
    if not member:
        return {"deactivated": False, "reason": "No membership found for user"}

    # Mark membership as suspended
    member.identity_verification = "suspended"
    member.voting_eligibility = "ineligible"
    member.public_benefits_eligibility = "ineligible"

    Notification(
        topic="membership",
        title="Citizenship Suspended",
        message="Your citizenship has been suspended. Reason: " + reason
                + ". Pay your outstanding invoices to reactivate.",
        user=user,
        read=False,
        icon="shield_off",
        href="/extensions/member_dashboard#my_taxes",
        color="orange",
        metadata="uid:" + user_id + "|mid:" + str(member.id)
    )

    return {
        "deactivated": True,
        "member_id": member.id,
        "user_id": user_id,
        "reason": reason,
        "deactivated_at": _ic_now().isoformat(),
    }


def reactivate_member(user_id: str) -> dict:
    """Reactivate a suspended member after they pay their overdue bills."""
    user = User[user_id]
    if not user:
        return {"reactivated": False, "reason": "User not found"}

    member = _find_member_for_user(user_id)
    if not member:
        return {"reactivated": False, "reason": "No membership found for user"}

    if member.identity_verification != "suspended":
        return {"reactivated": False, "reason": "Member is not suspended"}

    member.identity_verification = "verified"
    member.voting_eligibility = "eligible"
    member.public_benefits_eligibility = "eligible"

    Notification(
        topic="membership",
        title="Citizenship Reactivated",
        message="Your outstanding invoices have been settled. Your citizenship is active again. Welcome back!",
        user=user,
        read=False,
        icon="shield_check",
        href="/",
        color="green",
        metadata="uid:" + user_id + "|mid:" + str(member.id)
    )

    return {
        "reactivated": True,
        "member_id": member.id,
        "user_id": user_id,
        "reactivated_at": _ic_now().isoformat(),
    }


# Main execution
if __name__ == "__main__":
    reqs = get_join_requirements()
    print(json.dumps(reqs, indent=2))
