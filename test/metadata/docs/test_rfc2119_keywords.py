"""Tests for vultron.metadata.docs.rfc2119_keywords (issue #4895).

The Protocol Specification's normative text is the YAML requirements it
renders, so an RFC 2119 keyword in a fragment's own prose is a rule the YAML
does not hold (DF-12-004). The first test is the gate on the real ``docs/``
tree; the rest pin what the check reads, what it skips, and that an empty
or stale target list fails rather than passing (DF-09-009).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.docs.rfc2119_keywords import (
    CONVENTIONS_FRAGMENT,
    RECONCILED_FRAGMENTS,
    NoKeywordTargetsError,
    fragment_keyword_faults,
    keyword_faults,
)

DOCS = Path(__file__).resolve().parents[3] / "docs"
FRAGMENT = "reference/vultron-spec/_example.md"


def _keywords(text: str, path: str = FRAGMENT) -> list[tuple[int, str]]:
    return [(f.line, f.keyword) for f in fragment_keyword_faults(path, text)]


@pytest.mark.spec("DF-12-004", "DF-12-013")
def test_reconciled_fragments_hold_no_keyword_in_prose() -> None:
    faults = keyword_faults(DOCS)
    assert not faults, "\n".join(map(str, faults))


def test_reconciled_fragments_are_specification_fragments() -> None:
    for path in RECONCILED_FRAGMENTS:
        assert path.startswith("reference/vultron-spec/"), path
        assert Path(path).name.startswith("_"), path


@pytest.mark.spec("DF-12-004")
@pytest.mark.parametrize(
    "keyword",
    [
        "MUST",
        "SHALL",
        "SHOULD",
        "MAY",
        "REQUIRED",
        "RECOMMENDED",
        "OPTIONAL",
    ],
)
def test_each_keyword_in_prose_fails(keyword: str) -> None:
    assert _keywords(f"A sender {keyword} do it.\n") == [(1, keyword)]


def test_negated_forms_fail() -> None:
    text = (
        "It MUST NOT.\nIt SHALL NOT.\nIt SHOULD NOT.\nIt is NOT RECOMMENDED.\n"
    )
    assert _keywords(text) == [
        (1, "MUST"),
        (2, "SHALL"),
        (3, "SHOULD"),
        (4, "RECOMMENDED"),
    ]


def test_each_occurrence_is_reported_with_its_line() -> None:
    text = "Intro.\n\nIt MUST and it SHOULD.\n"
    assert _keywords(text) == [(3, "MUST"), (3, "SHOULD")]


def test_keywords_in_admonition_prose_fail() -> None:
    text = '!!! note "N"\n    A receiver MUST refuse it.\n'
    assert _keywords(text) == [(2, "MUST")]


def test_lower_case_and_longer_words_pass() -> None:
    assert _keywords("It must, MAYBE, MUSTARD, may.\n") == []


@pytest.mark.spec("DF-12-004")
def test_rendered_blocks_are_skipped() -> None:
    text = (
        'Prose.\n\n```python exec="true" idprefix=""\n'
        'print("A sender MUST")\n```\n\n'
        '!!! info "R"\n    ```text\n    MUST\n    ```\n'
    )
    assert _keywords(text) == []


def test_inline_code_is_skipped() -> None:
    assert _keywords("The token `MUST` and ``SHOULD`` are shown.\n") == []


def test_conventions_paragraph_is_exempt() -> None:
    text = (
        "### 1.4 Document Conventions\n\n"
        "This specification uses the key words defined in\n"
        "[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119): **MUST**,\n"
        "**SHOULD**, and **MAY**.\n\n"
        "Another paragraph that MUST still be checked.\n"
    )
    assert _keywords(text, CONVENTIONS_FRAGMENT) == [(7, "MUST")]


def test_conventions_exemption_is_only_in_the_conventions_fragment() -> None:
    text = (
        "### 1.4 Document Conventions\n\n"
        "This specification uses the key words defined in RFC 2119: MUST.\n"
    )
    assert _keywords(text) == [(3, "MUST")]


def test_conventions_exemption_is_only_under_its_heading() -> None:
    text = (
        "### 1.3 Other\n\n"
        "Words defined in RFC 2119: MUST.\n\n"
        "### 1.4 Document Conventions\n\n"
        "Words defined in RFC 2119: SHOULD.\n\n"
        "### 1.5 Next\n\n"
        "Words defined in RFC 2119: MAY.\n"
    )
    assert _keywords(text, CONVENTIONS_FRAGMENT) == [(3, "MUST"), (11, "MAY")]


def test_real_conventions_paragraph_is_found() -> None:
    """The exemption still matches the §1.4 paragraph as written: its keyword
    lines fail anywhere else and pass in the conventions fragment."""
    text = (DOCS / CONVENTIONS_FRAGMENT).read_text(encoding="utf-8")
    elsewhere = {f.line for f in fragment_keyword_faults("other.md", text)}
    exempt = elsewhere - {
        f.line for f in fragment_keyword_faults(CONVENTIONS_FRAGMENT, text)
    }
    assert exempt, "the §1.4 keyword paragraph was not found"
    heading = text.splitlines().index("### 1.4 Document Conventions") + 1
    assert min(exempt) > heading


@pytest.mark.spec("DF-12-014")
def test_empty_target_set_fails(tmp_path: Path) -> None:
    with pytest.raises(NoKeywordTargetsError, match="DF-09-009"):
        keyword_faults(tmp_path, [])


def test_missing_listed_fragment_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"_gone\.md"):
        keyword_faults(tmp_path, ["reference/vultron-spec/_gone.md"])


def test_fault_names_file_line_and_keyword(tmp_path: Path) -> None:
    path = tmp_path / FRAGMENT
    path.parent.mkdir(parents=True)
    path.write_text("Intro.\nIt SHOULD.\n", encoding="utf-8")
    [fault] = keyword_faults(tmp_path, [FRAGMENT])
    assert str(fault).startswith(f"docs/{FRAGMENT}:2: RFC 2119 keyword SHOULD")


def test_conventions_paragraph_at_end_of_file_is_exempt() -> None:
    text = "### 1.4 Document Conventions\n\nKey words of RFC 2119: MUST."
    assert _keywords(text, CONVENTIONS_FRAGMENT) == []


def test_later_conventions_paragraph_naming_rfc_2119_is_exempt() -> None:
    text = (
        "### 1.4 Document Conventions\n\n"
        "A first paragraph that MAY say anything.\n\n"
        "Key words of RFC 2119: MUST.\n"
    )
    assert _keywords(text, CONVENTIONS_FRAGMENT) == [(3, "MAY")]


def test_conventions_section_without_rfc_2119_paragraph_exempts_nothing() -> (
    None
):
    text = "### 1.4 Document Conventions\n\nIt MUST hold.\n"
    assert _keywords(text, CONVENTIONS_FRAGMENT) == [(3, "MUST")]


def test_conventions_fragment_without_its_heading_exempts_nothing() -> None:
    text = "Key words of RFC 2119: MUST.\n"
    assert _keywords(text, CONVENTIONS_FRAGMENT) == [(1, "MUST")]
