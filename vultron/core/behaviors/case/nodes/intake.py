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

"""Intake: the received tree's first write, once every door admitted it.

:class:`IntakeReceivedActivityNode` records the message.  It stores the
received activity exactly as received, as the message's one ``HELD`` record,
and performs no other write (CLP-10-017).  It decides nothing, gates nothing,
and ledgers nothing.  What the receiver keeps is decided once the handling
tree has run, by the outcome stage: the record is archived when the message
is applied or skipped, and reduced to a receipt stub when it is refused
(CLP-10-073, CLP-10-018).

It runs after the door guards (CLP-10-010, ADR-0154): a message a door turns
away is never held in full, and a resend has already been answered from its
record by the seen-before door.  So every delivery that reaches intake is
new, or is the re-run of a message a run left in holding with no verdict
(CLP-10-074).

What it stores is the body that arrived, as the parser sealed it (VM-08-002),
which the event carries as its received evidence
(``VultronEvent.received_evidence``), and nothing derived from it (ADR-0149).
A received ledger entry records the same body (CLP-07-011), so the record
and the ledger hold one account of what arrived.  A reader loads the body
again: core through the ``ReceivedActivityLoader`` port, a reply
through the wire seam that embeds it as received (DL-06-004).

The record is keyed by the receiver.  Each activity is written as one
:class:`~vultron.core.models.received_activity_record.ReceivedActivityRecord`
whose id the receiver derives (``ReceivedActivityRecord.build_id``), never
under the id the sender chose: a sender who names its activity after a record
this actor derives cannot occupy that id ahead of the actor's own write.  The
sender's id is kept on the record for the reverse lookup.

The letter's contents are not core's records.  A case, a note, a status, an
embargo carried inline in the activity is a *message shaped like* that object;
the record core keeps is written later, by an effect node, from the copy the
event carries, and only after the guards passed.  Writing the inlined objects
here would let any sender seed a replica ahead of the trust checks
(PCR-03-004, CBT-01-005), because a stored case row *is* the replica.  So
intake never writes them.

``create_receive_activity_tree`` supplies this node in every tree it builds,
right after the door guards, so no handler opts out and no handler needs a
store node or a store helper for the received activity (CLP-10-019).

Blackboard contract (BTND-03-003):

- ``activity`` (READ, ``/activity``): the received
  :class:`~vultron.core.models.events.base.VultronEvent`, placed by
  ``BTBridge.execute_with_setup``.  Its ``received_evidence`` is the body to
  record, under its ``activity_id``.

The node keeps no record of what it did for a later node to read: whether a
delivery is new is the seen-before door's answer, from the record (ADR-0154).
"""

import logging
from typing import NoReturn

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import (
    ACTIVITY_UNAVAILABLE,
    DataLayerActionWithPorts,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.services.received_activity import held_received_record
from vultron.errors import VultronAlreadyExistsError, VultronWiringError

logger = logging.getLogger(__name__)


class IntakeReceivedActivityNode(DataLayerActionWithPorts):
    """Record the received activity as received: the body that arrived.

    Each activity is recorded as a ``HELD`` ``ReceivedActivityRecord`` under
    the receiver's own key (``ReceivedActivityRecord.build_id``), so a
    sender's choice of id can collide with nothing but its own earlier
    delivery.  The record holds the event's received evidence, the body the
    parser sealed (VM-08-002), and nothing else (ADR-0149).

    A ``HELD`` record with no replay owed may already be there: a run that
    ended with no verdict left it (CLP-10-074), or the enclosing received
    tree's intake wrote it for a nested one.  It is left as it is, because
    its body is the one this delivery brings (ingress refuses a different
    one, IE-10-002).  Any other record means the seen-before door did not
    run ahead of this node, which is a wiring fault: the node raises
    :exc:`~vultron.errors.VultronWiringError` and writes nothing, so the
    handler raises and the outcome stage leaves the record as it is
    (ARCH-15-001, CLP-10-074).

    Returns ``FAILURE`` when the DataLayer is unavailable or no received event
    is on the blackboard, each a wiring fault the handler raises on, and when
    the event carries no received evidence (VM-08-002): there is nothing to
    record, and the delivery is refused.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.activity: object | None = None

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self._try_get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        event = self.activity
        if not isinstance(event, VultronEvent):
            self.logger.error(
                "%s: expected a VultronEvent on the blackboard, got %s",
                self.name,
                type(event).__name__,
            )
            self.feedback_message = ACTIVITY_UNAVAILABLE
            return Status.FAILURE

        assert self.datalayer is not None
        activity_id = event.activity_id
        evidence = event.received_evidence
        if evidence is None:
            # Nothing to record, so the delivery is refused: a resend routed
            # without its own body is answered by the seen-before door before
            # intake, so meeting one here is a copy no record backs.
            self.feedback_message = (
                f"activity '{activity_id}' carries no received body to"
                " record (VM-08-002, ARCH-15-001)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        # BT-HELPER-01: ``update()`` owns the only try/except.  Presence is the
        # ``VultronAlreadyExistsError`` that ``create()`` raises on a duplicate;
        # any other failure to store is a fault this node surfaces
        # (ARCH-15-001), not a benign duplicate.
        try:
            self.datalayer.create(
                ReceivedActivityRecord(
                    activity_id=activity_id,
                    received_body=evidence,
                    # In holding until the outcome stage settles it
                    # (CLP-10-073, ADR-0154).
                    stage=ReceivedStage.HELD,
                    replay_owed=False,
                )
            )
        except VultronAlreadyExistsError:
            return self._find_in_holding(activity_id)
        self.logger.info(
            "Intake recorded %s activity '%s'",
            event.activity_type,
            activity_id,
        )
        return Status.SUCCESS

    def _find_in_holding(self, activity_id: str) -> Status:
        """Answer a record already there: in holding and owed nothing, or a fault."""
        assert self.datalayer is not None
        record = held_received_record(self.datalayer, activity_id)
        if (
            record is not None
            and record.stage is ReceivedStage.HELD
            and not record.replay_owed
        ):
            self.logger.debug(
                "Intake: activity '%s' is already in holding; it runs again"
                " from the body held (CLP-10-074)",
                activity_id,
            )
            return Status.SUCCESS
        return self._wiring_fault(
            f"activity '{activity_id}' is already"
            f" {record.stage if record else 'held'}, so the seen-before door"
            " should have answered it before intake (ADR-0154)"
        )

    def _wiring_fault(self, message: str) -> NoReturn:
        """Raise *message* as a wiring fault (ARCH-15-001).

        Raised, not returned as ``FAILURE``, so the bridge reports an internal
        error: the handler raises instead of refusing the sender, and the
        outcome stage, seeing no verdict, leaves the record as it is rather
        than reducing it to a stub for a fault that is ours (CLP-10-074).
        """
        self.feedback_message = f"{message} (ARCH-15-001)"
        self.logger.error("%s: %s", self.name, self.feedback_message)
        raise VultronWiringError(f"{self.name}: {self.feedback_message}")
