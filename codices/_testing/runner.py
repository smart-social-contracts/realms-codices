"""
Test runner for codex test files.

Discovers ``test_*.py`` files, executes each in an isolated entity
registry, and reports results.

Usage::

    python -m codices._testing.runner codices/agora
    python -m codices._testing.runner codices/agora/tests/test_financial_setup.py
"""

import glob
import importlib
import os
import sys
import time
import traceback

from . import setup_test_env, reset_registry


def _discover_tests(path):
    """Return sorted list of test file paths."""
    if os.path.isfile(path):
        return [path]
    patterns = [
        os.path.join(path, "tests", "test_*.py"),
        os.path.join(path, "test_*.py"),
    ]
    found = []
    for pat in patterns:
        found.extend(glob.glob(pat))
    return sorted(set(found))


def _run_single_test(test_file, codex_dir, verbose=False):
    """Run a single test file. Returns (name, status, duration, error)."""
    name = os.path.basename(test_file)
    reset_registry()

    # Ensure codex modules are importable (e.g. "import financial_setup")
    codex_parent = os.path.dirname(test_file)
    # If tests/ subdir, also add parent so "import financial_setup" works
    codex_root = os.path.dirname(codex_parent) if os.path.basename(codex_parent) == "tests" else codex_parent
    paths_to_add = []
    if codex_root not in sys.path:
        paths_to_add.append(codex_root)
    if codex_dir not in sys.path and codex_dir != codex_root:
        paths_to_add.append(codex_dir)

    for p in paths_to_add:
        sys.path.insert(0, p)

    # Clear any previously cached codex module imports so they re-import
    # against the fresh registry
    modules_to_remove = []
    for mod_name, mod in sys.modules.items():
        mod_file = getattr(mod, "__file__", None)
        if mod_file and codex_root in mod_file and mod_name != "__main__":
            modules_to_remove.append(mod_name)
    for mod_name in modules_to_remove:
        del sys.modules[mod_name]

    # Provide ic and logger in the exec namespace (like the canister does)
    from . import cdk_module
    import logging
    logger = logging.getLogger(f"codex.test.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    ns = {
        "__builtins__": __builtins__,
        "__name__": "__main__",
        "__file__": test_file,
        "ic": cdk_module.ic,
        "logger": logger,
    }

    t0 = time.time()
    try:
        with open(test_file, "r") as f:
            code = f.read()
        compiled = compile(code, test_file, "exec")
        exec(compiled, ns)
        duration = time.time() - t0
        return (name, "PASSED", duration, None)
    except Exception as e:
        duration = time.time() - t0
        tb = traceback.format_exc()
        return (name, "FAILED", duration, tb)
    finally:
        for p in paths_to_add:
            if p in sys.path:
                sys.path.remove(p)


def run_tests(path, verbose=False):
    """Discover and run codex tests. Returns (passed, failed, results)."""
    setup_test_env()

    test_files = _discover_tests(path)
    if not test_files:
        print(f"No test files found in {path}")
        return 0, 0, []

    codex_dir = path if os.path.isdir(path) else os.path.dirname(path)

    results = []
    passed = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"  Codex Test Runner")
    print(f"  {len(test_files)} test file(s) in {path}")
    print(f"{'='*60}\n")

    for test_file in test_files:
        name, status, duration, error = _run_single_test(test_file, codex_dir, verbose)
        results.append((name, status, duration, error))

        icon = "\u2705" if status == "PASSED" else "\u274c"
        print(f"  {icon} {name} ({duration:.3f}s)")
        if error and (verbose or status == "FAILED"):
            for line in error.strip().split("\n"):
                print(f"     {line}")

        if status == "PASSED":
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return passed, failed, results


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Codex Test Runner")
    parser.add_argument("path", help="Path to codex directory or test file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    passed, failed, _ = run_tests(args.path, verbose=args.verbose)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
