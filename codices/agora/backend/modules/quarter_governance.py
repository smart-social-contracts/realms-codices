"""
Quarter Governance Codex — Agora Realm

Quarter-dependent logic that branches on canister identity. The same codex
runs on every quarter, but behavior differs based on:

  - ``ic.id()``                    — which canister am I?
  - ``Realm.is_capital``           — am I the capital?
  - ``QuarterConfig``              — local parameters per quarter

Two areas of quarter-specific behavior:

  1. **Taxes** — quarters collect local revenue and forward a federal share
     to the capital.  The capital keeps all revenue locally.
  2. **Budget allocation** — the capital redistributes federal tax revenue
     to quarters proportionally by population.

Realm-wide votes use the GOS federal-vote mechanism (``propose_federal_vote``),
not this module.
"""

from _cdk import ic
from ggg import (
    Realm, Quarter, QuarterConfig,
    LedgerEntry, Fund, FiscalPeriod, Budget,
    EntryType, Category, Transfer,
)
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEDERAL_TAX_RATE = 0.10          # 10% of quarter revenue goes to capital
SATOSHIS_PER_BTC = 100_000_000

DEFAULT_VOTING_WINDOW_DAYS = 7
DEFAULT_WELFARE_PERCENT = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso():
    """Current time as ISO 8601 string (from ic.time())."""
    return epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")


def get_quarter_context() -> dict:
    """Determine which quarter we're running on and return config.

    Returns a dict with:
      - canister_id: this canister's principal
      - is_capital: whether this is the capital backend
      - local_tax_rate: additional local tax rate (from QuarterConfig)
      - welfare_percent: local welfare allocation percent
      - voting_window_days: local voting window
    """
    own_id = ic.id().to_str()
    realm = Realm.load("1")
    is_capital = bool(getattr(realm, "is_capital", False)) if realm else False

    # QuarterConfig is a singleton per canister
    config = QuarterConfig.load("1")

    return {
        "canister_id": own_id,
        "is_capital": is_capital,
        "local_tax_rate": float(getattr(config, "local_tax_rate", 0.0) or 0.0),
        "welfare_percent": int(
            getattr(config, "welfare_percent", DEFAULT_WELFARE_PERCENT) or DEFAULT_WELFARE_PERCENT
        ),
        "voting_window_days": int(
            getattr(config, "voting_window_days", DEFAULT_VOTING_WINDOW_DAYS)
            or DEFAULT_VOTING_WINDOW_DAYS
        ),
    }


def _btc_to_satoshis(btc_amount: float) -> int:
    return int(round(btc_amount * SATOSHIS_PER_BTC))


# ---------------------------------------------------------------------------
# 1. Taxes — Quarter-Dependent Revenue Collection
# ---------------------------------------------------------------------------

def record_tax_payment(user_id: str, amount_btc: float, currency: str,
                       description: str = "Tax payment") -> dict:
    """Record a payment with quarter-dependent tax splitting.

    - Capital: keeps 100% locally (it is the federal treasury).
    - Quarter: keeps (1 - FEDERAL_TAX_RATE) locally, earmarks the rest
      as a federal transfer to the capital.

    Returns dict with local and federal portions.
    """
    ctx = get_quarter_context()
    sat_amount = _btc_to_satoshis(amount_btc)

    now_str = _now_iso()

    if ctx["is_capital"]:
        # Capital keeps everything
        local_amount = sat_amount
        federal_amount = 0
        ic.print(f"Capital: recorded {sat_amount} sat from {user_id} (100% local)")
    else:
        # Quarter splits between local and federal
        federal_amount = int(sat_amount * FEDERAL_TAX_RATE)
        local_amount = sat_amount - federal_amount
        ic.print(
            f"Quarter {ctx['canister_id']}: recorded {sat_amount} sat from {user_id} "
            f"(local={local_amount}, federal={federal_amount})"
        )

    # Persist local revenue as a LedgerEntry (debit Cash / credit Tax Revenue).
    try:
        LedgerEntry(
            entry_type=EntryType.CREDIT,
            category=Category.REVENUE,
            amount=local_amount,
            currency=currency,
            description=f"{description} — local share ({ctx['canister_id']})",
            user_id=user_id,
            timestamp=now_str,
        )
    except Exception as _e:
        ic.print(f"record_tax_payment: LedgerEntry failed: {_e}")

    # Record federal portion as a Transfer earmarked for the capital.
    if federal_amount > 0:
        try:
            Transfer(
                amount=federal_amount,
                currency=currency,
                sender_canister=ctx["canister_id"],
                recipient_canister="capital",  # resolved at settlement time
                description=f"{description} — federal share (10%) from {ctx['canister_id']}",
                user_id=user_id,
                timestamp=now_str,
                status="pending",
            )
        except Exception as _e:
            ic.print(f"record_tax_payment: Transfer (federal) failed: {_e}")

    return {
        "recorded": True,
        "total_satoshis": sat_amount,
        "local_satoshis": local_amount,
        "federal_satoshis": federal_amount,
        "is_capital": ctx["is_capital"],
        "quarter": ctx["canister_id"],
    }


# ---------------------------------------------------------------------------
# 2. Budget Allocation — Capital Redistributes to Quarters
# ---------------------------------------------------------------------------

def allocate_federal_budget(total_federal_revenue_sat: int) -> dict:
    """Capital distributes collected federal taxes back to quarters.

    Allocation is proportional to quarter population.  Only meaningful
    when called on the capital canister.

    Args:
        total_federal_revenue_sat: total federal revenue to distribute.

    Returns dict with per-quarter allocations or a skip reason.
    """
    ctx = get_quarter_context()
    if not ctx["is_capital"]:
        return {"allocated": False, "reason": "not capital"}

    quarters = list(Quarter.instances())
    if not quarters:
        return {"allocated": False, "reason": "no quarters registered"}

    total_pop = sum(getattr(q, "population", 1) or 1 for q in quarters)
    allocations = []

    now_str = _now_iso()
    for q in quarters:
        pop = getattr(q, "population", 1) or 1
        share = pop / total_pop
        amount = int(total_federal_revenue_sat * share)
        canister_id = q.canister_id or ""
        allocations.append({
            "quarter": q.name or canister_id,
            "canister_id": canister_id,
            "population": pop,
            "share": round(share, 4),
            "amount_satoshis": amount,
        })
        ic.print(
            f"  → {q.name}: {amount} sat ({share:.1%} of {total_federal_revenue_sat})"
        )

        # Record an inter-quarter allocation Transfer even before the actual
        # ICP inter-canister call is made (the call itself is a TODO stub).
        if canister_id:
            try:
                Transfer(
                    amount=amount,
                    currency="ckBTC_sat",
                    sender_canister=ctx["canister_id"],
                    recipient_canister=canister_id,
                    description=(
                        f"Federal budget allocation to {q.name or canister_id} "
                        f"({share:.1%} of {total_federal_revenue_sat} sat)"
                    ),
                    timestamp=now_str,
                    status="pending",
                    # TODO: cross-quarter inter-canister call to canister_id
                )
            except Exception as _e:
                ic.print(f"allocate_federal_budget: Transfer record failed for {canister_id}: {_e}")

    ic.print(f"Federal budget allocated to {len(quarters)} quarters")
    return {"allocated": True, "distributions": allocations}


# ---------------------------------------------------------------------------
# 3. Tax Summary Query
# ---------------------------------------------------------------------------

def get_tax_summary() -> dict:
    """Return total taxes collected, routed to projects, and social security."""
    try:
        total_collected = sum(
            (e.amount or 0)
            for e in LedgerEntry.instances()
            if getattr(e, "category", None) == Category.REVENUE
        )
    except Exception:
        total_collected = 0  # TODO: sum from LedgerEntry REVENUE records

    try:
        quarters_allocated = []
        project_funding = 0
        for t in Transfer.instances():
            rc = getattr(t, "recipient_canister", "") or ""
            amt = t.amount or 0
            if rc and rc != "capital":
                project_funding += amt
                if rc not in quarters_allocated:
                    quarters_allocated.append(rc)
    except Exception:
        project_funding = 0  # TODO: sum from Transfer records
        quarters_allocated = []

    return {
        "total_collected_ago": total_collected,  # TODO: sum from Transfer records
        "project_funding_ago": project_funding,
        "social_security_ago": 0,  # TODO: derive from welfare allocations
        "quarters_allocated": quarters_allocated,
    }
