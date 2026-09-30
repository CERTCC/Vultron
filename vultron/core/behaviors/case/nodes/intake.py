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

"""Intake: the first stage of every received-side tree (ADR-0111).

:class:`IntakeReceivedActivityNode` archives the mail.  It stores the received
wire activity exactly as received, idempotently, and performs no other write
(CLP-10-017).  It decides nothing, gates nothing, and ledgers nothing: a
guard that refuses the assertion a moment later leaves the archive in place
(CLP-10-018).

The letter's contents are not core's records.  A case, a note, a status, an
embargo carried inline in the activity is a *message shaped like* that object;
the record core keeps is written later, by an effect node, from the copy the
event carries, and only after the guards passed.  Writing the inlined objects
here would let any sender seed a replica ahead of the trust checks
(PCR-03-004, CBT-01-005), because a stored case row *is* the replica.  So
intake never writes them.  The faithful copy of what arrived is the received
evidence ``parse_activity`` seals onto the activity; #3742 persists it beside
the archived row, and this node is where.

``create_receive_activity_tree`` supplies this node as the first child of
every tree it builds, so no handler opts out and no handler needs a store node
or a store helper for the received activity (CLP-10-019).

Blackboard contract (BTND-03-003):

- ``activity`` (READ, ``/activity``): the received
  :class:`~vultron.core.models.events.base.VultronEvent`, placed by
  ``BTBridge.execute_with_setup``.  Its ``activity`` field is the wire
  activity to archive.

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
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.base import VultronEvent
from vultron.errors import VultronAlreadyExistsError

logger = logging.getLogger(__name__)


class IntakeReceivedActivityNode(DataLayerActionWithPorts):
    """Archive the received activity as received.

    Idempotent: an activity already archived is left untouched and recorded
    in :attr:`found_ids`; one this store did not hold is created and recorded
    in :attr:`stored_ids`.  Presence is the ``VultronAlreadyExistsError`` that
    ``create()`` raises on a duplicate — an activity cannot be looked up by id
    through ``dl.read()``.  Only that error is caught: any other failure to
    store means the activity is malformed, which is a fault this node must
    surface (ARCH-15-001), not a benign duplicate.

    An event with no wire activity (a sync drain event, for instance) has
    nothing to archive and succeeds having written nothing.

    Returns ``FAILURE`` when the DataLayer is unavailable or no received
    event is on the blackboard (ARCH-15-001); both are wiring faults the
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
        if event.activity is None:
            self.logger.debug(
                "%s: event '%s' carries no wire activity — nothing to archive",
                self.name,
                event.activity_id,
            )
            return Status.SUCCESS
        self._archive(event.activity)
        return Status.SUCCESS

    def _archive(self, activity: VultronActivity) -> None:
        assert self.datalayer is not None
        try:
            self.datalayer.create(activity)
        except VultronAlreadyExistsError:
            self.found_ids.append(activity.id_)
            self.logger.debug(
                "Intake: %s activity '%s' already archived",
                activity.type_,
                activity.id_,
            )
            return
        self.stored_ids.append(activity.id_)
        self.logger.info(
            "Intake archived %s activity '%s'", activity.type_, activity.id_
        )
