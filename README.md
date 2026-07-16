# realms-codices

Codex packages for the Realms platform. A codex is a **privileged system
extension** (issue #244): an extension package whose manifest declares
`"kind": "codex"`. It configures a realm, pulls in the extensions it needs
(distro behavior), and integrates with the core through a versioned hook API
— exactly one codex is installed per realm.

## Package layout (unified extension pipeline)

```
<codex_id>/
├── manifest.json         id, version, kind: codex, codex_api_version,
│                         dependencies, config blocks (fees, governance, …)
└── backend/
    ├── entry.py          hook implementations (see below)
    ├── *.py              helpers importable from entry.py (e.g. org_seeding)
    ├── data/*.json       reference data (departments, zones, …)
    └── modules/*.py      governance modules — each becomes a Codex DB
                          entity (codex_change proposal targets, task shims)
```

Publish with `realms codex publish` (delegates to the extension publisher,
uploading under `ext/<id>/<version>/`); install with
`install_codex_from_registry` or directly via
`install_extension_from_registry`.

## Hook API (v1)

Core calls the codex at these `entry.py` functions (all take a JSON string
argument, all optional except `get_config` and `init`):

- `get_config` — realm configuration blocks (fees, governance, onboarding, …)
- `init` — post-install realm setup (idempotent; enforce realm settings here)
- `seed` — idempotent data/org seeding
- `on_user_register` — called after user registration (`{"user_id": ...}`)
- `on_treasury_send` — async treasury transfer hook
- `check_lifecycle_transition` — verdict on stage transitions
  (`{"allowed": bool, "missing": [...]}`)
- `get_dashboard_config`, `get_extension_overrides`

## Manifest keys (excerpt)

- `kind` — must be `"codex"`; the file registry only accepts this from
  curated publishers, and the realm requires the `codex.install` permission.
- `codex_api_version` — hook contract version (currently `1`); installs are
  refused when the realm's core does not support the declared version.
- `dependencies` — extensions installed with the codex. Either a list
  (latest versions) or a dict with version pins resolved by the file
  registry: `{"voting": "1.1.x", "vault": "^2.0.0"}`.
- `extension_overrides` — optional replacements for system extensions
  (extensions whose manifest has `"system": true`, e.g. `member_dashboard`,
  `public_dashboard`): `{"member_dashboard": "agora_member_dashboard"}`.
  Override extensions are installed as implicit dependencies; the realm
  backend then routes calls, sidebar entries, and frontend navigation for
  the base id to the replacement.
- `onboarding.registration.default_profile` — profile granted on codeless
  open registration (defaults to `member`).
- `entity_method_overrides` — **deprecated** (replaced by the hook API);
  only legacy packages under the old `codex/` registry namespace still use it.

## End-to-end testing

Each codex ships an agent-executable test plan in
`codices/<codex>/E2E_TEST_PROMPT.md`. Give an agent that prompt together with
the shared preamble `testing/E2E_AGENT_GUIDE.md` (staging environment,
authentication, Playwright conventions, universal checks) and it will drive a
real browser through the wizard, founder/member/civil-servant journeys, and
backend assertions, producing a pass/fail report. Prompt files are
documentation only — the registry publisher does not ship `.md` files with
the package.
