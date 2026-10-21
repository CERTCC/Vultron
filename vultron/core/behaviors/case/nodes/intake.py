"""Intake: the first stage of every received-side tree (ADR-0111).

:class:`IntakeReceivedActivityNode` archives the mail.  It stores the received
activity exactly as received, idempotently, and performs no other write
(CLP-10-017).  It decides nothing, gates nothing, and ledgers nothing: a
guard that refuses the assertion a moment later leaves the archive in place
(CLP-10-018).

What it stores is the body that arrived, as the parser sealed it (VM-08-002),
which the event carries as its received evidence
(``VultronEvent.received_evidence``), and nothing derived from it (ADR-0149).
A received ledger entry records the same body (CLP-07-011), so the archive
and the ledger hold one account of what arrived.  A reader loads the body
again: core through the ``ReceivedActivityLoader`` port, a reply
through the wire seam that embeds it as received (DL-06-004).

The archive is keyed by the receiver.  Each activity is written as one
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

``create_receive_activity_tree`` supplies this node as the first child of
every tree it builds, so no handler opts out and no handler needs a store node
or a store helper for the received activity (CLP-10-019).

Blackboard contract (BTND-03-003):

- ``activity`` (READ, ``/activity``): the received
  :class:`~vultron.core.models.events.base.VultronEvent`, placed by
  ``BTBridge.execute_with_setup``.  Its ``received_evidence`` is the body to
  archive, under its ``activity_id``.

The node exposes what it did through :attr:`stored_ids` and
:attr:`found_ids`, so a handler whose only work is intake can report
``APPLIED`` or ``SKIPPED`` (HP-01-003) without inspecting the DataLayer — see
``intake_verdict`` in ``vultron/core/use_cases/received/_bt_verdict.py``.
"""

import logging

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import (
    ACTIVITY_UNAVAILABLE,
    DataLayerActionWithPorts,
)
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.errors import VultronAlreadyExistsError

logger = logging.getLogger(__name__)


class IntakeReceivedActivityNode(DataLayerActionWithPorts):
    """Archive the received activity as received: the body that arrived.

    Each activity is archived as a ``ReceivedActivityRecord`` under the
    receiver's own key (``ReceivedActivityRecord.build_id``), so a sender's
    choice of id can collide with nothing but its own earlier delivery.  The
    record holds the event's received evidence, the body the parser sealed
    (VM-08-002), and nothing else (ADR-0149).

    Idempotent: an activity already archived is left untouched and its sender
    id recorded in :attr:`found_ids`; one this store did not hold is archived
    and recorded in :attr:`stored_ids`.  Presence is the
    ``VultronAlreadyExistsError`` that ``create()`` raises on the derived id.
    Only that error is caught: any other failure to store is a fault this
    node must surface (ARCH-15-001), not a benign duplicate.

    An event with no received evidence is a resend under an id the receiver
    already holds (VM-08-002, IE-10-001): it is routed without a body of its
    own, so there is nothing new to archive.  Intake finds the archive, or
    the deferred record whose replay will archive it, and succeeds having
    written nothing.  With neither, there is no body to archive and none
    held: that is a wiring fault, and the node returns ``FAILURE`` and writes
    nothing (ARCH-15-001).

    Returns ``FAILURE`` also when the DataLayer is unavailable or no received
    event is on the blackboard (ARCH-15-001); each is a wiring fault the
    handler raises on rather than refusing the sender.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.activity: object | None = None
        self.stored_ids: list[str] = []
        self.found_ids: list[str] = []

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self._try_get_input("activity")

    @property
    def stored_anything(self) -> bool:
        """True when this run archived something new."""
        return bool(self.stored_ids)

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

        self.stored_ids = []
        self.found_ids = []
        assert self.datalayer is not None
        activity_id = event.activity_id
        evidence = event.received_evidence
        if evidence is None:
            return self._find_held(activity_id)
        # BT-HELPER-01: ``update()`` owns the only try/except.  Presence is the
        # ``VultronAlreadyExistsError`` that ``create()`` raises on a duplicate;
        # any other failure to store is a fault this node surfaces
        # (ARCH-15-001), not a benign duplicate.
        try:
            self.datalayer.create(
                ReceivedActivityRecord(
                    activity_id=activity_id, received_body=evidence
                )
            )
        except VultronAlreadyExistsError:
            self.found_ids.append(activity_id)
            self.logger.debug(
                "Intake: %s activity '%s' already archived",
                event.activity_type,
                activity_id,
            )
            return Status.SUCCESS
        self.stored_ids.append(activity_id)
        self.logger.info(
            "Intake archived %s activity '%s'",
            event.activity_type,
            activity_id,
        )
        return Status.SUCCESS

    def _find_held(self, activity_id: str) -> Status:
        """Answer an event with no body: find what this receiver holds.

        A resend under an id already held carries no received evidence
        (VM-08-002).  Finding its archive, or the deferred record whose
        replay archives it, is success with nothing written; finding neither
        is a wiring fault (ARCH-15-001).
        """
        assert self.datalayer is not None
        for record_id in (
            ReceivedActivityRecord.build_id(activity_id),
            DeferredInboxActivity.build_id(activity_id),
        ):
            if self.datalayer.read(record_id) is not None:
                self.found_ids.append(activity_id)
                self.logger.debug(
                    "Intake: activity '%s' carries no received body and is"
                    " already held (%s); nothing to archive",
                    activity_id,
                    record_id,
                )
                return Status.SUCCESS
        self.feedback_message = (
            f"activity '{activity_id}' carries no received body to archive"
            " and this receiver holds none for it (VM-08-002, ARCH-15-001)"
        )
        self.logger.error("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
