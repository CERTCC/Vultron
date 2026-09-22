"""The vocabulary of bundle selection: tiers, weights, and the three records.

Requirements: PAD-03-001 (Schedule is the priority authority), PAD-05 (``size:``
labels), PAD-15 (bundle selection and execution).

This module holds the constants the rest of the subpackage reads and the three
dataclasses it passes around. It deliberately contains no policy: deciding which
candidates form a bundle is ``select``'s job, reading a GraphQL payload is
``parse``'s, and reporting is ``render``'s.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Effort weights from the PAD-05 label taxonomy. An unlabelled candidate counts
# as the largest size rather than as zero: size:L is unbounded above (301+ diff
# lines), so "no label" is an unmeasured issue, not a small one.
SIZE_WEIGHTS: dict[str, int] = {"size:S": 1, "size:M": 2, "size:L": 3}
UNSIZED_WEIGHT = 3

# A bundle becomes one PR, so the budget is a review budget.
DEFAULT_BUDGET = 6
DEFAULT_MAX_MEMBERS = 5

# Project #24's Schedule tiers, best first. The board offers six options
# (`.agents/skills/shared/board-ids.json`), and `check-priority-status` names the
# canonical order Focus -> Now -> Next -> Later -> Someday.
#
# Every option the board offers MUST appear here or in EXCLUDED_TIERS.
# `schedule_rank` ranks anything it does not recognise *last*, so omitting a real
# tier silently turns the board's highest priority into its lowest — which is how
# `Focus` came to rank below `Someday` (ISSUE-3482 follow-up).
SCHEDULE_ORDER: tuple[str, ...] = ("Focus", "Now", "Next", "Later", "Someday")

# Someday is explicit deprioritisation by a human and Completed is finished work,
# so neither is ever bundled. An unset tier is merely unstated and falls back to
# the Epic's tier.
EXCLUDED_TIERS: frozenset[str] = frozenset({"Someday", "Completed"})

# The board's full option set. `board-id.sh` documents these options as
# server-generated and MUTABLE, so a value outside this set means the board was
# edited; it is reported rather than silently ranked as though it were unset.
KNOWN_TIERS: frozenset[str] = frozenset(SCHEDULE_ORDER) | EXCLUDED_TIERS

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
NON_TOPIC_LABELS = frozenset(
    {
        "stale-claim",
        "needs-rebase",
        "needs-triage",
        "needs-info",
        "needs-decomposition",
    }
)


def schedule_rank(schedule: str | None) -> int:
    """Sort key for a Schedule tier; unset sorts after every named tier.

    Anything unrecognised also sorts last, which is why every board option must
    appear in ``SCHEDULE_ORDER`` or ``EXCLUDED_TIERS`` — an omitted tier is
    ranked worst rather than rejected. ``select_bundle`` rejects a tier outside
    ``KNOWN_TIERS`` before it ever reaches this function.
    """
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
    def size_label(self) -> str:
        """The ``size:`` label that produced ``weight``.

        Derived from the same ``max`` decision as ``weight`` so a candidate
        carrying two size labels cannot be reported as ``size:S weight=3``.
        """
        sized = [label for label in self.labels if label in SIZE_WEIGHTS]
        if not sized:
            return "unsized"
        return max(sized, key=lambda label: SIZE_WEIGHTS[label])

    @property
    def workflow(self) -> str | None:
        """The skill that can execute this issue, or ``None`` if unroutable."""
        return WORKFLOW_BY_TYPE.get(self.issue_type or "")

    @property
    def topic_labels(self) -> list[str]:
        return [
            label
            for label in self.labels
            if label not in SIZE_WEIGHTS and label not in NON_TOPIC_LABELS
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
