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
"""Enforce number-plus-name citation text on links into the Protocol Specification.

The specification is published one part per page (#4061), so a section number no
longer tells a reader which page a link lands on, and a bare "§6" says nothing a
reader can act on before following it. A citation of a section therefore carries
its number *and* its name: "§6 Report Management (RM) State Machine", never "§6",
"section 6" or "§6 of the specification" (#4062; see the docs style guide, SG-25).

:func:`spec_links` collects every Markdown link under ``docs/`` whose target
resolves into ``reference/vultron-spec/``. :func:`citation_faults` reports the
ones whose text is a bare number, and the ones whose cited number disagrees with
the numbered anchor they link to. :func:`check_spec_citations` combines the two
and refuses an empty link set: a check that inspects nothing and reports success
is worse than no check (DF-09-009).
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

SPEC_DIR = "reference/vultron-spec"
"""``docs/``-relative directory holding the Protocol Specification pages."""

_LINK_RE = re.compile(
    r"(?<!!)\[([^\]\n]+)\]\(\s*(<[^>\n]+>|[^)\s]+)"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_NUM = r"\d+(?:\.\d+)*"
_REF = (
    rf"(?:§{{1,2}}\s?{_NUM}|[Ss]ections?\s+{_NUM}|Annex(?:es)?\s+[A-G])"
    rf"(?:\s*(?:[–-]|,|and|to|through)\s*(?:§{{1,2}}\s?)?(?:{_NUM}|[A-G]))*"
)
_BARE_RE = re.compile(
    rf"^(?:.*?\S,?\s+)?{_REF}[.,;:]?(?:\s+(?:of|in)\s+the\s+.*)?$"
)
_CITED_NUMBER_RE = re.compile(rf"^(?:.*?\s)?§\s?({_NUM})(?:\s|$)")


class NoSpecLinksError(ValueError):
    """Raised when the scan finds no link into the specification at all."""


@dataclass(frozen=True)
class SpecLink:
    """One Markdown link from a ``docs/`` page into the specification.

    Attributes:
        path: ``docs/``-relative path of the page holding the link.
        line: One-based line number of the link.
        text: The link text as written.
        target: The link target as written, anchor included.
    """

    path: str
    line: int
    text: str
    target: str

    def __str__(self) -> str:
        return f"docs/{self.path}:{self.line}: [{self.text}]({self.target})"


@dataclass(frozen=True)
class CitationFault:
    """A spec link whose citation text breaks the number-plus-name rule.

    Attributes:
        link: The offending link.
        reason: What is wrong with its text.
    """

    link: SpecLink
    reason: str

    def __str__(self) -> str:
        return f"{self.link} — {self.reason}"


def _in_spec(docs_path: str) -> bool:
    return docs_path == SPEC_DIR or docs_path.startswith(SPEC_DIR + "/")


def _targets_spec(docs_path: str, target: str) -> bool:
    """Return whether *target*, written on *docs_path*, resolves into the spec."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", target):
        return False
    if target.startswith("#"):
        return _in_spec(docs_path)
    page = target.split("#", 1)[0]
    return _in_spec(
        posixpath.normpath(posixpath.join(posixpath.dirname(docs_path), page))
    )


def spec_links(docs_root: Path) -> list[SpecLink]:
    """Return every link under *docs_root* whose target is a specification page.

    In-page links on a specification page count, since they land in the
    specification too. Fenced code blocks are skipped: a link shown as code is
    not one a reader follows.

    Args:
        docs_root: The ``docs/`` directory to scan.
    """
    found: list[SpecLink] = []
    for page in sorted(docs_root.rglob("*.md")):
        docs_path = page.relative_to(docs_root).as_posix()
        fence: str | None = None
        lines = page.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, 1):
            opened = _FENCE_RE.match(line)
            if opened:
                marker = opened.group(1)
                if fence is None:
                    fence = marker
                elif marker[0] == fence[0] and len(marker) >= len(fence):
                    fence = None
                continue
            if fence is not None:
                continue
            for match in _LINK_RE.finditer(line):
                text, target = match.group(1), match.group(2).strip("<>")
                if _targets_spec(docs_path, target):
                    found.append(SpecLink(docs_path, number, text, target))
    return found


def _plain(text: str) -> str:
    return text.replace("`", "").strip()


def citation_faults(links: list[SpecLink]) -> list[CitationFault]:
    """Return the citation faults among *links*.

    A link is at fault when its text cites a number without the section name
    ("§6", "§9 of the specification", "Vultron Protocol Specification §8"), or
    when the section number it cites is not the number of the anchor it links
    to ("§4.8" pointing at ``#47-...``).
    """
    faults: list[CitationFault] = []
    for link in links:
        text = _plain(link.text)
        if _BARE_RE.match(text):
            faults.append(
                CitationFault(link, "cites a number without its name")
            )
            continue
        cited = _CITED_NUMBER_RE.match(text)
        anchor = link.target.partition("#")[2]
        if cited and anchor[:1].isdigit():
            slug = cited.group(1).replace(".", "") + "-"
            if not anchor.startswith(slug):
                faults.append(
                    CitationFault(
                        link, f"cites §{cited.group(1)} but links #{anchor}"
                    )
                )
    return faults


def check_spec_citations(docs_root: Path) -> list[CitationFault]:
    """Return the citation faults under *docs_root*.

    Raises:
        NoSpecLinksError: If *docs_root* holds no link into the specification,
            so the check would otherwise pass while inspecting nothing.
    """
    links = spec_links(docs_root)
    if not links:
        raise NoSpecLinksError(
            f"no link under {docs_root} targets {SPEC_DIR}/; "
            "an empty target set is a failure, not a pass (DF-09-009)"
        )
    return citation_faults(links)
