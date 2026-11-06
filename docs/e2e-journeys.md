# End-to-end journeys

The agent-driven browser suite that used to live in `testing/` is retired.
Its journeys are kept here, to be built as deterministic **geister scenarios**:
the real realm wasm plus the codex under test, running on PocketIC with time
control. No browser, no deployed realm, the same result on every run.

## Journeys

| Journey | Role | Pass when |
|---|---|---|
| Join as admin | admin | Joining with the admin invite code grants the admin profile; the admin sidebar entries (Admin Dashboard, Access Manager, Realm Settings, Member Manager) are available. |
| Join as member | member | Joining follows the codex's registration rule (open, or invitation-only); the member profile is granted and no admin-only entries are available. |
| Public visitor | visitor (logged out) | The public dashboard renders; no admin entries, Vault, Voting or Member Dashboard are offered. |
| Voting | member | The voting extension loads; the proposal list and filters render without error. |
| Vault | member | The vault extension loads; the balances area renders without error. |
| Extension mount sweep | admin | Every sidebar extension mounts without an error. |
| Lifecycle phases | founder, citizens, department staff | See below. |

### Lifecycle phases

1. Founder preflight: stage is alpha, registration mode is as the codex
   declares, departments are seeded.
2. Set the stage gates for the test (critical mass, proving period).
3. Advancing alpha → beta is refused before critical mass.
4. Citizens join until critical mass; each gets the invoices the codex
   declares.
5. Every department seat is staffed.
6. Zones are defined (Syntropia).
7. Procurement: publish a request, receive a bid, award it.
8. The founder hands root authority to the legislature and loses the
   configure powers.
9. The legislature advances to beta; deposits lock and tax invoices appear.
10. Citizens submit identity; the registrar approves.
11. A citizen pays a tax invoice; the treasury balance rises.
12. Beta → production is refused before the vote and the proving period, then
    approved; the stage is production.

Time control replaces the waiting periods the browser suite had to sit out.

### Checks for every codex

- The founder enters with the admin profile without redeeming a code.
- The core extensions and every codex dependency are installed.
- The realm settings lifecycle data loads (stage and metrics).
- Uninstalling a core extension is refused.
- The realm keeps the name and manifesto its creator chose.

### Codex-specific checks

- Agora: joining without an invite is refused; no invoice on join; the seeded
  departments exist; a position invite code grants that position's seat only.
- Dominion: no departments are seeded; registration issues an initial invoice;
  membership activates only after passport verification and payment.
- Syntropia: open registration admits citizens; it never offers the admin
  profile; the seeded departments exist; a position invite code grants that
  position's seat only.

## Report format

One report per run, one line per check:

```
PASS     <check id>  <evidence>
FAIL     <check id>  <evidence>
SKIPPED  <check id>  <reason>
```

- Evidence is the exact query output or state that was asserted.
- Every FAIL carries a minimal reproduction: identity, steps, expected and
  actual result.
- The report ends with a verdict: is the codex releasable? Blocking and
  cosmetic findings are listed separately.
- A check that depends on a flag or setting that was not in the expected state
  is reported SKIPPED, with the flag, never PASS.
