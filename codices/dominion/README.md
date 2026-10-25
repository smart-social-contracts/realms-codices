# Dominion Codex

A demo codex for a direct democracy with taxation, in its own currency (`DOM`).

## Hooks (`backend/hooks.py`)

| Hook | What it does |
|------|--------------|
| `init` | Names the realm if unnamed |
| `on_user_register` | Registration invoice in DOM and a welcome notice (pay, then verify with ZK passport) |

Taxes (progressive brackets on income: 10% ≤ 10,000, 20% ≤ 50,000, 30% above) are adopted as the
realm's tax policy and assessed by the realm (`tax_policy_propose`, `tax_assess`); proposals and votes
are the realm's own operations.

## Usage

```bash
realms realm create --template dominion
```
