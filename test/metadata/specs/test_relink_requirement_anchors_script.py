"""Tests for the ``scripts/relink_requirement_anchors.py`` CLI.

The rewrite rules live in :mod:`vultron.metadata.docs.requirement_links` and
are tested in ``test/metadata/docs/test_requirement_links.py``. These tests
pin the CLI around them: it writes the rewritten files, reports what it did
and what it did not know, and ``--check`` reports without writing.
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
        "statement": f"{spec_id} statement",
        "rationale": "Because testing.",
    }


# VP is a file the real placement table puts on the vultron-protocol page.
_SPECS = {
    "id": "VP",
    "title": "Test",
    "description": "Test spec file",
    "scope": ["production"],
    "groups": [
        {
            "id": "VP-01",
            "title": "Group",
            "specs": [
                _item("VP-01-001", "protocol"),
                _item("VP-01-002", "project"),
            ],
        },
    ],
}

_DOC = """\
Moved: [VP-01-001](../reference/specs/protocol.md#vp-01-001).
Split: [VP-01-001, VP-01-002](../reference/specs/protocol.md#vp-01).
Unknown: [Overview](../reference/specs/project.md#overview).
"""

_EXPECTED = """\
Moved: [VP-01-001](../reference/vultron-spec/requirements/vultron-protocol.md#vp-01-001).
Split: [VP-01-001](../reference/vultron-spec/requirements/vultron-protocol.md#vp-01-001), [VP-01-002](../reference/specs/project.md#vp-01-002).
Unknown: [Overview](../reference/specs/project.md#overview).
"""


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "vp.yaml").write_text(yaml.dump(_SPECS), encoding="utf-8")
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


def test_rewrites_and_reports(tree, capsys):
    assert relink.main([]) == 0
    assert _page(tree) == _EXPECTED
    out = capsys.readouterr().out
    assert "unknown anchor left as-is: #overview (1)" in out
    assert (
        "2 requirement link(s) repointed at their own anchor; 1 link(s) "
        "moved to the page their anchor renders on; 1 file(s) changed"
    ) in out


def test_check_reports_without_writing_then_passes_once_applied(tree):
    assert relink.main(["--check"]) == 1
    assert _page(tree) == _DOC
    assert relink.main([]) == 0
    assert relink.main(["--check"]) == 0
    assert _page(tree) == _EXPECTED
