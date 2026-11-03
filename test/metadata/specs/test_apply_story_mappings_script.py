"""Smoke tests for ``scripts/apply_story_mappings.py``.

The script is line-based YAML surgery: it adds a ``stories:`` block and drops
``missing_story_reference`` from ``lint_suppress:``. The shapes below are the
ones the live corpus holds, including a justification comment between
suppression items, which once stranded the items after it (#4513). The edits
go through ``vultron.metadata.specs.yaml_items``, whose own suite covers the
flow-list and quoting shapes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

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


apply_mod = _load("apply_story_mappings")

_FIXTURE = """\
id: TST
groups:
- id: TST-01
  specs:
  - id: TST-01-001
    statement: only the story suppression
    lint_suppress:
    - missing_story_reference
  - id: TST-01-002
    statement: another code survives
    lint_suppress:
    - missing_story_reference
    - phantom_path_ref
  - id: TST-01-003
    statement: a commented code after the story suppression
    lint_suppress:
    - missing_story_reference
    # compound_statement: kept whole on purpose.
    - compound_statement
  - id: TST-01-004
    statement: a comment justifying the story suppression
    lint_suppress:
    - phantom_path_ref
    # No story yet: the need is unwritten.
    - missing_story_reference
  - id: TST-01-005
    statement: never named by the mapping
    lint_suppress:
    - missing_story_reference
  - id: TST-01-006
    statement: a trailing comment after the only suppression
    lint_suppress:
    - missing_story_reference
    # Introduces the next item; it must survive the emptied block.
  - id: TST-01-007
    statement: an inline justification on the suppression
    lint_suppress:
    - missing_story_reference  # no story yet
    - phantom_path_ref
"""

_STORIES = ["story_2026_013"]


def _apply(tmp_path: Path) -> tuple[str, dict[str, dict]]:
    path = tmp_path / "tst.yaml"
    path.write_text(_FIXTURE, encoding="utf-8")
    mappings = [
        {"spec_id": f"TST-01-00{n}", "story_ids": _STORIES}
        for n in (1, 2, 3, 4, 6, 7)
    ]
    applied, skipped = apply_mod.apply_file_mappings(path, mappings)
    assert (applied, skipped) == (6, 0)
    text = path.read_text(encoding="utf-8")
    items = {
        item["id"]: item for item in yaml.safe_load(text)["groups"][0]["specs"]
    }
    return text, items


def test_suppression_only_block_becomes_stories(tmp_path: Path) -> None:
    _, items = _apply(tmp_path)
    assert items["TST-01-001"]["stories"] == _STORIES
    assert "lint_suppress" not in items["TST-01-001"]


def test_other_codes_survive(tmp_path: Path) -> None:
    _, items = _apply(tmp_path)
    assert items["TST-01-002"]["lint_suppress"] == ["phantom_path_ref"]


def test_a_comment_between_items_keeps_the_block_whole(
    tmp_path: Path,
) -> None:
    text, items = _apply(tmp_path)
    assert items["TST-01-003"]["stories"] == _STORIES
    assert items["TST-01-003"]["lint_suppress"] == ["compound_statement"]
    assert "# compound_statement: kept whole on purpose." in text


def test_the_removed_items_justification_goes_with_it(
    tmp_path: Path,
) -> None:
    text, items = _apply(tmp_path)
    assert items["TST-01-004"]["lint_suppress"] == ["phantom_path_ref"]
    assert "No story yet" not in text


def test_an_unmapped_item_is_untouched(tmp_path: Path) -> None:
    _, items = _apply(tmp_path)
    assert items["TST-01-005"]["lint_suppress"] == ["missing_story_reference"]
    assert "stories" not in items["TST-01-005"]


def test_a_trailing_comment_survives_an_emptied_block(tmp_path: Path) -> None:
    text, items = _apply(tmp_path)
    assert items["TST-01-006"]["stories"] == _STORIES
    assert "lint_suppress" not in items["TST-01-006"]
    assert "# Introduces the next item; it must survive" in text


def test_an_inline_comment_leaves_with_its_entry(tmp_path: Path) -> None:
    text, items = _apply(tmp_path)
    assert items["TST-01-007"]["stories"] == _STORIES
    assert items["TST-01-007"]["lint_suppress"] == ["phantom_path_ref"]
    assert "no story yet" not in text


def test_a_blank_line_inside_the_block_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "tst.yaml"
    original = """\
id: TST
groups:
- id: TST-01
  specs:
  - id: TST-01-001
    statement: a blank line splits the suppression list
    lint_suppress:
    - missing_story_reference

    - compound_statement
"""
    path.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="blank line"):
        apply_mod.apply_file_mappings(
            path, [{"spec_id": "TST-01-001", "story_ids": _STORIES}]
        )
    assert path.read_text(encoding="utf-8") == original
