# Syntropia Codex

The **greenfield** codex: a brand-new sovereign smart city built from scratch, onboarding citizens who did not previously exist as a population.

Because legitimacy is **earned** (not inherited from an existing administration), Syntropia onboards new citizens with strong identity and commitment:

1. **ZK passport** — identity verified via the `passport_verification` extension (one person = one citizenship).
2. **Deposit** — each citizen pays a deposit (*a house in a zone*) to secure their place.
3. **Know-Your-Citizen (KYC)** — real citizen data submitted before the city goes live.

The public dashboard shows a **go-live countdown**, a **live citizen counter**, and progress toward **critical mass**. **Before the production phase, member voting is not executable — only admins (the founders) can make fundamental changes.**

## Hooks (`backend/hooks.py`)

| Hook | What it does |
|------|--------------|
| `init` | Enforces open registration, names the realm if unnamed, seeds departments, positions and courts |
| `on_user_register` | Deposit invoice (a house in a zone) and the three steps to citizenship |
| `on_stage_change` | Entering beta: membership invoices, payroll, and a request to every citizen to submit their real identity |
| `assign_quarter` | Home quarter of a joiner: the preferred one if it has room, else the least populated |

Identity submission and review are realm operations (`identity_submit`, `identity_review`); invoice
accounting is done by the realm's treasury.

## Territory mode

`greenfield` (`manifest.json → onboarding.territory_mode`). Informational: the realm does not read it.

## Dependencies (extensions)

- `passport_verification` — Rarimo ZK passport onboarding.
- Plus the shared civic stack declared in `manifest.json` (`access_manager`, `member_manager`, `justice_litigation`, `land_registry`, …).

## Reference data

`manifest.json → seed`: departments (permissions, fund, policy, salaried positions) and the court hierarchy of the Justice department.

## Quarters

Syntropia uses **predefined quarters/zones** for now. Placement is the `assign_quarter` hook; capacity is `quarter.max_population` in the manifest (0 = unlimited). Scaling out is the realm's own job.

## Usage

```bash
realms realm create --template syntropia
```
