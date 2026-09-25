"""Tests for the prose scanner the docs level-order check reads (SG-11).

Requirements: DF-11-002; positions survive masking so findings keep their
``path:line:col`` (MS-17-001).
"""

from __future__ import annotations

import pytest

from vultron.metadata.docs.concept_scan import (
    first_use,
    scan_page,
    term_forms,
)
from vultron.metadata.markdown_tables import fenced_lines

# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("term", "forms"),
    [
        (
            "Coordinated Vulnerability Disclosure (CVD)",
            ("Coordinated Vulnerability Disclosure", "CVD"),
        ),
        (
            "Semantic Type (or MessageSemantics)",
            ("Semantic Type", "MessageSemantics"),
        ),
        ("Embargo Revise (R)", ("Embargo Revise",)),
        ("V/v", ()),
        ("CASE_MANAGER", ("CASE_MANAGER",)),
    ],
)
def test_term_forms(term, forms):
    assert term_forms(term) == forms


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("Two case ledger entries.", None),  # "entries" is not "entry" + s
        ("The Case Ledger Entries.", None),
        ("The case ledger entry.", "case ledger entry"),
        ("The CASE_MANAGER role.", "CASE_MANAGER"),
        ("The case_manager role.", None),  # identifiers match exactly
        ("A CASE_MANAGER_ID field.", None),
        ("Multi-CASE_MANAGER setups.", None),
    ],
)
def test_first_use_matches_whole_words(text, found):
    page = scan_page(text, "a.md")
    forms = ("Case Ledger Entry", "CASE_MANAGER")

    use = first_use(page, forms)

    assert (use.text if use else None) == found


def test_scan_resolves_relative_links():
    page = scan_page(
        "[a](../b/c.md#x) [d](./) [e](https://x.org/f.md) [g](#h)\n",
        "topics/sub/page.md",
    )

    assert {link.target for link in page.links} == {
        "topics/b/c.md",
        "topics/sub/index.md",
    }


_FORMS = ("Case Ledger Entry",)


@pytest.mark.parametrize(
    ("text", "position"),
    [
        # A comment opener inside a code span is code, not a comment.
        ("Type `<!--` here.\n\nA case ledger entry.\n\n<!-- c -->\n", (3, 3)),
        # A backtick inside a comment is comment, not a code span.
        ("<!-- a ` b -->\nA case ledger entry `x`.\n", (2, 3)),
        # A code span may wrap, but never across a blank line.
        ("`a\ncase ledger entry` then a case ledger entry.\n", (2, 27)),
        ("`a\n\nA case ledger entry.\n", (3, 3)),
        # Windows line endings still end the frontmatter.
        (
            "---\r\ntitle: case ledger entry\r\n---\r\nA case ledger entry.\r\n",
            (4, 3),
        ),
    ],
    ids=[
        "comment-in-code",
        "tick-in-comment",
        "wrapped-code",
        "blank-line-ends-code",
        "crlf-frontmatter",
    ],
)
def test_masking_finds_only_the_prose_use(text, position):
    use = first_use(scan_page(text, "a.md"), _FORMS)

    assert use is not None
    assert (use.position.line, use.position.column) == position


def test_an_image_inside_a_link_keeps_the_outer_link():
    page = scan_page(
        "[![i](i.png)](../topics/case-ledger-entry.md) Text.\n", "howto/a.md"
    )

    assert [link.target for link in page.links] == [
        "topics/case-ledger-entry.md"
    ]
    assert first_use(page, _FORMS) is None


def test_reference_labels_fold_case_and_whitespace():
    page = scan_page(
        "See [x][The  Ledger].\n\n[the ledger]: ../b.md\n", "topics/a.md"
    )

    assert [link.target for link in page.links] == ["b.md"]


def test_a_root_relative_link_is_not_a_docs_page():
    assert scan_page("[a](/topics/b.md)\n", "topics/a.md").links == ()


def test_nested_fences_are_tracked_only_when_asked():
    """A four-space fence is code inside an admonition, not plain Markdown."""
    text = "!!! note\n\n    ```\n    # x\n    ```\nafter\n"

    assert fenced_lines(text) == frozenset()
    assert fenced_lines(text, nested=True) == {3, 4, 5}


def test_a_shorter_run_does_not_close_a_longer_fence():
    assert fenced_lines("````\n```\nx\n````\ny\n") == {1, 2, 3, 4}
