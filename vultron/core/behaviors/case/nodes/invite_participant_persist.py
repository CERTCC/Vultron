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


"""Invitee participant activation leaf node.

Marks the invitee's inert participant record joined when its ``Accept`` of the
stub Invite is processed (CM-11-001, ADR-0114).  The record already exists:
the stub Invite created it at RM.RECEIVED (CM-11-006), and
``InviteeHasParticipantRecordNode`` refuses an Accept that finds none
(CM-11-021).  Composed by ``create_accept_invite_actor_to_case_tree``
(BTND-07-003).
"""

from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.case.participant_ledger import (
    commit_participant_status_added,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.stub_reply import mark_joined, reply_published
from vultron.core.ports.case_outbox import CaseOutboxPersistence


class ActivateInviteeParticipantNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Set ``joined=True`` on the invitee's existing participant record.

    A record that is already joined (the backfill-resume path) is left as it
    is.  RM stays at ``RECEIVED``: accepting the stub is joining, not judging
    the case (CM-11-001).
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "new_invite_participant": PortInformation(
            data_type=object, required=True
        ),
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "new_invite_participant": "/new_invite_participant",
            "activity": "/activity",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._participant_bb = self.get_input("new_invite_participant")
        except (NoDataAvailable, NotImplementedError):
            self._participant_bb = None
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        participant = self._participant_bb
        if not isinstance(participant, CaseParticipant):
            self.logger.error(
                "%s: participant record not on blackboard for '%s'",
                self.name,
                self.invitee_id,
            )
            return Status.FAILURE
        try:
            published = reply_published(self.activity)
        except ValueError as exc:
            self.feedback_message = f"{self.name}: {exc} (CLP-15-006)"
            self.logger.exception("%s", self.feedback_message)
            return Status.FAILURE
        # The same write a replica makes from the Accept's own entry; the
        # record's time is the Accept's ``published``, never the local clock.
        if mark_joined(participant, published):
            self.datalayer.save(participant)
            self.logger.info(
                "%s: promoted inert participant '%s' to joined=True"
                " (ADR-0114, CM-11-006)",
                self.name,
                participant.id_,
            )
        return Status.SUCCESS


class CommitInviteeAcceptEntriesNode(DataLayerActionWithPorts):
    """Ledger the status the Accept made on the invitee's record (ADR-0114).

    The ledger holds the wire messages exchanged: the invitee's Accept is the
    entry for its consent and its ``joined`` mark.  The vendor-aware status
    (VF ``Vf``, VENDOR role only) is a CASE_MANAGER-written object with its own
    id and times, so it has its own ``add_participant_status_to_participant``
    entry.  It is committed here, after the case announce and the backfill of
    the prior ledger, so it reaches the invitee in chain order and not before
    its case seed (#2898).  A resumed Accept that appended no status commits
    nothing.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "invitee_vf_status_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"invitee_vf_status_id": "/invitee_vf_status_id"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self._status_id = self.get_input("invitee_vf_status_id")
        except (NoDataAvailable, NotImplementedError, KeyError):
            self._status_id = None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        if not self._status_id:
            return Status.SUCCESS
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        participant_id = case.actor_participant_index.get(self.invitee_id)
        record = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if not isinstance(record, CaseParticipant):
            self.feedback_message = (
                f"{self.name}: no record for '{self.invitee_id}' to ledger"
            )
            return Status.FAILURE
        status = next(
            (
                x
                for x in record.participant_statuses
                if x.id_ == self._status_id
            ),
            None,
        )
        if status is None:
            return Status.SUCCESS
        try:
            commit_participant_status_added(
                datalayer=cast(CaseOutboxPersistence, self.datalayer),
                actor_id=self.actor_id,
                case_id=self.case_id,
                participant=record,
                status=status,
                wire_render_port=self._require_wire_render_port(),
            )
        except RuntimeError as exc:
            self.feedback_message = f"{self.name}: {exc}"
            self.logger.exception("%s", self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS
