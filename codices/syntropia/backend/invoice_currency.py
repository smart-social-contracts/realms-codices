"""Resolve invoice currency: codex-pinned symbol, else realm treasury currency."""


def invoice_currency(manifest: dict, default: str = "REALMS") -> str:
    """Currency for invoices and treasury transfers.

    Resolution order:
      1. ``manifest["currency"]["symbol"]`` (codex-pinned or config_overrides)
      2. ``Realm.accounting_currency`` (wizard / realm settings)
      3. *default* (REALMS for greenfield codices)
    """
    if not isinstance(manifest, dict):
        manifest = {}
    currency_block = manifest.get("currency")
    if isinstance(currency_block, dict):
        symbol = str(currency_block.get("symbol") or "").strip()
        if symbol:
            return symbol[:16]
    try:
        from ggg import Realm

        realms = Realm.instances()
        if realms:
            acct = str(getattr(realms[0], "accounting_currency", "") or "").strip()
            if acct:
                return acct[:16]
    except Exception:
        pass
    return (default or "REALMS")[:16]
