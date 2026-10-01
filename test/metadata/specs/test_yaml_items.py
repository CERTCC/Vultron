"""Item boundaries of :func:`vultron.metadata.specs.yaml_items.iter_blocks`.

Three scripts edit ``specs/*.yaml`` as text through this one slicer (#4016), so
where an item ends decides which lines each of them may touch. An item that
runs one line long swallows its neighbour's ``id``; one that stops early leaves
its own fields outside it.
"""

from __future__ import annotations

import pytest

from vultron.metadata.specs.yaml_items import SpecItem, iter_blocks


def _items(text: str) -> list[SpecItem]:
    lines = text.splitlines(keepends=True)
    return [b for b in iter_blocks(lines) if isinstance(b, SpecItem)]


def _rebuild(text: str) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(
        b if isinstance(b, str) else "".join(b.lines)
        for b in iter_blocks(lines)
    )


def test_item_stops_at_a_sibling_id():
    text = (
        "  - id: TST-01-001\n"
        "    kind: protocol\n"
        "  - id: TST-01-002\n"
        "    kind: general\n"
    )
    first, second = _items(text)
    assert first.lines == ["  - id: TST-01-001\n", "    kind: protocol\n"]
    assert second.lines == ["  - id: TST-01-002\n", "    kind: general\n"]


def test_item_stops_at_a_shallower_line():
    text = (
        "  specs:\n"
        "  - id: TST-01-001\n"
        "    kind: protocol\n"
        "- id: TST-02\n"
        "  title: Next group\n"
    )
    blocks = list(iter_blocks(text.splitlines(keepends=True)))
    (item,) = [b for b in blocks if isinstance(b, SpecItem)]
    assert item.lines == ["  - id: TST-01-001\n", "    kind: protocol\n"]
    # the shallower lines are yielded as plain lines, not folded into the item
    assert blocks[-2:] == ["- id: TST-02\n", "  title: Next group\n"]


def test_item_keeps_blank_lines_inside_it():
    text = (
        "  - id: TST-01-001\n"
        "    statement: >-\n"
        "      First paragraph.\n"
        "\n"
        "      Second paragraph.\n"
        "    kind: protocol\n"
        "  - id: TST-01-002\n"
    )
    first, _ = _items(text)
    assert first.lines[3] == "\n"
    assert first.lines[-1] == "    kind: protocol\n"


def test_item_at_end_of_file_takes_the_remaining_lines():
    text = "  - id: TST-01-001\n    kind: protocol\n    priority: MUST"
    (item,) = _items(text)
    assert item.lines == [
        "  - id: TST-01-001\n",
        "    kind: protocol\n",
        "    priority: MUST",
    ]
    assert _rebuild(text) == text


def test_item_at_column_zero_reports_its_indent():
    (item,) = _items("- id: TST-01-001\n  kind: protocol\nother: x\n")
    assert item.spec_id == "TST-01-001"
    assert item.indent == ""
    assert item.field_indent == "  "
    assert item.lines == ["- id: TST-01-001\n", "  kind: protocol\n"]


def test_group_ids_are_not_items():
    assert _items("- id: TST-01\n  title: Group\n") == []


_CORPUS_SHAPES = """\
id: TST
groups:
- id: TST-01
  title: Group
  specs:
  - id: TST-01-001
    lint_suppress: [missing_story_reference]
  - id: TST-01-002
    lint_suppress:
    # a justification comment between list entries (CP-01-007)
    - missing_story_reference
    statement: >-
      TST-01-002 MUST do the thing
      across two lines.
- id: TST-02
  specs:
  - id: TST-02-001
    kind: protocol
"""


@pytest.mark.parametrize(
    "text", [_CORPUS_SHAPES, _CORPUS_SHAPES.rstrip("\n"), ""]
)
def test_reemitting_every_block_reproduces_the_file(text):
    assert _rebuild(text) == text


def test_items_in_a_corpus_shaped_file_carry_their_own_fields():
    found = _items(_CORPUS_SHAPES)
    assert [b.spec_id for b in found] == [
        "TST-01-001",
        "TST-01-002",
        "TST-02-001",
    ]
    assert all(b.indent == "  " and b.field_indent == "    " for b in found)
    # the comment and the block scalar both belong to their item
    assert any("CP-01-007" in line for line in found[1].lines)
    assert found[1].lines[-1] == "      across two lines.\n"
