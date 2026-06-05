# Syntropia Codex

The **greenfield** codex: a brand-new sovereign smart city built from scratch, onboarding citizens who did not previously exist as a population.

## Overview

Because legitimacy is **earned** (not inherited from an existing administration), Syntropia onboards new citizens with strong identity and commitment:

1. **ZK passport** — identity verified via the `passport_verification` extension (one person = one citizenship).
2. **Deposit** — each citizen pays a deposit (*a house in a zone*) to secure their place.
3. **Know-Your-Citizen (KYC)** — real citizen data submitted before the city goes live.

The public dashboard shows a **go-live countdown**, a **live citizen counter**, and progress toward **critical mass**. **Before the production phase, member voting is not executable — only admins (the founders) can make fundamental changes.** Once live, Syntropia runs a representative democracy with separation of powers, progressive taxation, universal welfare, land treaties, licensed providers, and zones of action.

### Territory mode

`greenfield` — see `manifest.json → onboarding.territory_mode` and `docs/reference/ONBOARDING_SCENARIOS.md`.

### Dependencies (extensions)

- `llm_chat` — AI assistant that guides citizens through onboarding.
- `passport_verification` — Rarimo ZK passport onboarding.

### Reference data (JSON)

- `departments.json` — initial departments, profiles, and permission assignments.
- `justice_license.json` — the license authorizing the constitutional court.
- `zones.json` — founding land zones.

### Quarters (TODO: dynamic creation)

Syntropia uses **predefined quarters/zones** for now. The product vision is for quarters to be **created dynamically as the population grows**, with zones shared among quarters. That requires a backend mechanism to provision a new quarter canister when a codex policy (e.g. `should_create_new_quarter`) decides one is needed — see `src/realm_backend/main.py` (federation/`_assign_quarter`) and the installer. This is **out of scope** for the current codex and tracked as a future capability.

## Codices

### `tax_collection.py`
Automated tax calculation and collection system.

**Features:**
- Progressive tax rates (10% / 20% / 30% based on income brackets)
- Automatic income calculation from transfer history
- Tax payment processing via Transfer records

**Tax Brackets:**
| Income | Rate |
|--------|------|
| ≤ 10,000 | 10% |
| ≤ 50,000 | 20% |
| > 50,000 | 30% |

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

### `init.py`
Realm configuration and manifest loading.

**Features:**
- Loads realm settings from `manifest.json`
- Updates realm metadata (name, description, logo)
- Configures entity method overrides

## Usage

This codex is automatically loaded when creating a realm with the `syntropia` template:

```bash
realms realm create --template syntropia
```
