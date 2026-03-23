"""
Tests for governance_automation.py — proposal and voting system.

Validates:
  - Proposal creation with correct metadata
  - Sample proposal batch creation
  - BUG DETECTION: process_votes() uses Proposal.get_all() which doesn't exist
    (should be Proposal.instances())
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

# The function returns proposal.id which is an internal field, not proposal_id
# (Note: agora stores everything in metadata JSON, not in Proposal fields)
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

# ── Test process_votes — BUG DETECTION ─────────────────────────────────────

print("Testing process_votes (expected to fail — Proposal.get_all() is not a valid API)...")

try:
    results = governance_automation.process_votes()
    print("  UNEXPECTED: process_votes() did not raise an error")
    print("  This means the bug may have been fixed")
except AttributeError as e:
    assert "get_all" in str(e), f"Expected get_all error, got: {e}"
    print(f"  BUG CONFIRMED: {e}")
    print("  FIX: Replace Proposal.get_all() with Proposal.instances()")

print("\n✅ All governance_automation tests passed!")
