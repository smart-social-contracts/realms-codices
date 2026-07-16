"""
Justice Codex
A simple dispute resolution system for the Agora realm.

How it works:
  1. Any active member can file a case against another member.
  2. A jury of random active members is selected to decide the case.
  3. Jurors vote "guilty" or "not_guilty" (one vote each).
  4. When the voting deadline passes, the verdict is tallied.
  5. If guilty: a fine is recorded and the defendant is notified.
     If not guilty: the case is dismissed.

All fines flow into the Justice Fund and are tracked in the budget.
"""

from _cdk import ic
from ggg import Proposal, Vote, User, Member, Notification
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json
import hashlib

import budget
import governance


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JURY_SIZE = 5                  # number of jurors per case
TRIAL_WINDOW_DAYS = 7          # how long jurors have to vote
GUILTY_THRESHOLD = 0.5         # >50% of jurors must vote guilty
DEFAULT_FINE_SATOSHIS = 500    # default fine for guilty verdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso():
    return epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")


def _get_active_member_ids() -> list:
    """Return user IDs of all active members."""
    ids = []
    for member in Member.instances():
        if member.user and member.identity_verification == "verified":
            ids.append(member.user.id)
    return ids


def _pick_jury(exclude_ids: list, seed: str) -> list:
    """Pick JURY_SIZE random active members, excluding plaintiff and defendant.

    Uses a deterministic hash-based shuffle so results are reproducible.
    """
    candidates = [uid for uid in _get_active_member_ids() if uid not in exclude_ids]

    if len(candidates) <= JURY_SIZE:
        return candidates

    def sort_key(uid):
        return hashlib.sha256((seed + uid).encode()).hexdigest()

    candidates.sort(key=sort_key)
    return candidates[:JURY_SIZE]


# ---------------------------------------------------------------------------
# File a Case
# ---------------------------------------------------------------------------

def file_case(plaintiff_id: str, defendant_id: str,
              title: str, description: str) -> dict:
    """File a dispute case against another member.

    Both plaintiff and defendant must be active members.
    A jury is automatically selected and voting opens.
    """
    if not governance._is_active_member(plaintiff_id):
        return {"filed": False, "reason": "Only active members can file cases."}

    if not governance._is_active_member(defendant_id):
        return {"filed": False, "reason": "The defendant must be an active member."}

    if plaintiff_id == defendant_id:
        return {"filed": False, "reason": "You cannot file a case against yourself."}

    now_epoch = ic_time_to_epoch(ic.time())
    deadline = epoch_to_datetime_str(now_epoch + TRIAL_WINDOW_DAYS * 86400).replace(" ", "T")

    seed = f"{plaintiff_id}-{defendant_id}-{now_epoch}"
    jury = _pick_jury(exclude_ids=[plaintiff_id, defendant_id], seed=seed)

    if len(jury) < 3:
        return {"filed": False, "reason": "Not enough eligible jurors available."}

    metadata = json.dumps({
        "type": "justice_case",
        "plaintiff": plaintiff_id,
        "defendant": defendant_id,
        "jury": jury,
        "filed_at": _now_iso(),
    })

    user = User[plaintiff_id]
    case = Proposal(
        title=f"Case: {title}",
        description=description,
        status="voting",
        deadline=deadline,
        proposer=user,
        metadata=metadata,
    )

    ic.print(f"Case #{case.id} filed by {plaintiff_id} against {defendant_id}")

    # Notify jurors
    for juror_id in jury:
        juror_user = User[juror_id]
        if juror_user:
            Notification(
                topic="justice",
                title=f"Jury Duty: {title}",
                message=f"You have been selected as a juror. "
                        f"Please review the case and vote before {deadline[:10]}.",
                user=juror_user,
                read=False,
                icon="gavel",
                href="/extensions/voting",
                color="purple",
                metadata=f"case_id:{case.id}"
            )

    # Notify defendant
    defendant_user = User[defendant_id]
    if defendant_user:
        Notification(
            topic="justice",
            title=f"Case Filed Against You: {title}",
            message=f"A case has been filed against you. "
                    f"A jury of {len(jury)} members will decide by {deadline[:10]}.",
            user=defendant_user,
            read=False,
            icon="gavel",
            href="/extensions/voting",
            color="orange",
            metadata=f"case_id:{case.id}"
        )

    return {
        "filed": True,
        "case_id": case.id,
        "title": title,
        "jury_size": len(jury),
        "deadline": deadline,
    }


# ---------------------------------------------------------------------------
# Jury Voting
# ---------------------------------------------------------------------------

def cast_verdict(juror_id: str, case_id: str, verdict: str) -> dict:
    """A juror casts their verdict on a case.

    verdict must be "guilty" or "not_guilty".
    Only selected jurors can vote.
    """
    if verdict not in ("guilty", "not_guilty"):
        return {"voted": False, "reason": "Verdict must be 'guilty' or 'not_guilty'."}

    case = Proposal[case_id]
    if not case:
        return {"voted": False, "reason": "Case not found."}

    if case.status != "voting":
        return {"voted": False, "reason": f"Case is not open for voting (status: {case.status})."}

    try:
        meta = json.loads(case.metadata) if case.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    if meta.get("type") != "justice_case":
        return {"voted": False, "reason": "This is not a justice case."}

    jury = meta.get("jury", [])
    if juror_id not in jury:
        return {"voted": False, "reason": "You are not a juror on this case."}

    # Check deadline
    try:
        if case.deadline and _now_iso() > case.deadline:
            return {"voted": False, "reason": "Voting period has ended."}
    except (ValueError, TypeError):
        pass

    # Check if already voted
    for v in Vote.instances():
        if (v.proposal and v.proposal.id == case_id
                and v.user and v.user.id == juror_id):
            return {"voted": False, "reason": "You have already voted on this case."}

    user = User[juror_id]
    Vote(
        proposal=case,
        user=user,
        vote=verdict,
        metadata=json.dumps({"voted_at": _now_iso()})
    )

    ic.print(f"Juror {juror_id} voted '{verdict}' on case #{case_id}")
    return {"voted": True, "case_id": case_id, "verdict": verdict}


# ---------------------------------------------------------------------------
# Verdict Processing (Scheduled Task)
# ---------------------------------------------------------------------------

def process_verdicts() -> dict:
    """Tally jury votes on cases whose deadline has passed.

    Designed to run as a scheduled task.
    """
    now_str = _now_iso()
    processed = 0
    guilty_count = 0
    dismissed_count = 0

    for case in Proposal.instances():
        if case.status != "voting":
            continue

        try:
            meta = json.loads(case.metadata) if case.metadata else {}
        except (json.JSONDecodeError, TypeError):
            continue

        if meta.get("type") != "justice_case":
            continue

        try:
            if case.deadline and case.deadline > now_str:
                continue
        except (ValueError, TypeError):
            continue

        # Tally votes
        guilty_votes = 0
        not_guilty_votes = 0
        for v in Vote.instances():
            if v.proposal and v.proposal.id == case.id:
                if v.vote == "guilty":
                    guilty_votes += 1
                elif v.vote == "not_guilty":
                    not_guilty_votes += 1

        total_votes = guilty_votes + not_guilty_votes
        processed += 1

        if total_votes == 0:
            case.status = "dismissed"
            dismissed_count += 1
            ic.print(f"Case #{case.id} dismissed — no votes cast")
            continue

        if (guilty_votes / total_votes) > GUILTY_THRESHOLD:
            case.status = "guilty"
            guilty_count += 1
            _apply_penalty(case, meta)
            ic.print(f"Case #{case.id} GUILTY ({guilty_votes}/{total_votes})")
        else:
            case.status = "not_guilty"
            dismissed_count += 1
            ic.print(f"Case #{case.id} NOT GUILTY ({guilty_votes}/{total_votes})")
            _notify_acquittal(case, meta)

    return {
        "processed": processed,
        "guilty": guilty_count,
        "dismissed": dismissed_count,
    }


def _apply_penalty(case, meta: dict):
    """Record a fine for a guilty verdict."""
    defendant_id = meta.get("defendant", "")

    budget.record_service_payment(
        recipient="justice_fund",
        amount_btc=DEFAULT_FINE_SATOSHIS / budget.SATOSHIS_PER_BTC,
        currency="ckBTC",
        description=f"Fine from case #{case.id}"
    )

    defendant_user = User[defendant_id]
    if defendant_user:
        Notification(
            topic="justice",
            title=f"Guilty Verdict: {case.title}",
            message=f"The jury found you guilty. A fine of {DEFAULT_FINE_SATOSHIS} satoshis has been applied.",
            user=defendant_user,
            read=False,
            icon="gavel",
            href="/extensions/voting",
            color="red",
            metadata=f"case_id:{case.id}"
        )


def _notify_acquittal(case, meta: dict):
    """Notify the defendant they were found not guilty."""
    defendant_id = meta.get("defendant", "")
    defendant_user = User[defendant_id]
    if defendant_user:
        Notification(
            topic="justice",
            title=f"Acquitted: {case.title}",
            message="The jury found you not guilty. The case has been dismissed.",
            user=defendant_user,
            read=False,
            icon="gavel",
            href="/extensions/voting",
            color="green",
            metadata=f"case_id:{case.id}"
        )


# ---------------------------------------------------------------------------
# Scheduled Task Entry Point
# ---------------------------------------------------------------------------

def async_task():
    """Entry point for the Task Manager scheduled execution."""
    return process_verdicts()


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_case_summary(case_id: str) -> dict:
    """Get details about a justice case including the current vote tally."""
    case = Proposal[case_id]
    if not case:
        return {"error": "Case not found"}

    try:
        meta = json.loads(case.metadata) if case.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    guilty_votes = 0
    not_guilty_votes = 0
    for v in Vote.instances():
        if v.proposal and v.proposal.id == case_id:
            if v.vote == "guilty":
                guilty_votes += 1
            elif v.vote == "not_guilty":
                not_guilty_votes += 1

    return {
        "case_id": case.id,
        "title": case.title,
        "status": case.status,
        "deadline": case.deadline,
        "plaintiff": meta.get("plaintiff"),
        "defendant": meta.get("defendant"),
        "jury_size": len(meta.get("jury", [])),
        "guilty_votes": guilty_votes,
        "not_guilty_votes": not_guilty_votes,
    }


if __name__ == "__main__":
    print(json.dumps(get_case_summary(""), indent=2))
