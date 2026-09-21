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


"""Invitee participant persist/advance leaf nodes (ADR-0089 birth steps 2-3).

Persist and attach the invitee participant, then advance it to RM.RECEIVED
through the sole ``ParticipantStatus`` writer. Split from
``invite_participant.py`` to keep both modules under the BTND-07-004 cap.
Composed by ``create_accept_invite_actor_to_case_tree`` (BTND-07-003).
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.states.rm import RM

logger = logging.getLogger(__name__)


class PersistInviteeParticipantNode(DataLayerActionWithPorts):
    """Persist the participant, attach to case, record events, save case."""

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["invitee_already_participant"] = PortInformation(
            data_type=object, required=True
        )
        ports["new_invite_participant"] = PortInformation(
            data_type=object, required=True
        )
        ports["invitee_case"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_already_participant": "/invitee_already_participant",
            "new_invite_participant": "/new_invite_participant",
            "invitee_case": "/invitee_case",
        }

    def initialise(self) -> None:
        super().initialise()
        self.invitee_already_participant = self.get_input(
            "invitee_already_participant"
        )
        self.new_invite_participant = self.get_input("new_invite_participant")
        self.invitee_case = self.get_input("invitee_case")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self.invitee_already_participant:
            return Status.SUCCESS

        participant = self.new_invite_participant
        case = self.invitee_case
        if not isinstance(participant, VultronParticipant) or not isinstance(
            case, VulnerabilityCase
        ):
            self.logger.error(
                "%s: new_invite_participant or invitee_case missing",
                self.name,
            )
            return Status.FAILURE

        self.datalayer.create(participant)
        case.add_participant(participant)
        self.datalayer.save(case)
        self.logger.info(
            "%s: participant '%s' persisted and attached to case '%s'"
            " (RM.RECEIVED, CM-11-001)",
            self.name,
            participant.id_,
            self.case_id,
        )
        return Status.SUCCESS


class AdvanceInviteeToReceivedNode(DataLayerActionWithPorts):
    """Advance the freshly-attached invitee participant to RM.RECEIVED.

    ADR-0089 birth step 3 (*advance*): once
    :class:`PersistInviteeParticipantNode` has attached the participant to the
    case (at RM.START), this node advances it to ``RM.RECEIVED`` through the
    sole ``ParticipantStatus`` writer, :class:`CreateParticipantStatusNode`,
    rather than letting the participant be born already-advanced.  The write is
    attributed to the invitee (the subject), while the tree executes as the
    CaseActor (the store owner); the two actors are kept distinct (#2300).

    On the backfill-resume path (``invitee_already_participant`` is true) the
    advance is *forward-only on the participant's actual RM state*, not a blanket
    skip: an existing participant already at ``RM.RECEIVED`` or beyond keeps its
    state (forcing it back would be an illegal backward transition), but one
    still at ``RM.START`` is advanced.  Birth now commits in three separate
    steps (construct → persist → advance), so a prior run that persisted the
    participant at ``RM.START`` and then failed the advance leaves it durably at
    ``RM.START``; a blanket skip on retry would strand it there permanently, and
    ``RM.START → RM.VALID`` is illegal, so the invitee could never validate
    (issue #3283 — the #2548 family AC-4 guards).  ``RM.START → RM.RECEIVED`` is
    a legal forward move, so the retry completes the interrupted birth.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id
        from vultron.core.behaviors.case.nodes.participant.status import (
            CreateParticipantStatusNode,
        )

        # Pre-built once (BTND-10-004); its own stop() resets the latched actor
        # id after each tick (#3268).
        self._status_node = CreateParticipantStatusNode(
            actor_id=invitee_id,
            rm_state=RM.RECEIVED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        )

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["invitee_already_participant"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "invitee_already_participant": "/invitee_already_participant",
        }

    def initialise(self) -> None:
        super().initialise()
        self.invitee_already_participant = self.get_input(
            "invitee_already_participant"
        )

    def _current_participant_rm(self) -> RM | None:
        """Return the persisted invitee participant's current RM state.

        None when the participant record cannot be read or has no status yet.
        The participant id is derived the same way steps 1–2 build it
        (:class:`CreateInviteeParticipantNode`), so this reads the participant
        directly rather than resolving the case (ADR-0087: no direct
        ``read_case`` here).
        """
        assert self.datalayer is not None
        participant_id = (
            f"{self.case_id}/participants/" f"{self.invitee_id.split('/')[-1]}"
        )
        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return None
        status = participant.participant_status
        return status.rm.state if status is not None else None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if self.invitee_already_participant:
            # Backfill resume: forward-only on the participant's actual RM
            # state.  Skip only when it already reached RM.RECEIVED or beyond
            # (forcing it back would be illegal).  A participant still at
            # RM.START — a prior run persisted it but failed the advance —
            # must be advanced, or it is stranded permanently (issue #3283).
            current_rm = self._current_participant_rm()
            if current_rm is not None and current_rm != RM.START:
                return Status.SUCCESS

        from vultron.core.behaviors.bridge import BTBridge

        result = BTBridge(datalayer=self.datalayer).execute_with_setup(
            self._status_node,
            actor_id=self.actor_id,
            case_id=self.case_id,
        )
        if result.status != Status.SUCCESS:
            self.feedback_message = (
                f"failed to advance invitee '{self.invitee_id}'"
                " to RM.RECEIVED"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
        return result.status
