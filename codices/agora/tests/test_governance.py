"""
Tests for governance_automation.py — proposal and voting system.

Validates:
  - Proposal creation with correct metadata
  - Sample proposal batch creation
  - Vote processing (tally and status updates)
"""

from ggg import Proposal, Vote, User
from datetime import datetime, timedelta
import json

import governance_automation

# ── Test create_sample_proposal ────────────────────────────────────────────

print("Testing create_sample_proposal...")

proposal_id = governance_automation.create_sample_proposal(
    "Test Proposal",
    "A test proposal description"
)

assert Proposal.count() == 1, f"Expected 1 proposal, got {Proposal.count()}"

p = Proposal.instances()[0]
assert p.metadata is not None

metadata = json.loads(p.metadata)
assert metadata["title"] == "Test Proposal"
assert metadata["description"] == "A test proposal description"
assert metadata["status"] == "active"
assert metadata["votes_for"] == 0
assert metadata["votes_against"] == 0

# Verify voting deadline is ~7 days from now
deadline = datetime.fromisoformat(metadata["voting_deadline"])
now = datetime.now()
delta = deadline - now
assert 6 <= delta.days <= 7, f"Expected ~7 day deadline, got {delta.days} days"

print("  create_sample_proposal: OK")

# ── Test create_sample_proposals ───────────────────────────────────────────

print("Testing create_sample_proposals...")

# Clear and recreate
for p in Proposal.instances():
    p.delete()

proposal_ids = governance_automation.create_sample_proposals()
assert len(proposal_ids) == 3, f"Expected 3 proposals, got {len(proposal_ids)}"
assert Proposal.count() == 3

titles = []
for p in Proposal.instances():
    meta = json.loads(p.metadata)
    titles.append(meta["title"])

assert "Increase Social Benefits by 10%" in titles
assert "Implement Green Energy Tax Credits" in titles
assert "Digital Identity Verification System" in titles

print("  create_sample_proposals: OK")

# ── Test process_votes ─────────────────────────────────────────────────────

print("Testing process_votes...")

# process_votes should run without errors and return results list
# (no proposals have expired deadlines yet, so results should be empty)
results = governance_automation.process_votes()
assert isinstance(results, list), f"Expected list, got {type(results)}"
assert len(results) == 0, "No proposals should be past deadline yet"

# Now create a proposal with an already-expired deadline and test processing
for p in Proposal.instances():
    p.delete()

expired_proposal = Proposal(
    metadata=json.dumps({
        "title": "Expired Proposal",
        "description": "This proposal has an expired deadline",
        "status": "active",
        "created_by": "system",
        "voting_deadline": (datetime.now() - timedelta(days=1)).isoformat(),
        "votes_for": 5,
        "votes_against": 2,
        "total_votes": 7
    })
)

results = governance_automation.process_votes()
assert len(results) == 1, f"Expected 1 processed proposal, got {len(results)}"
assert results[0]["status"] == "passed", f"Expected 'passed', got {results[0]['status']}"
assert results[0]["votes_for"] == 5
assert results[0]["votes_against"] == 2

# Verify the proposal metadata was updated
updated_meta = json.loads(expired_proposal.metadata)
assert updated_meta["status"] == "passed"
assert "final_tally" in updated_meta

print("  process_votes: OK")

print("\n✅ All governance_automation tests passed!")
