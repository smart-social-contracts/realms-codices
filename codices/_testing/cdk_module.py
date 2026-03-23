"""
Mock ``_cdk`` module.

Provides a minimal ``ic`` object that codex files can use for:
    ic.print(...)     → forwards to Python print()
    ic.caller()       → returns a test principal string
    ic.time()         → returns current time in nanoseconds
    ic.id()           → returns a mock canister principal
"""

import time as _time


class _MockPrincipal:
    """Minimal Principal stand-in."""

    def __init__(self, text):
        self._text = text

    def to_str(self):
        return self._text

    def __str__(self):
        return self._text

    def __repr__(self):
        return f"Principal({self._text!r})"


class _MockIC:
    """Mock of the ``ic`` canister SDK object."""

    def print(self, *args, **kwargs):
        print(*args, **kwargs)

    def caller(self):
        return _MockPrincipal("test-caller-principal")

    def time(self):
        """Return current time in nanoseconds (matches IC convention)."""
        return int(_time.time() * 1_000_000_000)

    def id(self):
        """Return mock canister principal."""
        return _MockPrincipal("test-canister-principal")

    def msg_cycles_available(self):
        return 1_000_000_000_000

    def msg_cycles_accept(self, amount):
        return amount


ic = _MockIC()


class Async:
    """Stub for the async/yield inter-canister call pattern.

    In the real canister, ``yield Async(...)`` suspends execution.
    Here it just raises NotImplementedError so codex error-handling
    paths can be exercised.
    """

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def __iter__(self):
        raise NotImplementedError(
            "Async inter-canister calls are not supported in local testing. "
            "Use canister integration tests for async call flows."
        )
