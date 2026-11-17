"""The effect hooks of the layered codex's chapters (``legislation/``), run with the realm's legislation library and no
realm: every chapter of the layers loads from its file, and a hook runs on the event the realm would build.

REALM_BACKEND points at realms-gos/src/realm_backend (default: the checkout this repo is a submodule of).

What the realm hands ``on_codex_install`` as ``event.result`` is what the operation returned (core.legislation._hooks
runs the hooks after it): a call that starts the install job returns ``{"job": ...}``, and only the install that
switches the codex, the scheduled vote's at its ``effective_at``, also returns its ``codex``.
"""

import os
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = pathlib.Path(os.environ.get("REALM_BACKEND", ROOT.parent / "src" / "realm_backend"))
sys.path.insert(0, str(BACKEND))

from realms.legislation import Codex, Event  # noqa: E402

TREE = ROOT / "legislation"
SPAIN, VALENCIA = "eu/es", "eu/es/vc/46250-valencia"
LAYERS = ("eu", "eu/es", "eu/es/vc", VALENCIA)
INSTALL = {"url": "https://example.org/change.json", "checksum": "sha256:" + "0" * 64}
CODEX = "sha256:" + "a" * 64
JOB_STARTED = {"job": "J-1"}  # a controller's call, or a vote with no effective_at to wait for
CODEX_SWITCHED = {"codex": CODEX, "job": "J-1"}  # the scheduled vote's install, at its effective_at


def codex_of(realm, members=()):
    """The codex of ``realm``: every chapter of the layers down to it, top to bottom, as the realm loads them."""
    ggg = types.ModuleType("ggg")
    for name in ("Attribute", "External", "Human", "TaxPolicy"):
        setattr(ggg, name, type(name, (), {}))
    ggg.Member = types.SimpleNamespace(each=lambda: [types.SimpleNamespace(id=m) for m in members])
    codex = Codex(LAYERS[: LAYERS.index(realm) + 1], realm=realm, modules={"ggg": ggg})
    for source in codex.layers:
        for chapter in sorted((TREE / source).glob("*.py")):
            codex.load(source, chapter.stem, chapter.read_text())
    return codex


def effects_of(codex, result):
    """The effects the ``on_codex_install`` hooks of ``codex`` queue for an install whose operation returned ``result``."""
    context = codex.context()
    codex.instance("local_regime", context).on_codex_install(Event("ctl", INSTALL, result, 1_790_000_000))
    return context.effects.queued


@pytest.mark.parametrize("realm", [SPAIN, VALENCIA])
@pytest.mark.parametrize("result", [JOB_STARTED, {}])
def test_an_install_that_names_no_codex_yet_tells_no_one(realm, result):
    assert effects_of(codex_of(realm, members=["alice"]), result) == []


def test_spain_tells_the_state_and_the_region_the_codex_an_install_switched_to():
    told = effects_of(codex_of(SPAIN), CODEX_SWITCHED)
    assert [(op, args["recipient"]["id"], args["topic"], args["body"]) for op, args in told] == [
        ("notification_send", "AGE", "ordinance", CODEX), ("notification_send", "GVA", "ordinance", CODEX)]


def test_valencia_tells_its_members_the_codex_after_the_state_and_the_region():
    told = effects_of(codex_of(VALENCIA, members=["alice", "bob"]), CODEX_SWITCHED)
    assert [args["recipient"] for _, args in told] == [
        {"kind": "external", "id": "AGE"}, {"kind": "external", "id": "GVA"},
        {"kind": "user", "id": "alice"}, {"kind": "user", "id": "bob"}]
    assert {args["body"] for _, args in told} == {CODEX}
    assert [t["language"] for t in told[2][1]["translations"]] == ["es", "ca-valencia"]  # the languages CV set
