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

"""The refusal-effects stage of a received-side tree (ADR-0111, CLP-10-022).

A precondition guard that refuses an assertion ends the tree before the
commit, so nothing is ledgered and no protocol effect runs (CLP-10-006).
Some refusals still owe the sender feedback in the moment: a wholly refused
backward RM declaration owes the RSH-06-004 clarification note.

:class:`PreconditionGuardStage` is the composite
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
builds when a tree passes ``refusal_effects``.  It runs the guards; only when
they refuse does it run the refusal effects, and it then fails with the
guards' refusal, so the root Sequence still stops before the commit and the
handler still reports ``REFUSED`` for the guard's reason.  A guard failure
that is an idempotent repeat the handler reports ``SKIPPED``
(:class:`~vultron.core.behaviors.idempotency.ReportsIdempotentRepeat`) is not
a refusal, so it runs no refusal effect either.  Nor is a delivery a
:class:`~vultron.core.behaviors.case.nodes.diversion_stage.DiversionStage`
among the guards diverted: its diversion has already answered it
(CLP-10-026).

While the refusal effects run, the stage holds the guards' reason in
:attr:`PreconditionGuardStage.refusal_reason`; an effect reads it through
:func:`enclosing_refusal_reason`.

The factory owns this structure; a tree supplies only the effect nodes.
"""

import logging
from collections.abc import Iterator

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.diversion_stage import (
    DiversionStage,
)
from vultron.core.behaviors.case.nodes.earlier_run import (
    FirstRunOfMessageNode,
)
from vultron.core.behaviors.idempotency import repeat_ending_run

logger = logging.getLogger(__name__)

__all__ = [
    "PreconditionGuardStage",
    "RefusalEffectsBestEffort",
    "enclosing_refusal_reason",
    "enclosing_refusal_stage",
]


class RefusalEffectsBestEffort(py_trees.decorators.Decorator):
    """Run the refusal effects; their failure never changes the verdict.

    The delivery is already refused when this runs.  A refusal effect that
    fails is logged at WARNING and reported as ``SUCCESS`` here, so the
    failure reason the handler reads is still the guard's refusal, not the
    feedback that could not be sent.  The child keeps its ``FAILURE`` status
    for inspection.
    """

    def update(self) -> Status:
        child = self.decorated
        if child.status == Status.FAILURE:
            logger.warning(
                "%s: refusal effect '%s' failed: %s",
                self.name,
                child.name,
                child.feedback_message or child.__class__.__name__,
            )
            return Status.SUCCESS
        return child.status


class PreconditionGuardStage(py_trees.composites.Composite):
    """Precondition guards, then the refusal effects only when they refuse.

    Children, in order:

    - ``guards`` — a ``Sequence`` of the tree's precondition guards;
    - ``first_run`` — a condition that succeeds when no earlier run began
      handling the message, read from its record
      (:class:`~vultron.core.behaviors.case.nodes.earlier_run.FirstRunOfMessageNode`);
    - ``refusal`` — the refusal effects, wrapped by the factory.

    Returns:
        SUCCESS when the guards pass; the refusal effects do not run, so an
        accepted delivery reaches the commit having run no effect
        (CLP-10-006).

        FAILURE when a guard refuses, after running the refusal effects once. A
        guard whose failure is an idempotent repeat (``failed_as_repeat``) was
        not refused, so the refusal effects are skipped (CLP-10-042,
        CLP-05-006).  A delivery a diversion among the guards took
        (``skipped_as_diversion``) has been answered by that diversion, so
        the refusal effects are skipped too (CLP-10-070).  A resend of a
        refused activity never reaches this stage: the seen-before door
        answers it from its receipt stub (ADR-0154).  The re-run of a record
        a run left in holding, which ``first_run`` reads from the record,
        skips the refusal effects too (``skipped_as_redelivery``): the first
        run may already have answered the refusal, and its receipt stub was
        then lost, so a refused activity is answered at most once
        (CLP-10-044).  A refusal effect writes no state but the RSH-06-004
        note (CLP-10-048), so nothing records that the effects ran: a re-run
        whose first run never reached them is not answered either.  The
        effects' own ids are derived, so even a re-run that ran them would
        send and commit nothing twice (ID-04-004).

        RUNNING while the guards or the refusal effects are running.
    """

    def __init__(
        self,
        name: str,
        guards: py_trees.behaviour.Behaviour,
        refusal: py_trees.behaviour.Behaviour,
        *,
        first_run: py_trees.behaviour.Behaviour,
    ) -> None:
        super().__init__(name=name, children=[guards, first_run, refusal])
        self.skipped_as_redelivery = False
        self.skipped_as_repeat = False
        self.skipped_as_diversion = False
        self.refusal_reason = ""
        """The guards' reason, set when they refuse; empty otherwise."""

    @property
    def guards(self) -> py_trees.behaviour.Behaviour:
        """The precondition-guard Sequence."""
        return self.children[0]

    @property
    def intake_ran(self) -> bool:
        """Whether the stage sits after intake in its tree.

        Read from the ``first_run`` condition, which is built knowing it.
        False for the post-close stage, a door ahead of intake (ADR-0154):
        its refusal effects run before the receiver holds a record of the
        message, so an effect that embeds the message takes it from the
        received event.  A stage whose ``first_run`` is not a
        :class:`FirstRunOfMessageNode` is read as after intake.
        """
        first_run = self.first_run
        if isinstance(first_run, FirstRunOfMessageNode):
            return first_run.intake_ran
        return True

    @property
    def first_run(self) -> py_trees.behaviour.Behaviour:
        """The condition that this run is the first to handle the message."""
        return self.children[1]

    @property
    def refusal(self) -> py_trees.behaviour.Behaviour:
        """The refusal effects, run only when :attr:`guards` refuse."""
        return self.children[2]

    def tick(self) -> Iterator[py_trees.behaviour.Behaviour]:
        """Tick the guards, then the refusal effects if the guards failed.

        A stage resumed while its refusal effects are ``RUNNING`` resumes
        them directly: the guards already refused, and re-ticking them would
        re-judge the delivery and re-publish what they publish.
        """
        if self.status != Status.RUNNING:
            for child in self.children:
                if child.status != Status.INVALID:
                    child.stop(Status.INVALID)
            self.skipped_as_redelivery = False
            self.skipped_as_repeat = False
            self.skipped_as_diversion = False
            self.refusal_reason = ""
            self.initialise()
        elif self.refusal.status == Status.RUNNING:
            yield from self._tick_refusal()
            return

        self.current_child = self.guards
        yield from self.guards.tick()
        if self.guards.status == Status.RUNNING:
            self.status = Status.RUNNING
            yield self
            return
        if self.guards.status == Status.SUCCESS:
            if self.refusal.status != Status.INVALID:
                self.refusal.stop(Status.INVALID)
            self.stop(Status.SUCCESS)
            yield self
            return

        if self._skips_refusal_effects():
            self._fail()
            yield self
            return
        self.current_child = self.first_run
        yield from self.first_run.tick()
        if self.first_run.status != Status.SUCCESS:
            # The guards' refusal is the reason the run reports, not the
            # condition's answer (BTBridge follows the last failed child).
            self.first_run.stop(Status.INVALID)
            self.skipped_as_redelivery = True
            logger.debug(
                "%s: re-run of an activity a run left in holding — refusal"
                " effects skipped (CLP-10-044)",
                self.name,
            )
            self._fail()
            yield self
            return
        self.refusal_reason = BTBridge.get_failure_reason(self.guards)
        yield from self._tick_refusal()

    def _skips_refusal_effects(self) -> bool:
        """True, with its flag set, when the guards' failure is no refusal.

        A repeat (``skipped_as_repeat``) and a diverted delivery
        (``skipped_as_diversion``) are each already answered, or owe no
        answer (CLP-10-044, CLP-10-070).  The re-run of a record a run left
        in holding is the ``first_run`` child's question, asked next.
        """
        if self._failed_as_repeat():
            self.skipped_as_repeat = True
            logger.debug(
                "%s: guard failure is an idempotent repeat — refusal effects"
                " skipped (CLP-10-044)",
                self.name,
            )
            return True
        if self._diverted():
            self.skipped_as_diversion = True
            logger.debug(
                "%s: the delivery was diverted — its diversion answered it,"
                " so refusal effects skipped (CLP-10-026)",
                self.name,
            )
            return True
        return False

    def _tick_refusal(self) -> Iterator[py_trees.behaviour.Behaviour]:
        """Tick the refusal effects; fail with the guards' refusal when done."""
        self.current_child = self.refusal
        yield from self.refusal.tick()
        if self.refusal.status == Status.RUNNING:
            self.status = Status.RUNNING
            yield self
            return
        self._fail()
        yield self

    def _failed_as_repeat(self) -> bool:
        """True when a guard on the failure chain reports a repeat.

        See :func:`~vultron.core.behaviors.idempotency.repeat_ending_run`: a
        guard that failed off the chain (an alternative a ``Selector`` tried
        first) did not decide the refusal, so its repeat flag does not skip
        the effects.
        """
        return repeat_ending_run(self.guards) is not None

    def _diverted(self) -> bool:
        """True when a diversion among the guards took the delivery."""
        return any(
            isinstance(node, DiversionStage) and node.taken
            for node in self.guards.iterate()
        )

    def _fail(self) -> None:
        """End FAILURE, pointing at the guards so their reason is reported."""
        self.current_child = self.guards
        self.stop(Status.FAILURE)


def enclosing_refusal_stage(
    node: py_trees.behaviour.Behaviour,
) -> PreconditionGuardStage | None:
    """The stage whose refusal effects hold *node*, if any.

    ``None`` when *node* is not inside a :class:`PreconditionGuardStage`'s
    refusal effects: a node among its guards is not a refusal effect.
    """
    child: py_trees.behaviour.Behaviour = node
    parent = node.parent
    while parent is not None:
        if isinstance(parent, PreconditionGuardStage):
            return parent if child is parent.refusal else None
        child, parent = parent, parent.parent
    return None


def enclosing_refusal_reason(node: py_trees.behaviour.Behaviour) -> str | None:
    """The refusal reason of the stage whose refusal effects hold *node*.

    ``None`` when *node* is not inside a :class:`PreconditionGuardStage`'s
    refusal effects, or the stage holds no reason: a refusal effect placed
    anywhere else is a composition fault its caller reports.
    """
    stage = enclosing_refusal_stage(node)
    if stage is None or not stage.refusal_reason:
        return None
    return stage.refusal_reason
