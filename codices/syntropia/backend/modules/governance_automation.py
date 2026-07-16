"""
Syntropia Governance Codex
Implements separation of powers for a representative democracy.

Three branches:
  - Legislative: Parliament debates and votes on proposals (bills)
  - Executive: Head of state approves or vetoes bills passed by parliament
  - Judicial: Constitutional court reviews enacted laws for constitutionality
"""

from ggg import Proposal, Vote, User, Realm
from datetime import datetime, timedelta
import json
import uuid


# ---------------------------------------------------------------------------
# Lifecycle gate — before production, member voting is not executable.
# Only admins can make fundamental changes (see issue: Syntropia greenfield).
# ---------------------------------------------------------------------------

class MemberVotingNotAllowed(Exception):
    """Raised when a member attempts to vote/propose before the realm is live."""


def _realm():
    instances = Realm.instances()
    return list(instances)[0] if instances else None


def _realm_stage() -> str:
    realm = _realm()
    return (getattr(realm, "status", None) or "alpha") if realm else "alpha"


def _member_voting_enabled_stage() -> str:
    """Stage at which member voting becomes executable (default: production)."""
    realm = _realm()
    try:
        meta = json.loads(realm.manifest_data) if realm and realm.manifest_data else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}
    return meta.get("governance", {}).get("member_voting_enabled_stage", "production")


def member_voting_enabled() -> bool:
    """True once the realm has reached the stage where members may vote."""
    return _realm_stage() == _member_voting_enabled_stage()


def _ensure_can_act(actor_is_admin: bool):
    """Gate: members can only propose/vote once the realm is live; admins always can."""
    if actor_is_admin:
        return
    if not member_voting_enabled():
        raise MemberVotingNotAllowed(
            f"Member voting is not executable before the '{_member_voting_enabled_stage()}' "
            f"stage (current: '{_realm_stage()}'). Only admins can make fundamental changes."
        )


# ---------------------------------------------------------------------------
# Legislative Branch
# ---------------------------------------------------------------------------

def create_legislative_proposal(title: str, description: str, branch: str = "legislative",
                                actor_is_admin: bool = False) -> str:
    """Create a new legislative proposal (bill) for parliamentary debate.

    Before the realm reaches production, only admins may create proposals.
    """
    _ensure_can_act(actor_is_admin)
    pid = "leg_" + uuid.uuid4().hex[:8]
    deadline = (datetime.now() + timedelta(days=14)).isoformat()

    proposal = Proposal(
        proposal_id=pid,
        title=title,
        description=description,
        status="debate",
        voting_deadline=deadline,
        metadata=f"branch:{branch}",
    )
    return proposal.proposal_id


def cast_member_vote(proposal_id: str, choice: str, actor_is_admin: bool = False) -> dict:
    """Record a member's vote on a proposal.

    Enforces the lifecycle gate: before production, members cannot vote — only
    admins can make fundamental changes.
    """
    _ensure_can_act(actor_is_admin)

    proposal = _find_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    if choice == "yes":
        proposal.votes_yes = int(proposal.votes_yes or 0) + 1
    elif choice == "no":
        proposal.votes_no = int(proposal.votes_no or 0) + 1
    else:
        return {"error": "Vote must be 'yes' or 'no'"}

    return {
        "proposal_id": proposal_id,
        "choice": choice,
        "votes_yes": int(proposal.votes_yes or 0),
        "votes_no": int(proposal.votes_no or 0),
    }


# ---------------------------------------------------------------------------
# Executive Branch
# ---------------------------------------------------------------------------

def _find_proposal(proposal_id: str):
    """Find a Proposal by proposal_id."""
    return Proposal[proposal_id]


def executive_approve(proposal_id: str, approved: bool) -> dict:
    """Executive branch approves or vetoes a bill that passed parliament"""
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    if proposal.status != "passed_parliament":
        return {"error": "Proposal must pass parliament before executive review"}

    new_status = "enacted" if approved else "vetoed"
    proposal.status = new_status

    return {"proposal_id": proposal_id, "status": new_status}


# ---------------------------------------------------------------------------
# Judicial Branch
# ---------------------------------------------------------------------------

def judicial_review(proposal_id: str, constitutional: bool) -> dict:
    """Judicial branch reviews an enacted law for constitutionality"""
    proposal = _find_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    if proposal.status != "enacted":
        return {"error": "Only enacted laws can be judicially reviewed"}

    if not constitutional:
        proposal.status = "struck_down"

    return {
        "proposal_id": proposal_id,
        "constitutional": constitutional,
        "status": proposal.status,
    }


# ---------------------------------------------------------------------------
# Vote Processing
# ---------------------------------------------------------------------------

def process_votes():
    """Tally votes on proposals whose deadline has passed and advance them"""
    results = []

    for proposal in Proposal.instances():
        if proposal.status != "debate":
            continue

        if not proposal.voting_deadline:
            continue

        try:
            deadline = datetime.fromisoformat(proposal.voting_deadline)
        except (ValueError, TypeError):
            continue

        if datetime.now() <= deadline:
            continue

        votes_for = int(proposal.votes_yes or 0)
        votes_against = int(proposal.votes_no or 0)
        total_votes = votes_for + votes_against

        # Simple majority required
        if total_votes > 0 and votes_for > votes_against:
            status = "passed_parliament"
        elif total_votes == 0:
            status = "no_quorum"
        else:
            status = "rejected"

        proposal.status = status

        results.append({
            "proposal_id": proposal.proposal_id,
            "title": proposal.title,
            "status": status,
            "votes_for": votes_for,
            "votes_against": votes_against,
        })

    return results


# ---------------------------------------------------------------------------
# Sample Data
# ---------------------------------------------------------------------------

def create_sample_proposals():
    """Create sample proposals typical of a representative democracy"""
    proposals = [
        {
            "title": "Annual Budget Appropriations Act",
            "description": "Allocate public funds for healthcare, education, infrastructure, and welfare for the fiscal year."
        },
        {
            "title": "Income Tax Rate Adjustment",
            "description": "Adjust progressive income tax brackets to account for inflation and economic growth."
        },
        {
            "title": "Universal Healthcare Coverage Extension",
            "description": "Extend basic healthcare coverage to all registered citizens and permanent residents."
        }
    ]

    created = []
    for p in proposals:
        pid = create_legislative_proposal(p["title"], p["description"])
        created.append(pid)
    return created


# Main execution
if __name__ == "__main__":
    proposals = create_sample_proposals()
    print(f"Created {len(proposals)} sample proposals")
    results = process_votes()
    print(f"Processed {len(results)} proposals")
