# Agora codex E2E re-run — 2026-07-13 (after fixes)

**Realm:** ManualTest8Agora (`335qe-iyaaa-aaaac-bfnwa-cai`)

## Fixes applied before re-run

1. **Reinstalled agora v0.6.0** with `run_init` — `open_registration` now **false**; manifest lists 7 civic departments.
2. **Enabled `test_mode_ii_bypass`** on the realm via `set_canister_config`.
3. **Code fixes** (pending installer/registry deploy):
   - Installer omits `open_registration` from `update_realm_config` when a codex is present.
   - Backend `update_realm_config` skips `open_registration` when codex `manifest_data` pins registration policy.
   - Wizard staging test flags default `ii_bypass: true` for new deploys.

## Playwright results (2nd run): **4 passed / 3 failed**

| Test | Result |
|---|---|
| U1 Wizard Agora manifest | **PASS** |
| U4 Realm Settings (no JSON error) | **PASS** |
| A2 Migration Console | **PASS** |
| A2 Metrics | **PASS** |
| A2 Public dashboard | FAIL (heading locator; content renders in screenshots) |
| A3 Join without invite | FAIL (II bypass skips auth step — assertion needs update) |
| U2 Admin via II bypass | FAIL (join flow navigation; needs step-by-step automation) |

## Backend verification

| Check | Value |
|---|---|
| `open_registration` | **false** ✓ |
| `test_mode_ii_bypass` | **true** ✓ |
| Codex init log | 4 departments, 9 positions, 9 invite codes seeded |
| `get_realm_stage` departments | Civil Registry, Justice, Defense, Social Security, Infrastructure, Economy, Administration |

## Remaining work

- Deploy **realm_installer** + **registry frontend** so code fixes apply to new wizard deploys.
- Fresh **E2E-Agora-*** realm deploy blocked on credits (balance 1, need 5).
- Harden Playwright specs for II-bypass join flow (multi-step wizard).
- Investigate `organizations_count` metric (counts `Organization` entity, not `Department`).

## Verdict

**Improved — core Agora policy now enforced on ManualTest8Agora.** Not fully releasable until installer/registry are deployed and authenticated E2E journeys pass consistently.
