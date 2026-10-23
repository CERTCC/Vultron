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

"""Diversions: an arm a delivery takes instead of its commit (CLP-10-026).

Some deliveries are answered by an act of the receiver's own rather than by
committing the received activity: the CASE_MANAGER honours, re-invites or
acknowledges a late embargo ``Accept`` with an entry of its own (EMB-17), and
a receiver answers an embargo Invite or Accept with ER once P/X/A is set
(EMB-01-002, EMB-02-002).  Which arm runs is decided by the case at tick
time, so the choice belongs in the tree, never in the use case (CLP-10-005,
ADR-0135).

A tree passes a :class:`Diversion` among its ``precondition_guards``;
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
builds a :class:`DiversionStage` in its place::

    DiversionStage(<name>)
    ├─ <condition>        # read-only: SUCCESS diverts the delivery
    └─ <effects>          # the receiver's own answer to it

When the condition fails the stage succeeds and the tree goes on to its next
guard.  When it holds, the stage runs the effects and then fails, so the
received activity is never committed and no effect of the admitted path runs;
the handler reads :attr:`DiversionStage.taken` to report the delivery.  The
stage fails whatever the effects return, and an exception the effects raise
ends the tree as an internal error (ADR-0095).

A :data:`DiversionGate.CASE_MANAGER` diversion runs only at the case's
CASE_MANAGER and may commit its own CASE_MANAGER-authored entry (the late
Accept's honour, re-invite or acknowledgement).  A
:data:`DiversionGate.RECEIVER` diversion is the receiver's own answer,
wherever the door guards admitted the copy; it writes no case state and every
emit in it must be covered by a registered
:class:`~vultron.core.behaviors.replica_emit_exemptions.ReplicaEmitExemption`
(BT-17-008).
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.replica_emit_exemptions import (
    ReplicaEmitExemption,
)

__all__ = ["Diversion", "DiversionGate", "DiversionStage"]


class DiversionGate(StrEnum):
    """Where a :class:`Diversion` may run.

    - ``CASE_MANAGER`` — only at the case's CASE_MANAGER (BT-17-001); the
      factory checks the role before the condition and gates the effects.
    - ``RECEIVER`` — at any receiver the door guards admitted; the effects
      are the receiver's own answer and write no case state (RSH-08-003).
    """

    CASE_MANAGER = "case-manager"
    RECEIVER = "receiver"


@dataclass(frozen=True)
class Diversion:
    """An arm a received tree takes in place of committing the activity.

    Attributes:
        name: Names the stage, and the delivery's outcome in a reason.
        condition: Read-only check; SUCCESS diverts the delivery.
        effects: The receiver's answer, run in order once diverted.
        gate: Where the diversion may run.
        emit_exemption: The registered decision covering the emits of a
            ``RECEIVER`` diversion (BT-17-008).
    """

    name: str
    condition: py_trees.behaviour.Behaviour
    effects: tuple[py_trees.behaviour.Behaviour, ...] = field(
        default_factory=tuple
    )
    gate: DiversionGate = DiversionGate.CASE_MANAGER
    emit_exemption: ReplicaEmitExemption | None = None


class DiversionStage(py_trees.composites.Composite):
    """A condition and the effects that answer a delivery it diverts.

    Children, in order: the condition, then the effects (one node; the
    factory wraps several in a ``Sequence``).

    Returns:
        SUCCESS when the condition fails: the delivery is not diverted.

        FAILURE once the condition holds and the effects have run, whatever
        they returned, so the tree stops before the commit.
        :attr:`taken` says the delivery was diverted and
        :attr:`effects_succeeded` whether its answer completed.

        RUNNING while a child is running.

    Only the received-tree factory constructs one.
    """

    def __init__(
        self,
        name: str,
        condition: py_trees.behaviour.Behaviour,
        effects: py_trees.behaviour.Behaviour,
    ) -> None:
        super().__init__(name=name, children=[condition, effects])
        self.taken = False

    @property
    def condition(self) -> py_trees.behaviour.Behaviour:
        """The read-only check that diverts the delivery."""
        return self.children[0]

    @property
    def effects(self) -> py_trees.behaviour.Behaviour:
        """The receiver's answer to a diverted delivery."""
        return self.children[1]

    def terminate(self, new_status: Status) -> None:
        """A stage reset to ``INVALID`` has diverted nothing.

        A stage the next run never reaches (a guard ahead of it refused) is
        left ``INVALID``, so :attr:`taken` must not still report the earlier
        run's diversion.
        """
        if new_status == Status.INVALID:
            self.taken = False

    @property
    def effects_succeeded(self) -> bool:
        """True when the delivery was diverted and its answer completed."""
        return self.taken and self.effects.status == Status.SUCCESS

    def tick(self) -> Iterator[py_trees.behaviour.Behaviour]:
        """Tick the condition, then the effects if it holds."""
        if self.status != Status.RUNNING:
            for child in self.children:
                if child.status != Status.INVALID:
                    child.stop(Status.INVALID)
            self.taken = False
            self.initialise()
        elif self.effects.status == Status.RUNNING:
            yield from self._tick_effects()
            return

        self.current_child = self.condition
        yield from self.condition.tick()
        if self.condition.status == Status.RUNNING:
            self.status = Status.RUNNING
            yield self
            return
        if self.condition.status != Status.SUCCESS:
            self.stop(Status.SUCCESS)
            yield self
            return
        self.taken = True
        yield from self._tick_effects()

    def _tick_effects(self) -> Iterator[py_trees.behaviour.Behaviour]:
        """Tick the effects; fail once they finish, ending the tree."""
        self.current_child = self.effects
        yield from self.effects.tick()
        if self.effects.status == Status.RUNNING:
            self.status = Status.RUNNING
            yield self
            return
        self.feedback_message = (
            f"the delivery was diverted to {self.name}"
            f" ({'answered' if self.effects_succeeded else 'not answered'})"
        )
        self.stop(Status.FAILURE)
        yield self
