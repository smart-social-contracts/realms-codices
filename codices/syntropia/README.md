# Syntropia Codex

A demo codex package for realms focused on **sustainable governance** and **balanced taxation**.

## Overview

Syntropia implements a balanced governance model combining taxation with sustainable development principles. It emphasizes harmony between fiscal responsibility and community growth.

## Codices

### `tax_collection_codex.py`
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

### `governance_automation_codex.py`
Democratic proposal and voting system.

**Features:**
- Create governance proposals with voting deadlines
- Automatic vote tallying when deadlines pass
- Proposal status tracking (active, passed, rejected)

### `satoshi_transfer_codex.py`
Scheduled micro-transfer demonstration.

**Features:**
- Sends 1 satoshi to a target principal on schedule
- Demonstrates scheduled task execution
- Integrates with vault extension for ckBTC transfers

### `adjustments.py`
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
