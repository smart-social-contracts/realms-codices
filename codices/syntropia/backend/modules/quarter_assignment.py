"""
Quarter Assignment Codex
Defines how users are assigned to quarters when joining a federated realm.

The realm's federation codex must expose an ``assign_quarter`` function with
the signature::

    assign_quarter(principal: str, quarters: list[Quarter], preferred: str) -> str

where *quarters* is the list of active Quarter entities and *preferred* is the
canister_id the user requested (empty string if no preference).  The function
must return a canister_id string or raise ``ValueError`` with a human-readable
rejection reason.

Three built-in strategies are provided and can be composed:

1. **random** — deterministic hash of principal → uniform load balancing.
2. **user_choice** — honour the user's preference if the quarter has capacity.
3. **least_populated** — always pick the quarter with the fewest residents.

The active strategy is selected via ``ASSIGNMENT_STRATEGY``.  A custom codex
can override ``assign_quarter`` entirely for arbitrary eligibility rules
(geography, invitation codes, profile attributes, etc.).
"""

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Maximum residents per quarter.  Set to 0 for unlimited.
MAX_POPULATION = 0

# Strategy: "random", "user_choice", "least_populated"
# Product default (issue #156): least_populated among joinable quarters.
ASSIGNMENT_STRATEGY = "least_populated"


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

def _strategy_random(principal, quarters, preferred):
    """Deterministic random: hash of principal modulo quarter count."""
    idx = hash(principal) % len(quarters)
    return quarters[idx].canister_id


def _strategy_user_choice(principal, quarters, preferred):
    """Honour the user's preference, with capacity check."""
    if preferred:
        for q in quarters:
            if q.canister_id == preferred or q.name == preferred:
                _check_capacity(q)
                return q.canister_id
        raise ValueError(
            f"Requested quarter '{preferred}' not found among active quarters."
        )
    # No preference → fall back to least populated
    return _strategy_least_populated(principal, quarters, preferred)


def _strategy_least_populated(principal, quarters, preferred):
    """Assign to the quarter with the fewest residents."""
    target = min(quarters, key=lambda q: q.population)
    _check_capacity(target)
    return target.canister_id


def _check_capacity(quarter):
    """Raise if the quarter has reached MAX_POPULATION (when set)."""
    if MAX_POPULATION > 0 and quarter.population >= MAX_POPULATION:
        raise ValueError(
            f"Quarter '{quarter.name}' is at capacity "
            f"({quarter.population}/{MAX_POPULATION})."
        )


# ---------------------------------------------------------------------------
# Public entry point (called by _assign_quarter in main.py)
# ---------------------------------------------------------------------------

STRATEGIES = {
    "random": _strategy_random,
    "user_choice": _strategy_user_choice,
    "least_populated": _strategy_least_populated,
}


def assign_quarter(principal: str, quarters: list, preferred: str) -> str:
    """Assign a quarter to the joining user.

    Args:
        principal:  The caller's IC principal.
        quarters:   List of active Quarter entities.
        preferred:  Canister ID or name the user requested (empty = no pref).

    Returns:
        The canister_id of the assigned quarter.

    Raises:
        ValueError: If the user cannot be placed (quarter full, not found, …).
    """
    strategy_fn = STRATEGIES.get(ASSIGNMENT_STRATEGY)
    if not strategy_fn:
        raise ValueError(f"Unknown assignment strategy: {ASSIGNMENT_STRATEGY}")
    return strategy_fn(principal, quarters, preferred)


# ---------------------------------------------------------------------------
# Auto-scaling / sharding hook (issue #156)
# ---------------------------------------------------------------------------

# Per-quarter capacity N. 0 => use the environment default (2000 prod,
# 10 for test/staging/demo). Override here to tune sharding for this realm.
SCALE_N = 0

# Spawn a new quarter once the fullest quarter reaches this fraction of N,
# leaving headroom so the triggering user still lands on an existing quarter.
SCALE_FRACTION = 0.9

_LOW_THRESHOLD_NETWORKS = ("test", "staging", "demo")


def _effective_n(network: str) -> int:
    if SCALE_N and SCALE_N > 0:
        return int(SCALE_N)
    return 10 if (network or "").strip().lower() in _LOW_THRESHOLD_NETWORKS else 2000


def should_deploy_quarter(populations: list, network: str, realm=None) -> bool:
    """Decide whether the federation should spawn a new quarter.

    Called after each new user registration. ``populations`` is the list of
    per-quarter resident counts (including the capital). Returns True when the
    fullest quarter has reached 90% of N — the realm then queues a (non-blocking)
    Casals provisioning job. A custom codex can replace this with any policy
    (cycle budget, time-of-day, manual approval, …).
    """
    pops = [int(p or 0) for p in (populations or [])]
    if not pops:
        return False
    n = _effective_n(network)
    if n <= 0:
        return False  # unlimited / disabled
    threshold = max(1, int((SCALE_FRACTION * n) + 0.999))  # ceil
    return max(pops) >= threshold
