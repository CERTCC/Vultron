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
"""Render a :class:`ThemeFitReport` as a Markdown report body.

The same text serves the terminal and the standing "Theme fit report" Issue
the daily Action rewrites, so it is plain GitHub-flavored Markdown with no
HTML beyond what GitHub renders.
"""

from __future__ import annotations

from vultron.metadata.planning.theme_fit.model import (
    FindingKind,
    ThemeFitReport,
    TierCoherence,
)

TITLE = "Theme fit report"
"""The report's top heading."""

GITHUB_BODY_LIMIT = 65536
"""The most characters GitHub accepts in an Issue body."""


WORD_JOINER = "\u2060"
"""An invisible character that keeps ``@`` and the name after it apart."""


def _no_mentions(text: str) -> str:
    """*text* with a :data:`WORD_JOINER` after each ``@``.

    An Issue title can hold an ``@word``, such as ``@context``. Posted in an
    Issue body, it would notify whoever owns that name. GitHub reads mentions
    from the rendered text, where an HTML entity is already a plain ``@``
    again, and shows an entity literally inside a code span; an invisible
    character between ``@`` and the name breaks the mention in both places.
    """
    return text.replace("@", "@" + WORD_JOINER)


def _share(row: TierCoherence) -> str:
    share = row.share
    return "n/a" if share is None else f"{share:.0%}"


def _total(rows: tuple[TierCoherence, ...]) -> TierCoherence:
    return TierCoherence(
        tier="All tiers",
        epics=sum(r.epics for r in rows),
        children=sum(r.children for r in rows),
        matching=sum(r.matching for r in rows),
    )


def render_coherence(report: ThemeFitReport) -> list[str]:
    """The coherence-per-tier table, one Markdown line per element."""
    lines = [
        "| Tier | Epics | Children | Matching | Coherence |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in (*report.coherence, _total(report.coherence)):
        lines.append(
            f"| {row.tier} | {row.epics} | {row.children} | {row.matching} "
            f"| {_share(row)} |"
        )
    return lines


def _render(report: ThemeFitReport, per_kind: int | None) -> str:
    """The report, listing at most *per_kind* findings under each kind."""
    total = len(report.findings)
    lines = [
        f"# {TITLE}",
        "",
        f"{report.issues} open Issues checked; {total} finding(s).",
        "",
        "## Coherence per Schedule tier",
        "",
        "A child is an open non-Epic Issue, in its nearest Epic's tier. It",
        "matches when it carries exactly one theme and its Epic carries it.",
        "",
        *render_coherence(report),
        "",
        "## Findings",
        "",
        "| Kind | Rule | Count |",
        "|---|---|---:|",
    ]
    for kind in FindingKind:
        lines.append(
            f"| {kind.heading} | {kind.rule} | {len(report.of_kind(kind))} |"
        )
    for kind in FindingKind:
        found = report.of_kind(kind)
        if not found:
            continue
        shown = found if per_kind is None else found[:per_kind]
        lines += ["", f"### {kind.heading} ({len(found)})", ""]
        lines += [
            f"- #{f.number} {_no_mentions(f.title)} — {f.detail}"
            for f in shown
        ]
        if len(shown) < len(found):
            lines.append(
                f"- … and {len(found) - len(shown)} more; run "
                "`uv run theme-fit` for the full list"
            )
    return "\n".join(lines) + "\n"


def render_markdown(report: ThemeFitReport, limit: int | None = None) -> str:
    """The whole report: summary, coherence per tier, then each finding.

    Args:
        report: The report to render.
        limit: The most characters the text may have, such as
            :data:`GITHUB_BODY_LIMIT` for an Issue body. When the full list
            is longer, each kind lists only its first findings, the same
            number for every kind, and says how many it left out. The
            summary and coherence tables always appear in full.

    Raises:
        ValueError: If even the summary alone is longer than *limit*.
    """
    full = _render(report, None)
    if limit is None or len(full) <= limit:
        return full
    most = max((len(report.of_kind(k)) for k in FindingKind), default=0)
    low, high = 0, most
    while low < high:
        mid = (low + high + 1) // 2
        if len(_render(report, mid)) <= limit:
            low = mid
        else:
            high = mid - 1
    text = _render(report, low)
    if len(text) > limit:
        raise ValueError(
            f"the report summary alone is {len(text)} characters; "
            f"the limit is {limit}"
        )
    return text
