"""Tests for vultron.metadata.docs.spec_citations (issue #4062).

Paginating the Protocol Specification (#4061) made a section number stop
telling a reader which page a link lands on, so every citation of a section
carries its number and its name. The first test is the gate on the real
``docs/`` tree; the rest pin what counts as bare, that a cited number must
agree with its anchor, and that an empty link set fails rather than passing
while checking nothing (DF-09-009).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.docs.spec_citations import (
    NoSpecLinksError,
    check_spec_citations,
    spec_links,
)

DOCS = Path(__file__).resolve().parents[3] / "docs"
SPEC_PAGE = "../reference/vultron-spec/tracking-models.md"


def _page(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _faults_for(root: Path, text: str, target: str = SPEC_PAGE) -> list[str]:
    _page(root, "howto/page.md", f"See [{text}]({target}).\n")
    return [fault.reason for fault in check_spec_citations(root)]


def test_docs_cite_spec_sections_by_number_and_name() -> None:
    faults = check_spec_citations(DOCS)
    assert not faults, "spec citation faults:\n" + "\n".join(map(str, faults))


@pytest.mark.parametrize(
    "text",
    [
        "§6",
        "§ 6",
        "§6.",
        "§12.4.3",
        "`§6`",
        "§6–9",
        "§§6–9",
        "§6 and §7",
        "section 6",
        "Section 9.4",
        "Sections 6 to 9",
        "Annex G",
        "Annexes A and B",
        "§9 of the specification",
        "§2.2 of the Vultron Protocol Specification",
        "Annex G in the protocol specification",
        "Vultron Protocol Specification §8",
        "Vultron Protocol Specification, §6",
        "see §6",
        "§6—9",
        "§6 of this specification",
        "§6 in this spec",
        "§6 above",
        "§6, below",
        "§6 here",
        "(§6)",
        "transitions table (§7.2)",
    ],
)
def test_bare_number_fails(tmp_path: Path, text: str) -> None:
    assert _faults_for(tmp_path, text) == ["cites a number without its name"]


def test_fault_names_file_line_and_link(tmp_path: Path) -> None:
    _page(tmp_path, "howto/page.md", f"intro\n\nSee [§6]({SPEC_PAGE}).\n")
    (fault,) = check_spec_citations(tmp_path)
    assert str(fault).startswith(f"docs/howto/page.md:3: [§6]({SPEC_PAGE}) — ")


@pytest.mark.parametrize(
    "text",
    [
        "§6 Report Management (RM) State Machine",
        "§9.4 Deadlines and the Pocket Veto in the Vultron Protocol Specification",
        "Vultron Protocol Specification §8 Case State (CS) Dimensions",
        "Annex G Capability Shapes",
        "Vultron Protocol Specification",
    ],
)
def test_number_plus_name_passes(tmp_path: Path, text: str) -> None:
    assert _faults_for(tmp_path, text) == []


def test_cited_number_must_match_its_anchor(tmp_path: Path) -> None:
    target = "../reference/vultron-spec/layers.md#47-knowledge-model"
    assert _faults_for(tmp_path, "§4.8 Knowledge Model", target) == [
        "cites §4.8 but links #47-knowledge-model"
    ]


@pytest.mark.parametrize(
    ("text", "anchor", "reason"),
    [
        (
            "§1.2 Foo",
            "12-conformance-n",
            "cites §1.2 but links #12-conformance-n",
        ),
        (
            "Section 4.8 Knowledge Model",
            "47-knowledge-model",
            "cites §4.8 but links #47-knowledge-model",
        ),
        (
            "Annex G Capability Shapes",
            "annex-f-behavior-trees-i",
            "cites Annex G but links #annex-f-behavior-trees-i",
        ),
        (
            "Annex G Capability Shapes",
            "g1-the-four-capability-shapes",
            "cites Annex G but links #g1-the-four-capability-shapes",
        ),
    ],
)
def test_cited_section_must_be_the_anchored_one(
    tmp_path: Path, text: str, anchor: str, reason: str
) -> None:
    target = f"../reference/vultron-spec/page.md#{anchor}"
    assert _faults_for(tmp_path, text, target) == [reason]


@pytest.mark.parametrize(
    ("text", "anchor"),
    [
        ("§12 Conformance", "12-conformance-n"),
        ("§14 Security Considerations", "14-security-considerations-ni"),
        (
            "§4 Semantic Layer — Message Meanings",
            "4-semantic-layer-message-meanings-n",
        ),
        (
            "§9.4 Deadlines and the Pocket Veto in the Vultron Protocol "
            "Specification",
            "94-deadlines-and-the-pocket-veto",
        ),
        ("Annex G Capability Shapes", "annex-g-capability-shapes-i"),
        (
            "Annex G.1 The Four Capability Shapes",
            "g1-the-four-capability-shapes",
        ),
    ],
)
def test_cited_section_matching_its_anchor_passes(
    tmp_path: Path, text: str, anchor: str
) -> None:
    target = f"../reference/vultron-spec/page.md#{anchor}"
    assert _faults_for(tmp_path, text, target) == []


def test_unnumbered_anchor_is_not_compared(tmp_path: Path) -> None:
    target = (
        "../reference/vultron-spec/conformance.md#case-observer-capability-set"
    )
    assert (
        _faults_for(tmp_path, "§12.2 Case Observer capability set", target)
        == []
    )


def test_links_resolve_relative_to_the_page(tmp_path: Path) -> None:
    _page(
        tmp_path,
        "reference/vultron-spec/_fragment.md",
        "[§6](tracking-models.md#x) and [§7](#local) and [§8](../other.md)\n",
    )
    assert [link.text for link in spec_links(tmp_path)] == ["§6", "§7"]


def test_in_page_link_off_the_spec_is_not_a_spec_link(tmp_path: Path) -> None:
    _page(tmp_path, "howto/page.md", "[§7](#local)\n")
    assert spec_links(tmp_path) == []


def test_titles_and_angle_bracket_targets_are_read(tmp_path: Path) -> None:
    _page(
        tmp_path,
        "howto/page.md",
        f"[§6]({SPEC_PAGE} 'Title')\n"
        f'[§7]({SPEC_PAGE} "Title")\n'
        f"[§8](<{SPEC_PAGE}>)\n",
    )
    links = spec_links(tmp_path)
    assert [(link.text, link.target) for link in links] == [
        ("§6", SPEC_PAGE),
        ("§7", SPEC_PAGE),
        ("§8", SPEC_PAGE),
    ]


def test_absolute_urls_and_fenced_code_are_ignored(tmp_path: Path) -> None:
    _page(
        tmp_path,
        "howto/page.md",
        f"````markdown\n```\n[§6]({SPEC_PAGE})\n```\n````\n"
        f"!!! note\n    ~~~\n    [§6]({SPEC_PAGE})\n    ~~~\n"
        "[§6](https://example.org/reference/vultron-spec/tracking-models.md)\n"
        f"[§6 Report Management (RM) State Machine]({SPEC_PAGE})\n",
    )
    links = spec_links(tmp_path)
    assert [(link.line, link.text) for link in links] == [
        (11, "§6 Report Management (RM) State Machine")
    ]


def test_zero_spec_links_fails(tmp_path: Path) -> None:
    _page(tmp_path, "howto/page.md", "See [elsewhere](../topics/page.md).\n")
    with pytest.raises(NoSpecLinksError, match="empty target set"):
        check_spec_citations(tmp_path)
