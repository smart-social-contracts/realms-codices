"""Each codex's hooks, run with the realm's SDK against canned reads: no realm needed.

REALM_BACKEND points at realms-gos/src/realm_backend (default: the checkout this repo is a submodule of).
The realm's own tests (tests/ggg/test_codex.py) run the same hooks in its sandbox against a live world.
"""

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = pathlib.Path(os.environ.get("REALM_BACKEND", ROOT.parent / "src" / "realm_backend"))
SDK = {}
exec((BACKEND / "core" / "sdk.py").read_text(), SDK)
USERS = [{"id": "alice", "status": "active", "profiles": ["member"]},
         {"id": "founder", "status": "active", "profiles": ["member", "admin"]}]
READS = {"user_list": {"users": USERS, "next": None},
         "department_list": {"departments": [{"id": "Administration"}], "next": None}}


def run(codex, fn, args=None, **realm):
    sdk = type(sys)("ggg_sdk")
    sdk.rpc = lambda op, **kw: {"ok": True, **READS[op]}
    exec(SDK["SOURCE"], sdk.__dict__)
    sys.modules["ggg_sdk"] = sdk
    manifest = json.loads((ROOT / "codices" / codex / "manifest.json").read_text())
    hooks = {}
    exec((ROOT / "codices" / codex / "backend" / "hooks.py").read_text(), hooks)
    info = {"name": "", "status": "alpha", "accounting_currency": "REALM", "accounting_currency_decimals": 8,
            "is_capital": True, "open_registration": False, **realm}
    out = hooks[fn](args or {}, {"config": manifest, "now": 1_790_000_000, "realm": info})
    assert out["ok"], out
    assert {op for op, _ in out["effects"]} <= set(manifest["capabilities"])
    assert set(manifest["hooks"]) <= set(hooks)
    return out["result"], out["effects"]


def ops(effects):
    return [op for op, _ in effects]


def test_agora_bills_nothing_during_migration_then_registration_at_beta():
    _, effects = run("agora", "on_user_register", {"user": "bob"})
    assert ops(effects) == ["notification_send"]
    result, effects = run("agora", "on_user_register", {"user": "bob"}, status="beta")
    (_, invoice), (_, notice) = effects
    assert result == {"invoice": "$eff:0:invoice"} and notice["recipient"] == "User:bob"
    assert (invoice["payer"], invoice["amount"], invoice["symbol"]) == ("User:bob", 100_000_000, "REALM")


def test_agora_init_seeds_departments_and_courts_top_down():
    _, effects = run("agora", "init")
    assert effects[0] == ["realm_configure", {"open_registration": False, "name": "Agora"}]
    created = [a["department"] for op, a in effects if op == "department_create"]
    assert "Congress" in created and "Administration" not in created
    courts = [a for op, a in effects if op == "court_create"]
    assert [c["name"] for c in courts] == ["Supreme Court", "Court of Appeals", "District Court"]
    assert courts[0]["parent"] == "" and courts[1]["parent"].startswith("$eff:")


def test_agora_beta_bills_members_but_not_admins_and_runs_payroll():
    result, effects = run("agora", "on_stage_change", {"stage": "beta"})
    assert result == {"invoiced": 1} and ops(effects).count("payroll_run") == 8
    assert run("agora", "on_stage_change", {"stage": "production"})[1] == []


def test_dominion_invoices_in_its_own_currency():
    _, ((op, invoice), _) = run("dominion", "on_user_register", {"user": "bob"})
    assert (op, invoice["symbol"], invoice["amount"]) == ("invoice_create", "DOM", 100_000_000)


def test_syntropia_deposit_identity_requests_and_quarters():
    _, effects = run("syntropia", "on_user_register", {"user": "bob"})
    assert effects[0][1]["amount"] == 1_000_000
    result, _ = run("syntropia", "on_stage_change", {"stage": "beta"})
    assert result == {"invoiced": 1, "identity_requests": 2}
    quarters = [{"id": "north", "population": 5}, {"id": "south", "population": 2}]
    assert run("syntropia", "assign_quarter", {"user": "bob", "quarters": quarters})[0] == {"quarter": "south"}
    assert run("syntropia", "assign_quarter", {"user": "bob", "quarters": quarters, "preferred": "north"})[0] == {
        "quarter": "north"}
