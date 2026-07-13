# E2E Test Agent Guide (common context for all codex test prompts)

This file is the shared preamble for the per-codex end-to-end test prompts
(`codices/<codex>/E2E_TEST_PROMPT.md`). Give an agent this guide plus one
codex prompt. The agent is expected to drive a real browser (Playwright or
equivalent) against the **staging** environment and verify backend state
through canister queries.

## Environment

| Thing | Value |
|---|---|
| Registry portal + wizard | `https://staging.realmsgos.org` / `https://staging.realmsgos.org/create-realm` |
| Realms under test | `https://staging.realmsgos.org/r/<slug>` (also directly at `https://<frontend-canister-id>.icp0.io`) |
| Realm registry backend (staging) | `7wzxh-wyaaa-aaaau-aggyq-cai` — `list_realms` query resolves slug → backend/frontend canister ids |
| File registry (staging) | `iebdk-kqaaa-aaaau-agoxq-cai` — `list_codices` / `list_extensions` queries show published packages |

Staging realms run with `TEST_MODE` enabled (visible banner: "Test Mode
Active"). Relevant flags a realm may have: `test_mode_ii_bypass` (the Login
button authenticates a synthetic identity without real Internet Identity),
`test_mode_user_self_registration`, `test_mode_skip_terms`,
`test_mode_skip_passport_zkproof`. Report which flags are active (they are
returned by the realm backend `status()` / shown in `realmInfo`) because they
change join-flow behavior — a "registration blocked" assertion is only
meaningful when the bypass flags are off.

## Inputs (provided by the operator, or self-provisioned)

- `REALM_URL` — an existing realm deployed with the codex under test. If not
  provided, deploy one through the wizard; this requires a logged-in registry
  account **with deployment credits**. If you cannot obtain credits, stop and
  report that the wizard-deployment part was skipped, then continue against a
  provided realm.
- Two or three browser identities (founder + 1–2 joiners). With
  `test_mode_ii_bypass` each fresh browser context gets its own identity, so
  separate Playwright contexts are sufficient.

## Tooling conventions

- Use Playwright. A reusable base config lives in the realms repo at
  `extensions/extensions/_shared/testing/e2e/playwright.config.base.ts`
  (screenshots + video on failure, fail-fast). Put specs in a `specs/` dir.
- Backend assertions: prefer `dfx canister --network ic call <realm_backend>`
  queries — `get_sidebar_manifests '()'` (installed extensions + versions),
  `extension_sync_call '("<ext>", "<fn>", "{}")'` (extension backends),
  `status '()'`. These need no identity for queries. Canister logs
  (`dfx canister logs`) are controller-only — skip if not a controller.
- Wait for canister cold starts: first page load of a fresh realm can take
  30–60 s. Use generous navigation timeouts before declaring failure.
- Never test against `demo` or `ic` environments.

## What every run must produce

1. A markdown report: one line per checklist item — PASS / FAIL / SKIPPED
   (with reason), screenshots for failures, browser console errors, and the
   exact backend query outputs used as evidence.
2. For each FAIL: a minimal reproduction (URL, identity, steps) suitable for
   a GitHub issue on `smart-social-contracts/realms`. File the issues if the
   operator asked for that; otherwise include them in the report.
3. A final verdict: is the codex releasable? List blocking vs cosmetic
   findings separately.

## Universal checks (run for every codex, before the codex-specific journey)

- **U1 Wizard facts**: on `/create-realm`, selecting the codex shows its
  version and dependency list fetched from the **file registry** (not GitHub).
  Cross-check against `list_codices` + the published `manifest.json`.
- **U2 Founder**: after deployment the deploying identity enters the realm
  with the admin profile (admin sidebar sections: Data Explorer, Realm
  Settings, Organizations if access_manager is installed) without redeeming
  any code.
- **U3 Extensions installed**: `get_sidebar_manifests` lists the 9 core
  extensions (public_dashboard, member_dashboard, realm_settings,
  extensions_manager, voting, census, admin_dashboard, vault, codex_viewer)
  **plus** every dependency in the codex manifest, at the registry's latest
  versions. Every sidebar entry must load without an error page.
- **U4 Realm Settings lifecycle panel**: loads without errors (regression
  check for "Unexpected token 'E' … not valid JSON"); stage and metrics
  render; `extension_sync_call '("realm_settings", "get_realm_stage", "{}")'`
  returns `success: true` JSON.
- **U5 System-extension protection**: uninstalling a system/core extension
  from Extensions Manager is refused.
- **U6 Codex identity intact**: the realm keeps the name/manifesto the
  creator typed in the wizard — the codex must not have overwritten them.
