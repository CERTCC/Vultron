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
    commit_case_participant_updated,
    commit_participant_status_added,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models._helpers import now_utc
from vultron.core.models.case_participant import CaseParticipant
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
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "invitee_joined_now": PortInformation(data_type=bool, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "new_invite_participant": "/new_invite_participant",
            "invitee_joined_now": "/invitee_joined_now",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._participant_bb = self.get_input("new_invite_participant")
        except (NoDataAvailable, NotImplementedError):
            self._participant_bb = None

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
        self._set_output("invitee_joined_now", False)
        if not participant.joined:
            participant.joined = True
            participant.updated = now_utc()
            self.datalayer.save(participant)
            self._set_output("invitee_joined_now", True)
            self.logger.info(
                "%s: promoted inert participant '%s' to joined=True"
                " (ADR-0114, CM-11-006)",
                self.name,
                participant.id_,
            )
        return Status.SUCCESS


class CommitInviteeAcceptEntriesNode(DataLayerActionWithPorts):
    """Ledger the changes the Accept made to the invitee's record (ADR-0114).

    Every state change the CASE_MANAGER makes emits an entry.  The Accept's
    changes are made first (the consent row signed, ``joined`` set, a vendor's
    VF advanced) so the invitee is active when the case is announced to it, and
    they are ledgered here, after the announce and the backfill of the prior
    ledger: a ledger entry committed earlier would fan out to the invitee
    before its case seed (#2898).  Two entries, from the record as stored:

    - ``update_case_participant`` -- the record with its consent row and
      ``joined`` mark, committed only when this Accept joined the invitee;
    - ``add_participant_status_to_participant`` -- the vendor-aware status, only
      when this Accept appended one.

    A resumed Accept that changed nothing commits nothing.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "invitee_joined_now": PortInformation(data_type=bool, required=False),
        "invitee_vf_status_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_joined_now": "/invitee_joined_now",
            "invitee_vf_status_id": "/invitee_vf_status_id",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._joined_now = bool(self.get_input("invitee_joined_now"))
        except (NoDataAvailable, NotImplementedError, KeyError):
            self._joined_now = False
        try:
            self._status_id = self.get_input("invitee_vf_status_id")
        except (NoDataAvailable, NotImplementedError, KeyError):
            self._status_id = None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        if not self._joined_now and not self._status_id:
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
        port = self._require_wire_render_port()
        outbox = cast(CaseOutboxPersistence, self.datalayer)
        try:
            if self._joined_now:
                commit_case_participant_updated(
                    datalayer=outbox,
                    actor_id=self.actor_id,
                    case_id=self.case_id,
                    participant=record,
                    wire_render_port=port,
                )
            status = next(
                (
                    s
                    for s in record.participant_statuses
                    if s.id_ == self._status_id
                ),
                None,
            )
            if status is not None:
                commit_participant_status_added(
                    datalayer=outbox,
                    actor_id=self.actor_id,
                    case_id=self.case_id,
                    participant=record,
                    status=status,
                    wire_render_port=port,
                )
        except RuntimeError as exc:
            self.feedback_message = f"{self.name}: {exc}"
            self.logger.exception("%s", self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS
