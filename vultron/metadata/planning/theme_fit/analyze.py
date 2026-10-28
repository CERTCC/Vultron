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
"""The structural theme rules, as one pure function over open Issues.

Requirements: PAD-01-002, PAD-01-007, PAD-02-001, PAD-02-008, PAD-02-014, PAD-02-015,
PAD-02-017, PAD-02-018.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from itertools import chain

from vultron.metadata.planning.bundle_fit.model import SCHEDULE_ORDER
from vultron.metadata.planning.theme_fit.model import (
    UNSCHEDULED,
    Finding,
    FindingKind,
    OpenIssue,
    ThemeFitReport,
    TierCoherence,
)
from vultron.metadata.planning.themes import ThemeCatalog, ThemeStatus


def nearest_epic(
    issue: OpenIssue, by_number: Mapping[int, OpenIssue]
) -> int | None:
    """The number of *issue*'s nearest Epic ancestor, or ``None``.

    Walks the fetched parent chain; where it stops short, continues through
    the last ancestor's own chain when that ancestor is an open Issue in
    *by_number*. A cycle ends the walk.
    """
    seen: set[int] = {issue.number}
    current = issue
    while True:
        for ancestor in current.ancestors:
            if ancestor.is_epic:
                return ancestor.number
        if not current.ancestors:
            return None
        last = current.ancestors[-1].number
        nxt = by_number.get(last)
        if nxt is None or last in seen:
            return None
        seen.add(last)
        current = nxt


def _fmt(themes: Iterable[str]) -> str:
    listed = ", ".join(f"`{t}`" for t in themes)
    return listed or "none"


def _count_detail(issue: OpenIssue, is_leaf: bool) -> str | None:
    """Why *issue* breaks the theme-count rule, or ``None`` if it does not."""
    themes = issue.themes
    if issue.is_epic:
        if len(themes) == 2 and not issue.names_split(*themes):
            return f"two themes ({_fmt(themes)}) and no body line naming both"
        if 1 <= len(themes) <= 2:
            return None
    elif not is_leaf or len(themes) == 1:
        return None
    if not themes:
        return "no theme label"
    return f"{len(themes)}: {_fmt(themes)}"


def _catalog_findings(
    issue: OpenIssue, catalog: ThemeCatalog
) -> Iterator[tuple[FindingKind, str]]:
    """A finding for each theme the catalog does not list or is retiring."""
    listed = {t.label: t for t in catalog.themes}
    for theme in issue.themes:
        entry = listed.get(theme)
        if entry is None:
            yield FindingKind.UNKNOWN_THEME, f"`{theme}` is not in the catalog"
        elif entry.status is ThemeStatus.RETIRING:
            use = " or ".join(f"`{t}`" for t in entry.replaced_by)
            yield (
                FindingKind.RETIRING_THEME,
                f"`{theme}` is retiring; use {use}",
            )


def _label_findings(
    issue: OpenIssue, catalog: ThemeCatalog, is_leaf: bool
) -> Iterator[tuple[FindingKind, str]]:
    """Count, catalog-membership and reason-line findings for one Issue."""
    detail = _count_detail(issue, is_leaf)
    if detail is not None:
        kind = (
            FindingKind.EPIC_THEME_COUNT
            if issue.is_epic
            else FindingKind.LEAF_THEME_COUNT
        )
        yield kind, detail
    yield from _catalog_findings(issue, catalog)
    named = issue.reason_line_themes()
    unnamed = [t for t in issue.themes if t not in named]
    if unnamed:
        yield (
            FindingKind.MISSING_REASON_LINE,
            f"no `Theme:` line names {_fmt(unnamed)}",
        )


def _epic_findings(
    epic: OpenIssue, ancestor_epic: int | None, open_children: int
) -> Iterator[tuple[FindingKind, str]]:
    """Nesting and calving findings for one Epic."""
    if ancestor_epic is not None:
        yield FindingKind.NESTED_EPIC, f"under Epic #{ancestor_epic}"
    if epic.is_auto_calved() and open_children < 2:
        yield (
            FindingKind.SINGLE_CHILD_CALVED_EPIC,
            f"{open_children} open sub-issue(s)",
        )


def _unparented_detail(issue: OpenIssue, epic_number: int | None) -> str:
    if epic_number is not None:
        return f"its nearest Epic, #{epic_number}, is closed"
    if issue.parent is None:
        return "no parent"
    return f"parent #{issue.parent} has no Epic ancestor"


def _parent_theme_detail(
    issue: OpenIssue, epic: OpenIssue, open_children: int
) -> str | None:
    """Why *issue*'s themes break PAD-02-017 against *epic*, or ``None``."""
    carries = f"Epic #{epic.number} carries {_fmt(epic.themes)}"
    if not epic.themes:
        return None
    if not issue.themes:
        # A leaf with no theme is already a leaf-theme-count finding.
        return f"no theme label; {carries}" if open_children else None
    stray = [t for t in issue.themes if t not in epic.themes]
    return f"carries {_fmt(stray)}; {carries}" if stray else None


def _hierarchy_findings(
    issue: OpenIssue,
    epic_number: int | None,
    open_children: int,
    by_number: Mapping[int, OpenIssue],
) -> Iterator[tuple[FindingKind, str]]:
    """Ancestry, calving and parent-theme findings for one Issue."""
    if issue.is_epic:
        yield from _epic_findings(issue, epic_number, open_children)
        return
    epic = None if epic_number is None else by_number.get(epic_number)
    if epic is None:
        yield FindingKind.UNPARENTED, _unparented_detail(issue, epic_number)
        return
    detail = _parent_theme_detail(issue, epic, open_children)
    if detail is not None:
        yield FindingKind.THEME_MISMATCH, detail


def _matches(child: OpenIssue, epic: OpenIssue) -> bool:
    """True when *child* has one theme and *epic* carries it."""
    return len(child.themes) == 1 and child.themes[0] in epic.themes


def _tier_order(tier: str) -> tuple[int, str]:
    if tier in SCHEDULE_ORDER:
        return (SCHEDULE_ORDER.index(tier), tier)
    if tier == UNSCHEDULED:
        return (len(SCHEDULE_ORDER) + 1, tier)
    return (len(SCHEDULE_ORDER), tier)


def _coherence(
    issues: Iterable[OpenIssue],
    epic_of: Mapping[int, int | None],
    by_number: Mapping[int, OpenIssue],
) -> tuple[TierCoherence, ...]:
    epics: Counter[str] = Counter()
    children: Counter[str] = Counter()
    matching: Counter[str] = Counter()
    for issue in issues:
        if issue.is_epic:
            epics[issue.schedule or UNSCHEDULED] += 1
            continue
        epic_number = epic_of[issue.number]
        epic = None if epic_number is None else by_number.get(epic_number)
        if epic is None:
            continue
        tier = epic.schedule or UNSCHEDULED
        children[tier] += 1
        matching[tier] += _matches(issue, epic)
    tiers = sorted(set(epics) | set(children), key=_tier_order)
    return tuple(
        TierCoherence(t, epics[t], children[t], matching[t]) for t in tiers
    )


def analyze(
    issues: Iterable[OpenIssue], catalog: ThemeCatalog
) -> ThemeFitReport:
    """Apply every structural theme rule to the open *issues*.

    Args:
        issues: Every open Issue; a parent outside the set is closed.
        catalog: The theme catalog the labels are checked against.
    """
    ordered = sorted(issues, key=lambda i: i.number)
    by_number = {i.number: i for i in ordered}
    open_children: Counter[int] = Counter(
        i.parent for i in ordered if i.parent is not None
    )
    epic_of = {i.number: nearest_epic(i, by_number) for i in ordered}
    findings: list[Finding] = []
    for issue in ordered:
        epic_number = epic_of[issue.number]
        children = open_children[issue.number]
        found = chain(
            _label_findings(issue, catalog, is_leaf=children == 0),
            _hierarchy_findings(issue, epic_number, children, by_number),
        )
        findings.extend(
            Finding(kind, issue.number, issue.title, detail)
            for kind, detail in found
        )
    findings.sort(key=lambda f: (list(FindingKind).index(f.kind), f.number))
    return ThemeFitReport(
        issues=len(ordered),
        findings=tuple(findings),
        coherence=_coherence(ordered, epic_of, by_number),
    )
