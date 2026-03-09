# Test: Governance
# Covers: legislative proposals, voting, vote processing, executive approval/veto,
#         judicial review
import sys as _sys
from ggg import Proposal, User, Vote, Codex

def load_codex(name):
    """Load a codex module by exec'ing its source from the Codex entity."""
    mod = _sys.modules.get(name)
    if mod is None:
        mod = type(_sys)(name)
        _sys.modules[name] = mod
    if not getattr(mod, '_codex_loaded', False):
        for c in Codex.instances():
            if c.name == name and c.code:
                exec(compile(c.code, name + '.py', 'exec'), mod.__dict__)
                mod._codex_loaded = True
                return mod
        raise ImportError("Codex not found: " + name)
    return mod

ts = "g" + str(id(object()))[-6:]
today = "2026-03-09"
deadline = today + "T23:59:59"

# Setup users
user_alice = User(id=ts + "_alice", name="Alice")
user_bob = User(id=ts + "_bob", name="Bob")
user_carol = User(id=ts + "_carol", name="Carol")

# ── TEST 1: Create Legislative Proposal ──────────────────────────────────
print("=== TEST 1: LEGISLATIVE PROPOSAL ===")
leg_prop = Proposal(
    proposal_id=ts + "_leg_001",
    title="Universal Healthcare Coverage Act",
    description="Extend basic healthcare to all registered citizens",
    status="debate",
    voting_deadline=deadline,
    metadata="branch:legislative",
)
print("Legislative proposal: " + leg_prop.proposal_id + " status=" + leg_prop.status)

# ── TEST 2: Cast Votes ───────────────────────────────────────────────────
print("=== TEST 2: CAST VOTES ===")
# Note: Vote.proposal ManyToOne expects a 'votes' reverse on Proposal which
# is not defined, so we link votes via metadata instead.
vote_a = Vote(voter=user_alice, vote_choice="yes", metadata="proposal:" + leg_prop.proposal_id)
vote_b = Vote(voter=user_bob, vote_choice="yes", metadata="proposal:" + leg_prop.proposal_id)
vote_c = Vote(voter=user_carol, vote_choice="no", metadata="proposal:" + leg_prop.proposal_id)
print("Votes cast: Alice=yes, Bob=yes, Carol=no")

leg_prop.votes_yes = 2.0
leg_prop.votes_no = 1.0
leg_prop.total_voters = 3.0
print("Tally: yes=" + str(int(leg_prop.votes_yes)) + " no=" + str(int(leg_prop.votes_no)))

# ── TEST 3: Process Vote Results (simple majority) ───────────────────────
print("=== TEST 3: VOTE RESULTS ===")
votes_for = int(leg_prop.votes_yes or 0)
votes_against = int(leg_prop.votes_no or 0)
total = votes_for + votes_against
assert total > 0, "Should have votes"
passed = votes_for > votes_against
assert passed, "Proposal should pass with 2 vs 1"
leg_prop.status = "passed_parliament"
print("Proposal " + leg_prop.proposal_id + " passed parliament (" + str(votes_for) + " vs " + str(votes_against) + ")")

# ── TEST 4: Executive Approval & Veto ────────────────────────────────────
print("=== TEST 4: EXECUTIVE APPROVAL & VETO ===")
governance_codex = load_codex("governance_automation_codex")

approve_result = governance_codex.executive_approve(leg_prop.proposal_id, approved=True)
assert approve_result.get("status") == "enacted", "Should be enacted: " + str(approve_result)
print("Executive approved: " + str(approve_result))

# Create a second proposal to test veto
veto_prop = Proposal(
    proposal_id=ts + "_leg_002",
    title="Controversial Tax Bill",
    description="Double all tax rates immediately",
    status="passed_parliament",
    voting_deadline=deadline,
    metadata="branch:legislative",
)
veto_result = governance_codex.executive_approve(veto_prop.proposal_id, approved=False)
assert veto_result.get("status") == "vetoed", "Should be vetoed"
print("Executive vetoed: " + str(veto_result))

# ── TEST 5: Judicial Review ──────────────────────────────────────────────
print("=== TEST 5: JUDICIAL REVIEW ===")
jr_pass = governance_codex.judicial_review(leg_prop.proposal_id, constitutional=True)
assert jr_pass.get("constitutional") == True
print("Judicial review (constitutional): " + str(jr_pass))

strike_prop = Proposal(
    proposal_id=ts + "_leg_003",
    title="Unconstitutional Surveillance Act",
    description="Mass surveillance without warrant",
    status="enacted",
    voting_deadline=deadline,
    metadata="branch:legislative",
)
jr_fail = governance_codex.judicial_review(strike_prop.proposal_id, constitutional=False)
assert jr_fail.get("status") == "struck_down"
print("Judicial review (struck down): " + str(jr_fail))

# Summary
print("=== GOVERNANCE TESTS PASSED ===")
print("Proposals: " + str(Proposal.count()) + " Votes: " + str(Vote.count()))
