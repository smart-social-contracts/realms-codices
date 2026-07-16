"""
Governance Automation Codex
Processes proposals and votes for democratic governance
"""

from ggg import Proposal, Vote, User
from datetime import datetime, timedelta
import json

def create_sample_proposal(title: str, description: str) -> str:
    """Create a new governance proposal"""
    proposal = Proposal(
        metadata=json.dumps({
            "title": title,
            "description": description,
            "status": "active",
            "created_by": "system",
            "voting_deadline": (datetime.now() + timedelta(days=7)).isoformat(),
            "votes_for": 0,
            "votes_against": 0,
            "total_votes": 0
        })
    )
    
    return proposal.id

def process_votes():
    """Process all active proposals and tally votes"""
    results = []
    
    # Get all proposals
    proposals = Proposal.get_all()
    
    for proposal in proposals:
        metadata = json.loads(proposal.metadata)
        
        if metadata.get("status") == "active":
            # Check if voting deadline has passed
            deadline = datetime.fromisoformat(metadata["voting_deadline"])
            
            if datetime.now() > deadline:
                # Tally votes and close proposal
                votes_for = metadata.get("votes_for", 0)
                votes_against = metadata.get("votes_against", 0)
                total_votes = votes_for + votes_against
                
                # Determine outcome
                if total_votes > 0:
                    if votes_for > votes_against:
                        status = "passed"
                    else:
                        status = "rejected"
                else:
                    status = "no_votes"
                
                # Update proposal
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

def create_sample_proposals():
    """Create sample governance proposals"""
    proposals = [
        {
            "title": "Increase Social Benefits by 10%",
            "description": "Proposal to increase monthly social benefits for all eligible citizens by 10% to account for inflation."
        },
        {
            "title": "Implement Green Energy Tax Credits",
            "description": "Provide tax credits for citizens and organizations investing in renewable energy infrastructure."
        },
        {
            "title": "Digital Identity Verification System",
            "description": "Implement a new digital identity verification system to streamline government services."
        }
    ]
    
    created_proposals = []
    for proposal in proposals:
        proposal_id = create_sample_proposal(proposal["title"], proposal["description"])
        created_proposals.append(proposal_id)
    
    return created_proposals

# Main execution
if __name__ == "__main__":
    # Create sample proposals
    proposals = create_sample_proposals()
    print(f"Created {len(proposals)} sample proposals")
    
    # Process votes
    results = process_votes()
    print(f"Processed {len(results)} proposals")
