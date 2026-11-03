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
"""The protocol story gap, as a worklist per spec file (TRACE-03-004).

Every ``kind: protocol`` requirement should name the stories that motivated it
(SR-11-003 for the binding tier, SR-11-004 for the advisory one). The ones that
do not are the gap, and closing it is worked one spec-file area at a time
(``notes/user-story-catalog.md`` § "Working the protocol story gap"). This
report is that worklist.

It exists because the hand-written lists the five SR-11 gap Ideas carried were
measured once, on 2026-08-25, and about a third of the IDs on them had since
been relabelled or retired. A list derived from the registry on each run cannot
go stale that way.

The report is a read, never a gate: it issues no verdict on the corpus, however
many gaps it finds. ``spec-lint`` owns the verdicts (SR-11-003's hard error,
SR-11-004's advisory, and MS-12-007's PR-only guard on a new suppression);
counting the same population here as a pinned figure would be the
committed-count anti-pattern MS-10 forbids. Its one non-zero exit is about the
request rather than the corpus, below.

CLI (``uv run story-gaps``):
    story-gaps                one summary line per spec file
    story-gaps CM CSB         the same, narrowed to those files
    story-gaps --list CM-23   the requirements themselves, grouped by file
                              then priority

A selector that matches nothing exits ``2`` rather than printing an empty
report, so a mistyped area cannot read as a finished one.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import (
    LintWarningCode,
    RFC2119Priority,
    SpecKind,
)

#: Priorities in report order: the binding tier first, then the advisory one.
PRIORITY_ORDER: tuple[RFC2119Priority, ...] = (
    RFC2119Priority.MUST,
    RFC2119Priority.MUST_NOT,
    RFC2119Priority.SHOULD,
    RFC2119Priority.SHOULD_NOT,
    RFC2119Priority.MAY,
)

#: What a requirement carrying the SR-11-003 suppression is marked with.
SUPPRESSED_MARK = "[suppressed]"


@dataclass(frozen=True)
class Gap:
    """One ``kind: protocol`` requirement with no ``stories:``.

    Attributes:
        spec_id: The requirement's ID.
        file_id: The ID of the spec file it is declared in.
        priority: Its RFC 2119 priority.
        suppressed: Whether it carries
            ``lint_suppress: [missing_story_reference]``, which is what holds
            SR-11-003's hard error off it today. Adding one is forbidden
            (MS-12-007); these are the inherited carriers to retire.
    """

    spec_id: str
    file_id: str
    priority: RFC2119Priority
    suppressed: bool


class UnknownSelector(ValueError):
    """A selector named no spec file, group or requirement in the registry.

    Its own type, so :func:`main` catches the selector fault alone and cannot
    report an unrelated ``ValueError`` from deeper in the report as a mistyped
    area (CS-23-002). Derived from ``ValueError`` because that is what a bad
    argument value is, and so a caller that only wants "the selector was
    wrong" need not import this name.
    """


#: What may follow a selector inside a requirement ID it selects: the ``-``
#: before the next ID component, or a sub-item letter. Anchoring at ``-`` alone
#: is what keeps one file ID out of another's requirements — a bare
#: ``startswith`` made ``CS`` collect all sixteen of CSB's gaps and ``MS``
#: collect MSM's and none of its own, and AR/ARCH, BT/BTND, BT/BTC and DR/DRPT
#: are the same shape. But the index carries an optional sub-item letter
#: (``_SUFFIX`` in ``schema/ids.py``), so ``-`` alone also hid ``VP-12-002c``
#: from the selector ``VP-12-002``. A single letter cannot reinstate the file-ID
#: over-match: ``CSB-16-001`` leaves ``B-16-001``, which neither branch matches
#: whole. Upper-case, because every argument to :func:`_selects` already is.
#: Not optional: an empty remainder means the selector *is* the ID, which
#: :func:`_selects` has already answered before it reaches this pattern.
_CONTINUATION = re.compile(r"-.*|[A-Z]")


def _selects(spec_id: str, file_id: str, selector: str) -> bool:
    """Whether *selector* names *file_id*, the requirement, or an ID prefix.

    Every argument is already upper-cased. A selector selects a requirement
    whose ID it equals, or whose ID it is a component- or sub-item-boundary
    prefix of (:data:`_CONTINUATION`).
    """
    if selector in (file_id, spec_id):
        return True
    if not spec_id.startswith(selector):
        return False
    return _CONTINUATION.fullmatch(spec_id[len(selector) :]) is not None


def unmatched_selectors(
    registry: SpecRegistry, selectors: tuple[str, ...]
) -> tuple[str, ...]:
    """Return the *selectors* that name no requirement in *registry*.

    A selector matching nothing is a typo, and a report that renders it as
    "no requirement is missing a story" reads as "this area is done" — the
    empty-target-set trap, here on the selection rather than the corpus
    (DF-09-009). Matching is against the whole registry, not the gap set, so
    an area that genuinely has no gaps stays distinguishable from a mistyped
    one.

    Walking the requirements is enough to key every file and group: ``SpecFile``
    validates ``groups`` non-empty and ``SpecGroup`` validates ``specs``
    non-empty (``schema/models.py``), so no file or group can exist with
    nothing under it.
    """
    known = [
        (spec.id.upper(), spec_file.id.upper())
        for spec_file in registry.files
        for group in spec_file.groups
        for spec in group.specs
    ]
    return tuple(
        selector
        for selector in selectors
        if not any(
            _selects(spec_id, file_id, selector.upper())
            for spec_id, file_id in known
        )
    )


def story_gaps(
    registry: SpecRegistry, selectors: tuple[str, ...] = ()
) -> tuple[Gap, ...]:
    """Return every protocol requirement with no story, narrowed by *selectors*.

    A selector is a spec-file ID (``CM``) or any ID prefix (``CM-23``,
    ``CM-23-004``), matched case-insensitively; an empty *selectors* selects
    every file. Gaps come back in spec-file order, then
    :data:`PRIORITY_ORDER`, then requirement-ID order, which is the order an
    area's worklist is worked in.
    """
    wanted = tuple(selector.upper() for selector in selectors)
    found: list[Gap] = []
    for spec_file in registry.files:
        for group in spec_file.groups:
            for spec in group.specs:
                if spec.kind != SpecKind.PROTOCOL or spec.stories:
                    continue
                if wanted and not any(
                    _selects(spec.id.upper(), spec_file.id.upper(), selector)
                    for selector in wanted
                ):
                    continue
                found.append(
                    Gap(
                        spec_id=spec.id,
                        file_id=spec_file.id,
                        priority=spec.priority,
                        suppressed=(
                            LintWarningCode.MISSING_STORY_REFERENCE
                            in set(spec.lint_suppress or [])
                        ),
                    )
                )
    return tuple(
        sorted(
            found,
            key=lambda gap: (
                gap.file_id,
                PRIORITY_ORDER.index(gap.priority),
                gap.spec_id,
            ),
        )
    )


def _priority_counts(gaps: tuple[Gap, ...]) -> str:
    counts: Counter[RFC2119Priority] = Counter(gap.priority for gap in gaps)
    return ", ".join(
        f"{priority.value} {counts[priority]}"
        for priority in PRIORITY_ORDER
        if counts[priority]
    )


def _by_file(
    gaps: tuple[Gap, ...],
) -> list[tuple[str, tuple[Gap, ...]]]:
    """``(file_id, its gaps)`` in first-seen order; *gaps* is already sorted."""
    grouped: dict[str, list[Gap]] = {}
    for gap in gaps:
        grouped.setdefault(gap.file_id, []).append(gap)
    return [(file_id, tuple(found)) for file_id, found in grouped.items()]


def summary_lines(gaps: tuple[Gap, ...]) -> list[str]:
    """One line per spec file: its total, its priorities, its suppressions."""
    if not gaps:
        return ["No kind: protocol requirement is missing a story."]
    lines: list[str] = []
    for file_id, in_file in _by_file(gaps):
        suppressed = sum(1 for gap in in_file if gap.suppressed)
        tail = f", {suppressed} suppressed" if suppressed else ""
        lines.append(
            f"{file_id:<8} {len(in_file):>4} without a story "
            f"({_priority_counts(in_file)}{tail})"
        )
    lines.append(
        f"{len(gaps)} requirement(s) in {len({g.file_id for g in gaps})} "
        f"spec file(s); {sum(1 for g in gaps if g.suppressed)} carry "
        f"{LintWarningCode.MISSING_STORY_REFERENCE.value}."
    )
    return lines


def listing_lines(gaps: tuple[Gap, ...]) -> list[str]:
    """The worklist: each requirement under its spec file and priority."""
    if not gaps:
        return ["No kind: protocol requirement is missing a story."]
    lines: list[str] = []
    for file_id, in_file in _by_file(gaps):
        lines.append(f"{file_id} ({len(in_file)})")
        for priority in PRIORITY_ORDER:
            at_priority = [g for g in in_file if g.priority == priority]
            if not at_priority:
                continue
            lines.append(f"  {priority.value} ({len(at_priority)})")
            lines.extend(
                f"    {gap.spec_id}"
                + (f" {SUPPRESSED_MARK}" if gap.suppressed else "")
                for gap in at_priority
            )
    lines.extend(summary_lines(gaps)[-1:])
    return lines


def gap_report(
    registry: SpecRegistry,
    selectors: tuple[str, ...] = (),
    *,
    detail: bool = False,
) -> list[str]:
    """Return the report's lines: the worklist when *detail*, else summaries.

    Raises:
        UnknownSelector: If a selector names nothing in *registry*, every such
            selector named. Reporting a typo as an empty gap set would tell
            the reader its area was done (:func:`unmatched_selectors`).
    """
    unknown = unmatched_selectors(registry, selectors)
    if unknown:
        raise UnknownSelector(
            f"no spec file or requirement ID matches {', '.join(unknown)}; "
            "a selector is a spec-file ID (CM) or a requirement-ID prefix "
            "(CM-23)"
        )
    gaps = story_gaps(registry, selectors)
    return listing_lines(gaps) if detail else summary_lines(gaps)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``uv run story-gaps [--list] [SELECTOR ...]``.

    Returns ``0`` with the report, or ``2`` naming each selector that matches
    nothing — the same exit code ``spec-dump`` gives an unknown selector
    value (SR-07-011), so one mistyped area reads as an error, never as a
    clean area.
    """
    parser = argparse.ArgumentParser(
        prog="story-gaps",
        description=(
            "List the kind: protocol requirements with no stories: field, "
            "grouped by spec file and priority (TRACE-03-004)."
        ),
    )
    parser.add_argument(
        "selector",
        nargs="*",
        help=(
            "A spec-file ID (CM) or requirement-ID prefix (CM-23) to narrow "
            "the report to. Repeatable; no selector reports every file."
        ),
    )
    parser.add_argument(
        "--list",
        dest="detail",
        action="store_true",
        help=(
            "Print each requirement, not one summary line per spec file. "
            "This is the worklist an area's drafting task reads."
        ),
    )
    parser.add_argument(
        "--spec-dir",
        type=Path,
        default=None,
        help="Directory holding the spec YAML files; defaults to specs/.",
    )
    args = parser.parse_args(argv)
    spec_dir = args.spec_dir or repo_root() / "specs"
    registry = load_registry(spec_dir)
    try:
        lines = gap_report(registry, tuple(args.selector), detail=args.detail)
    except UnknownSelector as exc:
        print(f"story-gaps: {exc}", file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    return 0


__all__ = [
    "PRIORITY_ORDER",
    "SUPPRESSED_MARK",
    "Gap",
    "UnknownSelector",
    "gap_report",
    "listing_lines",
    "main",
    "story_gaps",
    "summary_lines",
    "unmatched_selectors",
]


if __name__ == "__main__":
    sys.exit(main())
