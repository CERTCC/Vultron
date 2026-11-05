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

``create_receive_activity_tree`` is the only place the stage is built; a tree
declares its paths with the factory's ``paths`` argument and nothing else
(HP-01-007, ADR-0115).
"""

from collections.abc import Collection
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
    "ReceivedPath",
    "ReceivedPathNode",
    "declared_paths",
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
    does — the ``/case_id`` input port, else the case the activity names —
    then asks
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

    The case comes only through the ``/case_id`` port (BTND-01-006): a tree
    that names its case at build time seeds the port with
    :func:`~vultron.core.behaviors.case_id_scope.with_case_id`, and a tree
    that names none leaves the port to an earlier node of the same execution,
    falling back to :func:`activity_case_id` as the documented resolution
    step.

    Args:
        declared: The paths the message type handles.
        label: Names the tree in log lines; the factory passes the tree's own
            name.
    """

    def __init__(
        self,
        declared: frozenset[ReceivedPath],
        label: str = "",
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.declared = declared
        self.label = label
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
        (HP-01-038, HP-01-042).
        :func:`~vultron.core.behaviors.case.receive_stages.guards.diversion_stage`
        takes it as the answer to where a diversion may run, instead of a
        second declaration beside the tree's own, and the commit-ordering
        ratchet reads it from here rather than re-deriving what the
        declaration means (CLP-10-026, CS-22-001).
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
        case_id = self._case_id_bb or activity_case_id(self._activity)
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
