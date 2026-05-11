"""
Enforcement Codex
Community policing through elected enforcers and transparent sanctions.

How it works:
  1. The community elects enforcers via governance proposals (type "elect_enforcer").
  2. Any member can report a rule violation.
  3. An enforcer reviews the report and can propose a sanction.
  4. Minor sanctions (warnings) are applied immediately.
  5. Major sanctions (fines, suspensions) require a community vote.
  6. Enforcers can be removed by the community at any time via a vote.

Everything is logged so the community can hold enforcers accountable.
"""

from _cdk import ic
from ggg import Proposal, Vote, User, Member, Notification
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json

import budget
import governance
import membership


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_ENFORCERS = 3              # maximum number of active enforcers
SANCTION_VOTE_DAYS = 5         # days to vote on major sanctions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso():
    return epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")


def _get_enforcer_ids() -> list:
    """Return user IDs of all currently elected enforcers."""
    ids = []
    for p in Proposal.instances():
        try:
            meta = json.loads(p.metadata) if p.metadata else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if meta.get("type") == "elect_enforcer" and p.status == "approved":
            uid = meta.get("enforcer_id")
            if uid and governance._is_active_member(uid):
                ids.append(uid)
    # Remove enforcers who were later removed
    for p in Proposal.instances():
        try:
            meta = json.loads(p.metadata) if p.metadata else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if meta.get("type") == "remove_enforcer" and p.status == "approved":
            uid = meta.get("enforcer_id")
            if uid in ids:
                ids.remove(uid)
    return ids


def is_enforcer(user_id: str) -> bool:
    """Check if a user is a currently elected enforcer."""
    return user_id in _get_enforcer_ids()


# ---------------------------------------------------------------------------
# Report a Violation
# ---------------------------------------------------------------------------

def report_violation(reporter_id: str, target_id: str,
                     title: str, description: str) -> dict:
    """Any active member can report a rule violation.

    The report is recorded and enforcers are notified to review it.
    """
    if not governance._is_active_member(reporter_id):
        return {"reported": False, "reason": "Only active members can report violations."}

    metadata = json.dumps({
        "type": "violation_report",
        "reporter": reporter_id,
        "target": target_id,
        "status": "reported",
        "reported_at": _now_iso(),
    })

    user = User[reporter_id]
    report = Proposal(
        title=f"Violation: {title}",
        description=description,
        status="reported",
        proposer=user,
        metadata=metadata,
    )

    ic.print(f"Violation #{report.id} reported by {reporter_id} against {target_id}")

    # Notify enforcers
    for enforcer_id in _get_enforcer_ids():
        enforcer_user = User[enforcer_id]
        if enforcer_user:
            Notification(
                topic="enforcement",
                title=f"New Violation Report: {title}",
                message=f"A violation has been reported against {target_id}. Please review.",
                user=enforcer_user,
                read=False,
                icon="shield",
                href="/extensions/voting",
                color="orange",
                metadata=f"report_id:{report.id}"
            )

    return {
        "reported": True,
        "report_id": report.id,
        "title": title,
        "target": target_id,
    }


# ---------------------------------------------------------------------------
# Enforcer Actions
# ---------------------------------------------------------------------------

def investigate(enforcer_id: str, report_id: str, findings: str) -> dict:
    """An enforcer reviews a violation report and records their findings."""
    if not is_enforcer(enforcer_id):
        return {"investigated": False, "reason": "Only enforcers can investigate reports."}

    report = Proposal[report_id]
    if not report:
        return {"investigated": False, "reason": "Report not found."}

    if report.status != "reported":
        return {"investigated": False, "reason": f"Report is not pending review (status: {report.status})."}

    try:
        meta = json.loads(report.metadata) if report.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    meta["investigated_by"] = enforcer_id
    meta["findings"] = findings
    meta["investigated_at"] = _now_iso()
    meta["status"] = "investigated"
    report.metadata = json.dumps(meta)
    report.status = "investigated"

    ic.print(f"Report #{report_id} investigated by enforcer {enforcer_id}")

    return {
        "investigated": True,
        "report_id": report_id,
        "enforcer": enforcer_id,
    }


def propose_sanction(enforcer_id: str, report_id: str,
                     sanction_type: str, reason: str) -> dict:
    """An enforcer proposes a sanction based on their investigation.

    sanction_type:
      "warning"    — a formal warning (applied immediately, no vote needed)
      "fine"       — a monetary fine (requires community vote)
      "suspension" — temporary membership suspension (requires community vote)
    """
    if not is_enforcer(enforcer_id):
        return {"proposed": False, "reason": "Only enforcers can propose sanctions."}

    if sanction_type not in ("warning", "fine", "suspension"):
        return {"proposed": False, "reason": "Sanction type must be 'warning', 'fine', or 'suspension'."}

    report = Proposal[report_id]
    if not report:
        return {"proposed": False, "reason": "Report not found."}

    try:
        meta = json.loads(report.metadata) if report.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    target_id = meta.get("target", "")

    if sanction_type == "warning":
        # Warnings are applied immediately — no vote needed
        meta["sanction"] = {
            "type": "warning",
            "reason": reason,
            "applied_by": enforcer_id,
            "applied_at": _now_iso(),
        }
        meta["status"] = "resolved"
        report.metadata = json.dumps(meta)
        report.status = "resolved"

        target_user = User[target_id]
        if target_user:
            Notification(
                topic="enforcement",
                title="Formal Warning",
                message=f"You have received a formal warning. Reason: {reason}",
                user=target_user,
                read=False,
                icon="shield",
                href="/extensions/voting",
                color="orange",
                metadata=f"report_id:{report_id}"
            )

        ic.print(f"Warning applied to {target_id} for report #{report_id}")
        return {"proposed": True, "applied": True, "sanction_type": "warning"}

    # Major sanctions require a community vote
    now_epoch = ic_time_to_epoch(ic.time())
    vote_deadline = epoch_to_datetime_str(
        now_epoch + SANCTION_VOTE_DAYS * 86400
    ).replace(" ", "T")

    meta["sanction"] = {
        "type": sanction_type,
        "reason": reason,
        "proposed_by": enforcer_id,
        "proposed_at": _now_iso(),
    }
    meta["status"] = "pending_vote"
    report.metadata = json.dumps(meta)
    report.status = "voting"
    report.deadline = vote_deadline

    ic.print(f"Sanction '{sanction_type}' proposed for {target_id}, voting until {vote_deadline[:10]}")

    # Notify members about the vote
    for member in Member.instances():
        if member.identity_verification == "verified" and member.user:
            Notification(
                topic="enforcement",
                title=f"Vote on Sanction: {report.title}",
                message=f"Enforcer proposes a {sanction_type} for {target_id}. "
                        f"Reason: {reason}. Vote before {vote_deadline[:10]}.",
                user=member.user,
                read=False,
                icon="shield",
                href="/extensions/voting",
                color="purple",
                metadata=f"report_id:{report_id}"
            )

    return {
        "proposed": True,
        "applied": False,
        "sanction_type": sanction_type,
        "vote_deadline": vote_deadline,
    }


# ---------------------------------------------------------------------------
# Sanction Vote Processing (Scheduled Task)
# ---------------------------------------------------------------------------

def process_sanctions() -> dict:
    """Tally votes on proposed sanctions whose deadline has passed.

    Designed to run as a scheduled task.
    """
    now_str = _now_iso()
    processed = 0
    applied = 0
    rejected = 0

    active_members = governance._count_active_members()

    for report in Proposal.instances():
        if report.status != "voting":
            continue

        try:
            meta = json.loads(report.metadata) if report.metadata else {}
        except (json.JSONDecodeError, TypeError):
            continue

        if meta.get("type") != "violation_report":
            continue

        try:
            if report.deadline and report.deadline > now_str:
                continue
        except (ValueError, TypeError):
            continue

        # Tally votes
        yes_votes = 0
        no_votes = 0
        for v in Vote.instances():
            if v.proposal and v.proposal.id == report.id:
                if v.vote == "yes":
                    yes_votes += 1
                elif v.vote == "no":
                    no_votes += 1

        total_votes = yes_votes + no_votes
        processed += 1

        # Simple majority
        if total_votes > 0 and (yes_votes / total_votes) > 0.5:
            _apply_sanction(report, meta)
            applied += 1
        else:
            report.status = "rejected"
            meta["status"] = "rejected"
            report.metadata = json.dumps(meta)
            rejected += 1
            ic.print(f"Sanction for report #{report.id} rejected ({yes_votes}/{total_votes})")

    return {"processed": processed, "applied": applied, "rejected": rejected}


def _apply_sanction(report, meta: dict):
    """Apply an approved sanction."""
    sanction = meta.get("sanction", {})
    sanction_type = sanction.get("type", "")
    target_id = meta.get("target", "")

    if sanction_type == "fine":
        budget.record_service_payment(
            recipient="justice_fund",
            amount_btc=500 / budget.SATOSHIS_PER_BTC,
            currency="ckBTC",
            description=f"Enforcement fine — report #{report.id}"
        )
        ic.print(f"Fine applied to {target_id} for report #{report.id}")

    elif sanction_type == "suspension":
        membership.deactivate_member(target_id, f"Enforcement sanction — report #{report.id}")
        ic.print(f"Suspension applied to {target_id} for report #{report.id}")

    report.status = "resolved"
    meta["status"] = "resolved"
    meta["sanction"]["applied_at"] = _now_iso()
    report.metadata = json.dumps(meta)

    target_user = User[target_id]
    if target_user:
        Notification(
            topic="enforcement",
            title=f"Sanction Applied: {sanction_type}",
            message=f"A {sanction_type} sanction has been applied. "
                    f"Reason: {sanction.get('reason', 'Community vote')}",
            user=target_user,
            read=False,
            icon="shield",
            href="/extensions/voting",
            color="red",
            metadata=f"report_id:{report.id}"
        )


# ---------------------------------------------------------------------------
# Scheduled Task Entry Point
# ---------------------------------------------------------------------------

def async_task():
    """Entry point for the Task Manager scheduled execution."""
    return process_sanctions()


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_enforcers() -> list:
    """List all currently elected enforcers."""
    return _get_enforcer_ids()


def get_report_summary(report_id: str) -> dict:
    """Get details about a violation report."""
    report = Proposal[report_id]
    if not report:
        return {"error": "Report not found"}

    try:
        meta = json.loads(report.metadata) if report.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    return {
        "report_id": report.id,
        "title": report.title,
        "status": report.status,
        "reporter": meta.get("reporter"),
        "target": meta.get("target"),
        "findings": meta.get("findings"),
        "sanction": meta.get("sanction"),
    }


if __name__ == "__main__":
    print(json.dumps(get_enforcers(), indent=2))
