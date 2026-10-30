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
"""The branch-point table of the demo scenario tree (DEMOCI-11-013).

Every decision a presenter can make in the demo is defined here, exactly once:
the role that decides, the prompt the presenter sees, and the choices, each
with a label and the one trigger the deciding role calls. The prompt and the
labels live nowhere else (not on ``@scenario``, not in ``ui/``), so the
offline and live forms of the demo cannot disagree about them.

Each registered scenario then declares its full path through this table on
``@scenario(path=...)`` (DEMOCI-11-014), and
:func:`vultron.demo.scenario.tree.build_scenario_tree` merges the paths into
the tree.

Two rules shape every entry:

- **A choice is a trigger, never a non-action.** It names the deciding role's
  *next* trigger on that path; steps by other roles may run between the
  decision and that trigger. "Carry on" is therefore written as what the role
  does next ("Report the fix ready"), not as "invite nobody".
- **A branch point is a decision, not a tree node.** One entry labels every
  node where that decision is made, so a decision that recurs on one path, or
  appears in two families (``owner-keep-case``), is still one entry.

Rules: ``notes/demo-scenario-registry.md`` § "The path and the branch-point
table"; remaining design: ``notes/demo-scenario-tree.md``; decision records
ADR-0098 and ADR-0104.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from vultron.enums.roles import CVDRole
from vultron.errors import DemoScenarioRegistryError

#: Identifier spelling for branch points and choices: lowercase alphanumerics
#: separated by single hyphens, the same grammar as scenario names, so an id
#: can appear in a URL fragment or a JSON key without escaping.
_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\Z")

#: A trigger verb: the last path segment of
#: ``/actors/{id}/trigger/{verb}`` or ``/actors/{id}/demo/{verb}``. Whether the
#: verb is actually mounted is a test against the routers, not a check here.
_VERB_RE = _ID_RE


def _require_id(kind: str, value: object) -> None:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise DemoScenarioRegistryError(
            f"{kind} id {value!r} is not a valid identifier; expected "
            "lowercase alphanumerics separated by single hyphens."
        )


def _require_text(owner: str, field_name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DemoScenarioRegistryError(
            f"{owner} has an empty {field_name}; the presenter has nowhere "
            "else to read it."
        )
    if value != value.strip() or len(value.splitlines()) > 1:
        raise DemoScenarioRegistryError(
            f"{owner} has a {field_name} with surrounding whitespace or a "
            f"line break ({value!r}); keep it to one stripped line."
        )


@dataclass(frozen=True, slots=True)
class Choice:
    """One choice at a branch point: a label and exactly one trigger."""

    #: Identifier, unique within its branch point, e.g. ``"report-fix-ready"``.
    id: str
    #: Presenter-facing label, written as what happens.
    label: str
    #: The trigger verb the branch point's role calls for this choice, e.g.
    #: ``"notify-fix-ready"``.
    trigger: str

    def __post_init__(self) -> None:
        _require_id("choice", self.id)
        _require_text(f"choice {self.id!r}", "label", self.label)
        if not isinstance(self.trigger, str) or not _VERB_RE.match(
            self.trigger
        ):
            raise DemoScenarioRegistryError(
                f"choice {self.id!r} has trigger {self.trigger!r}, which is "
                "not a trigger verb; a choice is exactly one trigger POST "
                "(DEMOCI-11-013), never a wait, a skip or a fall-through."
            )


@dataclass(frozen=True, slots=True)
class BranchPoint:
    """One decision of the scenario tree, defined once (DEMOCI-11-013)."""

    #: Identifier, unique across the table, e.g. ``"reporter-whom-to-tell"``.
    id: str
    #: The CVD role that decides here and calls the chosen trigger.
    role: CVDRole
    #: The presenter prompt, e.g. ``"As the Vendor, choose what to do next."``.
    prompt: str
    #: At least two choices, in presentation order.
    choices: tuple[Choice, ...]

    def __post_init__(self) -> None:
        _require_id("branch point", self.id)
        owner = f"branch point {self.id!r}"
        if not isinstance(self.role, CVDRole):
            raise DemoScenarioRegistryError(
                f"{owner} has role {self.role!r}, which is not a CVDRole; the "
                "harness checks the calling actor holds this role."
            )
        _require_text(owner, "prompt", self.prompt)
        if not isinstance(self.choices, tuple) or len(self.choices) < 2:
            raise DemoScenarioRegistryError(
                f"{owner} has fewer than two choices; a decision with one "
                "choice is a shared step, not a branch point."
            )
        seen: set[str] = set()
        for choice in self.choices:
            if not isinstance(choice, Choice):
                raise DemoScenarioRegistryError(
                    f"{owner} has a choice that is not a Choice: {choice!r}"
                )
            if choice.id in seen:
                raise DemoScenarioRegistryError(
                    f"{owner} declares choice {choice.id!r} twice."
                )
            seen.add(choice.id)

    def choice(self, choice_id: str) -> Choice:
        """Return the choice named *choice_id*.

        Raises:
            DemoScenarioRegistryError: If this branch point has no such choice.
        """
        for choice in self.choices:
            if choice.id == choice_id:
                return choice
        raise DemoScenarioRegistryError(
            f"branch point {self.id!r} has no choice {choice_id!r}; its "
            f"choices are {[c.id for c in self.choices]}."
        )


def build_branch_point_table(
    branch_points: Iterable[BranchPoint],
) -> Mapping[str, BranchPoint]:
    """Index *branch_points* by id, refusing a repeated id.

    Returns:
        A read-only mapping from branch-point id to branch point, in
        declaration order.

    Raises:
        DemoScenarioRegistryError: If two branch points share an id.
    """
    table: dict[str, BranchPoint] = {}
    for branch_point in branch_points:
        if branch_point.id in table:
            raise DemoScenarioRegistryError(
                f"branch point {branch_point.id!r} is defined twice; every "
                "branch point is defined exactly once (DEMOCI-11-013)."
            )
        table[branch_point.id] = branch_point
    return MappingProxyType(table)


#: The branch points of the scenario tree, in root-first order. The tree they
#: make is ``registry.scenario_tree()``; the declaration rules are in
#: ``notes/demo-scenario-registry.md`` § "The path and the branch-point table".
BRANCH_POINTS: Mapping[str, BranchPoint] = build_branch_point_table(
    (
        BranchPoint(
            id="reporter-whom-to-tell",
            role=CVDRole.REPORTER,
            prompt="As the Reporter, choose whom to tell about the vul.",
            choices=(
                Choice(
                    id="vendor",
                    label="Report it to the Vendor",
                    trigger="submit-report",
                ),
                Choice(
                    id="coordinator",
                    label="Report it to a Coordinator",
                    trigger="submit-report",
                ),
            ),
        ),
        BranchPoint(
            id="vendor-after-answer",
            role=CVDRole.VENDOR,
            prompt="As the Vendor, choose what to do next.",
            choices=(
                Choice(
                    id="report-fix-ready",
                    label="Report the fix ready",
                    trigger="notify-fix-ready",
                ),
                Choice(
                    id="invite-vendor",
                    label="Invite another Vendor",
                    trigger="invite-actor-to-case",
                ),
                Choice(
                    id="invite-coordinator",
                    label="Invite a Coordinator",
                    trigger="invite-actor-to-case",
                ),
            ),
        ),
        BranchPoint(
            id="coordinator-invite-whom",
            role=CVDRole.COORDINATOR,
            prompt="As the Coordinator, choose whom to invite to the case.",
            choices=(
                Choice(
                    id="vendor",
                    label="Invite the Vendor",
                    trigger="invite-actor-to-case",
                ),
                Choice(
                    id="coordinator",
                    label="Invite a second Coordinator",
                    trigger="invite-actor-to-case",
                ),
            ),
        ),
        BranchPoint(
            id="vendor-join",
            role=CVDRole.VENDOR,
            prompt="As the Vendor, choose whether to join the case.",
            choices=(
                Choice(
                    id="reject",
                    label="Reject the invite",
                    trigger="reject-case-invite",
                ),
                Choice(
                    id="accept",
                    label="Accept the invite",
                    trigger="accept-case-invite",
                ),
            ),
        ),
        BranchPoint(
            id="reporter-after-join",
            role=CVDRole.REPORTER,
            prompt="As the Reporter, choose what to do next.",
            choices=(
                Choice(
                    id="propose-embargo",
                    label="Propose new embargo terms",
                    trigger="propose-embargo",
                ),
                Choice(
                    id="ask-vendor",
                    label="Ask the Vendor a question",
                    trigger="add-note-to-case",
                ),
            ),
        ),
        BranchPoint(
            id="vendor-after-embargo",
            role=CVDRole.VENDOR,
            prompt="As the Vendor, choose what to do next.",
            choices=(
                Choice(
                    id="propose-revision",
                    label="Propose an embargo revision",
                    trigger="propose-embargo-revision",
                ),
                Choice(
                    id="report-fix-ready",
                    label="Report the fix ready",
                    trigger="notify-fix-ready",
                ),
            ),
        ),
        BranchPoint(
            id="coordinator-after-answer",
            role=CVDRole.COORDINATOR,
            prompt="As the Coordinator, choose what to do next.",
            choices=(
                Choice(
                    id="invite-coordinator",
                    label="Invite a second Coordinator",
                    trigger="invite-actor-to-case",
                ),
                Choice(
                    id="publish",
                    label="Publish after the Vendor's fix",
                    trigger="notify-published",
                ),
            ),
        ),
        BranchPoint(
            id="owner-keep-case",
            role=CVDRole.CASE_OWNER,
            prompt="As the case owner, choose whether to keep the case.",
            choices=(
                Choice(
                    id="keep",
                    label="Keep it: accept the Coordinator's suggestion",
                    trigger="accept-actor-recommendation",
                ),
                Choice(
                    id="offer-ownership",
                    label="Offer case ownership to the Coordinator",
                    trigger="offer-case-ownership-transfer",
                ),
            ),
        ),
    )
)


def validate_path(
    path: object, table: Mapping[str, BranchPoint] = BRANCH_POINTS
) -> tuple[tuple[str, str], ...]:
    """Check *path* names only branch points and choices in *table*.

    A branch point may occur more than once on one path (DEMOCI-11-022).

    Args:
        path: Ordered ``(branch point id, choice id)`` pairs from the root.
        table: The branch-point table to resolve against.

    Returns:
        *path* as a tuple of ``(str, str)`` tuples.

    Raises:
        DemoScenarioRegistryError: If *path* is empty or malformed, or names an
            unknown branch point or choice.
    """
    if isinstance(path, (str, bytes)) or not isinstance(path, Iterable):
        raise DemoScenarioRegistryError(
            f"path {path!r} is not a sequence of (branch point, choice) pairs."
        )
    steps = tuple(path)
    if not steps:
        raise DemoScenarioRegistryError(
            "path is empty; every scenario declares its full path from the "
            "root of the tree (DEMOCI-11-014)."
        )
    normalized: list[tuple[str, str]] = []
    for step in steps:
        if (
            not isinstance(step, tuple)
            or len(step) != 2
            or not all(isinstance(part, str) for part in step)
        ):
            raise DemoScenarioRegistryError(
                f"path step {step!r} is not a (branch point, choice) pair."
            )
        branch_point_id, choice_id = step
        branch_point = table.get(branch_point_id)
        if branch_point is None:
            raise DemoScenarioRegistryError(
                f"path names unknown branch point {branch_point_id!r}; known "
                f"branch points are {sorted(table)}."
            )
        branch_point.choice(choice_id)
        normalized.append((branch_point_id, choice_id))
    return tuple(normalized)


__all__ = [
    "BRANCH_POINTS",
    "BranchPoint",
    "Choice",
    "build_branch_point_table",
    "validate_path",
]
