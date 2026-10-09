"""Item boundaries of :func:`vultron.metadata.specs.yaml_items.iter_blocks`.

Three scripts edit ``specs/*.yaml`` as text through this one slicer (#4016), so
where an item ends decides which lines each of them may touch. An item that
runs one line long swallows its neighbour's ``id``; one that stops early leaves
its own fields outside it.
"""

from __future__ import annotations

import pytest
import yaml

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


def test_append_list_field_keeps_a_block_scalar_ending_in_a_hash_line():
    """A ``#`` line deeper than the fields is scalar text, not a comment.

    UCORG-01-003's ``rationale: >-`` ends with the line ``#3377.``; treating
    it as a trailing comment put the new list inside the scalar and cut it.
    """
    text = (
        "- id: TST-01-001\n"
        "  statement: x\n"
        "  rationale: >-\n"
        "    Kept for history. See\n"
        "    #3377.\n"
        "  # comment introducing the next item\n"
    )
    lines = append_list_field(_item(text), "stories", ["s1"])
    data = yaml.safe_load("".join(lines))
    assert data == [
        {
            "id": "TST-01-001",
            "statement": "x",
            "rationale": "Kept for history. See #3377.",
            "stories": ["s1"],
        }
    ]
    assert "".join(lines).endswith(
        "  stories:\n  - s1\n  # comment introducing the next item\n"
    )


def test_append_list_field_refuses_duplicate_values():
    with pytest.raises(ValueError, match="duplicate values"):
        append_list_field(_item(_PLAIN), "stories", ["s1", "s1"])


def test_inserted_lines_copy_a_crlf_line_ending():
    text = _PLAIN.replace("\n", "\r\n")
    lines = append_list_field(_item(text), "stories", ["s1"])
    assert all(line.endswith("\r\n") for line in lines)
    flow = "- id: TST-01-001\r\n  lint_suppress: [a_code]\r\n"
    for added_lines in (
        add_lint_suppression(_item(flow), "x_code")[0],
        remove_lint_suppression(
            _item(flow.replace("[a_code]", "[a_code, x_code]")), "x_code"
        )[0],
    ):
        assert all(line.endswith("\r\n") for line in added_lines)


def test_add_lint_suppression_refuses_an_unparseable_block_entry():
    """Stopping at the bad entry would insert mid-list and miss later codes."""
    text = "- id: TST-01-001\n  lint_suppress:\n  - a-code\n  - b_code\n"
    with pytest.raises(ValueError, match="unparseable lint_suppress entry"):
        add_lint_suppression(_item(text), "x_code")


_COMMENTED_HEADER = (
    "- id: TST-01-001\n  lint_suppress:  # why\n  - a_code\n  statement: x\n"
)


def test_add_lint_suppression_handles_a_commented_block_header():
    lines, added = add_lint_suppression(_item(_COMMENTED_HEADER), "x_code")
    assert added
    assert "".join(lines) == _COMMENTED_HEADER.replace(
        "  - a_code\n", "  - a_code\n  - x_code\n"
    )


def test_remove_lint_suppression_handles_a_commented_block_header():
    lines, removed = remove_lint_suppression(
        _item(_COMMENTED_HEADER), "a_code"
    )
    assert removed
    assert "".join(lines) == "- id: TST-01-001\n  statement: x\n"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "- id: TST-01-001\n  lint_suppress: []\n",
            "- id: TST-01-001\n  lint_suppress: [x_code]\n",
        ),
        (
            "- id: TST-01-001\n  lint_suppress: ['a_code']  # n\n",
            "- id: TST-01-001\n  lint_suppress: ['a_code', x_code]  # n\n",
        ),
        (
            "- id: TST-01-001\n  lint_suppress:\n  statement: x\n",
            "- id: TST-01-001\n  lint_suppress:\n  - x_code\n  statement: x\n",
        ),
        (
            "- id: TST-01-001\n  lint_suppress:\n    - a_code\n",
            "- id: TST-01-001\n  lint_suppress:\n    - a_code\n    - x_code\n",
        ),
    ],
    ids=["empty-flow", "quoted-flow-comment", "empty-block", "deep-block"],
)
def test_add_lint_suppression_list_shapes(text, expected):
    lines, added = add_lint_suppression(_item(text), "x_code")
    assert added
    assert "".join(lines) == expected
    assert yaml.safe_load(expected)[0]["lint_suppress"][-1] == "x_code"
