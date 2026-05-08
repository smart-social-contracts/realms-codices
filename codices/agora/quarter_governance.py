"""
Quarter Governance Codex — Agora Realm

Quarter-dependent logic that branches on canister identity. The same codex
runs on every quarter, but behavior differs based on:

  - ``ic.id()``                    — which canister am I?
  - ``Realm.is_capital``           — am I the capital?
  - ``QuarterConfig``              — local parameters per quarter

Three areas of quarter-specific behavior:

  1. **Taxes** — quarters collect local revenue and forward a federal share
     to the capital.  The capital keeps all revenue locally.
  2. **Budget allocation** — the capital redistributes federal tax revenue
     to quarters proportionally by population.
  3. **Voting scope** — "local" proposals are voted on only by quarter
     residents; "federal" proposals can only be submitted on the capital
     and are voted on by all federation members.
"""

from _cdk import ic
from ggg import (
    Realm, Quarter, QuarterConfig, User, Member,
    Proposal, Vote, Notification,
    LedgerEntry, Fund, FiscalPeriod, Budget,
    EntryType, Category,
)
from ic_basilisk_toolkit.date_utils import ic_time_to_epoch, epoch_to_datetime_str
import json
import os


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEDERAL_TAX_RATE = 0.10          # 10% of quarter revenue goes to capital
SATOSHIS_PER_BTC = 100_000_000

DEFAULT_VOTING_WINDOW_DAYS = 7
DEFAULT_QUORUM_PERCENT = 20
DEFAULT_APPROVAL_THRESHOLD = 0.5
DEFAULT_WELFARE_PERCENT = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso():
    """Current time as ISO 8601 string (from ic.time())."""
    return epoch_to_datetime_str(ic_time_to_epoch(ic.time())).replace(" ", "T")


def _load_manifest() -> dict:
    """Load manifest.json from the codex directory."""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path) as f:
        return json.load(f)


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


def _is_active_member(user_id: str) -> bool:
    """Check if a user is an active (verified) member."""
    for member in Member.instances():
        if (member.user and member.user.id == user_id
                and member.identity_verification == "verified"):
            return True
    return False


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

    for q in quarters:
        pop = getattr(q, "population", 1) or 1
        share = pop / total_pop
        amount = int(total_federal_revenue_sat * share)
        allocations.append({
            "quarter": q.name or q.canister_id,
            "canister_id": q.canister_id or "",
            "population": pop,
            "share": round(share, 4),
            "amount_satoshis": amount,
        })
        ic.print(
            f"  → {q.name}: {amount} sat ({share:.1%} of {total_federal_revenue_sat})"
        )

    ic.print(f"Federal budget allocated to {len(quarters)} quarters")
    return {"allocated": True, "distributions": allocations}


# ---------------------------------------------------------------------------
# 3. Voting — Scope-Dependent Proposal Submission and Voting
# ---------------------------------------------------------------------------

def submit_proposal(user_id: str, title: str, description: str,
                    proposal_type: str, scope: str = "local",
                    details: dict = None) -> dict:
    """Submit a governance proposal with scope awareness.

    Scopes:
      - "local"   — voted on only by this quarter's residents.
      - "federal" — can only be submitted on the capital; voted on by all.

    Args:
        user_id: proposer's principal.
        title: short title.
        description: full description.
        proposal_type: one of the manifest-defined types.
        scope: "local" or "federal".
        details: type-specific data dict.

    Returns result dict.
    """
    ctx = get_quarter_context()

    if not _is_active_member(user_id):
        return {"submitted": False, "reason": "Only active members can submit proposals."}

    if scope not in ("local", "federal"):
        return {"submitted": False, "reason": f"Invalid scope: {scope}"}

    # Federal proposals can only be submitted on the capital
    if scope == "federal" and not ctx["is_capital"]:
        return {
            "submitted": False,
            "reason": "Federal proposals must be submitted on the capital.",
        }

    manifest = _load_manifest()
    gov = manifest.get("governance", {})
    allowed_types = gov.get("proposal_types", [])
    if proposal_type not in allowed_types:
        return {"submitted": False, "reason": f"Invalid proposal type: {proposal_type}"}

    voting_days = ctx["voting_window_days"]
    now_epoch = ic_time_to_epoch(ic.time())
    deadline = epoch_to_datetime_str(now_epoch + voting_days * 86400).replace(" ", "T")

    metadata = json.dumps({
        "type": proposal_type,
        "scope": scope,
        "quarter": ctx["canister_id"],
        "details": details or {},
        "proposer": user_id,
        "submitted_at": epoch_to_datetime_str(now_epoch).replace(" ", "T"),
    })

    user = User[user_id]
    proposal = Proposal(
        title=title,
        description=description,
        status="voting",
        deadline=deadline,
        proposer=user,
        metadata=metadata,
    )

    ic.print(
        f"Proposal #{proposal.id} [{scope}] submitted by {user_id}: "
        f"[{proposal_type}] {title}"
    )

    return {
        "submitted": True,
        "proposal_id": proposal.id,
        "title": title,
        "type": proposal_type,
        "scope": scope,
        "quarter": ctx["canister_id"],
        "deadline": deadline,
    }


def cast_vote(user_id: str, proposal_id: str, vote_choice: str) -> dict:
    """Cast a vote on a proposal with scope enforcement.

    - Local proposals: only residents of this quarter can vote.
    - Federal proposals: any active member can vote.
    """
    ctx = get_quarter_context()

    if not _is_active_member(user_id):
        return {"voted": False, "reason": "Only active members can vote."}

    if vote_choice not in ("yes", "no"):
        return {"voted": False, "reason": "Vote must be 'yes' or 'no'."}

    proposal = Proposal[proposal_id]
    if not proposal:
        # Also try load by id
        proposal = Proposal.load(proposal_id)
    if not proposal:
        return {"voted": False, "reason": "Proposal not found."}

    if proposal.status != "voting":
        return {"voted": False, "reason": f"Proposal not open (status: {proposal.status})."}

    # Parse scope from metadata
    try:
        meta = json.loads(proposal.metadata) if proposal.metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    scope = meta.get("scope", "local")

    # Enforce local scope: only home-quarter residents can vote
    if scope == "local":
        user = User[user_id]
        if not user:
            user = User.load(user_id)
        home_quarter = getattr(user, "home_quarter", "") if user else ""
        if home_quarter != ctx["canister_id"]:
            return {
                "voted": False,
                "reason": "Only quarter residents can vote on local proposals.",
            }

    # Check for duplicate votes
    for v in Vote.instances():
        if (v.proposal and v.proposal.id == proposal_id
                and v.user and v.user.id == user_id):
            return {"voted": False, "reason": "You have already voted on this proposal."}

    user = User[user_id]
    vote = Vote(
        proposal=proposal,
        user=user,
        vote=vote_choice,
        metadata=json.dumps({"voted_at": _now_iso()}),
    )

    ic.print(f"Vote cast on proposal #{proposal_id} by {user_id}: {vote_choice}")

    return {
        "voted": True,
        "vote_id": vote.id,
        "proposal_id": proposal_id,
        "choice": vote_choice,
        "scope": scope,
    }
