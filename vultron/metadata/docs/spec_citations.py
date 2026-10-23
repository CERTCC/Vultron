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

The link reader here is separate from :mod:`vultron.metadata.docs.page_links`
on purpose: that module returns only the resolved page each link points at,
while this check needs each link's text, line and anchor. Fences are read by
the shared :func:`~vultron.metadata.markdown_tables.fenced_lines`. The gate is
the pytest test ``test/metadata/docs/test_spec_citations.py``, which the
unit suite runs on every change; it has no CLI of its own.
"""

from __future__ import annotations

import posixpath
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.markdown_tables import fenced_lines

SPEC_DIR = "reference/vultron-spec"
"""``docs/``-relative directory holding the Protocol Specification pages."""

_LINK_RE = re.compile(
    r"(?<!!)\[([^\]\n]+)\]\(\s*(<[^>\n]+>|[^)\s]+)"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)
_NUM = r"\d+(?:\.\d+)*"
_REF = (
    rf"(?:§{{1,2}}\s?{_NUM}|[Ss]ections?\s+{_NUM}|Annex(?:es)?\s+[A-G])"
    rf"(?:\s*(?:[–—-]|,|and|to|through)\s*(?:§{{1,2}}\s?)?(?:{_NUM}|[A-G]))*"
)
_BARE_RE = re.compile(
    rf"^(?:.*?(?:\S,?\s+|\())?{_REF}\)?[.,;:]?"
    r"(?:,?\s+(?:(?:of|in)\s+(?:the|this)\s+.*|above|below|here))?$"
)
_CITED_RE = re.compile(
    rf"^(?:.*?\s)?(?:§\s?(?P<num>{_NUM})|[Ss]ection\s+(?P<sec>{_NUM})"
    r"|Annex\s+(?P<annex>[A-G](?:\.\d+)*))(?P<name>\s.*)?$"
)
_ANNEX_ANCHOR_RE = re.compile(r"^(?:annex-[a-g]-|[a-g]\d+-)")
_STATUS_TAG_RE = re.compile(r"-(?:n|i|ni)$")
"""Slug of a heading's ``[N]``, ``[I]`` or ``[N/I]`` status marker."""


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
        text = page.read_text(encoding="utf-8")
        fenced = fenced_lines(text)
        for number, line in enumerate(text.splitlines(), 1):
            if number in fenced:
                continue
            for match in _LINK_RE.finditer(line):
                label, target = match.group(1), match.group(2).strip("<>")
                if _targets_spec(docs_path, target):
                    found.append(SpecLink(docs_path, number, label, target))
    return found


def _plain(text: str) -> str:
    return text.replace("`", "").strip()


def _slug(text: str) -> str:
    """Slugify *text* the way the default Python-Markdown ``toc`` slugify does."""
    ascii_text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(
        r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", ascii_text).strip().lower()
    )


def _anchor_fault(text: str, anchor: str) -> str | None:
    """Return why *text* disagrees with the numbered *anchor*, or ``None``.

    The cited number must open the anchor's slug and the cited name must
    start with the rest of it, so "§1.2 Foo" is refused at ``#12-conformance``
    although the dot-free digits agree. An anchor on an unnumbered heading
    is not compared.
    """
    cited = _CITED_RE.match(text)
    if cited is None:
        return None
    annex = cited.group("annex")
    if annex is not None:
        if not _ANNEX_ANCHOR_RE.match(anchor):
            return None
        letter, _, rest = annex.lower().partition(".")
        prefix = (
            f"{letter}{rest.replace('.', '')}-"
            if rest
            else (f"annex-{letter}-")
        )
        label = f"Annex {annex}"
    else:
        number = cited.group("num") or cited.group("sec")
        if not anchor[:1].isdigit():
            return None
        prefix = number.replace(".", "") + "-"
        label = f"§{number}"
    heading = _STATUS_TAG_RE.sub("", anchor.removeprefix(prefix))
    if anchor.startswith(prefix) and _slug(
        cited.group("name") or ""
    ).startswith(heading):
        return None
    return f"cites {label} but links #{anchor}"


def citation_faults(links: list[SpecLink]) -> list[CitationFault]:
    """Return the citation faults among *links*.

    A link is at fault when its text cites a number without the section name
    ("§6", "§9 of the specification", "Vultron Protocol Specification §8"), or
    when the section it cites is not the one its anchor names ("§4.8" pointing
    at ``#47-...``, or "§1.2 Foo" pointing at ``#12-conformance``).
    """
    faults: list[CitationFault] = []
    for link in links:
        text = _plain(link.text)
        if _BARE_RE.match(text):
            faults.append(
                CitationFault(link, "cites a number without its name")
            )
            continue
        reason = _anchor_fault(text, link.target.partition("#")[2])
        if reason is not None:
            faults.append(CitationFault(link, reason))
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
