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
"""Keep RFC 2119 keywords out of the Protocol Specification's own prose.

The specification writes no normative sentence of its own: its normative text
is the ``protocol`` and ``foundation`` requirements, rendered from the YAML as
callouts and catalog rows (ADR-0147). A keyword such as MUST in a fragment's
prose is therefore a requirement the YAML does not hold, or holds in other
words (DF-12-004). :func:`keyword_faults` reports each one.

What it reads, and what it skips:

* **The fragment source.** A keyword is a sentence-scoped rule, so it is
  checked in the file that holds the sentence, not on the rendered page
  (DF-09-007). A source page an annex pulls in through ``include-markdown`` is
  not a specification fragment and is not read.
* **Rendered blocks are skipped.** A callout is printed by a fenced
  ``markdown-exec`` block, so its lines are skipped. Every other fenced block
  is skipped too, as is an inline code span: code shows a keyword (a wire
  example, a quoted requirement) rather than using one, so it states no rule
  of the specification's own. Telling an exec fence apart would only add
  ways for the check to misread a fence.
* **The §1.4 Document Conventions paragraph** in :data:`CONVENTIONS_FRAGMENT`,
  the one that names RFC 2119 and lists the keywords, is the one exception.

The check enforces :data:`RECONCILED_FRAGMENTS`, the fragments whose prose has
been reconciled with the YAML (``notes/rfc-spec-authoring.md`` § "Normative
Text Comes from the YAML"). Each reconcile task under #4888 adds its page's
fragments, until every fragment is listed (#4902). An empty list is a failure,
not a pass (DF-09-009). The gate is the pytest test
``test/metadata/docs/test_rfc2119_keywords.py``, which the unit suite runs on
every change; it has no CLI of its own.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.markdown_tables import fenced_lines
from vultron.metadata.rfc2119 import keywords_in

RECONCILED_FRAGMENTS: tuple[str, ...] = (
    "reference/vultron-spec/_abstract.md",
    "reference/vultron-spec/_introduction.md",
    "reference/vultron-spec/_terminology.md",
    "reference/vultron-spec/_protocol-overview.md",
    "reference/vultron-spec/_messages.md",
    "reference/vultron-spec/_encoding-transport.md",
    "reference/vultron-spec/includes/_state-ownership-table.md",
    "reference/vultron-spec/includes/_dimensions-vs-machines.md",
    "reference/vultron-spec/_iana.md",
    "reference/vultron-spec/_security.md",
    "reference/vultron-spec/_references.md",
    "reference/vultron-spec/_annex-a.md",
    "reference/vultron-spec/_annex-b.md",
    "reference/vultron-spec/_annex-c.md",
    "reference/vultron-spec/_annex-d.md",
    "reference/vultron-spec/_annex-e.md",
    "reference/vultron-spec/_annex-f.md",
    "reference/vultron-spec/_conformance/_capability-shapes.md",
    "reference/vultron-spec/_open-questions.md",
    "reference/vultron-spec/_oq-cs-ordering.md",
    "reference/vultron-spec/_oq-embargo-termination-authority.md",
    "reference/vultron-spec/_oq-negative-ack.md",
    "reference/vultron-spec/_oq-role-acquisition.md",
    "reference/vultron-spec/_oq-transport-status-codes.md",
    "reference/vultron-spec/_oq-v-to-V.md",
)
"""``docs/``-relative fragments the keyword check enforces (DF-12-004)."""

CONVENTIONS_FRAGMENT = "reference/vultron-spec/_introduction.md"
"""The fragment holding §1.4 Document Conventions."""

# Every RFC 2119 keyword, as RFC 8174 defines them: upper case only. The
# negated forms ("MUST NOT", "NOT RECOMMENDED") contain a listed word.
_CONVENTIONS_HEADING_RE = re.compile(
    r"^#{1,6}\s+1\.4\s+Document Conventions\b"
)
_HEADING_RE = re.compile(r"^#{1,6}\s")


class NoKeywordTargetsError(ValueError):
    """Raised when the check is given no fragment to read."""


@dataclass(frozen=True)
class KeywordFault:
    """An RFC 2119 keyword in a fragment's prose.

    Attributes:
        path: ``docs/``-relative path of the fragment.
        line: One-based line number.
        keyword: The keyword found.
    """

    path: str
    line: int
    keyword: str

    def __str__(self) -> str:
        return (
            f"docs/{self.path}:{self.line}: RFC 2119 keyword {self.keyword} "
            "in prose; render the rule as a callout or reword it as "
            "informative (DF-12-004)"
        )


def _conventions_lines(lines: list[str]) -> frozenset[int]:
    """Return the line numbers of the §1.4 paragraph that names RFC 2119."""
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if _CONVENTIONS_HEADING_RE.match(line)
        ),
        None,
    )
    if start is None:
        return frozenset()
    paragraph: list[int] = []
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if _HEADING_RE.match(line):
            break
        if line.strip():
            paragraph.append(index + 1)
            continue
        if any("RFC 2119" in lines[n - 1] for n in paragraph):
            return frozenset(paragraph)
        paragraph = []
    if any("RFC 2119" in lines[n - 1] for n in paragraph):
        return frozenset(paragraph)
    return frozenset()


def fragment_keyword_faults(path: str, text: str) -> list[KeywordFault]:
    """Return the keyword faults in *text*, the fragment at ``docs/`` *path*."""
    lines = text.splitlines()
    skipped = fenced_lines(text)
    if path == CONVENTIONS_FRAGMENT:
        skipped = skipped | _conventions_lines(lines)
    faults: list[KeywordFault] = []
    for number, line in enumerate(lines, start=1):
        if number in skipped:
            continue
        faults.extend(
            KeywordFault(path, number, keyword)
            for keyword in keywords_in(line)
        )
    return faults


def keyword_faults(
    docs_root: Path, fragments: Iterable[str] = RECONCILED_FRAGMENTS
) -> list[KeywordFault]:
    """Return the keyword faults in *fragments* under *docs_root*.

    Raises:
        NoKeywordTargetsError: If *fragments* is empty, so the check would
            otherwise pass while reading nothing (DF-09-009).
        FileNotFoundError: If a listed fragment does not exist; a stale entry
            checks nothing.
    """
    targets = list(fragments)
    if not targets:
        raise NoKeywordTargetsError(
            "no specification fragment to check for RFC 2119 keywords; an "
            "empty target set is a failure, not a pass (DF-09-009)"
        )
    faults: list[KeywordFault] = []
    for path in targets:
        source = docs_root / path
        if not source.is_file():
            raise FileNotFoundError(
                f"docs/{path} is listed for the RFC 2119 keyword check but "
                "does not exist"
            )
        faults.extend(
            fragment_keyword_faults(path, source.read_text(encoding="utf-8"))
        )
    return faults


__all__ = [
    "CONVENTIONS_FRAGMENT",
    "RECONCILED_FRAGMENTS",
    "KeywordFault",
    "NoKeywordTargetsError",
    "fragment_keyword_faults",
    "keyword_faults",
]
