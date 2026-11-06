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

"""The seen-before door of every received tree (ADR-0154, CLP-10-010).

A resend is answered from what the receiver recorded for it, before intake
writes anything and before the handling tree runs, so nothing is re-run and
no refusal notice is sent again.  The answer is read from the message's one
:class:`~vultron.core.models.received_activity_record.ReceivedActivityRecord`,
by its stage, and never from in-memory state an earlier stage left:

- no record -- a delivery this receiver has not seen: the door passes;
- a receipt stub -- the message was refused, and the refusal is whole and
  final for that activity: it is refused again, with the stub's reason;
- an archive -- the message was applied: the resend is skipped;
- ``HELD`` with a replay owed -- the message is waiting (for its case, a
  ledger gap, a fetch, a retry): the resend is skipped, and the held record
  is answered when its replay reaches its own outcome;
- ``HELD`` or ``HANDLED`` with no replay owed -- the record a run left with
  no verdict (CLP-10-074): the door passes, so the act runs again from the
  body (ADR-0154).  Inbox runs are serialized per actor, so a resend never
  meets a run in progress.

The door keeps nothing for a later stage to read.  A stage that answers a
delivery once (the ledger position, the sender's number, the refusal effects)
tells a re-run from a first run by reading the record itself
(``began_in_an_earlier_run``), because the door is outside the handling tree
and a stage reads only the record and the store (ADR-0154).

The door does not compare bodies.  A delivery whose body differs from what
the receiver holds, as a body or as a stub's digest, is a reused id, which
ingress refuses before routing it (IE-10-002); so every delivery that reaches
this door carries the body the record was made from.

:class:`ActivityNotSeenBeforeNode` is the door.
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
places it in every received tree, after the addressee check and before the
path stage.  A handler reads its answer through
``seen_before_verdict`` in ``vultron/core/use_cases/received/_bt_verdict/``.
"""

from enum import StrEnum

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import (
    ACTIVITY_UNAVAILABLE,
    DataLayerConditionWithPorts,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.services.received_activity import held_received_record

__all__ = ["ActivityNotSeenBeforeNode", "SeenBefore", "seen_before"]


class SeenBefore(StrEnum):
    """What the receiver recorded for a delivery it has seen before."""

    REFUSED = "refused"
    """A receipt stub: the message was refused (CLP-10-018)."""

    APPLIED = "applied"
    """An archive: the message was applied (CLP-10-073)."""

    WAITING = "waiting"
    """In holding, owed a replay (IO-03-009)."""


def seen_before(record: ReceivedActivityRecord | None) -> SeenBefore | None:
    """The door's answer for *record*; ``None`` when the delivery passes.

    See the module docstring for each case.
    """
    if record is None:
        return None
    if record.stage is ReceivedStage.REFUSED:
        return SeenBefore.REFUSED
    if record.stage is ReceivedStage.ARCHIVED:
        return SeenBefore.APPLIED
    if record.replay_owed:
        return SeenBefore.WAITING
    return None


class ActivityNotSeenBeforeNode(DataLayerConditionWithPorts):
    """Door guard: the received activity is not one already answered.

    Returns:
        SUCCESS when :func:`seen_before` lets the delivery through.

        FAILURE when the receiver already answered the activity, with
        :attr:`seen` saying how and :attr:`refusal_reason` the reason a
        receipt stub recorded.  Nothing is written.

        FAILURE also when no received event is on the blackboard, which is a
        wiring fault (ARCH-15-001).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    def __init__(self, label: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.label = label
        self._activity: object | None = None
        self.seen: SeenBefore | None = None
        self.refusal_reason: str | None = None

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self._activity = self._try_get_input("activity")
        self.seen = None
        self.refusal_reason = None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        event = self._activity
        if not isinstance(event, VultronEvent):
            self.feedback_message = ACTIVITY_UNAVAILABLE
            self.logger.error(
                "%s: expected a VultronEvent on the blackboard, got %s",
                self.name,
                type(event).__name__,
            )
            return Status.FAILURE
        record = held_received_record(self.datalayer, event.activity_id)
        self.seen = seen_before(record)
        if self.seen is None:
            return Status.SUCCESS
        assert record is not None
        self.refusal_reason = record.refusal_reason
        self.feedback_message = (
            f"{self.label}: activity '{event.activity_id}' was seen before"
            f" ({self.seen}); answered from its record, nothing re-run"
            " (ADR-0154)"
        )
        self.logger.info(
            "%s (actor '%s')",
            self.feedback_message,
            event.actor_id,
        )
        return Status.FAILURE
