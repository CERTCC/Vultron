"""Two-stage bundle selection for the ``propose-bundle`` skill.

Requirements: ISSUE-3482; PAD-03-001 (Schedule is the priority authority),
PAD-05 (``size:`` labels), PAD-15 (bundle selection and execution).

Selection used to be one stage: filter an Epic's sub-issues for *eligibility*
(open, unassigned, unblocked, leaf) and take the first five in GitHub order.
Every candidate that cleared eligibility was proposed, so an ``Idea``, a
``Concern`` scheduled ``Someday`` and two ``size:L`` Tasks all looked like
equally good members of one bundle.

This module adds the missing second stage — **fit** — over three signals that
already exist on every candidate:

1. ``issueType`` decides which skill can execute the issue at all, so a bundle
   is homogeneous by workflow (``work-issue`` routes Task/Feature to ``build``,
   Bug to ``bugfix``, Idea/Concern/Epic to ``plan-issue``).
2. The ``Schedule`` field on Project #24 is the authoritative priority ordering
   (PAD-03-001) — sub-issue list order is manual drag-order and means nothing.
   A leaf with no Schedule of its own inherits its Epic's tier.
3. ``size:`` labels weigh a candidate's effort, and the bundle's total weight is
   capped, because a bundle is implemented as **one PR** closing every member.

Thematic coherence is deliberately *not* scored here. ``calve-epics`` requires
cutting by design grain and warns that cutting by "superficial theme" produces
plausible-looking but wrong work units, so this module only emits structured
**hints** (shared spec IDs, shared file paths, shared topic labels) and leaves
the grain call to the agent, which must state the bundle's single shared design
idea in one sentence.

CLI: ``bash .agents/skills/shared/query-epic-subissues.sh <EPIC> | uv run bundle-fit``

    --workflow W        force the target skill instead of inferring it
    --budget N          total size-weight ceiling (default: 6)
    --max-members N     member-count ceiling (default: 5)
    --project-number N  planning board to read Schedule from (default: 24)
    --json              emit machine-readable JSON instead of the text report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

# Effort weights from the PAD-05 label taxonomy. An unlabelled candidate counts
# as the largest size rather than as zero: size:L is unbounded above (301+ diff
# lines), so "no label" is an unmeasured issue, not a small one.
SIZE_WEIGHTS: dict[str, int] = {"size:S": 1, "size:M": 2, "size:L": 3}
UNSIZED_WEIGHT = 3

# A bundle becomes one PR, so the budget is a review budget.
DEFAULT_BUDGET = 6
DEFAULT_MAX_MEMBERS = 5

# Project #24's Schedule tiers, best first. Someday is explicit deprioritisation
# by a human, so it is never bundled; an unset tier is merely unstated and falls
# back to the Epic's tier.
SCHEDULE_ORDER: tuple[str, ...] = ("Now", "Next", "Later", "Someday")
EXCLUDED_TIERS: frozenset[str] = frozenset({"Someday"})
PLANNING_PROJECT_NUMBER = 24

# Which skill executes which issue type — mirrors work-issue's routing table.
WORKFLOW_BY_TYPE: dict[str, str] = {
    "Task": "build",
    "Feature": "build",
    "Bug": "bugfix",
    "Idea": "plan-issue",
    "Concern": "plan-issue",
    "Epic": "plan-issue",
}

# Labels that say nothing about what an issue is *about*, so they are never
# coherence evidence.
_NON_TOPIC_LABELS = frozenset(
    {
        "stale-claim",
        "needs-rebase",
        "needs-triage",
        "needs-info",
        "needs-decomposition",
    }
)

# A fully-qualified spec requirement ID (CS-23-001, DEMOCI-11-002).
_SPEC_ID_RE = re.compile(r"\b[A-Z]{2,8}-\d{2}-\d{3}\b")
# A repo-relative path with an extension (vultron/core/x.py, specs/outbox.yaml).
_PATH_RE = re.compile(r"\b(?:[\w.-]+/)+[\w.-]+\.\w{2,5}\b")


def schedule_rank(schedule: str | None) -> int:
    """Sort key for a Schedule tier; unset sorts after every named tier."""
    if schedule in SCHEDULE_ORDER:
        return SCHEDULE_ORDER.index(schedule)
    return len(SCHEDULE_ORDER)


@dataclass
class Candidate:
    """One leaf sub-issue of an Epic, with the signals fit needs."""

    number: int
    title: str = ""
    state: str = "OPEN"
    issue_type: str | None = None
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    open_blockers: list[int] = field(default_factory=list)
    child_count: int = 0
    schedule: str | None = None

    @property
    def weight(self) -> int:
        """Effort weight from the ``size:`` labels (largest one wins)."""
        weights = [
            SIZE_WEIGHTS[label]
            for label in self.labels
            if label in SIZE_WEIGHTS
        ]
        return max(weights) if weights else UNSIZED_WEIGHT

    @property
    def sized(self) -> bool:
        return any(label in SIZE_WEIGHTS for label in self.labels)

    @property
    def workflow(self) -> str | None:
        """The skill that can execute this issue, or ``None`` if unroutable."""
        return WORKFLOW_BY_TYPE.get(self.issue_type or "")

    @property
    def topic_labels(self) -> list[str]:
        return [
            label
            for label in self.labels
            if label not in SIZE_WEIGHTS and label not in _NON_TOPIC_LABELS
        ]


@dataclass
class Rejection:
    """A candidate that is not in the bundle, and why.

    ``stage`` separates "cannot be worked at all" (eligibility) from "could be
    worked, but not in this bundle" (fit). The old report collapsed the two, so
    a candidate held back for size or tier looked indistinguishable from one
    that was blocked or already claimed.
    """

    number: int
    stage: str  # "eligibility" | "fit"
    reason: str


@dataclass
class Bundle:
    """A proposed bundle: members, per-candidate rejections, and hints."""

    workflow: str | None = None
    members: list[Candidate] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    epic: int | None = None
    epic_schedule: str | None = None
    budget: int = DEFAULT_BUDGET

    @property
    def weight(self) -> int:
        return sum(c.weight for c in self.members)

    @property
    def command(self) -> str | None:
        """The command the user runs to execute this bundle."""
        if not self.members or not self.workflow:
            return None
        return f"/{self.workflow} " + " ".join(
            str(c.number) for c in self.members
        )


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
        if c.workflow is None:
            bundle.rejected.append(
                Rejection(
                    c.number,
                    "fit",
                    f"unroutable issue type {c.issue_type or '(none)'} — "
                    "no skill executes it",
                )
            )
        elif tier in EXCLUDED_TIERS:
            bundle.rejected.append(
                Rejection(c.number, "fit", f"below tier (Schedule={tier})")
            )
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


def _schedule_of(node: dict, project_number: int) -> str | None:
    """Read the Schedule single-select value from one project item set."""
    for item in (node.get("projectItems") or {}).get("nodes") or []:
        if ((item.get("project") or {}).get("number")) != project_number:
            continue
        value = item.get("fieldValueByName")
        if value and value.get("name"):
            return str(value["name"])
    return None


def parse_graphql(
    payload: dict, project_number: int = PLANNING_PROJECT_NUMBER
) -> tuple[int | None, str | None, list[Candidate]]:
    """Parse ``query-epic-subissues.sh`` output into Epic number, tier, leaves."""
    issue = ((payload.get("data") or {}).get("repository") or {}).get(
        "issue"
    ) or {}
    epic = issue.get("number")
    epic_schedule = _schedule_of(issue, project_number)

    candidates: list[Candidate] = []
    for node in (issue.get("subIssues") or {}).get("nodes") or []:
        candidates.append(
            Candidate(
                number=node["number"],
                title=node.get("title") or "",
                state=node.get("state") or "OPEN",
                issue_type=(node.get("issueType") or {}).get("name"),
                labels=[
                    label["name"]
                    for label in (node.get("labels") or {}).get("nodes") or []
                ],
                assignees=[
                    a["login"]
                    for a in (node.get("assignees") or {}).get("nodes") or []
                ],
                open_blockers=[
                    b["number"]
                    for b in (node.get("blockedBy") or {}).get("nodes") or []
                    if b.get("state") == "OPEN"
                ],
                child_count=(node.get("subIssues") or {}).get("totalCount")
                or 0,
                schedule=_schedule_of(node, project_number),
            )
        )
    return epic, epic_schedule, candidates


def _render(bundle: Bundle) -> str:
    """Human-readable proposal, including the reasoning behind each choice."""
    lines: list[str] = []
    epic = f"#{bundle.epic}" if bundle.epic else "(unknown Epic)"
    tier = bundle.epic_schedule or "unset"
    if bundle.members:
        lines.append(
            f"Proposed /{bundle.workflow} bundle for Epic {epic} "
            f"(Epic Schedule={tier}) — size {bundle.weight}/{bundle.budget}:"
        )
        for i, c in enumerate(bundle.members, 1):
            size = next(
                (label for label in c.labels if label in SIZE_WEIGHTS),
                "unsized",
            )
            sched = c.schedule or f"inherits {tier}"
            lines.append(
                f"  {i}. #{c.number} [{c.issue_type} {size} "
                f"Schedule={sched} weight={c.weight}] {c.title}"
            )
        lines.append("")
        lines.append(f"Run: {bundle.command}")
    else:
        lines.append(f"No bundle for Epic {epic} — no candidate cleared fit.")

    if bundle.hints:
        lines.append("")
        lines.append("Coherence hints (evidence, not a verdict):")
        lines.extend(f"  - {h}" for h in bundle.hints)
    lines.append("")
    lines.append(
        "State the single design idea these members share in one sentence. "
        "If a member needs a different sentence, drop it from the bundle."
    )

    for stage, heading in (
        ("fit", "Held back by fit (workable, but not in this bundle)"),
        ("eligibility", "Not workable yet"),
    ):
        rows = [r for r in bundle.rejected if r.stage == stage]
        # Closed sub-issues stay in `rejected` so the API accounts for every
        # candidate, but a long Epic has dozens of them and listing finished
        # work under "not workable" buries the rows a human can act on.
        rows = [r for r in rows if not r.reason.startswith("closed")]
        if rows:
            lines.append("")
            lines.append(f"{heading}:")
            lines.extend(f"  - #{r.number}: {r.reason}" for r in rows)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: GraphQL JSON on stdin, bundle proposal on stdout."""
    parser = argparse.ArgumentParser(
        description="Select a fit-checked work bundle from an Epic's leaf issues."
    )
    parser.add_argument(
        "--workflow", choices=sorted(set(WORKFLOW_BY_TYPE.values()))
    )
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--max-members", type=int, default=DEFAULT_MAX_MEMBERS)
    parser.add_argument(
        "--project-number", type=int, default=PLANNING_PROJECT_NUMBER
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"❌ stdin is not valid JSON: {exc}", file=sys.stderr)
        return 2

    epic, epic_schedule, candidates = parse_graphql(
        payload, args.project_number
    )
    if not candidates:
        print(
            f"❌ no sub-issues found for Epic #{epic} — is the number right?",
            file=sys.stderr,
        )
        return 1

    bundle = select_bundle(
        candidates,
        epic=epic,
        epic_schedule=epic_schedule,
        workflow=args.workflow,
        budget=args.budget,
        max_members=args.max_members,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "epic": bundle.epic,
                    "epic_schedule": bundle.epic_schedule,
                    "workflow": bundle.workflow,
                    "command": bundle.command,
                    "budget": bundle.budget,
                    "weight": bundle.weight,
                    "members": [
                        {
                            "number": c.number,
                            "title": c.title,
                            "issue_type": c.issue_type,
                            "weight": c.weight,
                            "sized": c.sized,
                            "schedule": effective_schedule(
                                c, bundle.epic_schedule
                            ),
                        }
                        for c in bundle.members
                    ],
                    "rejected": [
                        {
                            "number": r.number,
                            "stage": r.stage,
                            "reason": r.reason,
                        }
                        for r in bundle.rejected
                    ],
                    "hints": bundle.hints,
                },
                indent=2,
            )
        )
    else:
        print(_render(bundle))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
