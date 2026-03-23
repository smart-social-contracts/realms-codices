# Agora Codex

A demo codex package for realms focused on **social welfare** and **democratic governance**.

## Overview

Agora implements a welfare-oriented governance model where citizens receive social benefits based on eligibility criteria, and decisions are made through democratic voting on proposals.

## Codices

### `social_benefits.py`
Automated distribution of social benefits to eligible members.

**Features:**
- Eligibility verification (residence permit, tax compliance, identity verification)
- Progressive benefit calculation based on member status
- Automatic distribution via Transfer records

### `governance_automation.py`
Democratic proposal and voting system.

**Features:**
- Create governance proposals with voting deadlines
- Automatic vote tallying when deadlines pass
- Proposal status tracking (active, passed, rejected)

### `satoshi_transfer.py`
Scheduled micro-transfer demonstration.

**Features:**
- Sends 1 satoshi to a target principal on schedule
- Demonstrates scheduled task execution
- Integrates with vault extension for ckBTC transfers

### `financial_setup.py`
Sets up the accounting structure for the Financial Statements dashboard.

**Features:**
- Creates Funds (General, Infrastructure, Capital Projects)
- Creates Fiscal Period for the current year
- Creates Budget allocations with planned amounts
- Idempotent: skips if funds already exist

### `init.py`
Realm configuration and manifest loading.

**Features:**
- Loads realm settings from `manifest.json`
- Updates realm metadata (name, description, logo)
- Configures entity method overrides

## Usage

This codex is automatically loaded when creating a realm with the `agora` template:

```bash
realms realm create --template agora
```
