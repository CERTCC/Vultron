"""Generate the contents listing of each top-level ``docs/`` section landing page.

Requirements: specs/diataxis-requirements.yaml DF-11-005 (generated, check
gated, never hand-maintained), DF-09-009 (an empty target set fails), DF-11-004
(a level is never rendered). Design rationale:
``notes/site-information-architecture.md`` § "Landing pages are generated,
never hand-maintained" (ADR-0102).

Every section landing page used to be a hand-written copy of the navigation,
and every one had drifted from it. So the listing is derived from two
machine-readable sources instead:

* **the ``mkdocs.yml`` nav**, which says what a section contains and supplies
  each entry's label and its fallback order;
* **each listed page's frontmatter**, which supplies an optional
  ``description:`` shown beside the link and an optional ``level`` that sorts
  the listing (DF-11-001).

Only the text between :data:`BEGIN_MARKER` and :data:`END_MARKER` is
generated. The prerequisites admonition, the section's framing, and any
cross-section pointers are hand-written prose and survive regeneration.

A landing page is the ``index.md`` a top-level nav section opens with. The
nav's own structure decides which pages those are; nothing lists them.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import mkdocs_config
from vultron.metadata.docs.page_schema import LEVELS
from vultron.metadata.file_loading import MetadataLoadError, load_frontmatter
from vultron.metadata.generated_block import splice_between

#: Command that regenerates every artifact, quoted in markers and errors.
WRITE_COMMAND = "uv run docs-site --write"

#: Opening marker of a generated listing. Names both inputs and the command, so
#: a reader who found the listing by grep learns where to make a change.
BEGIN_MARKER = (
    "<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml "
    "nav or a listed page's description: frontmatter, then run "
    f"`{WRITE_COMMAND}` -->"
)

#: Closing marker of a generated listing.
END_MARKER = "<!-- END GENERATED SECTION CONTENTS -->"

_INDEX_NAME = "index.md"
_H1_RE = re.compile(r"^#\s+(.*?)\s*#*\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Entry:
    """One item in a landing page's contents listing.

    Attributes:
        label: The nav label, or the page's H1 for an unlabelled nav path.
        target: ``docs/``-relative path, an external URL, or ``None`` for a
            group that has no landing page of its own.
        description: The target page's ``description:``, whitespace-folded.
        level: The level the entry sorts by, or ``None`` when undeclared.
        children: A group's members; empty when the entry links to a page.
    """

    label: str
    target: str | None
    description: str | None = None
    level: int | None = None
    children: tuple[Entry, ...] = ()


@dataclass(frozen=True, slots=True)
class LandingPage:
    """A top-level nav section and the entries its landing page lists."""

    path: str
    entries: tuple[Entry, ...]


@dataclass(frozen=True, slots=True)
class _PageFacts:
    description: str | None
    level: int | None


def _is_url(target: str) -> bool:
    return "://" in target


def _page_facts(docs_dir: Path, rel: str, root: Path) -> _PageFacts:
    """Read the ``description`` and ``level`` a page's frontmatter declares.

    A level off the ladder is treated as undeclared: ``docs-frontmatter``
    already reports it against the page, and failing here too would name one
    fault from two tools.

    Raises:
        MetadataLoadError: If the page is missing, or ``description`` is
            present but not a non-blank string.
    """
    path = docs_dir / rel
    if not path.is_file():
        raise MetadataLoadError(
            "is listed in the mkdocs.yml nav but does not exist",
            path=f"docs/{rel}",
        )
    metadata = load_frontmatter(path, root=root).metadata
    raw = metadata.get("description")
    description: str | None = None
    if raw is not None:
        if not isinstance(raw, str) or not raw.strip():
            raise MetadataLoadError(
                "description: must be a non-blank string when present",
                path=f"docs/{rel}",
            )
        description = " ".join(raw.split())
    level = metadata.get("level")
    return _PageFacts(
        description=description,
        level=level if type(level) is int and level in LEVELS else None,
    )


def _page_h1(docs_dir: Path, rel: str) -> str:
    text = (docs_dir / rel).read_text(encoding="utf-8")
    match = _H1_RE.search(text)
    return match.group(1).strip() if match else Path(rel).stem


def _split_item(item: object) -> tuple[str | None, object]:
    """Return ``(label, value)`` for one nav item; bare paths have no label."""
    if isinstance(item, dict) and len(item) == 1:
        ((label, value),) = item.items()
        return str(label), value
    return None, item


def _group_landing(items: list[object]) -> str | None:
    """The ``index.md`` a nav group opens with, which becomes its link."""
    if not items:
        return None
    _label, value = _split_item(items[0])
    if isinstance(value, str) and posixpath.basename(value) == _INDEX_NAME:
        return value
    return None


def sort_entries(entries: list[Entry]) -> tuple[Entry, ...]:
    """Order entries by level, keeping nav order wherever levels are absent.

    Each entry without a level stays attached to the nearest declared entry
    before it in nav order; entries before any declared one lead. The runs so
    formed are sorted stably by their leader's level. So a listing in which no
    page declares a level keeps nav order exactly, one in which every page does
    is sorted by level, and a partly declared listing moves only as far as its
    declarations say (#3527 AC-1).
    """
    runs: list[tuple[int, list[Entry]]] = [(0, [])]
    for entry in entries:
        if entry.level is None:
            runs[-1][1].append(entry)
        else:
            runs.append((entry.level, [entry]))
    ordered = sorted(runs, key=lambda run: run[0])
    return tuple(entry for _level, run in ordered for entry in run)


def _entry(item: object, docs_dir: Path, root: Path) -> Entry:
    label, value = _split_item(item)
    if isinstance(value, str):
        if _is_url(value):
            return Entry(label=label or value, target=value)
        facts = _page_facts(docs_dir, value, root)
        return Entry(
            label=label or _page_h1(docs_dir, value),
            target=value,
            description=facts.description,
            level=facts.level,
        )
    if not isinstance(value, list) or label is None:
        raise MetadataLoadError(
            f"has a nav item this generator cannot read: {item!r}",
            path="mkdocs.yml",
        )
    landing = _group_landing(value)
    if landing is not None:
        facts = _page_facts(docs_dir, landing, root)
        return Entry(
            label=label,
            target=landing,
            description=facts.description,
            level=facts.level,
        )
    children = sort_entries([_entry(i, docs_dir, root) for i in value])
    levels = [c.level for c in children if c.level is not None]
    return Entry(
        label=label,
        target=None,
        level=min(levels) if levels else None,
        children=children,
    )


def discover_landing_pages(root: Path) -> tuple[LandingPage, ...]:
    """Return every top-level nav section that opens with an ``index.md``.

    Raises:
        MetadataLoadError: If no section resolves (DF-09-009), a section lists
            nothing but its landing page, or a listed page is unreadable.
    """
    docs_dir = root / "docs"
    nav = mkdocs_config(root).get("nav")
    pages: list[LandingPage] = []
    for item in nav if isinstance(nav, list) else []:
        _label, value = _split_item(item)
        if not isinstance(value, list):
            continue
        landing = _group_landing(value)
        if landing is None:
            continue
        members = value[1:]
        if not members:
            raise MetadataLoadError(
                f"the nav section opening with {landing} lists nothing else, "
                "so its landing page would enumerate an empty section",
                path="mkdocs.yml",
            )
        entries = sort_entries([_entry(i, docs_dir, root) for i in members])
        pages.append(LandingPage(path=landing, entries=entries))
    if not pages:
        raise MetadataLoadError(
            "resolved no section landing pages from the nav; an empty target "
            "set is a failure, not a pass (DF-09-009)",
            path="mkdocs.yml",
        )
    return tuple(pages)


def _render_entry(entry: Entry, landing: str, depth: int) -> list[str]:
    indent = "    " * depth
    if entry.target is None:
        lines = [f"{indent}- **{entry.label}**"]
        for child in entry.children:
            lines.extend(_render_entry(child, landing, depth + 1))
        return lines
    href = (
        entry.target
        if _is_url(entry.target)
        else posixpath.relpath(entry.target, posixpath.dirname(landing))
    )
    line = f"{indent}- [{entry.label}]({href})"
    if entry.description:
        line += f" — {entry.description}"
    return [line]


#: Python-Markdown nests a list item only at a 4-space indent, but markdownlint's
#: MD007 wants 2 and its auto-fix would flatten every group, so a listing that
#: nests switches MD007 off for exactly its own span.
_MD007_OFF = "<!-- markdownlint-disable MD007 -->"
_MD007_ON = "<!-- markdownlint-enable MD007 -->"


def render_listing(page: LandingPage) -> str:
    """Render a landing page's generated contents listing as a markdown list.

    Levels are used only to sort; none is printed (DF-11-004).
    """
    lines: list[str] = []
    for entry in page.entries:
        lines.extend(_render_entry(entry, page.path, 0))
    if any(entry.children for entry in page.entries):
        lines = [_MD007_OFF, *lines, _MD007_ON]
    return "\n".join(lines)


def splice_listing(current: str, page: LandingPage) -> str:
    """Return *current* with its generated listing replaced from *page*."""
    return splice_between(
        current,
        render_listing(page),
        f"docs/{page.path}",
        BEGIN_MARKER,
        END_MARKER,
    )
