# Agora Codex

A direct democracy funded by **monthly membership dues**, with **ZK passport identity verification**, **community governance**, **justice**, **enforcement**, **procurement**, **defense**, and **real-time financial accounting**.

## Overview

Agora is a self-sustaining digital community where citizens pay monthly dues to fund a common treasury. Identity is verified via zero-knowledge passport proofs (Rarimo ZK Passport) to ensure one-person-one-vote. Active members govern collectively through proposals that can change the codex code, fund third-party services, or redistribute wealth as social welfare. Every financial transaction is recorded as double-entry bookkeeping entries, making the realm's finances fully transparent through the metrics dashboard.

### Accepted Currencies

- **ckBTC** — Bitcoin on the Internet Computer
- **AGO** — Agora realm token (ic-tokens), fixed rate: **1 AGO = 0.5 BTC**

Use `icw` (ICP Wallet CLI) to transfer and mint tokens.

### Activation Requirements

A new user must complete **both** steps to become an active citizen:
1. Verify identity via ZK passport (Rarimo rarime app)
2. Pay the initial registration invoice

## Codices

### `membership_codex.py`
Identity verification and membership lifecycle management.

**Features:**
- Rarimo ZK Passport verification (age ≥ 18, uniqueness)
- Sybil resistance — one person = one membership
- Activation requires both passport verification AND first invoice payment
- Suspension (non-payment) and reactivation (after paying overdue bills)

### `monthly_billing_codex.py`
Recurring monthly invoices and payment enforcement.

**Features:**
- Creates dual-currency invoices (ckBTC + AGO) — user pays either one
- Grace period warnings for overdue invoices
- Automatic membership suspension after prolonged non-payment
- Records payments as LedgerEntry for accurate real-time metrics
- Auto-reactivates suspended members when overdue bills are settled

### `governance_codex.py`
Direct democracy proposal and voting system.

**Features:**
- Three proposal types: `codex_change`, `treasury_spend`, `welfare_policy`
- Simple majority voting with configurable quorum
- Automatic vote tallying via scheduled task
- Codex change proposals integrate with the voting extension for code execution
- Treasury spend proposals create Transfers and record LedgerEntry expenses
- Welfare policy proposals update redistribution parameters

### `budget_codex.py`
Real-time financial accounting and budget tracking.

**Features:**
- Total budget income = sum of all paid bill payments
- Double-entry LedgerEntry records for every financial event
- Fund, FiscalPeriod, and Budget entity management
- Drives the metrics extension dashboard with accurate, real-time data
- Tracks revenue (dues), welfare expenses, and service expenses separately

### `welfare_redistribution_codex.py`
Social welfare distribution from the common budget.

**Features:**
- Welfare pool = configurable % of total income (default 30%)
- Equal distribution among all eligible active members
- Eligibility: verified, paid-up, no overdue invoices
- Welfare parameters changeable via governance proposals
- All distributions recorded as LedgerEntry for transparent metrics

### `justice.py`
Dispute resolution with jury trials.

**Features:**
- Any member can file a case against another member
- A jury of random active members is automatically selected
- Jurors vote "guilty" or "not_guilty" with a deadline
- Guilty verdicts result in fines recorded in the budget
- Not-guilty verdicts dismiss the case

### `procurement.py`
Transparent bidding process for community purchases.

**Features:**
- Members open tenders describing what the community needs
- Other members submit competitive bids within a budget cap
- After bidding closes, the community votes on the best bid
- Winning bids become contracts with payments tracked in the budget
- Replaces ad-hoc spending with structured procurement

### `enforcement.py`
Community policing through elected enforcers.

**Features:**
- Enforcers are elected (and removed) by community vote
- Any member can report rule violations
- Enforcers investigate reports and propose sanctions
- Warnings are applied immediately; fines and suspensions require a vote
- All actions are logged for community accountability

### `defense.py`
Defense fund for security and infrastructure protection.

**Features:**
- Configurable % of income allocated to defense (default 10%)
- Members can voluntarily enlist as defenders
- Defense missions (security audits, bug bounties, etc.) proposed via governance
- Approved missions funded from the defense fund
- Defense policy changeable via governance proposals

### `adjustments.py`
Realm configuration and manifest loading.

**Features:**
- Loads realm settings and entity method overrides from `manifest.json`
- Initializes accounting entities (Fund, FiscalPeriod, Budget) on deploy
- Updates realm metadata (name, description, logo)

## Usage

This codex is automatically loaded when creating a realm with the `agora` template:

```bash
realms realm create --template agora
```
