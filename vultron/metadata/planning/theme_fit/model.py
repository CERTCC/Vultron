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
"""The records ``theme-fit`` reads and reports.

:class:`OpenIssue` is one open Issue as the GraphQL query returns it, already
reduced to what the rules need. :class:`Finding` and :class:`TierCoherence`
are what :func:`~vultron.metadata.planning.theme_fit.analyze.analyze` derives
from them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from vultron.metadata.planning.themes import THEME_PREFIX

EPIC_TYPE = "Epic"
"""The GitHub issue type that marks an Epic (PAD-02-009)."""

UNSCHEDULED = "(unscheduled)"
"""The tier name for Epics with no Project #24 ``Schedule`` value."""

AUTO_CALVED_MARKER = "<!-- auto-calved -->"
"""The body line ``create-issue`` writes on an Epic it calves unattended.

The marker is how ``theme-fit`` tells an auto-calved Epic from one a person
made, so it can report the auto-calved ones that never gained a second child.
It is matched as a whole line, after stripping surrounding whitespace.
"""

REASON_LINE = re.compile(
    r"^Theme:\s*(?P<labels>.*?)\s+[\u2014\u2013-]+\s+(?P<outcome>\S.*)$"
)
"""The ``Theme: <label> — <outcome>`` reason line (PAD-02-018).

The labels and the outcome are split by the first dash with space on both
sides (an em dash, an en dash or a hyphen), and the outcome must not be empty.
"""

THEME_LABEL_PATTERN = re.compile(
    r"(?<![\w:-])theme:[a-z0-9]+(?:-[a-z0-9]+)*", re.IGNORECASE
)
"""A ``theme:`` label named in body text."""


def named_themes(line: str) -> frozenset[str]:
    """The ``theme:`` labels *line* names, case-folded."""
    return frozenset(m.casefold() for m in THEME_LABEL_PATTERN.findall(line))


class FindingKind(StrEnum):
    """One rule a finding breaks. The value is the report's key for it."""

    LEAF_THEME_COUNT = "leaf-theme-count"
    EPIC_THEME_COUNT = "epic-theme-count"
    MISSING_REASON_LINE = "missing-reason-line"
    THEME_MISMATCH = "theme-mismatch"
    UNPARENTED = "unparented"
    NESTED_EPIC = "nested-epic"
    SINGLE_CHILD_CALVED_EPIC = "single-child-calved-epic"
    UNKNOWN_THEME = "unknown-theme"
    RETIRING_THEME = "retiring-theme"

    @property
    def heading(self) -> str:
        """The heading the report gives this kind."""
        return _HEADINGS[self]

    @property
    def rule(self) -> str:
        """The requirement this kind enforces."""
        return _RULES[self]


_HEADINGS: dict[FindingKind, str] = {
    FindingKind.LEAF_THEME_COUNT: "Leaf without exactly one theme",
    FindingKind.EPIC_THEME_COUNT: "Epic without one theme or a named split",
    FindingKind.MISSING_REASON_LINE: "Missing `Theme:` reason line",
    FindingKind.THEME_MISMATCH: "Child theme differs from its Epic's",
    FindingKind.UNPARENTED: "Non-Epic with no open Epic ancestor",
    FindingKind.NESTED_EPIC: "Epic nested under an Epic",
    FindingKind.SINGLE_CHILD_CALVED_EPIC: "Auto-calved Epic still single-child",
    FindingKind.UNKNOWN_THEME: "Theme label not in the catalog",
    FindingKind.RETIRING_THEME: "Retiring theme label",
}

_RULES: dict[FindingKind, str] = {
    FindingKind.LEAF_THEME_COUNT: "PAD-02-014",
    FindingKind.EPIC_THEME_COUNT: "PAD-02-015",
    FindingKind.MISSING_REASON_LINE: "PAD-02-018",
    FindingKind.THEME_MISMATCH: "PAD-02-017",
    FindingKind.UNPARENTED: "PAD-01-007",
    FindingKind.NESTED_EPIC: "PAD-01-002",
    FindingKind.SINGLE_CHILD_CALVED_EPIC: "PAD-02-008",
    FindingKind.UNKNOWN_THEME: "PAD-02-014",
    FindingKind.RETIRING_THEME: "PAD-02-014",
}


@dataclass(frozen=True)
class Ancestor:
    """One step up an Issue's parent chain."""

    number: int
    issue_type: str | None

    @property
    def is_epic(self) -> bool:
        """True when this ancestor is an Epic."""
        return self.issue_type == EPIC_TYPE


@dataclass(frozen=True)
class OpenIssue:
    """One open Issue, as the theme rules see it.

    ``ancestors`` runs nearest first and may stop short of the root: the query
    reads a fixed depth, and the analysis continues the walk through any
    ancestor that is itself an open Issue in the set.
    """

    number: int
    title: str
    issue_type: str | None
    labels: frozenset[str]
    body: str
    ancestors: tuple[Ancestor, ...] = ()
    schedule: str | None = None

    @property
    def is_epic(self) -> bool:
        """True when this Issue is an Epic."""
        return self.issue_type == EPIC_TYPE

    @property
    def themes(self) -> tuple[str, ...]:
        """The ``theme:`` labels it carries, case-folded and sorted."""
        return tuple(
            sorted(
                label.casefold()
                for label in self.labels
                if label.casefold().startswith(THEME_PREFIX)
            )
        )

    @property
    def parent(self) -> int | None:
        """The number of its direct parent, if it has one."""
        return self.ancestors[0].number if self.ancestors else None

    def reason_line_themes(self) -> frozenset[str]:
        """Every theme a well-formed reason line in its body names.

        A ``Theme:`` line with no outcome after the dash names nothing.
        """
        named: set[str] = set()
        for line in self.body.splitlines():
            match = REASON_LINE.match(line.strip())
            if match:
                named |= named_themes(match["labels"])
        return frozenset(named)

    def names_split(self, first: str, second: str) -> bool:
        """True when one body line names both *first* and *second*."""
        return any(
            {first, second} <= named_themes(line)
            for line in self.body.splitlines()
        )

    def is_auto_calved(self) -> bool:
        """True when its body carries :data:`AUTO_CALVED_MARKER`."""
        return any(
            line.strip() == AUTO_CALVED_MARKER
            for line in self.body.splitlines()
        )


@dataclass(frozen=True)
class Finding:
    """One Issue breaking one rule."""

    kind: FindingKind
    number: int
    title: str
    detail: str

    def to_json(self) -> dict[str, object]:
        """The finding as a JSON-ready mapping."""
        return {
            "kind": self.kind.value,
            "rule": self.kind.rule,
            "number": self.number,
            "title": self.title,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class TierCoherence:
    """How many children in one ``Schedule`` tier match their Epic's theme.

    A child is a non-Epic open Issue; its tier is its nearest Epic's
    (PAD-02-001). It matches when it carries exactly one theme and its Epic
    carries that theme.
    """

    tier: str
    epics: int
    children: int
    matching: int

    @property
    def share(self) -> float | None:
        """``matching / children``, or ``None`` for a tier with no children."""
        return self.matching / self.children if self.children else None

    def to_json(self) -> dict[str, object]:
        """The tier's figures as a JSON-ready mapping."""
        return {
            "tier": self.tier,
            "epics": self.epics,
            "children": self.children,
            "matching": self.matching,
            "share": self.share,
        }


@dataclass(frozen=True)
class ThemeFitReport:
    """Every finding, and coherence per tier."""

    issues: int
    findings: tuple[Finding, ...]
    coherence: tuple[TierCoherence, ...]

    @property
    def clean(self) -> bool:
        """True when no Issue breaks a rule."""
        return not self.findings

    def of_kind(self, kind: FindingKind) -> tuple[Finding, ...]:
        """The findings of one *kind*, in Issue-number order."""
        return tuple(f for f in self.findings if f.kind is kind)

    def to_json(self) -> dict[str, object]:
        """The report as a JSON-ready mapping."""
        return {
            "issues": self.issues,
            "clean": self.clean,
            "counts": {k.value: len(self.of_kind(k)) for k in FindingKind},
            "findings": [f.to_json() for f in self.findings],
            "coherence": [t.to_json() for t in self.coherence],
        }
