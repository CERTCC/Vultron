#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Check over the built ``site/`` that every page renders its reading-path boxes.

Requirements: DF-11-023 (a box reaches a page only through an
``include-markdown`` line its author places, and a built-site check finds a
missing or misplaced one), DF-11-022 (a section member's box sits in its
section), DF-09-009 (an empty target set fails). Design:
``notes/site-information-architecture.md`` § "Threads: staged data, rendered
at both ends" (ADR-0150).

Boxes are placed by hand, so their placement is not mechanical and a check of
the ``docs/`` sources could only re-derive what the author was meant to do.
This check reads what the build produced instead. Each rendered box names its
thread and target in :data:`~vultron.metadata.docs.threads.THREAD_ATTR` and
:data:`~vultron.metadata.docs.threads.MEMBER_ATTR`, so for every built page
the check fails when:

* a box of a thread the page is on (as a member or as its start page) is
  missing — the message names the ``include-markdown`` line to add;
* the page renders a box made for another page, or the same box twice;
* a section member's box does not sit after the element carrying its anchor
  and before the next heading of the same or a higher level (DF-11-022);
* a rendered box has no matching ``include-markdown`` directive in the page's
  source, which is how a box something other than the author added shows.

It needs a full site build, so it runs in CI beside the other built-site
checks (``.github/actions/check-site-publication``), not as a pre-commit hook.

CLI (``uv run docs-path-boxes``)::

    uv run mkdocs build
    uv run docs-path-boxes        # exit 1 on any finding
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.docs.built_site import require_built_site
from vultron.metadata.docs.landing_pages import WRITE_COMMAND
from vultron.metadata.docs.page_frontmatter import classify_docs_tree
from vultron.metadata.docs.site_urls import url_path
from vultron.metadata.docs.threads import (
    BOX_CLASS,
    MEMBER_ATTR,
    THREAD_ATTR,
    StartThread,
    box_fragment_path,
    box_targets,
    include_line,
    load_threads,
    thread_name,
)
from vultron.metadata.file_loading import MetadataLoadError

_HEADING = re.compile(r"h([1-6])")
_INCLUDE = re.compile(r"""\{%\s*include-markdown\s+(["'])(.+?)\1""")


@dataclass(frozen=True, slots=True)
class ExpectedBox:
    """A box a page must render.

    Attributes:
        thread: The thread's name (its start page's stem).
        target: The start page's path, or the member's ``page`` (anchor kept).
        fragment: ``docs/``-relative path of the box's committed fragment.
    """

    thread: str
    target: str
    fragment: str

    @property
    def page(self) -> str:
        """The ``docs/``-relative page that renders the box."""
        return self.target.partition("#")[0]

    @property
    def anchor(self) -> str:
        """The section anchor of a section member's box, else ``""``."""
        return self.target.partition("#")[2]


@dataclass(frozen=True, slots=True)
class RenderedBox:
    """A box found in a built page, at document position *at*."""

    thread: str
    target: str
    at: int


@dataclass
class PageScan:
    """What one built page's article holds, in document order.

    Attributes:
        boxes: Every rendered reading-path box.
        ids: ``{id: (position, heading level)}``; the level is ``None`` for an
            element that is not a heading.
        headings: ``(position, level)`` of every heading.
    """

    boxes: list[RenderedBox] = field(default_factory=list)
    ids: dict[str, tuple[int, int | None]] = field(default_factory=dict)
    headings: list[tuple[int, int]] = field(default_factory=list)


class _ArticleParser(HTMLParser):
    """Collect boxes, ids and headings inside the page's ``<article>``.

    Material puts the page's content in its first ``<article>``; the nav and
    table of contents around it are left out, so their links and labels can
    neither satisfy nor trip the check.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scan = PageScan()
        self._inside = False
        self._done = False
        self._at = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if self._done:
            return
        if tag == "article" and not self._inside:
            self._inside = True
            return
        if not self._inside:
            return
        self._at += 1
        values = {name: value or "" for name, value in attrs}
        heading = _HEADING.fullmatch(tag)
        level = int(heading.group(1)) if heading else None
        if level is not None:
            self.scan.headings.append((self._at, level))
        if values.get("id"):
            self.scan.ids.setdefault(values["id"], (self._at, level))
        if BOX_CLASS in values.get("class", "").split():
            self.scan.boxes.append(
                RenderedBox(
                    thread=values.get(THREAD_ATTR, ""),
                    target=values.get(MEMBER_ATTR, ""),
                    at=self._at,
                )
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self._inside:
            self._inside = False
            self._done = True


def scan_page(text: str) -> PageScan:
    """Return what the built page *text* renders inside its article."""
    parser = _ArticleParser()
    parser.feed(text)
    parser.close()
    return parser.scan


def expected_boxes(
    threads: Iterable[StartThread],
) -> dict[str, list[ExpectedBox]]:
    """Return ``{docs/-relative page: boxes it must render}`` for *threads*."""
    expected: dict[str, list[ExpectedBox]] = {}
    for thread in threads:
        for target in box_targets(thread):
            box = ExpectedBox(
                thread=thread_name(thread),
                target=target,
                fragment=box_fragment_path(thread, target),
            )
            expected.setdefault(box.page, []).append(box)
    return expected


def included_fragments(source: str, page: str) -> set[str]:
    """``docs/``-relative paths the page *source* names in ``include-markdown``."""
    base = posixpath.dirname(page)
    return {
        posixpath.normpath(posixpath.join(base, match.group(2)))
        for match in _INCLUDE.finditer(source)
    }


def built_page(site: Path, page: str) -> Path:
    """The built HTML file of the ``docs/``-relative *page*."""
    return site / url_path(page) / "index.html"


def _placement_fault(box: ExpectedBox, scan: PageScan, at: int) -> str | None:
    """Why a section member's box at *at* is outside its section, if it is."""
    anchor = scan.ids.get(box.anchor)
    if anchor is None:
        return (
            f"renders the {box.thread} box for #{box.anchor}, but no element "
            "carries that id; restore the section, or change the thread and "
            f"rerun `{WRITE_COMMAND}` (DF-11-022)"
        )
    start, level = anchor
    bound_level = level if level is not None else 6
    end = next(
        (
            pos
            for pos, lvl in scan.headings
            if pos > start and lvl <= bound_level
        ),
        None,
    )
    if start < at and (end is None or at < end):
        return None
    return (
        f"renders the {box.thread} box for #{box.anchor} outside that "
        f"section; move {include_line(box.page, box.fragment)} to the end of "
        "the section, before the next heading of the same or a higher level "
        "(DF-11-022)"
    )


def page_faults(
    page: str,
    scan: PageScan,
    source: str,
    expected: list[ExpectedBox],
    fragments: dict[tuple[str, str], str],
) -> list[str]:
    """Every finding for one built *page*, each naming the page (DF-11-023)."""
    faults: list[str] = []
    included = included_fragments(source, page)
    wanted = {(box.thread, box.target) for box in expected}
    for box in expected:
        found = [
            r
            for r in scan.boxes
            if (r.thread, r.target) == (box.thread, box.target)
        ]
        where = f" at the end of section #{box.anchor}" if box.anchor else ""
        if not found:
            faults.append(
                f"does not render its box for the {box.thread} reading path; "
                f"add {include_line(page, box.fragment)}{where}"
            )
            continue
        if len(found) > 1:
            faults.append(
                f"renders its {box.thread} box {len(found)} times; keep one "
                f"{include_line(page, box.fragment)}"
            )
        if box.anchor:
            for rendered in found:
                fault = _placement_fault(box, scan, rendered.at)
                if fault:
                    faults.append(fault)
    for rendered in scan.boxes:
        key = (rendered.thread, rendered.target)
        fragment = fragments.get(key)
        if key not in wanted:
            line = (
                include_line(page, fragment)
                if fragment is not None
                else "the include-markdown line that renders it"
            )
            faults.append(
                f"renders the box made for {rendered.target} on the "
                f"{rendered.thread} reading path; remove {line}"
            )
        if fragment is not None and fragment not in included:
            faults.append(
                f"renders the {rendered.thread} box for {rendered.target} with "
                "no matching include-markdown directive in its source; a box "
                f"reaches a page only through {include_line(page, fragment)} "
                "placed by hand, never from the build (DF-11-023)"
            )
    return faults


@dataclass(frozen=True)
class BoxReport:
    """What one pass over the built site checked and found."""

    pages: int
    boxes: int
    faults: list[str]


def check_boxes(root: Path | None = None) -> BoxReport:
    """Check every built page's reading-path boxes (DF-11-023).

    Raises:
        FileNotFoundError: If ``site/`` is absent or empty.
        MetadataLoadError: If no start page declares a thread, so there is
            nothing to check (DF-09-009).
        MetadataLoadErrors: If a start page's thread does not validate.
    """
    root = root or repo_root()
    site = require_built_site(
        root, "every page renders its reading-path boxes"
    )
    threads = load_threads(root)
    expected = expected_boxes(threads)
    if not expected:
        raise MetadataLoadError(
            "resolved no reading-path boxes to check; an empty target set is "
            "a failure, not a pass (DF-11-023, DF-09-009)",
            path="docs/start",
        )
    fragments = {
        (box.thread, box.target): box.fragment
        for boxes in expected.values()
        for box in boxes
    }
    docs_dir = root / "docs"
    pages = sorted(set(classify_docs_tree(root).pages) | expected.keys())
    faults: list[str] = []
    checked = 0
    for page in pages:
        html_file = built_page(site, page)
        if not html_file.is_file():
            if page in expected:
                faults.append(
                    f"docs/{page}: is on a reading path but was not built, "
                    "so it shows no box"
                )
            continue
        checked += 1
        source_file = docs_dir / page
        source = (
            source_file.read_text(encoding="utf-8")
            if source_file.is_file()
            else ""
        )
        scan = scan_page(html_file.read_text(encoding="utf-8"))
        faults.extend(
            f"docs/{page}: {fault}"
            for fault in page_faults(
                page, scan, source, expected.get(page, []), fragments
            )
        )
    return BoxReport(pages=checked, boxes=len(fragments), faults=faults)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-path-boxes`` command."""
    parser = argparse.ArgumentParser(
        description=(
            "Check that every built page renders its reading-path boxes "
            "(DF-11-023). Run after 'uv run mkdocs build'."
        )
    )
    parser.parse_args(argv)
    try:
        report = check_boxes()
    except (FileNotFoundError, MetadataLoadError, OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    for fault in report.faults:
        print(f"[ERROR] {fault}", file=sys.stderr)
    if report.faults:
        print(
            f"{len(report.faults)} reading-path box finding(s) over "
            f"{report.pages} built page(s).",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        f"Checked {report.boxes} reading-path box(es) over {report.pages} "
        "built page(s)."
    )


if __name__ == "__main__":
    main()
