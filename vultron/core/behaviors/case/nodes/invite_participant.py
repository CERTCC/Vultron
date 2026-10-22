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


"""Invitee idempotency and record-exists guard nodes.

Guards a duplicate ``Accept(Invite(actor, case))`` from a joined or removed
participant (CM-17-012), and refuses an Accept whose invitee has no
participant record (CM-11-021): the record is created when the stub Invite is
sent (CM-11-006), never on the Accept.  The activation step
lives in ``invite_participant_persist.py``. Composed by
``create_accept_invite_actor_to_case_tree`` (BTND-07-003).
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.models.case_participant import CaseParticipant

logger = logging.getLogger(__name__)


class CheckInviteeNotAlreadyParticipantNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """Idempotency guard: FAILURE when the invitee is already joined or removed.

    The answer reads the invitee's participant record alone (CM-17-012),
    never any replication state the CASE_MANAGER holds for it: the embargo
    pause, the ledger-sync acknowledgement and the replay guard write that
    state too.

    - **Joined or removed record** → ``_idempotent_failure`` (FAILURE, INFO
      log, no ledger write; CLP-13-001, CLP-13-002).  A participant is joined
      when the case initialization sequence seated it or it already accepted
      its stub Invite (CM-10-004), so its Accept changes nothing.  A
      *removed* participant (CM-31-001) is sent no full-case Invite and no
      backfill until it is reinstated (CM-31-013).
    - **Inert record** (``joined=False``, CM-11-006) → SUCCESS: its first
      Accept joins it and runs the backfill (CM-17-004).
    - **No record** → SUCCESS: ``InviteeHasParticipantRecordNode`` refuses
      it next, before any write, since an Accept never creates a participant
      (CM-11-021).

    Writes the case to ``invitee_case`` on SUCCESS for the consent nodes, and
    ``None`` on the duplicate path (BT-17-003).
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "invitee_case": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"invitee_case": "/invitee_case"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        participant_id = case.actor_participant_index.get(self.invitee_id)
        record = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if isinstance(record, CaseParticipant) and (
            record.joined or record.removed
        ):
            self._set_output("invitee_case", None)  # BT-17-003
            return self._idempotent_failure(
                self.logger,
                "%s: actor '%s' is already %s in case '%s'"
                " — skipping its stub-Invite Accept (CM-17-012, CLP-13-001)",
                self.name,
                self.invitee_id,
                "removed" if record.removed else "joined",
                self.case_id,
            )

        self._set_output("invitee_case", case)
        return Status.SUCCESS


class InviteeHasParticipantRecordNode(DataLayerConditionWithPorts):
    """Guard: the invitee already has a participant record (CM-11-021).

    The CASE_MANAGER creates the record when it sends the stub Invite
    (CM-11-006), so an ``Accept(Invite(Actor, VulnerabilityCaseStub))`` finds
    it; an Accept never creates one.  FAILURE, with the reason as
    ``feedback_message``, when the case holds no record for the invitee.  The
    guard runs before the tree commits anything, so a refused Accept writes
    nothing.

    Writes the record to ``new_invite_participant`` for the downstream nodes.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "new_invite_participant": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"new_invite_participant": "/new_invite_participant"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        participant_id = case.actor_participant_index.get(self.invitee_id)
        record = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if not isinstance(record, CaseParticipant):
            self.feedback_message = (
                f"no participant record for '{self.invitee_id}' in case"
                f" '{self.case_id}' — Accept refused (CM-11-021)"
            )
            self.logger.warning(
                "%s: no participant record for invitee '%s' in case '%s'"
                " — refusing Accept(Invite) (CM-11-021)",
                self.name,
                self.invitee_id,
                self.case_id,
            )
            return Status.FAILURE
        self._set_output("new_invite_participant", record)
        return Status.SUCCESS
