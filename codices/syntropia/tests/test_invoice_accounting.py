"""Tests for Syntropia's realm-specific invoice journal policy."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND = Path(__file__).resolve().parents[1] / "backend"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "syntropia_invoice_accounting_testmod",
        BACKEND / "invoice_accounting.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _InvoiceRepo:
    items = {}

    @classmethod
    def __class_getitem__(cls, invoice_id):
        return cls.items.get(invoice_id)


class _FundRepo:
    items = {}

    def __new__(cls, **kwargs):
        fund = SimpleNamespace(**kwargs)
        cls.items[fund.code] = fund
        return fund

    @classmethod
    def __class_getitem__(cls, code):
        return cls.items.get(code)


class _LedgerEntry:
    transactions = {}

    @classmethod
    def find(cls, filters):
        return cls.transactions.get(filters["transaction_id"], [])

    @classmethod
    def create_transaction(cls, transaction_id, entries):
        cls.transactions[transaction_id] = entries
        return entries


class _Invoice:
    def __init__(self, invoice_id, metadata):
        self.id = invoice_id
        self.metadata = metadata
        self.currency = "REALMS"
        self.paid_at = "2026-07-22T12:00:00"
        self.user = SimpleNamespace(id="user-1")

    def _get_token_decimals(self):
        return 8

    def get_amount_raw(self, decimals):
        assert decimals == 8
        return 1_000_000


def _install_ggg(invoice):
    _InvoiceRepo.items = {invoice.id: invoice}
    _FundRepo.items = {}
    _LedgerEntry.transactions = {}
    sys.modules["ggg"] = SimpleNamespace(
        Invoice=_InvoiceRepo,
        Fund=_FundRepo,
        FundType=SimpleNamespace(GENERAL="general"),
        LedgerEntry=_LedgerEntry,
        EntryType=SimpleNamespace(
            ASSET="asset", LIABILITY="liability", REVENUE="revenue"
        ),
        Category=SimpleNamespace(
            CASH="cash",
            RECEIVABLE="receivable",
            DEFERRED_REVENUE="deferred_revenue",
            TAX="tax",
            FEE="fee",
        ),
    )


def test_deposit_remains_a_liability_after_payment():
    module = _load_module()
    invoice = _Invoice("inv-deposit", "deposit invoice - a house in a zone")
    _install_ggg(invoice)

    result = module.book_invoice_event(invoice.id, "paid")

    assert result["creation_entries"] == 2
    assert result["payment_entries"] == 2
    creation = _LedgerEntry.transactions["TXN-INV-inv-deposit"]
    payment = _LedgerEntry.transactions["TXN-INV-PAY-inv-deposit"]
    assert [entry["category"] for entry in creation] == [
        "receivable",
        "citizen_deposit",
    ]
    assert [entry["category"] for entry in payment] == ["cash", "receivable"]
    assert not any(entry["entry_type"] == "revenue" for entry in payment)


def test_membership_invoice_becomes_tax_revenue_and_is_idempotent():
    module = _load_module()
    invoice = _Invoice("inv-tax", "membership_tax invoice - beta stage")
    _install_ggg(invoice)

    first = module.book_invoice_event(invoice.id, "paid")
    second = module.book_invoice_event(invoice.id, "paid")

    assert first["creation_entries"] == 2
    assert first["payment_entries"] == 4
    assert second["creation_entries"] == 0
    assert second["payment_entries"] == 0
    payment = _LedgerEntry.transactions["TXN-INV-PAY-inv-tax"]
    assert payment[-1]["entry_type"] == "revenue"
    assert payment[-1]["category"] == "tax"


test_deposit_remains_a_liability_after_payment()
test_membership_invoice_becomes_tax_revenue_and_is_idempotent()
print("\n✅ All invoice_accounting tests passed!")
