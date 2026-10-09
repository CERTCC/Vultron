"""Item boundaries of :func:`vultron.metadata.specs.yaml_items.iter_blocks`.

Three scripts edit ``specs/*.yaml`` as text through this one slicer (#4016), so
where an item ends decides which lines each of them may touch. An item that
runs one line long swallows its neighbour's ``id``; one that stops early leaves
its own fields outside it.
"""

from __future__ import annotations

import pytest

from vultron.metadata.specs.yaml_items import (
    SpecItem,
    add_lint_suppression,
    append_list_field,
    iter_blocks,
    remove_lint_suppression,
)


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


def _item(text: str) -> SpecItem:
    (only,) = _items(text)
    return only


_SUPPRESSED = """\
- id: TST-01-001
  priority: MUST
  lint_suppress:
  # why the first one is here
  - phantom_path_ref
  - must_without_verification
  statement: x
"""


def test_remove_lint_suppression_keeps_other_codes_and_their_comments():
    lines, removed = remove_lint_suppression(
        _item(_SUPPRESSED), "must_without_verification"
    )
    assert removed
    assert "".join(lines) == _SUPPRESSED.replace(
        "  - must_without_verification\n", ""
    )


def test_remove_lint_suppression_drops_an_emptied_flow_list():
    text = (
        "- id: TST-01-001\n  lint_suppress: [x_code]  # note\n  statement: x\n"
    )
    lines, removed = remove_lint_suppression(_item(text), "x_code")
    assert removed
    assert "".join(lines) == "- id: TST-01-001\n  statement: x\n"


def test_remove_lint_suppression_reports_an_absent_code():
    lines, removed = remove_lint_suppression(_item(_SUPPRESSED), "other")
    assert not removed
    assert "".join(lines) == _SUPPRESSED


_PLAIN = "- id: TST-01-001\n  statement: x\n  steps:\n  - order: 1\n\n"


def test_append_list_field_goes_after_the_last_field():
    """Trailing blank lines stay after the new list, with the next item."""
    lines = append_list_field(_item(_PLAIN), "stories", ["s1", "s2"])
    assert "".join(lines) == (
        "- id: TST-01-001\n  statement: x\n  steps:\n  - order: 1\n"
        "  stories:\n  - s1\n  - s2\n\n"
    )


def test_append_list_field_refuses_an_existing_field():
    with pytest.raises(ValueError, match="already has a steps: field"):
        append_list_field(_item(_PLAIN), "steps", ["x"])


def test_append_list_field_refuses_no_values():
    with pytest.raises(ValueError, match="no values"):
        append_list_field(_item(_PLAIN), "stories", [])


def test_append_list_field_ignores_a_nested_key_of_the_same_name():
    text = "- id: TST-01-001\n  steps:\n  - stories: nested\n"
    lines = append_list_field(_item(text), "stories", ["s1"])
    assert "".join(lines) == text + "  stories:\n  - s1\n"


def test_add_lint_suppression_creates_a_block_when_absent():
    lines, added = add_lint_suppression(_item(_PLAIN), "x_code")
    assert added
    assert "".join(lines) == (
        "- id: TST-01-001\n  statement: x\n  steps:\n  - order: 1\n"
        "  lint_suppress:\n  - x_code\n\n"
    )


def test_add_lint_suppression_appends_to_a_block_list():
    lines, added = add_lint_suppression(_item(_SUPPRESSED), "x_code")
    assert added
    assert "".join(lines) == _SUPPRESSED.replace(
        "  - must_without_verification\n",
        "  - must_without_verification\n  - x_code\n",
    )


def test_add_lint_suppression_appends_to_a_flow_list_keeping_its_comment():
    text = (
        "- id: TST-01-001\n  lint_suppress: [a_code]  # note\n  statement: x\n"
    )
    lines, added = add_lint_suppression(_item(text), "x_code")
    assert added
    assert "".join(lines) == text.replace("[a_code]", "[a_code, x_code]")


@pytest.mark.parametrize(
    "text",
    [
        _SUPPRESSED,
        "- id: TST-01-001\n  lint_suppress: ['phantom_path_ref']\n",
    ],
)
def test_add_lint_suppression_reports_a_present_code(text):
    lines, added = add_lint_suppression(_item(text), "phantom_path_ref")
    assert not added
    assert "".join(lines) == text
