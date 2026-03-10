# Test: Spending & Welfare
# Covers: welfare benefit distribution, procurement project workflow,
#         treasury savings with supermajority withdrawal
import json
import procurement_codex
import treasury_savings_codex
from ggg import (
    Proposal, User, Member, Transfer, Notification,
    LedgerEntry, EntryType, Category,
    Budget, BudgetStatus,
)

ts = "s" + str(id(object()))[-6:]
today = "2026-03-09"
deadline = today + "T23:59:59"

# Setup
user_alice = User(id=ts + "_alice", name="Alice")
member_alice = Member(
    user=user_alice, identity_verification="verified",
    residence_permit="valid", tax_compliance="compliant",
    public_benefits_eligibility="eligible", voting_eligibility="eligible",
    criminal_record="clean|zk:" + ts,
)

# ── TEST 1: Welfare Benefit Distribution ─────────────────────────────────
print("=== TEST 1: WELFARE DISTRIBUTION ===")
welfare_transfer = Transfer(
    id=ts + "_ss_001",
    principal_from="system",
    principal_to=user_alice.id,
    instrument="ckBTC",
    amount=1000,
    status="completed",
    tags="social_security",
    timestamp="2026-03-09T00:00:00",
)
print("Welfare transfer " + str(welfare_transfer.id) + " to=" + user_alice.id + " amount=1000")

welfare_entries = LedgerEntry.create_transaction(
    transaction_id=ts + "_welfare_001",
    entries=[
        {"entry_type": EntryType.EXPENSE, "category": Category.TRANSFER_OUT, "debit": 1000, "credit": 0, "entry_date": today, "description": "Social security payment to " + user_alice.id},
        {"entry_type": EntryType.ASSET, "category": Category.CASH, "debit": 0, "credit": 1000, "entry_date": today, "description": "Cash outflow for social security"},
    ],
)
assert LedgerEntry.validate_transaction(ts + "_welfare_001"), "Welfare transaction should balance"
print("Welfare ledger recorded")

n_welfare = Notification(
    topic="social_security", title="Social Security Payment",
    message="You received 0.00001 ckBTC as social security benefit.",
    user=user_alice, read=False, icon="wallet",
    href="/extensions/member_dashboard#my_taxes", color="green",
    metadata="uid:" + user_alice.id,
)
print("Welfare notification sent")

# ── TEST 2: Procurement Project Workflow ─────────────────────────────────
print("=== TEST 2: PROCUREMENT WORKFLOW ===")
proj = procurement_codex.propose_project(
    name="Solar Farm",
    desc="Build a 10MW solar farm for the realm",
    amount_satoshis=200000,
    receiver_principal="aaaaa-aa",
    proposer_user_id=user_alice.id,
)
assert "proposal_id" in proj, "Project should have proposal_id"
print("Procurement proposed: " + str(proj.get("proposal_id")) + " amount=" + str(proj.get("amt")))

approval = procurement_codex.approve_project(proj["proposal_id"])
assert approval.get("status") == "approved", "Should be approved: " + str(approval)
print("Project approved: " + str(approval))

ps = procurement_codex.get_project_status(proj["proposal_id"])
assert ps.get("status") == "approved"
print("Project status: " + str(ps.get("status")) + " amount=" + str(ps.get("amount_satoshis")))

projects = procurement_codex.list_projects()
print("Total procurement projects: " + str(len(projects)))

# ── TEST 3: Treasury Savings & Supermajority Withdrawal ──────────────────
print("=== TEST 3: TREASURY SAVINGS ===")
treasury_codex = treasury_savings_codex

tsw_prop = Proposal(
    proposal_id=ts + "_tsw_001",
    title="Treasury Withdrawal: 10000 sat",
    description=json.dumps({"amt": 10000, "rcv": "aaaaa-aa", "by": user_alice.id, "st": "proposed"}),
    status="debate",
    voting_deadline=deadline,
    metadata="branch:treasury_savings",
)
print("Treasury withdrawal proposed: " + tsw_prop.proposal_id)

# 3 yes, 1 no → passes supermajority (75% > 66.7%)
tsw_prop.votes_yes = 3.0
tsw_prop.votes_no = 1.0
sm = treasury_codex.check_supermajority(tsw_prop.proposal_id)
assert sm.get("passed"), "Supermajority should pass with 3/4=75%: " + str(sm)
print("Supermajority check: passed=" + str(sm.get("passed")) + " ratio=" + str(sm.get("approval_ratio")))

# 2 yes, 2 no → fails supermajority (50% < 66.7%)
tsw_prop.votes_yes = 2.0
tsw_prop.votes_no = 2.0
sm_fail = treasury_codex.check_supermajority(tsw_prop.proposal_id)
assert not sm_fail.get("passed"), "Supermajority should fail with 2/4=50%"
print("Supermajority check (fail): passed=" + str(sm_fail.get("passed")) + " ratio=" + str(sm_fail.get("approval_ratio")))

withdrawals = treasury_codex.list_withdrawals()
print("Treasury withdrawal proposals: " + str(len(withdrawals)))

# Summary
print("=== SPENDING TESTS PASSED ===")
print("Proposals: " + str(Proposal.count()) + " Transfers: " + str(Transfer.count()))
