"""Tests for pass 2 of ``scripts/relink_requirement_anchors.py``.

A spec renders only on its own kind's docs page (SR-09-001, SR-09-002), so a
``kind:`` relabel moves its anchor and every prose link to the old page
dangles. Pass 2 rewrites the page slug in any kind-page link to the page the
anchor renders on; for a group or file whose items straddle pages, the page
holding the most of them, with ``SpecKind`` order as the tie-break.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from vultron.metadata.specs.registry import load_registry

_SCRIPTS = Path(__file__).parents[3] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, _SCRIPTS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


relink = _load("relink_requirement_anchors")


def _item(spec_id: str, kind: str) -> dict:
    return {
        "id": spec_id,
        "priority": "MUST",
        "kind": kind,
        "statement": f"{spec_id} MUST do the thing",
    }


_SPECS = {
    "id": "TST",
    "title": "Test",
    "description": "Test spec file",
    "scope": ["production"],
    "groups": [
        {
            # two project items, one protocol: the group anchor renders on
            # both pages (SR-09-002), so a link to either is left alone;
            # TST-01-003 alone stays on protocol.md
            "id": "TST-01",
            "title": "Straddling group",
            "specs": [
                _item("TST-01-001", "project"),
                _item("TST-01-002", "project"),
                _item("TST-01-003", "protocol"),
            ],
        },
        {
            "id": "TST-02",
            "title": "Protocol group",
            "specs": [_item("TST-02-001", "protocol")],
        },
        {
            # an even split: SpecKind order breaks the tie toward project
            "id": "TST-03",
            "title": "Tied group",
            "specs": [
                _item("TST-03-001", "process"),
                _item("TST-03-002", "project"),
            ],
        },
    ],
}

_DOC = """\
Moved requirement: [TST-01-001](../specs/protocol.md#tst-01-001).
Group with an item on this page stays: [TST-01](../specs/protocol.md#tst-01).
File with an item on this page stays: [TST](../../reference/specs/protocol.md#tst).
Still protocol: [TST-01-003](../specs/protocol.md#tst-01-003).
Still protocol group: [TST-02](../specs/protocol.md#tst-02).
Tied group from a page with none of its items: [TST-03](../specs/architecture.md#tst-03).
Tied group from a page holding some of its items: [TST-03](../specs/process.md#tst-03).
Not a spec anchor: [Overview](../specs/protocol.md#overview).
Pass 1 then pass 2: [TST-01-002](../specs/protocol.md#tst-01).
"""

_EXPECTED = """\
Moved requirement: [TST-01-001](../specs/project.md#tst-01-001).
Group with an item on this page stays: [TST-01](../specs/protocol.md#tst-01).
File with an item on this page stays: [TST](../../reference/specs/protocol.md#tst).
Still protocol: [TST-01-003](../specs/protocol.md#tst-01-003).
Still protocol group: [TST-02](../specs/protocol.md#tst-02).
Tied group from a page with none of its items: [TST-03](../specs/project.md#tst-03).
Tied group from a page holding some of its items: [TST-03](../specs/process.md#tst-03).
Not a spec anchor: [Overview](../specs/protocol.md#overview).
Pass 1 then pass 2: [TST-01-002](../specs/project.md#tst-01-002).
"""


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "tst.yaml").write_text(yaml.dump(_SPECS), encoding="utf-8")
    docs_dir = tmp_path / "docs" / "topics"
    docs_dir.mkdir(parents=True)
    (docs_dir / "page.md").write_text(_DOC, encoding="utf-8")
    monkeypatch.setattr(relink, "ROOT", tmp_path)
    monkeypatch.setattr(relink, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(
        relink, "load_registry", lambda: load_registry(specs_dir)
    )
    return tmp_path


def _page(tree: Path) -> str:
    return (tree / "docs" / "topics" / "page.md").read_text(encoding="utf-8")


def test_reroutes_every_link_to_the_page_its_anchor_renders_on(tree, capsys):
    assert relink.main([]) == 0
    assert _page(tree) == _EXPECTED
    out = capsys.readouterr().out
    assert "unknown anchor left as-is: #overview (1)" in out
    # 1 pass-1 repoint (moved to another page), 2 pass-2 reroutes
    assert (
        "1 requirement link(s) repointed at their own anchor, 1 of them moved "
        "to a different kind page; 2 link(s) moved to the page their anchor "
        "renders on; 1 file(s) changed"
    ) in out


def test_check_reports_without_writing_then_passes_once_applied(tree):
    assert relink.main(["--check"]) == 1
    assert _page(tree) == _DOC
    assert relink.main([]) == 0
    assert relink.main(["--check"]) == 0
    assert _page(tree) == _EXPECTED


def test_rerouter_picks_the_majority_page_and_breaks_ties_in_kind_order(
    tree,
):
    rerouter = relink._Rerouter(relink.load_registry())
    assert rerouter._page_for("tst-01") == "project"
    assert rerouter._page_for("tst-02") == "protocol"
    assert rerouter._page_for("tst-03") == "project"
    assert rerouter._page_for("tst") == "project"
    assert rerouter._page_for("nope") is None
