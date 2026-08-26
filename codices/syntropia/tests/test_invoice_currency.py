"""Tests for codex invoice_currency resolution and live billing refusal."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

from realms.testing import setup_test_env, reset_registry

setup_test_env()
reset_registry()

BACKEND = Path(__file__).resolve().parents[1] / "backend"
COMMON = Path(__file__).resolve().parents[2] / "_common"


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module(BACKEND / "invoice_currency.py", "invoice_currency_testmod")
common = _load_module(COMMON / "invoice_currency.py", "invoice_currency_common_testmod")

print("Testing invoice_currency...")

assert mod.invoice_currency({"currency": {"symbol": "ckBTC"}}) == "ckBTC"

realm = MagicMock()
realm.accounting_currency = "ckUSDC"
ggg = MagicMock()
ggg.Realm.instances.return_value = [realm]
sys.modules["ggg"] = ggg
assert mod.invoice_currency({}) == "ckUSDC"

assert mod.invoice_currency({"currency": {"symbol": "ckUSDC"}}) == "ckUSDC"

ggg.Realm.instances.return_value = []
assert mod.invoice_currency({}) == ""

err = common.no_treasury_token_error()
assert err["error_code"] == "no_treasury_token"
assert err["error"]

print("  invoice_currency: OK")


print("Testing lifecycle_billing currency refusal...")

# Restore the realms mock ggg so billing helpers can import Invoice/User/etc.
setup_test_env()
reset_registry()
import lifecycle_billing

refused = lifecycle_billing.issue_membership_invoices({}, "Syntropia")
assert refused["success"] is False
assert refused["error_code"] == "no_treasury_token"

payroll = lifecycle_billing.run_payroll({}, "Syntropia")
assert payroll["success"] is False
assert payroll["error_code"] == "no_treasury_token"

print("  lifecycle_billing refusal: OK")
print("\n✅ All invoice_currency tests passed!")
