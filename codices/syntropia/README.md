# Syntropia Codex

The **greenfield** codex: a brand-new sovereign smart city built from scratch, onboarding citizens who did not previously exist as a population.

Because legitimacy is **earned** (not inherited from an existing administration), Syntropia onboards new citizens with strong identity and commitment:

1. **Deposit** — each citizen pays a deposit (*a house in a zone*) to secure their place.
2. **Know-Your-Citizen (KYC)** — real citizen data, entered on the member's *Account* page and shared with the
   *Citizenship & Identity* department, which reviews it before the city goes live.

A **ZK passport** (one person = one citizenship) is optional: a realm that wants it installs the
`passport_verification` extension once a verifier it trusts is reachable. Until 1.1.0 it was a dependency, so every
Syntropia realm sent its citizens to a single outside service as their first step; when that service's domain stopped
resolving (November 2026) the step became a dead end for everyone.

**What the realm enforces.** The realm makes a citizen an active member when they join; it does not hold membership
back until these steps are done. `onboarding.identity_requirements` and `membership.activation_requires` in
`manifest.json` describe what the city asks of its citizens, and nothing in the realm reads them as a gate. Earlier
versions listed `passport_zk` and `passport_verified` there, which suggested a passport gate that never existed.

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

The shared civic stack declared in `manifest.json` (`access_manager`, `member_manager`, `justice_litigation`,
`land_registry`, …). Optional: `passport_verification`, for ZK passport proofs (see above).

## Reference data

`manifest.json → seed`: departments (permissions, fund, policy, salaried positions) and the court hierarchy of the Justice department.

## Quarters

Syntropia uses **predefined quarters/zones** for now. Placement is the `assign_quarter` hook; capacity is `quarter.max_population` in the manifest (0 = unlimited). Scaling out is the realm's own job.

## Usage

```bash
realms realm create --template syntropia
```
