# realms-codices

The first-party codices of [Realms GOS](https://github.com/smart-social-contracts/realms-gos). A
codex is a realm's laws and settings as code; each realm runs exactly one.

| Codex | For |
|---|---|
| [`agora`](codices/agora) | An existing public administration moving to Realms one-to-one |
| [`dominion`](codices/dominion) | A direct democracy with taxation, in its own currency (DOM) |
| [`syntropia`](codices/syntropia) | A greenfield smart city: ZK passport, a deposit and Know-Your-Citizen data before go-live |

```text
codices/<id>/
├── manifest.json     kind: codex, codex_api_version: 2, hooks, capabilities, configuration, seed
└── backend/hooks.py  the hooks, using ggg_sdk
```

## Documentation

In realms-gos, [`docs/codices/`](https://github.com/smart-social-contracts/realms-gos/tree/main/docs/codices):

- [What a codex is](https://github.com/smart-social-contracts/realms-gos/blob/main/docs/codices/README.md): hooks, capabilities, configuration, install
- [SDK](https://github.com/smart-social-contracts/realms-gos/blob/main/docs/codices/sdk.md): `ggg_sdk` reference
- [Build, test, publish](https://github.com/smart-social-contracts/realms-gos/blob/main/docs/codices/build-test-publish.md)

## Tests

```bash
REALM_BACKEND=<realms-gos>/src/realm_backend pytest tests
```

Runs every codex's hooks with the realm's SDK against canned reads. `REALM_BACKEND` defaults to the
realms-gos checkout this repository is a submodule of.

## End-to-end testing

Each codex has an agent-executable test plan, `codices/<id>/E2E_TEST_PROMPT.md`. Give it to an
agent together with the shared preamble `testing/E2E_AGENT_GUIDE.md`: the agent drives a browser
through the setup wizard and the founder, member and civil-servant journeys, and reports pass or
fail. These files are documentation; they are not published with the package.
