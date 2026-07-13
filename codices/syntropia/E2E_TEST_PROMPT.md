# Agent prompt: comprehensive E2E test of the Syntropia codex

Read `codices/testing/E2E_AGENT_GUIDE.md` first — it defines the staging
environment, authentication, tooling, evidence, and the universal checks
U1–U6. Then execute this Syntropia-specific journey with Playwright. Syntropia
is a **greenfield** smart-city codex: open registration, ZK-passport
onboarding, deposit ("a house in a zone"), Know-Your-Citizen, and a
critical-mass lifecycle gate.

Reference facts (assert against the currently published manifest — fetch it
from the file registry rather than trusting this list):

- Dependencies: `passport_verification`, `zone_selector`, `land_registry`,
  `notifications`, `access_manager`, `role_manager`.
- Registration: **open** (`default_profile: member`), admin requires invite.
- No codex currency → the wizard token step must offer free choice.
- Lifecycle: alpha → beta gated by `auto_milestones` on `critical_mass`
  (10,000 citizens); beta → production by admin vote.
- Seeded org chart (from `departments.json`): Citizenship & Identity,
  Justice, Defense, Social Security, Infrastructure, Economy, Administration —
  each with position seats, a fund, permissions, policy 1/1 (target 5/10),
  and one multi-use invite code per position.

## Journey

### S1 — Wizard (founder context)

1. Run U1. Additionally assert: the Basics step shows Member Registration as
   a read-only "Set by the Syntropia codex" panel saying **Open registration**
   (joiners become `member`); the Token step is a free choice (create new /
   REALMS / ckBTC / ckUSDC) with **no** codex-pinned panel.
2. Deploy a realm named `E2E-Syntropia-<timestamp>` (new token, any symbol).
   Record the backend/frontend canister ids from the registry.

### S2 — Founder experience

3. Run U2–U6.
4. Public dashboard (logged out): greenfield profile renders — join CTA
   ("Become a citizen"), go-live countdown, citizen counter, critical-mass
   threshold. No broken sections.
5. Organizations (as founder): the 7 seeded departments exist, each showing
   its positions (e.g. Justice → judge ×2, court_clerk ×3), fund code, policy
   1/1, and permissions. The permissions panel shows the browsable grouped
   catalog (categories expandable, descriptions visible) — not an empty
   search box.
6. Realm Settings: stage is **alpha**; "Advance to Beta" must be **refused**
   with a message about unmet milestones (critical mass 10,000 ≫ current
   citizens). This is the auto_milestones gate — record the exact error.

### S3 — Open citizen registration (second browser context)

7. Visit the realm logged out → Join. With open registration, joining must
   work **without** an invitation code; the new user gets the `member`
   profile (member sidebar only — no Data Explorer / Realm Settings).
8. Onboarding hooks (user_register_posthook): the new citizen should be
   prompted for passport verification and receive a deposit invoice /
   Know-Your-Citizen tasks (surfaced on the member dashboard or
   notifications). Record which of the three appear. If
   `test_mode_skip_passport_zkproof` is on, note that the ZK step is
   auto-skipped by design.
9. Passport Verification extension: opens from the member context and renders
   its flow (submit step is allowed to be stubbed in test mode — the check is
   that the UI works, not that a real passport verifies).

### S4 — Civil-servant seat via position invite (third browser context)

10. As founder, open Organizations → Justice → positions → copy the invite
    code/URL for `judge` (seeded by the codex).
11. In a fresh context, redeem it on the join page. Assert: user joins
    successfully, holds the `judge` profile, is a member of the Justice
    department, and is appointed to the `Justice/judge` seat (seat shows the
    holder in Organizations; headcount decrements accordingly).
12. As founder, grant Justice one permission it does not yet hold (pick any
    from the browsable catalog outside its seeded set of `case.read`,
    `case.assign`, `verdict.issue`, `license.read`) and apply; then revoke
    it. Both must round-trip without errors.

### S5 — Governance & extensions smoke

13. Voting: as founder create a proposal; check the member (S3 user) can see
    it. Per manifest, member voting is only *executable* at production stage —
    record actual behavior at alpha (visible-but-gated is expected; a hard
    crash is a failure).
14. Zone selector and Land registry extensions load and render their UI from
    both founder and member contexts (map/zones may be empty on a fresh
    realm — blank-but-functional is a PASS, an error page is a FAIL).
15. Notifications: the member's onboarding events from S3 appear.
16. Vault: opens, shows the realm token balance (0 is fine).

### S6 — Negative checks

17. Admin cannot be obtained by open join: the join flow must never offer an
    admin profile without an invite (`admin_requires_invite: true`).
18. A second `install_codex_from_registry`-driven realm feature: re-running
    codex install (if you are a controller) must be idempotent — department
    count stays 7, no duplicate positions or invite codes. Skip if you are
    not a controller.

Compile the report per the guide, including a comparison-ready summary table
(this run will be diffed against the Agora run).
