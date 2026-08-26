# Agora Codex

The **incumbent migration** codex: an existing public administration replaces its entire IT infrastructure with Realms GOS in a **1-to-1 migration**. Onboarding is by **registration code, manual entry, or programmatic/bulk import** — there is **no ZK passport** step (legitimacy is inherited from the existing administration). Imported citizens become active members immediately.

The realm follows the standard lifecycle (`alpha → beta → production → …`). During the **migration phases (alpha/beta)** members **pay nothing**: the member dashboard shows their declaration and any *potential future* tax deadlines so they can prepare, and the public dashboard tracks the **percentage of population migrated** and the **departments** coming online. Quarters are **well-defined in advance**, each mapped to specific zones. A registration invoice is only issued once the realm is live (beta/production) and a fee is configured.

## Live spine

The host calls `backend/entry.py` (in-process fallback) or `backend/sandbox_hooks.py` (sandboxed path). Do not add `init.py`, `adjustments.py`, or `*_codex.py` files — those mechanisms are gone.

| File | Role |
|------|------|
| `backend/entry.py` | Hook API: `get_config`, `init`, `seed`, `on_user_register`, `on_stage_change`, `on_treasury_send`, `run_payroll` |
| `backend/sandbox_hooks.py` | Sandboxed `init`, `on_user_register`, `on_treasury_send` |
| `backend/org_seeding.py` | Idempotent department / position / invite seeding |
| `backend/invoice_currency.py` | Invoice currency from pinned symbol or realm treasury |
| `backend/lifecycle_billing.py` | Beta membership invoices + payroll (this copy; Agora's payroll is the older fork) |
| `backend/modules/membership.py` | Host-loaded Codex `membership` — `activate_member` on registration |
| `backend/data/*.json` | Departments, justice template + license, zones |
| `manifest.json` | Package metadata, `codex_modules: ["membership"]` |

## Territory mode

`incumbent` — see `manifest.json → onboarding.territory_mode` and `docs/reference/ONBOARDING_SCENARIOS.md`.

## Dependencies (extensions)

Declared in `manifest.json` (`access_manager`, `member_manager`, `justice_litigation`, `land_registry`, …). No passport verification step.

## Reference data (JSON)

- `departments.json` — initial departments, profiles, and permission assignments.
- `justice.json` / `justice_license.json` — court hierarchy and the license authorizing it.
- `zones.json` — initial land zones (predefined quarters).

## Usage

```bash
realms realm create --template agora
```
