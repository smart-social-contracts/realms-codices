# realms-codices

Codex packages for the Realms platform. A codex is a **privileged system
extension** (issue #244): an extension package whose manifest declares
`"kind": "codex"`. It configures a realm, pulls in the extensions it needs
(distro behavior), and integrates with the core through a versioned hook API
— exactly one codex is installed per realm.

## Package layout

```
<codex_id>/
├── manifest.json     id, version, kind: codex, codex_api_version: 2, hooks, capabilities,
│                     config blocks (fees, governance, onboarding, …) and `seed` data
└── backend/
    └── hooks.py      the hooks, one self-contained module
```

A codex runs in the realm's sandbox (a fresh Basilisk subinterpreter per hook call). `hooks.py`
imports only `ggg_sdk`, the SDK the realm injects (`src/realm_backend/sdk.py` in realms-gos):

```python
from ggg_sdk import hook, realm

@hook
def on_user_register(args):
    invoice = realm.invoice(args["user"], realm.setting("fees.registration"), "registration")
    realm.notify(args["user"], "Welcome", "Please settle your registration invoice.")
    return {"invoice": invoice["invoice"]}
```

Reads come from the context the realm passes (`realm.config`, `realm.info`, `realm.now`,
`realm.stage`) or from `realm.call(op, **args)`, a read operation. Writes are recorded as
`(op, args)` effects that the realm applies through its operations after the hook returns.
`capabilities` lists the operations (by name: `invoice_create`, `notification_send`, …) the codex
may read or apply; the realm's Cedar guardrails refuse anything else. Shared helpers (seeding
departments and courts, billing members, payroll) live in the SDK.

Install with the realm's `codex_install` operation, governed realm-wide: either
`{"codex": "agora", "version": "1.0.0"}` (pulled from the file registry namespace
`ext/<id>/<version>`, marketplace-approved) or `{"manifest": …, "source": …}` (its checksum must be
allowlisted in the realm's trust policy). `codex_revert` goes back to the previous version.

## Hooks (codex_api_version 2)

All optional; the manifest's `hooks` lists the ones a codex implements.

- `init` — after install: enforce realm settings, seed data (idempotent)
- `on_user_register` — `{"user"}` after someone joins
- `on_stage_change` — `{"stage"}` when the realm moves through its lifecycle
- `assign_quarter` — `{"user", "preferred", "quarters": [{"id", "name", "population"}]}` → `{"quarter"}`

## Tests

`pytest tests` runs every codex's hooks with the SDK against canned reads
(`REALM_BACKEND=<realms-gos>/src/realm_backend`).

## End-to-end testing

Each codex ships an agent-executable test plan in
`codices/<codex>/E2E_TEST_PROMPT.md`. Give an agent that prompt together with
the shared preamble `testing/E2E_AGENT_GUIDE.md` (staging environment,
authentication, Playwright conventions, universal checks) and it will drive a
real browser through the wizard, founder/member/civil-servant journeys, and
backend assertions, producing a pass/fail report. Prompt files are
documentation only — the registry publisher does not ship `.md` files with
the package.
