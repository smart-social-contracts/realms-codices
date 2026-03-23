"""
Codex Testing Framework
=======================

Provides an in-memory mock of the ``ggg`` entity module so that codex files
and their tests can run locally with standard Python — no canister needed.

Usage::

    from codices._testing import setup_test_env, reset_registry

    setup_test_env()          # inject mock ggg + _cdk into sys.modules
    reset_registry()          # clear all entity data (call between tests)

    # Now codex code works:
    from ggg import User, Proposal, Fund
    u = User(id="alice")
    assert User["alice"] is u
"""

from .entity import _registry


def reset_registry():
    """Clear all entity data. Call between test files for isolation."""
    _registry.reset()


def setup_test_env():
    """Inject mock ``ggg`` and ``_cdk`` modules into ``sys.modules``.

    After calling this, any ``from ggg import ...`` in codex code will
    resolve to the in-memory mock entities.
    """
    import sys
    import builtins
    from . import ggg_module
    from . import cdk_module

    sys.modules["ggg"] = ggg_module
    sys.modules["_cdk"] = cdk_module

    # Inject ic and logger into builtins so they are available globally,
    # matching canister behavior where ic is an implicit global.
    builtins.ic = cdk_module.ic

    import logging
    _logger = logging.getLogger("codex")
    if not _logger.handlers:
        _handler = logging.StreamHandler(sys.stdout)
        _handler.setFormatter(logging.Formatter("%(message)s"))
        _logger.addHandler(_handler)
    _logger.setLevel(logging.DEBUG)
    builtins.logger = _logger

    reset_registry()
