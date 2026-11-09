# Agora Codex

The **incumbent migration** codex: an existing public administration replaces its entire IT infrastructure with Realms GOS in a **1-to-1 migration**. Onboarding is by **registration code, manual entry, or programmatic/bulk import** — there is **no ZK passport** step (legitimacy is inherited from the existing administration). Imported citizens become active members immediately.

The realm follows the standard lifecycle (`alpha → beta → production → …`). During the **migration phases (alpha/beta)** members **pay nothing**: the member dashboard shows their declaration and any *potential future* tax deadlines so they can prepare, and the public dashboard tracks the **percentage of population migrated** and the **departments** coming online. Quarters are **well-defined in advance**, each mapped to specific zones. A registration invoice is only issued once the realm is live (beta/production) and a fee is configured.

## Hooks (`backend/hooks.py`)

| Hook | What it does |
|------|--------------|
| `init` | Enforces invite-only registration, names the realm if unnamed, seeds departments, positions and courts |
| `on_user_register` | Alpha: a welcome notice, nothing to pay. Beta/production: registration invoice + notice |
| `on_stage_change` | Entering beta: membership invoice for every non-admin member, payroll for each salaried department |

## Territory mode

`incumbent` (`manifest.json → onboarding.territory_mode`). Informational: the realm does not read it.

## Dependencies (extensions)

Declared in `manifest.json` (`access_manager`, `member_manager`, `justice_litigation`, `land_registry`, …). No passport verification step.

## Reference data

`manifest.json → seed`: departments (permissions, fund, policy, salaried positions) and the court hierarchy of the Justice department.

## Usage

```bash
realms realm create --template agora
```
