"""Tests for codex invoice_currency resolution."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

BACKEND = Path(__file__).resolve().parents[1] / "backend"
COMMON = Path(__file__).resolve().parents[2] / "_common"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "invoice_currency_testmod",
        BACKEND / "invoice_currency.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_common_module():
    spec = importlib.util.spec_from_file_location(
        "invoice_currency_common_testmod",
        COMMON / "invoice_currency.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mock_realm(currency: str):
    realm = MagicMock()
    realm.accounting_currency = currency
    ggg = MagicMock()
    ggg.Realm.instances.return_value = [realm]
    sys.modules["ggg"] = ggg
    return ggg


class TestInvoiceCurrency:
    def test_codex_pinned_symbol_wins(self):
        mod = _load_module()
        assert mod.invoice_currency({"currency": {"symbol": "ckBTC"}}) == "ckBTC"

    def test_realm_accounting_currency_when_unpinned(self):
        mod = _load_module()
        _mock_realm("ckUSDC")
        assert mod.invoice_currency({}) == "ckUSDC"

    def test_codex_pinned_beats_realm(self):
        mod = _load_module()
        _mock_realm("REALMS")
        assert mod.invoice_currency({"currency": {"symbol": "ckUSDC"}}) == "ckUSDC"

    def test_empty_when_nothing_configured(self):
        mod = _load_module()
        ggg = MagicMock()
        ggg.Realm.instances.return_value = []
        sys.modules["ggg"] = ggg
        assert mod.invoice_currency({}) == ""

    def test_no_treasury_token_error_payload(self):
        mod = _load_common_module()
        err = mod.no_treasury_token_error()
        assert err["error_code"] == "no_treasury_token"
        assert err["error"]


class TestMonthlyBillingRefusal:
    def test_create_monthly_invoice_refuses_without_currency(self, monkeypatch):
        monthly_path = (
            Path(__file__).resolve().parents[1]
            / "backend"
            / "modules"
            / "monthly_billing.py"
        )
        spec = importlib.util.spec_from_file_location(
            "monthly_billing_refusal_testmod", monthly_path
        )
        mod = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, "ggg", MagicMock())
        monkeypatch.setitem(sys.modules, "invoice_currency", _load_module())
        spec.loader.exec_module(mod)
        monkeypatch.setattr(mod, "_invoice_currency", lambda: "")

        result = mod.create_monthly_invoice("user-1")
        assert result["error_code"] == "no_treasury_token"

    def test_create_monthly_invoice_uses_pinned_symbol(self, monkeypatch):
        monthly_path = (
            Path(__file__).resolve().parents[1]
            / "backend"
            / "modules"
            / "monthly_billing.py"
        )
        spec = importlib.util.spec_from_file_location(
            "monthly_billing_pin_testmod", monthly_path
        )
        mod = importlib.util.module_from_spec(spec)
        user = MagicMock()
        user.id = "user-1"
        invoice = MagicMock()
        invoice.id = "inv-1"
        ggg = MagicMock()
        ggg.User.__getitem__.return_value = user
        ggg.Invoice.return_value = invoice
        monkeypatch.setitem(sys.modules, "ggg", ggg)
        monkeypatch.setitem(sys.modules, "invoice_currency", _load_module())
        spec.loader.exec_module(mod)
        monkeypatch.setattr(mod, "_invoice_currency", lambda: "DOM")

        result = mod.create_monthly_invoice("user-1")
        assert result["currency"] == "DOM"
        assert ggg.Invoice.call_args.kwargs["currency"] == "DOM"
