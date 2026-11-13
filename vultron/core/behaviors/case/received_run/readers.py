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

"""Handler-specific readings of a finished received tree run (ADR-0194).

Each builds an :data:`~vultron.core.behaviors.case.received_run.reading.OutcomeReader`
that a handler passes to the runner.  A reader receives only the finished
run, so it can read only what the tree's nodes recorded; the generic
readings it stands in front of are in
:mod:`~vultron.core.behaviors.case.received_run.reading`.
"""

from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.case.received_run.lookup import (
    node_failed,
    taken_diversion,
)
from vultron.core.behaviors.case.received_run.reading import (
    OutcomeReader,
    ReceivedOutcome,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    EmbargoInviteNotYetRefusedNode,
)
from vultron.core.behaviors.sender_guard import closed_sender_turned_away
from vultron.core.models.use_case_result import HandlerResult
from vultron.errors import VultronWiringError


def first_reading(*readers: OutcomeReader) -> OutcomeReader:
    """One reader that asks *readers* in turn and keeps the first answer."""

    def read(outcome: ReceivedOutcome) -> HandlerResult | None:
        for reader in readers:
            if (verdict := reader(outcome)) is not None:
                return verdict
        return None

    return read


def closed_sender_reader(*, closes: bool) -> OutcomeReader:
    """The verdict owed a sender the tree's closed-sender door turned away.

    The door (``closed_sender`` on the receive-tree factory) stops the tree
    when the case already records the sender's closure, with nothing
    committed or sent (CM-23-018):

    - an act that would close it again (*closes*: a ``Leave``, a ``Reject``
      of a stub or full-case Invite) changes nothing, so it is ``SKIPPED``,
      whatever its activity id (ID-05-003);
    - any other act is ``REFUSED``: the sender may act on nothing further.

    The reader answers ``None`` when the run did not end at the door.  A run
    that failed on an internal error never reaches it: the runner raises
    first, so a crash is never read as a repeat or a refusal (ARCH-15-001).

    Raises:
        VultronWiringError: The tree was not built by
            :func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`.
    """

    def read(outcome: ReceivedOutcome) -> HandlerResult | None:
        root = outcome.tree
        if not isinstance(root, ReceivedActivityTree):
            raise VultronWiringError(
                f"closed_sender_reader: '{root.name}' is not a"
                " received-activity tree, so it has no closed-sender door"
                " (CM-23-018)"
            )
        closed = closed_sender_turned_away(root)
        if closed is None:
            return None
        if closes:
            return HandlerResult.skipped(
                f"{outcome.label}: {closed} — a repeat of a closing act,"
                " nothing to apply (ID-05-003)"
            )
        return HandlerResult.refused(
            f"{outcome.label}: {closed} — it may act on nothing further"
        )

    return read


def pxa_refusal_reader(name: str, answered: str) -> OutcomeReader:
    """The verdict of a delivery the P/X/A refusal *name* diverted.

    ``SKIPPED`` when the ``Reject`` of the Invite *answered* names was
    already sent by an earlier run that ended with no verdict (one whose
    queue write failed), so the re-run sends nothing new (HP-01-014,
    ID-04-005); otherwise ``REFUSED`` for the condition's reason
    (EMB-01-002, EMB-02-004), whether or not the ``Reject`` could be sent.
    ``None`` when the diversion was not taken.  A resend after a refusal
    never reaches this: the seen-before door refuses it again from its
    receipt stub (ADR-0154).
    """

    def read(outcome: ReceivedOutcome) -> HandlerResult | None:
        stage = taken_diversion(outcome.tree, name)
        if stage is None:
            return None
        if node_failed(stage, EmbargoInviteNotYetRefusedNode):
            return HandlerResult.skipped(
                f"{answered} not refused again: the Reject was already sent"
                " (HP-01-003)"
            )
        return HandlerResult.refused(
            stage.condition.feedback_message or f"{name}: P/X/A set"
        )

    return read


__all__ = [
    "closed_sender_reader",
    "first_reading",
    "pxa_refusal_reader",
]
