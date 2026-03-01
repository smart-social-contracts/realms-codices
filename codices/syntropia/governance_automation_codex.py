"""
Governance Codex
Implements separation of powers for a generic western-style democratic state.

Three branches:
  - Legislative: Parliament debates and votes on proposals (bills)
  - Executive: Head of state approves or vetoes bills passed by parliament
  - Judicial: Constitutional court reviews enacted laws for constitutionality
"""

from ggg import Proposal, Vote, User
from datetime import datetime, timedelta
import json


# ---------------------------------------------------------------------------
# Legislative Branch
# ---------------------------------------------------------------------------

def create_legislative_proposal(title: str, description: str, branch: str = "legislative") -> str:
    """Create a new legislative proposal (bill) for parliamentary debate"""
    proposal = Proposal(
        metadata=json.dumps({
            "title": title,
            "description": description,
            "branch": branch,
            "status": "debate",
            "created_by": "parliament",
            "voting_deadline": (datetime.now() + timedelta(days=14)).isoformat(),
            "votes_for": 0,
            "votes_against": 0,
            "votes_abstain": 0,
            "total_votes": 0,
            "executive_approval": None,
            "judicial_review": None
        })
    )
    return proposal.id


# ---------------------------------------------------------------------------
# Executive Branch
# ---------------------------------------------------------------------------

def executive_approve(proposal_id: str, approved: bool) -> dict:
    """Executive branch approves or vetoes a bill that passed parliament"""
    proposal = Proposal.get(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    metadata = json.loads(proposal.metadata)

    if metadata.get("status") != "passed_parliament":
        return {"error": "Proposal must pass parliament before executive review"}

    metadata["executive_approval"] = approved
    metadata["status"] = "enacted" if approved else "vetoed"
    metadata["executive_decision_at"] = datetime.now().isoformat()
    proposal.metadata = json.dumps(metadata)

    return {"proposal_id": proposal_id, "status": metadata["status"]}


# ---------------------------------------------------------------------------
# Judicial Branch
# ---------------------------------------------------------------------------

def judicial_review(proposal_id: str, constitutional: bool) -> dict:
    """Judicial branch reviews an enacted law for constitutionality"""
    proposal = Proposal.get(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}

    metadata = json.loads(proposal.metadata)

    if metadata.get("status") != "enacted":
        return {"error": "Only enacted laws can be judicially reviewed"}

    metadata["judicial_review"] = constitutional
    if not constitutional:
        metadata["status"] = "struck_down"
    metadata["judicial_review_at"] = datetime.now().isoformat()
    proposal.metadata = json.dumps(metadata)

    return {
        "proposal_id": proposal_id,
        "constitutional": constitutional,
        "status": metadata["status"]
    }


# ---------------------------------------------------------------------------
# Vote Processing
# ---------------------------------------------------------------------------

def process_votes():
    """Tally votes on proposals whose deadline has passed and advance them"""
    results = []
    proposals = Proposal.get_all()

    for proposal in proposals:
        metadata = json.loads(proposal.metadata)

        if metadata.get("status") != "debate":
            continue

        deadline = datetime.fromisoformat(metadata["voting_deadline"])
        if datetime.now() <= deadline:
            continue

        votes_for = metadata.get("votes_for", 0)
        votes_against = metadata.get("votes_against", 0)
        total_votes = votes_for + votes_against

        # Simple majority required
        if total_votes > 0 and votes_for > votes_against:
            status = "passed_parliament"
        elif total_votes == 0:
            status = "no_quorum"
        else:
            status = "rejected"

        metadata["status"] = status
        metadata["final_tally"] = {
            "votes_for": votes_for,
            "votes_against": votes_against,
            "total_votes": total_votes,
            "closed_at": datetime.now().isoformat()
        }
        proposal.metadata = json.dumps(metadata)

        results.append({
            "proposal_id": proposal.id,
            "title": metadata["title"],
            "status": status,
            "votes_for": votes_for,
            "votes_against": votes_against
        })

    return results


# ---------------------------------------------------------------------------
# Sample Data
# ---------------------------------------------------------------------------

def create_sample_proposals():
    """Create sample proposals typical of a western parliamentary democracy"""
    proposals = [
        {
            "title": "Annual Budget Appropriations Act",
            "description": "Allocate public funds for healthcare, education, infrastructure, and defence for the fiscal year."
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
