"""Membership Codex — Agora (incumbent migration).

Agora migrates the population of an *existing* public administration. The PA
already has a census, so there is **no ZK passport step**: citizens are
onboarded by registration code, manual entry, or programmatic/bulk import and
become active members immediately upon registration.

Activation model:
  - A Member record is created on registration with
    ``identity_verification = "verified"`` (the realm-wide "active member"
    signal used by governance, justice, welfare, etc.).
  - During the migration phases (alpha/beta) members owe nothing; a registration
    invoice is only issued once the realm is live (see entry.on_user_register).

This module also provides:
  - activate_member(): create/activate a member on registration (idempotent)
  - deactivate_member(): suspend a member
  - reactivate_member(): restore membership after paying overdue bills
"""

from _cdk import ic
from ggg import User, Member, Invoice, Notification
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json


def _now_iso():
    return epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")


# ---------------------------------------------------------------------------
# Join requirements (incumbent — no passport)
# ---------------------------------------------------------------------------

JOIN_REQUIREMENTS = {
    "registration_code": {
        "description": "Valid registration code issued to the existing population (or bulk/programmatic import)",
        "required": True,
    },
}


def get_join_requirements() -> dict:
    """Return the join requirements for prospective members."""
    return {
        "requirements": JOIN_REQUIREMENTS,
        "verification_method": "Registration code / census import (no ZK passport)",
        "steps": [
            "Receive your registration code from the administration",
            "Register with your code (or be imported by your department)",
            "Your citizenship is active immediately — nothing to pay during migration",
        ],
    }


# ---------------------------------------------------------------------------
# Member helpers
# ---------------------------------------------------------------------------

def _find_member_for_user(user_id: str):
    """Find an existing Member record for this user."""
    for member in Member.instances():
        if member.user and member.user.id == user_id:
            return member
    return None


def _is_first_invoice_paid(user_id: str) -> bool:
    """Check whether the user's registration invoice has been paid (if any)."""
    for inv in Invoice.instances():
        meta = inv.metadata or ""
        if inv.user and inv.user.id == user_id:
            if "registration" in meta.lower() or "welcome fee" in meta.lower():
                if inv.status == "Paid":
                    return True
    return False


def is_registered_member(user_id: str) -> bool:
    """True if the user is a registered, active member of the realm."""
    member = _find_member_for_user(user_id)
    return bool(member and member.identity_verification == "verified")


def activate_member(user_id: str) -> dict:
    """Create (or reactivate) an active member for a registered/imported user.

    Idempotent: safe to call from the registration hook on every join.
    """
    user = User[user_id]
    if not user:
        return {"accepted": False, "reason": "User not found"}

    member = _find_member_for_user(user_id)
    if member:
        if member.identity_verification != "verified":
            member.identity_verification = "verified"
            member.voting_eligibility = "eligible"
            member.public_benefits_eligibility = "eligible"
        return {"accepted": True, "member_id": member.id, "user_id": user_id, "already_member": True}

    member = Member(
        user=user,
        identity_verification="verified",
        residence_permit="valid",
        tax_compliance="compliant",
        public_benefits_eligibility="eligible",
        voting_eligibility="eligible",
        criminal_record="clean",
    )

    return {
        "accepted": True,
        "member_id": member.id,
        "user_id": user_id,
        "granted_at": _now_iso(),
    }


def check_membership_status(user_id: str) -> dict:
    """Check whether a user is a registered, active member."""
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

    return {"is_member": False, "reason": "No membership record found. Register with your code to activate citizenship."}


# ---------------------------------------------------------------------------
# Suspension / reactivation
# ---------------------------------------------------------------------------

def deactivate_member(user_id: str, reason: str = "Non-payment of dues") -> dict:
    """Suspend a member's citizenship due to non-payment."""
    user = User[user_id]
    if not user:
        return {"deactivated": False, "reason": "User not found"}

    member = _find_member_for_user(user_id)
    if not member:
        return {"deactivated": False, "reason": "No membership found for user"}

    member.identity_verification = "suspended"
    member.voting_eligibility = "ineligible"
    member.public_benefits_eligibility = "ineligible"

    Notification(
        topic="membership",
        title="Citizenship Suspended",
        message="Your citizenship has been suspended. Reason: " + reason
                + ". Pay your outstanding invoices to reactivate.",
        sender="Administration",
        recipient=user.id,
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
        "deactivated_at": _now_iso(),
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
        sender="Administration",
        recipient=user.id,
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
        "reactivated_at": _now_iso(),
    }


# Main execution
if __name__ == "__main__":
    print(json.dumps(get_join_requirements(), indent=2))
