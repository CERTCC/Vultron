"""``scripts/backfill_stories.py`` inserts ``stories:`` and suppressions per item.

Both insertions slice items through the shared ``iter_blocks`` (#4016), so
these pin what each one writes into an item and that every other line of the
file survives unchanged.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).parents[3] / "scripts" / "backfill_stories.py"

_HEAD = "id: TST\ngroups:\n- id: TST-01\n  specs:\n"


@pytest.fixture(scope="module")
def backfill_stories() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backfill_stories", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "tst.yaml"
    path.write_text(_HEAD + body, encoding="utf-8")
    return path


def test_stories_are_appended_to_the_named_item_only(
    tmp_path, backfill_stories
):
    path = _write(
        tmp_path,
        "  - id: TST-01-001\n"
        "    kind: protocol\n"
        "\n"
        "  - id: TST-01-002\n"
        "    kind: protocol\n",
    )
    n = backfill_stories.insert_stories_in_yaml(
        path, {"TST-01-001": ["story_2022_001", "story_2022_002"]}
    )
    assert n == 1
    assert path.read_text(encoding="utf-8") == _HEAD + (
        "  - id: TST-01-001\n"
        "    kind: protocol\n"
        "\n"
        "    stories:\n"
        "    - story_2022_001\n"
        "    - story_2022_002\n"
        "  - id: TST-01-002\n"
        "    kind: protocol\n"
    )


def test_an_item_that_has_stories_is_left_alone(tmp_path, backfill_stories):
    body = "  - id: TST-01-001\n    stories:\n    - story_2022_009\n"
    path = _write(tmp_path, body)
    n = backfill_stories.insert_stories_in_yaml(
        path, {"TST-01-001": ["story_2022_001"]}
    )
    assert n == 0
    assert path.read_text(encoding="utf-8") == _HEAD + body


def test_suppression_extends_an_existing_list_or_adds_one(
    tmp_path, backfill_stories
):
    path = _write(
        tmp_path,
        "  - id: TST-01-001\n"
        "    lint_suppress:\n"
        "    - phantom_path_ref\n"
        "    kind: protocol\n"
        "  - id: TST-01-002\n"
        "    kind: protocol\n"
        "  - id: TST-01-003\n"
        "    lint_suppress:\n"
        "    - missing_story_reference\n",
    )
    n = backfill_stories.insert_suppress_in_yaml(
        path, {"TST-01-001", "TST-01-002", "TST-01-003"}
    )
    assert n == 2
    assert path.read_text(encoding="utf-8") == _HEAD + (
        "  - id: TST-01-001\n"
        "    lint_suppress:\n"
        "    - phantom_path_ref\n"
        "    - missing_story_reference\n"
        "    kind: protocol\n"
        "  - id: TST-01-002\n"
        "    kind: protocol\n"
        "    lint_suppress:\n"
        "    - missing_story_reference\n"
        "  - id: TST-01-003\n"
        "    lint_suppress:\n"
        "    - missing_story_reference\n"
    )


def test_an_item_at_column_zero_is_edited_at_its_own_field_indent(
    tmp_path, backfill_stories
):
    """The shared slicer matches a column-0 item, which the script's old
    private regex skipped; its fields sit two spaces in."""
    path = tmp_path / "tst.yaml"
    path.write_text("- id: TST-01-001\n  kind: protocol\n", encoding="utf-8")
    assert backfill_stories.insert_stories_in_yaml(
        path, {"TST-01-001": ["story_2022_001"]}
    )
    assert path.read_text(encoding="utf-8") == (
        "- id: TST-01-001\n  kind: protocol\n  stories:\n  - story_2022_001\n"
    )
