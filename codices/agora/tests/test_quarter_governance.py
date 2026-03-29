"""
Tests for quarter_governance.py — quarter-dependent codex logic.

Validates:
  - Tax splitting: capital keeps 100%, quarters split local/federal
  - Budget allocation: capital distributes proportionally by population
  - Voting scope: local proposals restricted to quarter residents,
    federal proposals restricted to capital submission
"""

from ggg import Realm, Quarter, QuarterConfig, User, Member, Proposal, Vote

import quarter_governance as qg

# Constants for test canister IDs
CAPITAL_ID = "capital-canister-id"
QUARTER_1_ID = "quarter-1-canister-id"
QUARTER_2_ID = "quarter-2-canister-id"


def _setup_capital():
    """Configure mock as the capital canister."""
    ic.set_id(CAPITAL_ID)
    Realm(id="1", is_capital=True, is_quarter=False)
    Quarter(name="Quarter 1", canister_id=QUARTER_1_ID, status="active", population=10)
    Quarter(name="Quarter 2", canister_id=QUARTER_2_ID, status="active", population=20)


def _setup_quarter(quarter_id, local_tax_rate=0.0, welfare_percent=30,
                   voting_window_days=7):
    """Configure mock as a non-capital quarter canister."""
    ic.set_id(quarter_id)
    Realm(id="1", is_capital=False, is_quarter=True)
    QuarterConfig(
        id="1",
        local_tax_rate=local_tax_rate,
        welfare_percent=welfare_percent,
        voting_window_days=voting_window_days,
    )


def _add_active_member(user_id, home_quarter=None):
    """Create an active member for testing."""
    u = User(id=user_id, home_quarter=home_quarter or "")
    Member(user=u, identity_verification="verified")
    return u


# ══════════════════════════════════════════════════════════════════════════
# 1. Tax Tests
# ══════════════════════════════════════════════════════════════════════════

print("Testing tax collection on capital...")

_setup_capital()
result = qg.record_tax_payment("user-1", 1.0, "ckBTC")

assert result["recorded"], f"Expected recorded=True: {result}"
assert result["is_capital"] is True
assert result["local_satoshis"] == 100_000_000, f"Capital should keep 100%: {result}"
assert result["federal_satoshis"] == 0, f"Capital has no federal portion: {result}"
print("  capital keeps 100%: OK")

# ── Quarter splits local + federal ────────────────────────────────────────

# Reset entities between scenarios
from realms.testing import reset_registry
reset_registry()

print("Testing tax split on quarter...")

_setup_quarter(QUARTER_1_ID)
result = qg.record_tax_payment("user-2", 1.0, "ckBTC")

assert result["recorded"]
assert result["is_capital"] is False
assert result["federal_satoshis"] == 10_000_000, (
    f"Expected 10% federal (10M sat): {result['federal_satoshis']}"
)
assert result["local_satoshis"] == 90_000_000, (
    f"Expected 90% local (90M sat): {result['local_satoshis']}"
)
assert result["local_satoshis"] + result["federal_satoshis"] == 100_000_000
print("  quarter splits 90/10: OK")

# ── Small amount rounding ─────────────────────────────────────────────────

print("Testing tax rounding on small amounts...")
result = qg.record_tax_payment("user-3", 0.00000001, "ckBTC")  # 1 satoshi
assert result["total_satoshis"] == 1
assert result["federal_satoshis"] == 0  # 10% of 1 rounds to 0
assert result["local_satoshis"] == 1
print("  small amount rounding: OK")


# ══════════════════════════════════════════════════════════════════════════
# 2. Budget Allocation Tests
# ══════════════════════════════════════════════════════════════════════════

reset_registry()

print("Testing federal budget allocation on capital...")

_setup_capital()  # Creates Quarter 1 (pop=10) and Quarter 2 (pop=20)

result = qg.allocate_federal_budget(300_000_000)  # 3 BTC in sats

assert result["allocated"] is True
assert len(result["distributions"]) == 2

# Quarter 1 has pop=10 (1/3), Quarter 2 has pop=20 (2/3)
q1_alloc = result["distributions"][0]
q2_alloc = result["distributions"][1]

assert q1_alloc["quarter"] == "Quarter 1"
assert q1_alloc["amount_satoshis"] == 100_000_000, (
    f"Quarter 1 should get 1/3: {q1_alloc['amount_satoshis']}"
)
assert q2_alloc["quarter"] == "Quarter 2"
assert q2_alloc["amount_satoshis"] == 200_000_000, (
    f"Quarter 2 should get 2/3: {q2_alloc['amount_satoshis']}"
)
print("  population-proportional allocation: OK")

# ── Non-capital cannot allocate ───────────────────────────────────────────

reset_registry()

print("Testing budget allocation rejected on quarter...")

_setup_quarter(QUARTER_1_ID)
result = qg.allocate_federal_budget(100_000_000)
assert result["allocated"] is False
assert "not capital" in result["reason"]
print("  non-capital allocation rejected: OK")


# ══════════════════════════════════════════════════════════════════════════
# 3. Voting Scope Tests
# ══════════════════════════════════════════════════════════════════════════

reset_registry()

print("Testing local proposal submission on quarter...")

_setup_quarter(QUARTER_1_ID, voting_window_days=5)
resident = _add_active_member("resident-1", home_quarter=QUARTER_1_ID)

result = qg.submit_proposal(
    "resident-1", "Build a Park", "Green space for Quarter 1",
    "treasury_spend", scope="local"
)
assert result["submitted"], f"Local proposal should succeed: {result}"
assert result["scope"] == "local"
assert result["quarter"] == QUARTER_1_ID
proposal_id = result["proposal_id"]
print("  local proposal on quarter: OK")

# ── Resident can vote on local proposal ───────────────────────────────────

print("Testing resident can vote on local proposal...")

result = qg.cast_vote("resident-1", proposal_id, "yes")
assert result["voted"], f"Resident should be able to vote: {result}"
assert result["scope"] == "local"
print("  resident votes on local: OK")

# ── Outsider cannot vote on local proposal ────────────────────────────────

print("Testing outsider blocked from local proposal vote...")

outsider = _add_active_member("outsider-1", home_quarter=QUARTER_2_ID)
result = qg.cast_vote("outsider-1", proposal_id, "yes")
assert not result["voted"], f"Outsider should be blocked: {result}"
assert "quarter residents" in result["reason"].lower()
print("  outsider blocked from local vote: OK")

# ── Federal proposal rejected on quarter ──────────────────────────────────

print("Testing federal proposal rejected on quarter...")

result = qg.submit_proposal(
    "resident-1", "Change Federal Tax", "Reduce to 5%",
    "welfare_policy", scope="federal"
)
assert not result["submitted"]
assert "capital" in result["reason"].lower()
print("  federal proposal on quarter rejected: OK")

# ── Federal proposal allowed on capital ───────────────────────────────────

reset_registry()

print("Testing federal proposal on capital...")

_setup_capital()
capital_member = _add_active_member("capital-member-1", home_quarter=CAPITAL_ID)

result = qg.submit_proposal(
    "capital-member-1", "Federation Tax Rate", "Change to 5%",
    "welfare_policy", scope="federal"
)
assert result["submitted"], f"Federal proposal on capital should work: {result}"
assert result["scope"] == "federal"
federal_proposal_id = result["proposal_id"]
print("  federal proposal on capital: OK")

# ── Any member can vote on federal proposal ───────────────────────────────

print("Testing any member can vote on federal proposal...")

# A member whose home_quarter is a different quarter can still vote on federal
other_member = _add_active_member("quarter-member-1", home_quarter=QUARTER_1_ID)
result = qg.cast_vote("quarter-member-1", federal_proposal_id, "no")
assert result["voted"], f"Any member should vote on federal: {result}"
assert result["scope"] == "federal"
print("  cross-quarter federal vote: OK")

# ── Duplicate vote rejected ───────────────────────────────────────────────

print("Testing duplicate vote rejected...")

result = qg.cast_vote("quarter-member-1", federal_proposal_id, "yes")
assert not result["voted"]
assert "already voted" in result["reason"].lower()
print("  duplicate vote rejected: OK")

# ── Non-member cannot submit ──────────────────────────────────────────────

print("Testing non-member cannot submit proposal...")

result = qg.submit_proposal(
    "random-user", "Anything", "Description",
    "treasury_spend", scope="local"
)
assert not result["submitted"]
assert "active members" in result["reason"].lower()
print("  non-member submission rejected: OK")


# ══════════════════════════════════════════════════════════════════════════
# 4. Quarter Context Tests
# ══════════════════════════════════════════════════════════════════════════

reset_registry()

print("Testing quarter context on capital...")

_setup_capital()
ctx = qg.get_quarter_context()
assert ctx["canister_id"] == CAPITAL_ID
assert ctx["is_capital"] is True
assert ctx["voting_window_days"] == 7  # default
print("  capital context: OK")

reset_registry()

print("Testing quarter context with custom config...")

_setup_quarter(QUARTER_1_ID, local_tax_rate=0.05, welfare_percent=40,
               voting_window_days=3)
ctx = qg.get_quarter_context()
assert ctx["canister_id"] == QUARTER_1_ID
assert ctx["is_capital"] is False
assert ctx["local_tax_rate"] == 0.05
assert ctx["welfare_percent"] == 40
assert ctx["voting_window_days"] == 3
print("  custom quarter config: OK")


print("\n✅ All quarter governance tests passed!")
