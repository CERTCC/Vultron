"""The two selection stages — eligibility, then fit.

Requirements: PAD-15-001 (two stages), PAD-15-002 (homogeneous by workflow),
PAD-15-003/004 (Schedule tier ordering and exclusion), PAD-15-005 (size budget),
PAD-15-006 (per-candidate rejection reasons), PAD-15-007 (hints, not verdicts).

Selection used to be one stage: filter an Epic's sub-issues for *eligibility*
(open, unassigned, unblocked, leaf) and take the first five in GitHub order.
Every candidate that cleared eligibility was proposed, so an ``Idea``, a
``Concern`` scheduled ``Someday`` and two ``size:L`` Tasks all looked like
equally good members of one bundle. This module adds the missing second stage.

Everything here is a pure function over ``Candidate`` records, so the rules are
testable without the network.
"""

from __future__ import annotations

import re
from collections import Counter

from vultron.metadata.planning.bundle_fit.model import (
    DEFAULT_BUDGET,
    DEFAULT_MAX_MEMBERS,
    EXCLUDED_TIERS,
    KNOWN_TIERS,
    PLANNING_PROJECT_NUMBER,
    Bundle,
    Candidate,
    Rejection,
    schedule_rank,
)

# A fully-qualified spec requirement ID (CS-23-001, DEMOCI-11-002).
_SPEC_ID_RE = re.compile(r"\b[A-Z]{2,8}-\d{2}-\d{3}\b")
# A repo-relative path with an extension (vultron/core/x.py, specs/outbox.yaml).
_PATH_RE = re.compile(r"\b(?:[\w.-]+/)+[\w.-]+\.\w{2,5}\b")


def eligibility(
    candidates: list[Candidate],
) -> tuple[list[Candidate], list[Rejection]]:
    """Stage 1 — can this issue be worked at all? (unchanged behaviour)."""
    kept: list[Candidate] = []
    rejected: list[Rejection] = []
    for c in candidates:
        if c.state != "OPEN":
            rejected.append(
                Rejection(c.number, "eligibility", f"closed ({c.state})")
            )
        elif c.assignees:
            rejected.append(
                Rejection(
                    c.number,
                    "eligibility",
                    f"assigned to {', '.join(c.assignees)}",
                )
            )
        elif "stale-claim" in c.labels:
            rejected.append(
                Rejection(c.number, "eligibility", "has stale-claim label")
            )
        elif c.open_blockers:
            blockers = ", ".join(f"#{n}" for n in c.open_blockers)
            rejected.append(
                Rejection(c.number, "eligibility", f"blocked by {blockers}")
            )
        elif c.child_count:
            rejected.append(
                Rejection(
                    c.number,
                    "eligibility",
                    f"has {c.child_count} children — not a leaf",
                )
            )
        else:
            kept.append(c)
    return kept, rejected


def effective_schedule(
    candidate: Candidate, epic_schedule: str | None
) -> str | None:
    """The tier that governs this candidate.

    PAD-03-001 puts Schedule on "the relevant Epic **or** Issue", so a leaf
    that states no tier of its own is governed by its Epic's tier. An explicit
    leaf tier always wins, including when it is worse than the Epic's.
    """
    return candidate.schedule or epic_schedule


def coherence_hints(members: list[Candidate]) -> list[str]:
    """Structured signals that two or more members share subject matter.

    Hints, not verdicts: shared spec IDs, file paths and topic labels are
    evidence an agent can weigh when it states the bundle's shared design idea.
    Prose-word overlap is deliberately not measured — that is the superficial
    theme cut ``calve-epics`` forbids.
    """
    if len(members) < 2:
        return []

    hints: list[str] = []
    for label, pattern in (("spec", _SPEC_ID_RE), ("path", _PATH_RE)):
        counts: Counter[str] = Counter()
        for member in members:
            # Per member, not per occurrence: one title citing the same path
            # twice must not read as two members citing it.
            counts.update(set(pattern.findall(member.title)))
        for token, count in sorted(counts.items()):
            if count > 1:
                hints.append(f"{count} members cite {label} {token}")

    label_counts: Counter[str] = Counter()
    for member in members:
        label_counts.update(set(member.topic_labels))
    for name, count in sorted(label_counts.items()):
        if count > 1:
            hints.append(f"{count} members share label {name}")

    return hints


def _disqualifier(candidate: Candidate, tier: str | None) -> str | None:
    """Why ``candidate`` belongs in no bundle at all, or ``None`` if it may.

    Every reason here is disqualifying regardless of which workflow the bundle
    settles on, which is why they are decided before priority ordering rather
    than inside the budget loop.
    """
    if candidate.workflow is None:
        return (
            f"unroutable issue type {candidate.issue_type or '(none)'} — "
            "no skill executes it"
        )
    if tier is not None and tier not in KNOWN_TIERS:
        # Ranking an unrecognised tier would make it indistinguishable from an
        # unset one, which is how a renamed board option turns into a silent
        # ordering change.
        return (
            f"unrecognised Schedule tier {tier!r} — Project "
            f"#{PLANNING_PROJECT_NUMBER}'s options may have changed; "
            "refresh board-ids.json and update SCHEDULE_ORDER"
        )
    if tier in EXCLUDED_TIERS:
        return f"below tier (Schedule={tier})"
    if candidate.unbundlable:
        # Refused outright rather than weighted. A weight says "fits alongside
        # something smaller", and this band exists precisely because a PR that
        # size already exhausts the review budget on its own — findings per
        # 1000 diff lines fall by half above it.
        return (
            f"{candidate.size_label} is at the review ceiling on its own — "
            "work it alone, or decompose it first"
        )
    return None


def select_bundle(
    candidates: list[Candidate],
    *,
    epic: int | None = None,
    epic_schedule: str | None = None,
    workflow: str | None = None,
    budget: int = DEFAULT_BUDGET,
    max_members: int = DEFAULT_MAX_MEMBERS,
) -> Bundle:
    """Run both stages and return the proposed bundle.

    Every input candidate ends up either in ``members`` or in ``rejected`` with
    a stage and a reason — a candidate is never dropped silently.
    """
    bundle = Bundle(epic=epic, epic_schedule=epic_schedule, budget=budget)
    eligible, bundle.rejected = eligibility(candidates)

    # Fit, part 1: reject what no skill can execute, then what a human has
    # already deprioritised. Both are disqualifying regardless of the bundle's
    # eventual workflow.
    routable: list[tuple[Candidate, str | None]] = []
    for c in eligible:
        tier = effective_schedule(c, epic_schedule)
        reason = _disqualifier(c, tier)
        if reason is not None:
            bundle.rejected.append(Rejection(c.number, "fit", reason))
        else:
            routable.append((c, tier))

    # Priority order: Schedule tier first, then input order for ties. Sub-issue
    # list order is only a tie-breaker, never the priority signal itself.
    ranked = sorted(
        enumerate(routable),
        key=lambda pair: (schedule_rank(pair[1][1]), pair[0]),
    )

    # Fit, part 2: a bundle is homogeneous by workflow. Absent an explicit
    # request, the highest-priority candidate chooses it.
    if workflow is None and ranked:
        workflow = ranked[0][1][0].workflow
    bundle.workflow = workflow

    # Fit, part 3: fill to the budget. A candidate that does not fit does not
    # end the scan — a smaller one behind it may still fit.
    weight = 0
    for _, (c, _tier) in ranked:
        if c.workflow != workflow:
            bundle.rejected.append(
                Rejection(
                    c.number,
                    "fit",
                    f"targets /{c.workflow}, not /{workflow}",
                )
            )
        elif len(bundle.members) >= max_members:
            bundle.rejected.append(
                Rejection(
                    c.number, "fit", f"member ceiling of {max_members} reached"
                )
            )
        elif weight + c.weight > budget:
            unsized = "" if c.sized else " (unsized, counted as largest)"
            bundle.rejected.append(
                Rejection(
                    c.number,
                    "fit",
                    f"exceeds size budget — weight {c.weight}{unsized} would "
                    f"take the bundle past {budget}",
                )
            )
        else:
            bundle.members.append(c)
            weight += c.weight

    bundle.hints = coherence_hints(bundle.members)
    return bundle
