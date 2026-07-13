# realms-codices

Codex packages for the Realms platform. A codex is a distro-style bundle: a
`manifest.json` plus code/data files that configure a realm and pull in the
extensions it needs.

## Manifest keys (excerpt)

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
- `entity_method_overrides` — hooks replacing entity methods (see
  `codices/_common`).

## End-to-end testing

Each codex ships an agent-executable test plan in
`codices/<codex>/E2E_TEST_PROMPT.md`. Give an agent that prompt together with
the shared preamble `testing/E2E_AGENT_GUIDE.md` (staging environment,
authentication, Playwright conventions, universal checks) and it will drive a
real browser through the wizard, founder/member/civil-servant journeys, and
backend assertions, producing a pass/fail report. Prompt files are
documentation only — the registry publisher does not ship `.md` files with
the package.
