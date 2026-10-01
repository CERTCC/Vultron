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
"section 6" or "§6 of the specification" (#4062; see the docs style guide).

:func:`spec_links` collects every Markdown link under ``docs/`` whose target
resolves into ``reference/vultron-spec/``, and :func:`bare_citations` returns the
ones whose text is a bare number. :func:`check_spec_citations` combines the two
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

_LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_BARE_RE = re.compile(
    r"^(?:§\s?\d+(?:\.\d+)*|[Ss]ection\s+\d+(?:\.\d+)*|Annex\s+[A-G])"
    r"(?:\s+(?:of|in)\s+the\s+.*)?$"
)


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


def _targets_spec(docs_path: str, target: str) -> bool:
    """Return whether *target*, written on *docs_path*, resolves into the spec."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
        return False
    page = target.split("#", 1)[0]
    resolved = posixpath.normpath(
        posixpath.join(posixpath.dirname(docs_path), page)
    )
    return resolved == SPEC_DIR or resolved.startswith(SPEC_DIR + "/")


def spec_links(docs_root: Path) -> list[SpecLink]:
    """Return every link under *docs_root* whose target is a specification page.

    Fenced code blocks are skipped, since a link shown as code is not one a
    reader follows.

    Args:
        docs_root: The ``docs/`` directory to scan.
    """
    found: list[SpecLink] = []
    for page in sorted(docs_root.rglob("*.md")):
        docs_path = page.relative_to(docs_root).as_posix()
        in_fence = False
        for number, line in enumerate(page.read_text().splitlines(), 1):
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in _LINK_RE.finditer(line):
                text, target = match.group(1), match.group(2)
                if _targets_spec(docs_path, target):
                    found.append(SpecLink(docs_path, number, text, target))
    return found


def bare_citations(links: list[SpecLink]) -> list[SpecLink]:
    """Return the links in *links* whose text cites a number without its name."""
    return [link for link in links if _BARE_RE.match(link.text.strip())]


def check_spec_citations(docs_root: Path) -> list[SpecLink]:
    """Return the bare-number citations under *docs_root*.

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
    return bare_citations(links)
