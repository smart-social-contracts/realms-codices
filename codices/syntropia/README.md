# Syntropia Codex

The **greenfield** codex: a brand-new sovereign smart city built from scratch, onboarding citizens who did not previously exist as a population.

Because legitimacy is **earned** (not inherited from an existing administration), Syntropia onboards new citizens with strong identity and commitment:

1. **ZK passport** — identity verified via the `passport_verification` extension (one person = one citizenship).
2. **Deposit** — each citizen pays a deposit (*a house in a zone*) to secure their place.
3. **Know-Your-Citizen (KYC)** — real citizen data submitted before the city goes live.

The public dashboard shows a **go-live countdown**, a **live citizen counter**, and progress toward **critical mass**. **Before the production phase, member voting is not executable — only admins (the founders) can make fundamental changes.**

## Live spine

The host calls `backend/entry.py` (in-process fallback) or `backend/sandbox_hooks.py` (sandboxed path). Do not add `init.py`, `adjustments.py`, or `*_codex.py` files — those mechanisms are gone.

| File | Role |
|------|------|
| `backend/entry.py` | Hook API: `get_config`, `init`, `seed`, `on_user_register`, `on_invoice_accounting`, `on_stage_change`, `on_federation_message`, `run_payroll`, identity review methods |
| `backend/sandbox_hooks.py` | Sandboxed `init`, `on_user_register` |
| `backend/org_seeding.py` | Idempotent department / position / invite seeding |
| `backend/invoice_currency.py` | Invoice currency from pinned symbol or realm treasury |
| `backend/invoice_accounting.py` | Deposit stays a liability; membership invoices become tax revenue |
| `backend/lifecycle_billing.py` | Beta membership invoices + period-idempotent payroll |
| `backend/modules/quarter_assignment.py` | Host federation looks up Codex `quarter_assignment` |
| `backend/data/*.json` | Departments, justice template + license, zones |
| `manifest.json` | Package metadata, `codex_modules: ["quarter_assignment"]` |

## Territory mode

`greenfield` — see `manifest.json → onboarding.territory_mode` and `docs/reference/ONBOARDING_SCENARIOS.md`.

## Dependencies (extensions)

- `passport_verification` — Rarimo ZK passport onboarding.
- Plus the shared civic stack declared in `manifest.json` (`access_manager`, `member_manager`, `justice_litigation`, `land_registry`, …).

## Reference data (JSON)

- `departments.json` — initial departments, profiles, and permission assignments.
- `justice.json` / `justice_license.json` — court hierarchy and the license authorizing the constitutional court.
- `zones.json` — founding land zones.

## Quarters

Syntropia uses **predefined quarters/zones** for now. Dynamic quarter creation as the population grows is a future host capability (`should_deploy_quarter` in `quarter_assignment.py` is the policy hook).

## Usage

```bash
realms realm create --template syntropia
```
