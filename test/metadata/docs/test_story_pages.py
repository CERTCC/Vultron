"""The shape of every user-story page under ``docs/reference/user_stories/``.

A story page is a working-record page (DF-11-003), so its frontmatter declares
``stakeholder_type: [project-contributor]`` (DF-11-012) and nothing that
places it for a reader: no ``level`` (DF-11-033), ``page_type`` or
``subject``. The generated index table quotes the text between the
``story-start`` and ``story-end`` markers, so each marker appears exactly once.
The page's ID is its filename and its title, in the pattern every ``stories:``
entry must match (SR-11-002). The dated support level is retired (#4507): no
page carries it. A page added from 2026 on also carries the 2026 Metadata
shape and none of the 2022 provenance fields (``notes/user-story-catalog.md``
§ Story page shape).

The corpus tests run the checker over the real catalog; the remaining tests
pin that each fault is actually reported, so a passing corpus run is not a
vacuous one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from vultron.metadata.base import repo_root
from vultron.metadata.docs.story_pages import (
    STORY_ID_RE,
    STORY_ROOT,
    story_ids,
)

#: Files in the story directory that are not story pages.
_NOT_STORIES = frozenset({"index.md", "table.md", "traceability.md"})

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_TITLE_RE = re.compile(
    r"^# User Story `(?P<short>[^`]+)`(?: #)?$", re.MULTILINE
)
_START = "<!-- story-start -->"
_END = "<!-- story-end -->"
_SUPPORT_LEVEL_RE = re.compile(r"support level|as of v0\.4\.0", re.IGNORECASE)

#: The first year whose pages carry the 2026 Metadata shape.
_FIRST_2026_YEAR = 2026
_REQUIRED_2026_FIELDS = ("Speaker", "Related issues", "Drafted for", "Added")
_RETIRED_2022_FIELDS = (
    "Original ID",
    "2022 Whitepaper ID",
    "Potential future process or service",
)
_FIELD_RE = re.compile(r"^- \*\*(?P<name>[^*]+):\*\*", re.MULTILINE)


def _frontmatter_faults(text: str) -> list[str]:
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return ["no frontmatter block"]
    metadata = yaml.safe_load(match.group(1)) or {}
    if metadata == {"stakeholder_type": ["project-contributor"]}:
        return []
    return [
        "frontmatter must be exactly `stakeholder_type: [project-contributor]` "
        f"(DF-11-012, DF-11-033), got {metadata!r}"
    ]


def _marker_faults(text: str) -> list[str]:
    faults = [
        f"{marker} appears {text.count(marker)} times, not once"
        for marker in (_START, _END)
        if text.count(marker) != 1
    ]
    if not faults and text.index(_START) > text.index(_END):
        faults.append("story-end comes before story-start")
    return faults


def _id_faults(path: Path, text: str) -> list[str]:
    faults: list[str] = []
    if not STORY_ID_RE.fullmatch(path.stem):
        faults.append(f"filename {path.name!r} is not a story ID (SR-11-002)")
    titles = _TITLE_RE.findall(text)
    if len(titles) != 1:
        faults.append(
            f"expected one `# User Story` title, found {len(titles)}"
        )
    elif f"story_{titles[0]}" != path.stem:
        faults.append(
            f"title ID {titles[0]!r} does not match filename {path.name!r}"
        )
    return faults


def _metadata_faults(path: Path, text: str) -> list[str]:
    """The 2026 Metadata shape, for a page added from 2026 on."""
    if not STORY_ID_RE.fullmatch(path.stem):
        return []
    if int(path.stem.split("_")[1]) < _FIRST_2026_YEAR:
        return []
    fields = set(_FIELD_RE.findall(text))
    return [
        f"missing Metadata field {name!r}"
        for name in _REQUIRED_2026_FIELDS
        if name not in fields
    ] + [
        f"carries the 2022-only field {name!r}"
        for name in _RETIRED_2022_FIELDS
        if name in fields
    ]


def story_page_faults(path: Path) -> list[str]:
    """Return every shape fault in the story page at *path*, empty if none."""
    text = path.read_text(encoding="utf-8")
    faults = [
        *_id_faults(path, text),
        *_frontmatter_faults(text),
        *_marker_faults(text),
        *_metadata_faults(path, text),
    ]
    if _SUPPORT_LEVEL_RE.search(text):
        faults.append("carries the retired support level")
    return faults


def _story_dir() -> Path:
    return repo_root() / STORY_ROOT


def _real_pages() -> list[Path]:
    return sorted(
        path
        for path in _story_dir().glob("*.md")
        if path.name not in _NOT_STORIES
    )


def test_catalog_is_not_empty() -> None:
    """An empty catalog would make every corpus test below vacuous (DF-09-009)."""
    assert _real_pages()
    assert len(_real_pages()) == len(story_ids(repo_root()))


@pytest.mark.spec("DF-11-012")
@pytest.mark.spec("SR-11-002")
@pytest.mark.parametrize("path", _real_pages(), ids=lambda path: path.stem)
def test_every_story_page_has_the_documented_shape(path: Path) -> None:
    assert story_page_faults(path) == []


_GOOD_2026 = (
    "---\nstakeholder_type: [project-contributor]\n---\n\n"
    "# User Story `2026_999`\n\n"
    f"{_START}As a Tool Author, I want a thing, so that it works{_END}\n\n"
    "## Notes\n\nWhy.\n\n"
    "## Metadata\n\n"
    "- **Speaker:** Implementer (Tool Author)\n"
    "- **Related issues:** #1\n"
    "- **Drafted for:** #2\n"
    "- **Added:** 2026-11-03\n"
)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_the_good_page_passes(tmp_path: Path) -> None:
    assert (
        story_page_faults(_write(tmp_path, "story_2026_999.md", _GOOD_2026))
        == []
    )


@pytest.mark.parametrize(
    ("name", "body", "fault"),
    [
        ("story_26_999.md", _GOOD_2026, "is not a story ID"),
        ("story_2026_998.md", _GOOD_2026, "does not match filename"),
        (
            "story_2026_999.md",
            _GOOD_2026.replace("---\n\n", "level: 300\n---\n\n", 1),
            "frontmatter must be exactly",
        ),
        (
            "story_2026_999.md",
            _GOOD_2026.replace("[project-contributor]", "[cvd-practitioner]"),
            "frontmatter must be exactly",
        ),
        (
            "story_2026_999.md",
            _GOOD_2026.split("\n", 3)[3],
            "no frontmatter block",
        ),
        ("story_2026_999.md", _GOOD_2026.replace(_END, ""), "appears 0 times"),
        (
            "story_2026_999.md",
            _GOOD_2026.replace(_START, "@@")
            .replace(_END, _START)
            .replace("@@", _END),
            "story-end comes before story-start",
        ),
        (
            "story_2026_999.md",
            _GOOD_2026.replace("# User Story", "# Story"),
            "expected one `# User Story` title, found 0",
        ),
        (
            "story_2026_999.md",
            _GOOD_2026 + f"\n{_START}again\n",
            "appears 2 times",
        ),
        (
            "story_2026_999.md",
            _GOOD_2026 + "- **Support Level:** *(as of v0.4.0)* Allowed\n",
            "retired support level",
        ),
        (
            "story_2026_999.md",
            _GOOD_2026.replace("- **Added:** 2026-11-03\n", ""),
            "missing Metadata field 'Added'",
        ),
        (
            "story_2026_999.md",
            _GOOD_2026 + "- **Original ID:** `1.0`\n",
            "2022-only field 'Original ID'",
        ),
    ],
)
def test_each_fault_is_reported(
    tmp_path: Path, name: str, body: str, fault: str
) -> None:
    faults = story_page_faults(_write(tmp_path, name, body))
    assert any(fault in reported for reported in faults), faults


def test_a_2022_page_keeps_its_provenance_fields(tmp_path: Path) -> None:
    """The 2026 shape does not apply to the frozen 2022 catalog."""
    body = (
        _GOOD_2026.replace("2026_999", "2022_999")
        .replace("- **Related issues:** #1\n", "")
        .replace("- **Added:** 2026-11-03\n", "- **Original ID:** `1.0`\n")
    )
    assert story_page_faults(_write(tmp_path, "story_2022_999.md", body)) == []
