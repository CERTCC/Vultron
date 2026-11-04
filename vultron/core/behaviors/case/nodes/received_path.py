#!/usr/bin/env python

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

"""The path door stage of a received tree (ADR-0153, HP-01-005).

One role question per message picks the receiver's path in the case, and the
message type's declaration says which paths it handles:

- :class:`ReceivedPath` names the three paths.  The *manager* path is the
  receiver holding ``CVDRole.CASE_MANAGER`` in the case, the *participant
  replica* path is a receiver that holds a replica of the case without that
  role, and the *no case yet* path is a receiver that holds no replica.  No
  other role is a path: Case Owner, Vendor, Deployer and the rest are
  permission rules *inside* a path, checked with the same predicate, so a new
  role adds rules and never a path (HP-01-037, PCR-08-001).
- :class:`ReceivedPathNode` is the door guard that answers it, exactly once
  per message, through
  :func:`~vultron.core.participants.role_predicate.has_role` (CM-02-011).
  It runs after the addressee check and before the sender guard
  (CLP-10-010, HP-01-012), so the sender guard reads the path it chose rather
  than asking again.
- A message whose type declares no branch for the receiver's path is
  ``REFUSED`` with :func:`undeclared_path_reason`, composed in this one place
  for every message type from the resolved path and the declaration
  (HP-01-005, HP-01-039).
- :class:`CheckReceivedPathNode` is how a later node reads the answer: a pure
  condition over the path the stage already resolved, with no second read of
  the roster.
- :class:`ReceivedPathBranch` is the work a message type declared for one
  path, and :class:`PathScopedGuard` is a precondition guard scoped the same
  way.  Both select on :class:`CheckReceivedPathNode`, so a branch costs no
  second role read, and both are built by the received-tree factory alone
  (HP-01-038, HP-01-036).

``create_receive_activity_tree`` is the only place the stage is built; a tree
declares its paths with the factory's ``paths`` argument and nothing else
(HP-01-007, ADR-0115).
"""

from collections.abc import Collection
from dataclasses import dataclass
from enum import Enum
from typing import Self

import py_trees
from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.case.nodes.conditions import activity_case_id
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.participants.role_predicate import has_role
from vultron.enums.roles import CVDRole

__all__ = [
    "CheckReceivedPathNode",
    "PathScopedGuard",
    "ReceivedPath",
    "ReceivedPathBranch",
    "ReceivedPathNode",
    "declared_paths",
    "received_path_branch",
    "undeclared_path_reason",
]


class ReceivedPath(Enum):
    """The three paths a received message can take at a receiver (ADR-0153).

    Chosen by the ``CVDRole.CASE_MANAGER`` role alone.  Each member's value
    is the wording the path takes in a log line.
    """

    CASE_MANAGER = "manager"
    """The receiver holds ``CVDRole.CASE_MANAGER`` in the case."""

    PARTICIPANT_REPLICA = "participant replica"
    """The receiver holds a replica of the case without that role."""

    NO_CASE = "no case yet"
    """The receiver holds no replica of the case."""


def declared_paths(paths: Collection[ReceivedPath]) -> frozenset[ReceivedPath]:
    """*paths* as the frozen set the factory keeps, in any declared order."""
    return frozenset(paths)


#: What the receiver on each path *is*, as a clause about that receiver.
#: ``{case}`` takes the case phrase.  Each one is true of every receiver the
#: stage puts on that path, which is what makes the composed reason true of
#: the receiver it refuses (HP-01-039).
_PATH_CLAUSE: dict[ReceivedPath, str] = {
    ReceivedPath.CASE_MANAGER: "the CASE_MANAGER of {case}",
    ReceivedPath.PARTICIPANT_REPLICA: "not the CASE_MANAGER of {case}",
    ReceivedPath.NO_CASE: "holds no replica of {case}",
}

#: Added when the clause alone does not say what is missing.
_NOT_ADDRESSED = ", which this message type does not address"


def undeclared_path_reason(
    path: ReceivedPath,
    declared: Collection[ReceivedPath],
    case_id: str | None,
) -> str:
    """The reason an undeclared *path* is refused with (HP-01-039).

    Composed in this one place for every message type, from the path the
    stage resolved and the paths the type declared, so no handler maps a gate
    failure to a verdict after the run (HP-01-005).

    The clause states what the receiver on *path* is, so the reason is true of
    the receiver it refuses: a replica is "not the CASE_MANAGER", a store with
    no replica "holds no replica", and the case's actual CASE_MANAGER is told
    it *is* the CASE_MANAGER.  That last one is a refusal only because the
    type declares no manager branch, so the clause alone names nothing
    missing; a declaration that omits the manager path therefore says what is
    missing — a branch, not the role (HP-01-005).

    Args:
        path: The path the stage resolved for this receiver.
        declared: The paths the message type handles.
        case_id: The case the role was read in; ``None`` when the tree
            resolved none, which only the no-case path reaches.

    Returns:
        One sentence fragment, true of the receiver being refused.
    """
    case = f"case '{case_id}'" if case_id else "the case this activity names"
    clause = _PATH_CLAUSE[path].format(case=case)
    if ReceivedPath.CASE_MANAGER in declared:
        return clause
    return f"{clause}{_NOT_ADDRESSED}"


class ReceivedPathNode(DataLayerConditionWithPorts):
    """Door guard: pick the receiver's path, and admit only a declared one.

    Resolves the case the same way
    :class:`~vultron.core.behaviors.case.nodes.conditions.CheckIsCaseManagerNode`
    does — the constructor's ``case_id``, else the blackboard's, else the one
    the activity names — then asks
    :func:`~vultron.core.participants.role_predicate.has_role` once.

    Returns:
        SUCCESS when the resolved path is one the tree declared, with the
        path on :attr:`resolved_path` for every later node and, on the
        manager path, the resolved manager's id on ``/case_actor_id``, the
        key :class:`CheckIsCaseManagerNode` publishes there.

        FAILURE otherwise, with :func:`undeclared_path_reason` as the
        feedback message, logged at WARNING.  Intake has archived the copy
        and nothing after the stage runs (CLP-10-010, CLP-10-018).

    A case the store does not hold is the *no case yet* path, not an
    ADR-0087 anomaly: telling the three paths apart is this node's whole job,
    so an absent replica is an answer rather than a fault.

    Args:
        declared: The paths the message type handles.
        case_id: The case whose roster is read; ``None`` resolves it at run
            time.
        label: Names the tree in log lines; the factory passes the tree's own
            name.
    """

    def __init__(
        self,
        declared: frozenset[ReceivedPath],
        case_id: str | None = None,
        label: str = "",
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.declared = declared
        self.label = label
        self._case_id = case_id
        self._case_id_bb: str | None = None
        self._activity: object | None = None
        self.resolved_path: ReceivedPath | None = None
        self.resolved_case_id: str | None = None

    @property
    def manager_path_only(self) -> bool:
        """True when the declaration names the CASE_MANAGER path alone.

        Such a declaration gates the whole tree: the stage refuses every
        other receiver before any guard, commit or effect runs, so nothing
        after it executes anywhere but at the case's CASE_MANAGER
        (HP-01-038, HP-01-042).  The factory reads it to decide whether a
        diversion needs a gate of its own, and both authority ratchets read
        it from here rather than re-deriving it (CS-22-001).
        """
        return self.declared == frozenset({ReceivedPath.CASE_MANAGER})

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        "activity": PortInformation(data_type=object, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "case_actor_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "activity": "/activity",
            "case_actor_id": "/case_actor_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.resolved_path = None
        self.resolved_case_id = None
        self._case_id_bb = None
        self._activity = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass
        self._activity = self._try_get_input("activity")

    def _path(self, case_id: str | None) -> ReceivedPath:
        """The receiver's path in *case_id*, from one role read."""
        assert self.datalayer is not None and self.actor_id is not None
        if not case_id:
            return ReceivedPath.NO_CASE
        if has_role(
            self.actor_id, case_id, CVDRole.CASE_MANAGER, self.datalayer
        ):
            return ReceivedPath.CASE_MANAGER
        # Regime 3 (ADR-0087): a case the store does not hold is the no-case
        # path, which is this node's answer and not a fault, so the lookup
        # goes through the lenient resolver.
        if self._resolve_case_replica(case_id) is None:
            return ReceivedPath.NO_CASE
        return ReceivedPath.PARTICIPANT_REPLICA

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        case_id = (
            self._case_id
            or self._case_id_bb
            or activity_case_id(self._activity)
        )
        self.resolved_case_id = case_id
        path = self._path(case_id)
        self.resolved_path = path
        if path is ReceivedPath.CASE_MANAGER:
            # The same ``/case_actor_id`` CheckIsCaseManagerNode publishes
            # when it admits the manager, so a later node that reads the
            # resolved manager's id finds it whichever of the two answered
            # (BTND-03-009).  On this path the manager is the receiver.
            assert self.actor_id is not None
            self._set_output("case_actor_id", self.actor_id)
        if path in self.declared:
            self.logger.debug(
                "%s: '%s' takes the %s path of case '%s'",
                self.label or self.name,
                self.actor_id,
                path.value,
                case_id,
            )
            return Status.SUCCESS
        self.feedback_message = undeclared_path_reason(
            path, self.declared, case_id
        )
        self.logger.warning(
            "%s: refused at '%s' on the %s path; %s handles %s only: %s",
            self.label or self.name,
            self.actor_id,
            path.value,
            self.label or self.name,
            sorted(declared.value for declared in self.declared),
            self.feedback_message,
        )
        return Status.FAILURE


class CheckReceivedPathNode(py_trees.behaviour.Behaviour):
    """Condition: the path stage resolved the receiver onto *path*.

    The sender guard's ``at_case_manager`` and ``at_participant`` arms are
    selected with this, so the role question is asked once, by the path stage
    (HP-01-036, HP-01-008).  It reads the answer the stage already
    recorded and touches neither the store nor the blackboard.

    Returns:
        SUCCESS when the stage resolved *path*; FAILURE for any other path,
        and for a stage that has not run.

    FAILURE for a stage that has not run is not a safe default on its own:
    in the sender guard's two arms a FAILURE here skips the
    at-the-CASE_MANAGER rule and runs the at-a-participant one, so an unrun
    stage would judge the sender by the participant rule.  What makes that
    unreachable is the stage order, not this node: the factory places the
    path stage among the door guards, ahead of the guard it feeds, and a
    stage that refused ends the tree (CLP-10-010, HP-01-035).
    """

    def __init__(
        self,
        stage: ReceivedPathNode,
        path: ReceivedPath,
        name: str | None = None,
    ) -> None:
        label = path.name.title().replace("_", "")
        super().__init__(name=name or f"OnPath{label}")
        self.stage = stage
        self.path = path

    @classmethod
    def on_manager_path(cls, stage: ReceivedPathNode) -> Self:
        """The arm that runs only on the manager path."""
        return cls(stage, ReceivedPath.CASE_MANAGER)

    def update(self) -> Status:
        if self.stage.resolved_path is self.path:
            return Status.SUCCESS
        return Status.FAILURE


class ReceivedPathBranch(py_trees.composites.Selector):
    """The work a message type declared for one received path (HP-01-038).

    Structure::

        <name> (Selector)
        ├── SkipIfNotOn<Path> (Inverter[CheckReceivedPathNode])
        └── <children>

    The ``Inverter`` keeps the two FAILURE modes apart, as the CASE_MANAGER
    gate's does: a receiver on another path skips the branch as SUCCESS,
    while a receiver *on* this path whose work fails fails the Selector
    (BT-17-001).

    The branch is a structural guard, not a prose decision: the path stage
    already put this receiver on :attr:`branch_path`, so everything inside
    runs only there.  That is what BT-17-008 asks of an emit — the emit
    speaks for the actor the path names — which is why
    :func:`~vultron.core.behaviors.case.receive_stages.effects.ungated_emitters`
    does not walk into one.  The ``StateWriteCapable`` walk still does, and
    deliberately: only the CASE_MANAGER writes, so a participant-replica
    branch is exactly where RSH-08-003's one exception lives and has to stay
    visible to the ratchet that pins it.

    Only :func:`received_path_branch` constructs one, and only the
    received-tree factory calls that (HP-01-007).
    """

    def __init__(
        self,
        name: str,
        path: ReceivedPath,
        children: list[py_trees.behaviour.Behaviour],
    ) -> None:
        super().__init__(name=name, memory=False, children=children)
        self._path = path

    @property
    def branch_path(self) -> ReceivedPath:
        """The path this branch runs on."""
        return self._path

    @property
    def branch_body(self) -> py_trees.behaviour.Behaviour:
        """The child that runs only on :attr:`branch_path` (for inspection)."""
        return self.children[1]


def received_path_branch(
    name: str,
    stage: ReceivedPathNode,
    path: ReceivedPath,
    children: list[py_trees.behaviour.Behaviour],
    body_name: str | None = None,
) -> ReceivedPathBranch:
    """*children*, run only when *stage* resolved *path* (HP-01-038).

    Args:
        name: Name for the root Selector.
        stage: The tree's path stage, whose answer selects the branch.
        path: The declared path this branch belongs to.
        children: The work the message type does on that path.  More than
            one is wrapped in a Sequence so a mid-branch FAILURE still
            propagates.
        body_name: Name for that wrapping Sequence; defaults to
            ``{name}Body``.  A single child is its own body, so it keeps its
            own name and this argument has no effect.  Passing either name
            with no effects at all is a wiring error instead
            (``branch_arguments_without_effects``, HP-01-042).
    """
    label = path.name.title().replace("_", "")
    if len(children) == 1:
        body: py_trees.behaviour.Behaviour = children[0]
    else:
        body = py_trees.composites.Sequence(
            name=body_name or f"{name}Body", memory=False, children=children
        )
    return ReceivedPathBranch(
        name=name,
        path=path,
        children=[
            py_trees.decorators.Inverter(
                name=f"SkipIfNotOn{label}",
                child=CheckReceivedPathNode(stage, path),
            ),
            body,
        ],
    )


@dataclass(frozen=True)
class PathScopedGuard:
    """A precondition guard a message type runs on one declared path only.

    The guard counterpart of :class:`ReceivedPathBranch`, for a tree that
    declares more than one path and whose guard only has a question to ask on
    one of them — the embargo Invite's "does the canonical case's EM state
    admit a proposal?", which is the CASE_MANAGER's question (EP-09-001).  A
    receiver on another path skips it, so the guard neither refuses nor
    reports for a path it does not speak to.

    A tree that declares exactly one path needs none of this: the path stage
    already refused every other receiver, so its guards run bare.

    Attributes:
        path: The declared path the guard runs on.
        guard: The read-only guard itself.
        name: Names the branch Selector; defaults to
            ``{guard.name}IfOn<Path>``.
    """

    path: ReceivedPath
    guard: py_trees.behaviour.Behaviour
    name: str | None = None
