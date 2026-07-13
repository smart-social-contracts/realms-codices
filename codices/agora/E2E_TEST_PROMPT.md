# Agent prompt: comprehensive E2E test of the Agora codex

Read `codices/testing/E2E_AGENT_GUIDE.md` first — it defines the staging
environment, authentication, tooling, evidence, and the universal checks
U1–U6. Then execute this Agora-specific journey with Playwright. Agora is an
**incumbent-migration** codex: an existing polity moving on-chain —
invitation-only registration, bulk citizen import, no payments during
alpha/beta, and a checklist-gated lifecycle toward a 100,000 population
target.

Reference facts (assert against the currently published manifest — fetch it
from the file registry rather than trusting this list):

- Dependencies: `access_manager`, `role_manager`, `notifications`, `metrics`,
  `land_registry`, `migration_console`.
- Registration: **invitation-only** (`open_registration: false`,
  `member_requires_invite: true`), with `bulk_import` and
  `programmatic_import` enabled.
- No codex currency → the wizard token step must offer free choice.
- Lifecycle: alpha → beta by **checklist**, beta → production by admin
  approval; `population_target: 100000`.
- Seeded org chart (from `departments.json`): Civil Registry, Justice,
  Defense, Social Security, Infrastructure, Economy, Administration — each
  with position seats (e.g. Civil Registry → registrar ×2, clerk ×5), a fund
  code, permissions, policy 1/1 (target 5/10), and one invite code per
  position.
- Governance proposal types include welfare_policy, procurement,
  elect/remove_enforcer, defense_mission/policy.

## Journey

### A1 — Wizard (founder context)

1. Run U1. Additionally assert: the Basics step shows Member Registration as
   a read-only "Set by the Agora codex" panel saying **Invitation only** —
   the creator must NOT be able to switch it to open registration. The Token
   step is a free choice with no codex-pinned panel.
2. Deploy a realm named `E2E-Agora-<timestamp>` (new token, any symbol).
   Record the backend/frontend canister ids.

### A2 — Founder experience

3. Run U2–U6.
4. Public dashboard (logged out): incumbent-migration profile renders — no
   join CTA in the hero, migration-progress bar toward the 100,000
   population target, departments section, KPI strip. No broken sections.
5. Organizations: the 7 seeded departments exist with their positions, fund
   codes, permissions, and policy 1/1; the permissions panel shows the
   browsable grouped catalog.
6. Migration Console: opens for the founder and shows the migration/import
   tooling (this extension is Agora's differentiator — an error page here is
   a blocking failure).
7. Metrics extension: loads and renders (empty charts on a fresh realm are a
   PASS).

### A3 — Invitation-only enforcement (second browser context)

8. Visit the realm logged out → Join **without** any invite code. This must
   be **refused** (invite prompt shown, no member profile granted).
   Caveat: if `test_mode_user_self_registration` is enabled on the realm the
   check is void — report the flag state and mark SKIPPED instead of PASS.
9. `realm.open_registration` must be `false` on the backend regardless of
   what the wizard sent (`status` query) — the codex init enforces this
   server-side.

### A4 — Staff onboarding via position invite (third browser context)

10. As founder, open Organizations → Civil Registry → copy the invite code
    for `registrar`.
11. Redeem it in a fresh context. Assert: join succeeds, the user holds the
    `registrar` profile, belongs to Civil Registry, and occupies a registrar
    seat.
12. As the registrar (or founder), exercise a citizen-import path from the
    Migration Console: import a small test batch (2–3 synthetic citizens) if
    the UI offers it, or record precisely which import mechanisms exist
    (file upload / programmatic) and whether they respond. Imported citizens
    must appear in the census count.

### A5 — Governance & lifecycle

13. Voting: as founder create a `treasury_spend` (or `welfare_policy`)
    proposal; verify it appears with the 7-day window and 20% quorum shown,
    and the registrar context can see it. Cast a vote from an eligible
    identity.
14. Realm Settings lifecycle: stage **alpha**; the alpha → beta transition
    must present a **checklist** (mode: checklist), not auto-milestones.
    Record the checklist items and whether "Advance" is correctly blocked
    while items are unmet.
15. Onboarding hook: a newly joined user must NOT receive a payment invoice
    during alpha/beta (incumbent hook: declaration + future tax deadlines
    instead). Check the new user's notifications/dashboard and record what
    the hook produced.

### A6 — Negative checks

16. The registrar (non-admin) must not see admin-only surfaces (Realm
    Settings write actions, Data Explorer) and direct navigation to them
    must be denied gracefully.
17. Idempotent seeding: if you are a controller, re-run the codex install
    and assert department count stays 7 with no duplicate positions or
    invite codes. Skip if not a controller.

Compile the report per the guide. End with a side-by-side table against the
Syntropia run (if available): registration mode, onboarding hook effects,
lifecycle gate behavior, dashboard profile, seeded orgs — highlighting any
place where the two codices do NOT differ as designed.
