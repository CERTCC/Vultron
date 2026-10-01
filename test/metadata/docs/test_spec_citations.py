"""Tests for vultron.metadata.docs.spec_citations (issue #4062).

Paginating the Protocol Specification (#4061) made a section number stop
telling a reader which page a link lands on, so every citation of a section
carries its number and its name. The first test is the gate on the real
``docs/`` tree; the rest pin what counts as bare, and that an empty link set
fails rather than passing while checking nothing (DF-09-009).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.docs.spec_citations import (
    NoSpecLinksError,
    bare_citations,
    check_spec_citations,
    spec_links,
)

DOCS = Path(__file__).resolve().parents[3] / "docs"


def _page(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_docs_cite_spec_sections_by_number_and_name() -> None:
    findings = check_spec_citations(DOCS)
    assert not findings, "bare spec citations:\n" + "\n".join(
        str(link) for link in findings
    )


@pytest.mark.parametrize(
    "text",
    [
        "§6",
        "§ 6",
        "§12.4.3",
        "section 6",
        "Section 9.4",
        "Annex G",
        "§9 of the specification",
        "§2.2 of the Vultron Protocol Specification",
        "Annex G in the protocol specification",
    ],
)
def test_bare_number_fails(tmp_path: Path, text: str) -> None:
    _page(
        tmp_path,
        "howto/page.md",
        f"See [{text}](../reference/vultron-spec/tracking-models.md#x).\n",
    )
    findings = check_spec_citations(tmp_path)
    assert [link.text for link in findings] == [text]
    assert findings[0].line == 1
    assert str(findings[0]).startswith("docs/howto/page.md:1: ")


@pytest.mark.parametrize(
    "text",
    [
        "§6 Report Management (RM) State Machine",
        "§9.4 Deadlines and the Pocket Veto in the Vultron Protocol Specification",
        "Annex G Capability Shapes",
        "Vultron Protocol Specification",
    ],
)
def test_number_plus_name_passes(tmp_path: Path, text: str) -> None:
    _page(
        tmp_path,
        "howto/page.md",
        f"See [{text}](../reference/vultron-spec/tracking-models.md#x).\n",
    )
    assert check_spec_citations(tmp_path) == []


def test_links_resolve_relative_to_the_page(tmp_path: Path) -> None:
    _page(
        tmp_path,
        "reference/vultron-spec/_fragment.md",
        "[§6](tracking-models.md#x) and [§7](#local) and [§8](../other.md)\n",
    )
    links = spec_links(tmp_path)
    assert [link.text for link in links] == ["§6"]
    assert [link.text for link in bare_citations(links)] == ["§6"]


def test_absolute_urls_and_fenced_code_are_ignored(tmp_path: Path) -> None:
    _page(
        tmp_path,
        "howto/page.md",
        "```markdown\n[§6](../reference/vultron-spec/tracking-models.md)\n```\n"
        "[§6](https://example.org/reference/vultron-spec/tracking-models.md)\n"
        "[§6 Report Management (RM) State Machine]"
        "(../reference/vultron-spec/tracking-models.md)\n",
    )
    links = spec_links(tmp_path)
    assert [(link.line, link.text) for link in links] == [
        (5, "§6 Report Management (RM) State Machine")
    ]


def test_zero_spec_links_fails(tmp_path: Path) -> None:
    _page(tmp_path, "howto/page.md", "See [elsewhere](../topics/page.md).\n")
    with pytest.raises(NoSpecLinksError, match="empty target set"):
        check_spec_citations(tmp_path)
