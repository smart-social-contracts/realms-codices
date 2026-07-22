"""Tests for codex invoice_currency resolution."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

BACKEND = Path(__file__).resolve().parents[1] / "backend"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "invoice_currency_testmod",
        BACKEND / "invoice_currency.py",
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
        _mock_realm("REALMS")
        assert mod.invoice_currency({}) == "REALMS"

    def test_codex_pinned_beats_realm(self):
        mod = _load_module()
        _mock_realm("REALMS")
        assert mod.invoice_currency({"currency": {"symbol": "ckUSDC"}}) == "ckUSDC"

    def test_default_when_nothing_configured(self):
        mod = _load_module()
        ggg = MagicMock()
        ggg.Realm.instances.return_value = []
        sys.modules["ggg"] = ggg
        assert mod.invoice_currency({}) == "REALMS"
