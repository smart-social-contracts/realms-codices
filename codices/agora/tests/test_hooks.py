"""Live-spine hook tests for Agora (incumbent migration).

Covers the in-process entry hooks the host still calls, plus the sandboxed
init / seed / treasury path. Asserts behavior, not prints.
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
    Codex,
    Department,
    Fund,
    Invoice,
    Member,
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
    """The mock ggg used by `realms test` is entity-only; live hooks also
    import facade helpers. Install the same shapes the host exposes."""
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

    def extension_call(ext_id, method, args):
        return {"ext": ext_id, "method": method, "args": args}

    ggg.iter_users = iter_users
    ggg.user_has_profile = user_has_profile
    ggg.check_access = check_access
    ggg.extension_call = extension_call
    ggg.Operations = types.SimpleNamespace(REALM_ADMIN="realm.admin")


def _give_profile(user, name):
    profile = UserProfile[name] or UserProfile(name=name)
    user.profiles = [profile]
    return profile


def _seed_membership_codex():
    path = os.path.join(_CODEX_DIR, "backend", "modules", "membership.py")
    with open(path) as f:
        code = f.read()
    existing = Codex["membership"]
    if existing:
        existing.code = code
    else:
        Codex(name="membership", code=code)


def _realm(status="alpha", currency="ckBTC"):
    return Realm(
        name="Agora Hook Test",
        status=status,
        accounting_currency=currency,
        open_registration=True,
    )


_attach_live_helpers()
import _cdk

_cdk.ic.time = lambda: _PINNED_NS


# ── get_config strips packaging metadata ─────────────────────────────────────
print("Testing get_config...")

_realm()
_seed_membership_codex()
cfg = json.loads(entry.get_config("{}"))
assert "id" not in cfg
assert "codex_modules" not in cfg
assert "kind" not in cfg
assert "sandbox_module" not in cfg
assert "fees" in cfg
assert cfg["fees"]["registration"] == 1.0

print("  get_config: OK")


# ── on_user_register: unknown user ───────────────────────────────────────────
print("Testing on_user_register unknown user...")

reset_registry()
_attach_live_helpers()
_realm("alpha")
_seed_membership_codex()

missing = json.loads(entry.on_user_register(json.dumps({"user_id": "ghost"})))
assert missing["success"] is False
assert missing["error"] == "user not found"
assert Invoice.count() == 0

print("  unknown user: OK")


# ── on_user_register: alpha activates, no invoice ────────────────────────────
print("Testing on_user_register alpha (activate, no invoice)...")

reset_registry()
_attach_live_helpers()
_realm("alpha")
_seed_membership_codex()
resident = User(id="resident-1", name="Resident")

alpha = json.loads(entry.on_user_register(json.dumps({"user_id": "resident-1"})))
assert alpha["success"] is True, alpha
assert alpha["stage"] == "alpha"
assert Invoice.count() == 0
member = Member.for_user("resident-1")
assert member is not None, "alpha registration must activate via Codex['membership']"
assert member.identity_verification == "verified"
assert member.voting_eligibility == "eligible"
notes = [n for n in Notification.instances() if n.user is resident]
assert len(notes) == 1
assert notes[0].icon == "information_circle"
assert notes[0].topic == "welcome"
assert "stage:alpha" in (notes[0].metadata or "")

print("  alpha activate / no invoice: OK")


# ── on_user_register: beta issues registration invoice + activates ───────────
print("Testing on_user_register beta (invoice + activate)...")

reset_registry()
_attach_live_helpers()
_realm("beta")
_seed_membership_codex()
migrated = User(id="migrated-1", name="Migrated")

beta = json.loads(entry.on_user_register(json.dumps({"user_id": "migrated-1"})))
assert beta["success"] is True, beta
assert "invoice_id" in beta
invoice = Invoice[beta["invoice_id"]]
assert invoice is not None
assert invoice.amount == 1.0
assert invoice.currency == "ckBTC"
assert invoice.status == "Pending"
assert invoice.metadata == "registration invoice"
assert invoice.user is migrated
assert Member.for_user("migrated-1") is not None
notes = [n for n in Notification.instances() if n.user is migrated]
assert len(notes) == 1
assert notes[0].icon == "wallet"
assert notes[0].metadata == f"invoice_id:{invoice.id}"

print("  beta invoice + activate: OK")


# ── on_user_register: production with fee also invoices ──────────────────────
print("Testing on_user_register production...")

reset_registry()
_attach_live_helpers()
_realm("production")
_seed_membership_codex()
User(id="live-1", name="Live")

prod = json.loads(entry.on_user_register(json.dumps({"user_id": "live-1"})))
assert prod["success"] is True, prod
assert "invoice_id" in prod
assert Invoice.count() == 1

print("  production invoice: OK")


# ── on_stage_change skips non-beta ───────────────────────────────────────────
print("Testing on_stage_change skip...")

reset_registry()
_attach_live_helpers()
_realm("alpha")

skipped = json.loads(entry.on_stage_change(json.dumps({"to_stage": "production"})))
assert skipped["success"] is True
assert "skipped" in skipped
assert Invoice.count() == 0
assert Transfer.count() == 0

print("  non-beta skip: OK")


# ── on_stage_change / run_payroll (Agora stale fork) ─────────────────────────
print("Testing on_stage_change beta + stale payroll...")

reset_registry()
_attach_live_helpers()
_realm("beta")

member_user = User(id="citizen-alice", name="Alice")
_give_profile(member_user, "member")
admin_user = User(id="founder-admin", name="Admin")
_give_profile(admin_user, "admin")
staff = User(id="civil-servant-principal", name="Clerk")
_give_profile(staff, "member")

dept = Department(name="Civil Registry")
fund = Fund(code="CIVREG", name="Civil Registry Fund")
dept.fund = fund
seat = Position(
    key="Civil Registry/clerk",
    title="clerk",
    salary_amount=2500,
    department=dept,
    status="open",
    headcount=1,
)
Appointment(position=seat, user=staff, status="active")

stage = json.loads(entry.on_stage_change(json.dumps({"to_stage": "beta"})))
assert stage["success"] is True, stage
# Alice is a member (not admin) → membership invoice. Staff is also a member.
assert stage["invoiced"] == 2
assert stage["payroll_payments"] == 1

tax_invoices = [
    inv for inv in Invoice.instances() if "membership_tax" in (inv.metadata or "")
]
assert len(tax_invoices) == 2
assert all(inv.user.id != "founder-admin" for inv in tax_invoices)

# Agora's backend/lifecycle_billing.py is the stale fork: transfer id uses
# the first 12 chars of the principal and the raw epoch, no period key.
expected_id = f"SAL-Civil Registry/clerk-civil-servan-{_PINNED_EPOCH}"
payroll = Transfer[expected_id]
assert payroll is not None, f"expected {expected_id}, have {[t.id for t in Transfer.instances()]}"
assert payroll.amount == 2500
assert payroll.instrument == "ckBTC"
assert payroll.tags == "salary"
assert payroll.status == "recorded"

# Re-run records another Transfer with the same id (no idempotency skip).
# The stale fork always constructs a new Transfer; lookup still finds one.
rerun = json.loads(entry.run_payroll("{}"))
assert rerun["success"] is True, rerun
assert len(rerun["payments"]) == 1
assert rerun["payments"][0]["transfer_id"] == expected_id
assert "skipped" not in rerun["payments"][0]
assert rerun["total"] == 2500

print("  beta invoices + stale payroll: OK")


# ── on_treasury_send yields a vault transfer ────────────────────────────────
print("Testing on_treasury_send...")

reset_registry()
_attach_live_helpers()
_realm("beta")

gen = entry.on_treasury_send(
    json.dumps({"to_principal": "aaaaa-aa", "amount": 42, "treasury_name": "root"})
)
yielded = next(gen)
assert yielded["ext"] == "vault"
assert yielded["method"] == "transfer"
payload = json.loads(yielded["args"])
assert payload["to_principal"] == "aaaaa-aa"
assert payload["amount"] == 42
try:
    gen.send({"ok": True, "tx": "1"})
except StopIteration as stop:
    assert stop.value == {"ok": True, "tx": "1"}
else:
    raise AssertionError("on_treasury_send should return the vault result")

print("  on_treasury_send: OK")


# ── sandbox init / seed + treasury + stage-aware register ────────────────────
print("Testing sandbox_hooks...")

calls = []


class _Users:
    def __init__(self, store):
        self._store = store

    def get(self, user_id):
        return self._store.get(user_id)


class _Members:
    def activate(self, user_id, **kwargs):
        calls.append(("member.activate", {"user_id": user_id, **kwargs}))
        return {"accepted": True}


class _Invoices:
    def create(self, **kwargs):
        calls.append(("invoice.create", kwargs))
        return {"id": "inv-sandbox"}


class _Notifications:
    def create(self, **kwargs):
        calls.append(("notification.create", kwargs))
        return {"id": "ntf-sandbox"}


class _Treasury:
    def transfer(self, **kwargs):
        calls.append(("treasury.transfer", kwargs))
        return {"success": True}


class _Init:
    def apply_init_policy(self):
        calls.append(("init.apply_init_policy", {}))

    def seed_org(self, name):
        calls.append(("init.seed_org", {"name": name}))

    def seed_justice(self):
        calls.append(("init.seed_justice", {}))


class _Realm:
    def __init__(self):
        self.users = _Users({"u-alpha": {"id": "u-alpha"}, "u-beta": {"id": "u-beta"}})
        self.members = _Members()
        self.invoices = _Invoices()
        self.notifications = _Notifications()
        self.treasury = _Treasury()
        self.init = _Init()
        self._status = "alpha"
        self._config = {
            "fees": {"registration": 2.0},
            "membership": {"invoice_validity_days": 30},
        }

    def config(self):
        return self._config

    def currency(self):
        return "REALMS"

    def now(self):
        return {"epoch": _PINNED_EPOCH, "ns": _PINNED_NS}

    def info(self):
        return {"status": self._status}


fake_realm = _Realm()
ggg_sdk = types.ModuleType("ggg_sdk")
ggg_sdk.hook = lambda fn: fn
ggg_sdk.iso_days_from = lambda epoch, days: "2023-12-14T22:13:20"
ggg_sdk.realm = fake_realm
sys.modules["ggg_sdk"] = ggg_sdk

sys.modules.pop("sandbox_hooks", None)
import sandbox_hooks

init_result = sandbox_hooks.init({})
assert init_result == {"success": True, "codex": "agora"}
assert ("init.apply_init_policy", {}) in calls
assert ("init.seed_org", {"name": "departments"}) in calls
assert ("init.seed_justice", {}) in calls

calls.clear()
alpha_sb = sandbox_hooks.on_user_register({"user_id": "u-alpha"})
assert alpha_sb == {"success": True, "stage": "alpha"}
assert any(name == "member.activate" for name, _ in calls)
assert not any(name == "invoice.create" for name, _ in calls)
note = next(kwargs for name, kwargs in calls if name == "notification.create")
assert note["icon"] == "information_circle"

calls.clear()
fake_realm._status = "beta"
beta_sb = sandbox_hooks.on_user_register({"user_id": "u-beta"})
assert beta_sb == {"success": True, "invoice_id": "inv-sandbox"}
invoice_kwargs = next(kwargs for name, kwargs in calls if name == "invoice.create")
assert invoice_kwargs["metadata"] == "registration invoice"
assert invoice_kwargs["amount"] == 2.0
assert invoice_kwargs["currency"] == "REALMS"

calls.clear()
treasury = sandbox_hooks.on_treasury_send(
    {"to_principal": "bbbbb-bb", "amount": 9, "treasury_name": "root"}
)
assert treasury == {"success": True}
xfer = next(kwargs for name, kwargs in calls if name == "treasury.transfer")
assert xfer["to_principal"] == "bbbbb-bb"
assert xfer["amount"] == 9
assert xfer["treasury_name"] == "root"

print("  sandbox init / register / treasury: OK")


# ── keeper modules only ──────────────────────────────────────────────────────
print("Testing live module keepers...")

modules_dir = os.path.join(_CODEX_DIR, "backend", "modules")
present = sorted(
    os.path.splitext(name)[0]
    for name in os.listdir(modules_dir)
    if name.endswith(".py")
)
assert present == ["membership"], present
with open(os.path.join(_CODEX_DIR, "manifest.json")) as f:
    manifest = json.load(f)
assert manifest.get("codex_modules") == ["membership"]

print("  keeper modules: OK")

print("\n✅ All Agora live-spine hook tests passed!")
