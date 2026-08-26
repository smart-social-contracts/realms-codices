"""Live-spine hook tests for Syntropia (greenfield).

Covers the in-process entry hooks the host still calls, plus the sandboxed
init / seed path. Asserts behavior, not prints.
"""

import json
import os
import sys
import types

from realms.testing import setup_test_env, reset_registry

setup_test_env()
reset_registry()

from ggg import (
    Appointment,
    Department,
    Fund,
    Invoice,
    Notification,
    Position,
    Realm,
    Transfer,
    User,
    UserProfile,
)
import entry


_CODEX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PINNED_NS = 1_700_000_000 * 1_000_000_000  # 2023-11-14
_PINNED_EPOCH = 1_700_000_000


def _attach_live_helpers():
    import ggg

    def iter_users():
        return list(User.instances())

    def user_has_profile(user, profile):
        if user is None or profile is None:
            return False
        profile_name = (
            profile if isinstance(profile, str) else getattr(profile, "name", None)
        )
        if not profile_name:
            return False
        try:
            return any(getattr(p, "name", None) == profile_name for p in user.profiles)
        except Exception:
            return False

    def check_access(caller, operation):
        return True

    ggg.iter_users = iter_users
    ggg.user_has_profile = user_has_profile
    ggg.check_access = check_access
    ggg.Operations = types.SimpleNamespace(REALM_ADMIN="realm.admin")


def _give_profile(user, name):
    profile = UserProfile[name] or UserProfile(name=name)
    user.profiles = [profile]
    return profile


def _realm(status="alpha", currency="ckBTC"):
    return Realm(
        name="Syntropia Hook Test",
        status=status,
        accounting_currency=currency,
        open_registration=False,
    )


_attach_live_helpers()
import _cdk

_cdk.ic.time = lambda: _PINNED_NS


# ── get_config strips packaging metadata ─────────────────────────────────────
print("Testing get_config...")

_realm()
cfg = json.loads(entry.get_config("{}"))
assert "id" not in cfg
assert "codex_modules" not in cfg
assert "kind" not in cfg
assert "sandbox_module" not in cfg
assert "fees" in cfg
assert cfg["fees"]["deposit"] == 0.01

print("  get_config: OK")


# ── on_user_register: unknown user ───────────────────────────────────────────
print("Testing on_user_register unknown user...")

reset_registry()
_attach_live_helpers()
_realm("alpha")

missing = json.loads(entry.on_user_register(json.dumps({"user_id": "ghost"})))
assert missing["success"] is False
assert missing["error"] == "user not found"
assert Invoice.count() == 0

print("  unknown user: OK")


# ── on_user_register: always issues a deposit invoice ────────────────────────
print("Testing on_user_register deposit invoice...")

reset_registry()
_attach_live_helpers()
_realm("alpha")
citizen = User(id="citizen-1", name="Citizen")

reg = json.loads(entry.on_user_register(json.dumps({"user_id": "citizen-1"})))
assert reg["success"] is True, reg
assert "invoice_id" in reg
invoice = Invoice[reg["invoice_id"]]
assert invoice is not None
assert invoice.amount == 0.01
assert invoice.currency == "ckBTC"
assert invoice.status == "Pending"
assert invoice.metadata == "deposit invoice - a house in a zone"
assert invoice.user is citizen
notes = [n for n in Notification.instances() if n.user is citizen]
assert len(notes) == 1
assert notes[0].topic == "welcome"
assert notes[0].icon == "shield_check"
assert notes[0].metadata == f"invoice_id:{invoice.id}"
assert "ZK Passport" in notes[0].message
assert "Know-Your-Citizen" in notes[0].message

print("  deposit invoice: OK")


# ── on_invoice_accounting wiring ─────────────────────────────────────────────
print("Testing on_invoice_accounting wiring...")

reset_registry()
_attach_live_helpers()
_realm("alpha")

empty = json.loads(entry.on_invoice_accounting("{}"))
assert empty["success"] is False
assert "invoice_id" in empty["error"]

unknown = json.loads(
    entry.on_invoice_accounting(json.dumps({"invoice_id": "ghost", "event": "paid"}))
)
assert unknown["success"] is False
assert unknown["error"] == "invoice not found"

inv = Invoice(
    id="inv-skip",
    amount=0.01,
    currency="ckBTC",
    metadata="deposit invoice - a house in a zone",
    paid_at="2026-07-22T12:00:00",
)
skipped = json.loads(
    entry.on_invoice_accounting(
        json.dumps({"invoice_id": "inv-skip", "event": "created"})
    )
)
assert skipped["success"] is True
assert "skipped" in skipped

# Paid deposit path: book through the hook so we know wiring reaches
# invoice_accounting.book_invoice_event.
inv_paid = Invoice(
    id="inv-deposit",
    amount=0.01,
    currency="ckBTC",
    metadata="deposit invoice - a house in a zone",
    paid_at="2026-07-22T12:00:00",
    user=User(id="payer-1", name="Payer"),
)
inv_paid._get_token_decimals = lambda: 8
inv_paid.get_amount_raw = lambda decimals=8: 1_000_000
paid = json.loads(
    entry.on_invoice_accounting(
        json.dumps({"invoice_id": "inv-deposit", "event": "paid"})
    )
)
assert paid["success"] is True, paid
assert paid["invoice_id"] == "inv-deposit"
assert paid["creation_entries"] == 2
assert paid["payment_entries"] == 2

print("  on_invoice_accounting: OK")


# ── on_stage_change skips non-beta ───────────────────────────────────────────
print("Testing on_stage_change skip...")

reset_registry()
_attach_live_helpers()
_realm("alpha")

skipped_stage = json.loads(
    entry.on_stage_change(json.dumps({"to_stage": "production"}))
)
assert skipped_stage["success"] is True
assert "skipped" in skipped_stage
assert Invoice.count() == 0

print("  non-beta skip: OK")


# ── on_stage_change / run_payroll (period-idempotent fork) ───────────────────
print("Testing on_stage_change beta + payroll...")

reset_registry()
_attach_live_helpers()
_realm("beta")

member_user = User(id="citizen-alice", name="Alice")
_give_profile(member_user, "member")
admin_user = User(id="founder-admin", name="Admin")
_give_profile(admin_user, "admin")
staff = User(id="civil-servant-principal", name="Clerk")
_give_profile(staff, "member")

dept = Department(name="Citizenship & Identity")
fund = Fund(code="IDENT", name="Identity Fund")
dept.fund = fund
seat = Position(
    key="Citizenship & Identity/registrar",
    title="registrar",
    salary_amount=1800,
    department=dept,
    status="open",
    headcount=1,
)
Appointment(position=seat, user=staff, status="active")

stage = json.loads(entry.on_stage_change(json.dumps({"to_stage": "beta"})))
assert stage["success"] is True, stage
assert stage["invoiced"] == 2
assert stage["payroll_payments"] == 1
assert stage["identity_requests"] == 2

tax_invoices = [
    inv for inv in Invoice.instances() if "membership_tax" in (inv.metadata or "")
]
assert len(tax_invoices) == 2
identity_notes = [
    n for n in Notification.instances() if n.topic == "identity"
]
assert len(identity_notes) == 2

expected_id = (
    "SAL-Citizenship & Identity/registrar-civil-servant-principal-2023-11"
)
payroll = Transfer[expected_id]
assert payroll is not None, (
    f"expected {expected_id}, have {[t.id for t in Transfer.instances()]}"
)
assert payroll.amount == 1800
assert payroll.instrument == "ckBTC"

# Re-run is period-idempotent: same id, skipped flag, total not double-counted.
rerun = json.loads(entry.run_payroll("{}"))
assert rerun["success"] is True, rerun
assert len(rerun["payments"]) == 1
assert rerun["payments"][0]["transfer_id"] == expected_id
assert rerun["payments"][0].get("skipped") == "already recorded for this period"
assert rerun["total"] == 0
assert Transfer.count() == 1

print("  beta invoices + period payroll: OK")


# ── sandbox init / seed + deposit register ───────────────────────────────────
print("Testing sandbox_hooks...")

calls = []


class _Users:
    def __init__(self, store):
        self._store = store

    def get(self, user_id):
        return self._store.get(user_id)


class _Invoices:
    def create(self, **kwargs):
        calls.append(("invoice.create", kwargs))
        return {"id": "inv-sandbox"}


class _Notifications:
    def create(self, **kwargs):
        calls.append(("notification.create", kwargs))
        return {"id": "ntf-sandbox"}


class _Init:
    def apply_init_policy(self):
        calls.append(("init.apply_init_policy", {}))

    def seed_org(self, name):
        calls.append(("init.seed_org", {"name": name}))

    def seed_justice(self):
        calls.append(("init.seed_justice", {}))


class _Realm:
    def __init__(self):
        self.users = _Users({"u1": {"id": "u1"}})
        self.invoices = _Invoices()
        self.notifications = _Notifications()
        self.init = _Init()
        self._config = {
            "fees": {"deposit": 0.05},
            "lifecycle": {"deposit_label": "a house in a zone"},
            "membership": {"invoice_validity_days": 30},
        }

    def config(self):
        return self._config

    def currency(self):
        return "ckBTC"

    def now(self):
        return {"epoch": _PINNED_EPOCH, "ns": _PINNED_NS}


fake_realm = _Realm()
ggg_sdk = types.ModuleType("ggg_sdk")
ggg_sdk.hook = lambda fn: fn
ggg_sdk.iso_days_from = lambda epoch, days: "2023-12-14T22:13:20"
ggg_sdk.realm = fake_realm
sys.modules["ggg_sdk"] = ggg_sdk

sys.modules.pop("sandbox_hooks", None)
import sandbox_hooks

init_result = sandbox_hooks.init({})
assert init_result == {"success": True, "codex": "syntropia"}
assert ("init.apply_init_policy", {}) in calls
assert ("init.seed_org", {"name": "departments"}) in calls
assert ("init.seed_justice", {}) in calls

calls.clear()
missing_sb = sandbox_hooks.on_user_register({"user_id": "ghost"})
assert missing_sb == {"success": False, "error": "user not found"}
assert not any(name == "invoice.create" for name, _ in calls)

reg_sb = sandbox_hooks.on_user_register({"user_id": "u1"})
assert reg_sb == {"success": True, "invoice_id": "inv-sandbox"}
invoice_kwargs = next(kwargs for name, kwargs in calls if name == "invoice.create")
assert invoice_kwargs["metadata"] == "deposit invoice - a house in a zone"
assert invoice_kwargs["amount"] == 0.05
assert invoice_kwargs["currency"] == "ckBTC"
note = next(kwargs for name, kwargs in calls if name == "notification.create")
assert note["topic"] == "welcome"
assert note["metadata"] == "invoice_id:inv-sandbox"

print("  sandbox init / register: OK")


# ── keeper modules only ──────────────────────────────────────────────────────
print("Testing live module keepers...")

modules_dir = os.path.join(_CODEX_DIR, "backend", "modules")
present = sorted(
    os.path.splitext(name)[0]
    for name in os.listdir(modules_dir)
    if name.endswith(".py")
)
assert present == ["quarter_assignment"], present
with open(os.path.join(_CODEX_DIR, "manifest.json")) as f:
    manifest = json.load(f)
assert manifest.get("codex_modules") == ["quarter_assignment"]

print("  keeper modules: OK")

print("\n✅ All Syntropia live-spine hook tests passed!")
