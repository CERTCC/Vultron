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

"""Read a finished received tree's run into its ``HandlerResult`` (ADR-0194).

A tree's root status says only whether it succeeded.  A handler has to report
more than that (HP-01-003, HP-01-014, ADR-0095): a benign no-op is
``SKIPPED``, a refused assertion is ``REFUSED``, and a programming error is
neither — it propagates.  :func:`read_outcome` makes that reading from what
the tree's nodes recorded, and nothing else: no DataLayer, no port, no
request.  It asks, in this order:

1. A leadership skip (the tree never ran) → ``SKIPPED``.
2. On a failed run, the doors, in the order the factory places them
   (:func:`~vultron.core.behaviors.case.received_run.doors.door_refusal`),
   then the sender sequence stage
   (:func:`~vultron.core.behaviors.case.received_run.sequence.sender_sequence_verdict`)
   and the incomplete-activity guard.  Each keeps its node's own reason
   (CLP-10-010, SYNC-21-008, CLP-10-018).
3. ``internal_error`` → raise :class:`~vultron.errors.VultronBTInternalError`.
4. The handler's own reader, when it passed one (:data:`OutcomeReader`).
5. On a successful run, a node that reports it changed nothing
   (:class:`~vultron.core.behaviors.idempotency.ReportsNoChange`) →
   ``SKIPPED``; otherwise ``APPLIED``.
6. On a failed run, a guard on the failure chain that failed as a repeat
   (:class:`~vultron.core.behaviors.idempotency.ReportsIdempotentRepeat`) →
   ``SKIPPED``.
7. A node composed without a dependency (a ``WIRING_UNAVAILABLE_MESSAGES``
   reason) → raise: our fault, not the sender's (ADR-0095).
8. Any other failure → ``REFUSED`` with the failing leaf's reason, or a raise
   for a tree that judges nothing (``judges=False``): there a failure is a
   local fault, never a verdict on the sender.
"""

from collections.abc import Callable
from dataclasses import dataclass

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.behaviors.case.received_run.doors import (
    door_refusal,
    incomplete_activity_refusal,
)
from vultron.core.behaviors.case.received_run.lookup import (
    _HasRoot,
    _root,
    failure_reason,
)
from vultron.core.behaviors.case.received_run.sequence import (
    sender_sequence_verdict,
)
from vultron.core.behaviors.helpers import WIRING_UNAVAILABLE_MESSAGES
from vultron.core.behaviors.idempotency import (
    repeat_ending_run,
    unchanged_by_run,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.errors import VultronBTInternalError


@dataclass(frozen=True)
class ReceivedOutcome:
    """What a finished received tree run left behind: the tree and its result.

    The whole input of a verdict reading.  It carries no DataLayer, port or
    request, so a reading can only report what the tree's nodes recorded
    (ADR-0194).

    Attributes:
        tree: The root of the tree that ran.
        result: What ``BTBridge`` returned for it.
        label: Names the handler's step in a reason, e.g. ``"EngageCaseBT"``.
    """

    tree: py_trees.behaviour.Behaviour
    result: BTExecutionResult
    label: str

    @classmethod
    def of(
        cls,
        tree: py_trees.behaviour.Behaviour | _HasRoot,
        result: BTExecutionResult,
        label: str,
    ) -> ReceivedOutcome:
        """The outcome of *tree*'s run, from the tree or its wrapper."""
        return cls(tree=_root(tree), result=result, label=label)

    @property
    def succeeded(self) -> bool:
        """True when the run ended in ``SUCCESS``."""
        return self.result.status == Status.SUCCESS

    @property
    def failure_reason(self) -> str:
        """The failing leaf's reason (BT-13-001); never empty on a failure."""
        return failure_reason(self.tree, self.result)

    @property
    def refusal_reason(self) -> str:
        """The reason of the general refusal: the label, then the leaf's."""
        return f"{self.label}: {self.failure_reason}"


#: A handler's own reading of a finished run, asked after the doors and
#: before the generic repeat, no-change and refusal readings.  ``None`` means
#: "no reading of mine applies"; the generic reading then decides.
OutcomeReader = Callable[[ReceivedOutcome], HandlerResult | None]


def read_outcome(
    outcome: ReceivedOutcome,
    *,
    reader: OutcomeReader | None = None,
    judges: bool = True,
) -> HandlerResult:
    """The ``HandlerResult`` of a finished received tree run.

    See the module docstring for the order of the readings.

    Args:
        outcome: The finished run.
        reader: The handler's own reading, asked after the doors.
        judges: ``False`` for a tree that only stores or commits what the
            handler has already accepted: any failure past the doors is then
            a local fault and raises instead of refusing.

    Raises:
        VultronBTInternalError: The run failed on an internal error, on a
            node missing its DataLayer or a port, or — for a tree that judges
            nothing — for any reason past the doors.
    """
    result = outcome.result
    if result.leader_skipped:
        return HandlerResult.skipped("not the replication leader")
    if not outcome.succeeded:
        if (verdict := _door_verdict(outcome.tree)) is not None:
            return verdict
        if result.internal_error:
            raise VultronBTInternalError(
                f"{outcome.label}: {result.feedback_message}"
            )
    if reader is not None and (verdict := reader(outcome)) is not None:
        return verdict
    if outcome.succeeded:
        if (unchanged := unchanged_by_run(outcome.tree)) is not None:
            return HandlerResult.skipped(
                f"{outcome.label}: {unchanged.no_change_reason}"
            )
        return HandlerResult.applied()
    if (repeat := repeat_ending_run(outcome.tree)) is not None:
        return HandlerResult.skipped(_repeat_reason(repeat, outcome.label))
    reason = outcome.failure_reason
    if reason in WIRING_UNAVAILABLE_MESSAGES or not judges:
        # A node composed without a dependency (it set this message instead
        # of raising), or a failure of a tree that judges nothing: our fault,
        # not the sender's, so it must not read as a refusal (ADR-0095).
        raise VultronBTInternalError(f"{outcome.label}: {reason}")
    return HandlerResult.refused(outcome.refusal_reason)


def _door_verdict(
    tree: py_trees.behaviour.Behaviour,
) -> HandlerResult | None:
    """The verdict of a run a door, the sequence stage or intake's guard ended."""
    if (verdict := door_refusal(tree)) is not None:
        return verdict
    if (verdict := sender_sequence_verdict(tree)) is not None:
        # Held or refused for its number; its merits were never judged.
        return verdict
    # An incomplete activity's guard message is the whole reason (CLP-10-018).
    return incomplete_activity_refusal(tree)


def _repeat_reason(repeat: py_trees.behaviour.Behaviour, label: str) -> str:
    """The guard's own message for its repeat, or one naming the guard."""
    return repeat.feedback_message or (
        f"{label}: {repeat.name} found an idempotent repeat"
    )


__all__ = ["OutcomeReader", "ReceivedOutcome", "read_outcome"]
