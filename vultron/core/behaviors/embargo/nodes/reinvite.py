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

"""The CASE_MANAGER's EMB-17-003 re-invite of a late accepter (EMB-17-011).

A late ``Accept`` names an embargo that is no longer the case's current one,
so the manager asks the accepter again about the current embargo.  The frame is
the relay's (:class:`~vultron.core.behaviors.embargo.nodes.relay.RelayEmbargoInviteToEachNode`),
narrowed to one fixed recipient and committed under an event type of its own.
"""

from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.relay import (
    RelayEmbargoInviteToEachNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.rsvp_deadline import EMBARGO_REINVITE_EVENT_TYPE

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig


class ReinviteStaleAccepterNode(RelayEmbargoInviteToEachNode):
    """Commit and send the CASE_MANAGER's EMB-17-003 re-invite of one accepter.

    A late ``Accept`` named an embargo that is no longer the case's current
    one, so the manager asks the accepter again about the current embargo
    (EMB-17-003).  The frame is the relay's — stamp a fresh deadline (ASK-03-004,
    CM-28-012), build, commit before the outbox write, queue, apply PEC
    ``INVITE`` and record the deadline (CM-18-003, CM-28-013) — with two
    differences: the Invite is the manager's own ask, so it has no
    ``attributedTo``, and it is committed under
    :data:`~vultron.core.models.rsvp_deadline.EMBARGO_REINVITE_EVENT_TYPE`, so
    a replica replays the invitee's record and never re-adjudicates a proposal
    (EP-09-007, RSH-08-004).  The recipient and embargo are fixed at
    construction; the collect node and the recipients key are not used.
    """

    _EVENT_TYPE = EMBARGO_REINVITE_EVENT_TYPE

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        invitee_id: str,
        name: str | None = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        # No proposer: ``_attributed_to`` answers ``None``.
        super().__init__(
            case_id=case_id,
            embargo_id=embargo_id,
            proposer_id="",
            name=name or self.__class__.__name__,
            actor_config=actor_config,
        )
        self._invitee_id = invitee_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"sync_port": "/sync_port"}

    def _load_relay_inputs(self) -> None:
        self._recipients = [self._invitee_id]

    def _attributed_to(self) -> str | None:
        return None


class InviteReinstatedParticipantToEmbargoNode(ReinviteStaleAccepterNode):
    """Invite a reinstated participant to the active embargo it is not bound by.

    A participant reinstated into a case whose active embargo it has not
    accepted stays inert, so the CASE_MANAGER asks it (CM-31-013, ADR-0116):
    the same one-recipient Invite as the EMB-17-003 re-invite, the manager's
    own ask about the embargo in force, committed under
    :data:`~vultron.core.models.rsvp_deadline.EMBARGO_REINVITE_EVENT_TYPE`.
    Its CM-10-006 backfill waits for its consent: the honored ``Accept``
    admits it, and that tree backfills it.

    Which embargo, and whether any Invite is owed, are read at tick time:
    nothing is sent when no embargo is active or the participant is already
    ``SIGNATORY`` to it, since it is then active and was backfilled.
    """

    def __init__(
        self,
        case_id: str,
        invitee_id: str,
        participant_id: str,
        name: str | None = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            embargo_id="",
            invitee_id=invitee_id,
            name=name or self.__class__.__name__,
            actor_config=actor_config,
        )
        self._participant_id = participant_id

    def _load_relay_inputs(self) -> None:
        self._recipients = []

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        record = self.datalayer.read(self._participant_id)
        if not isinstance(record, CaseParticipant):
            self.feedback_message = (
                f"participant '{self._participant_id}' not found"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        embargo_id = case.active_embargo_id
        if not case.embargo_in_force or embargo_id is None:
            self.feedback_message = (
                f"case '{self._case_id}' has no active embargo; no Invite owed"
            )
            return Status.SUCCESS
        if record.is_signatory(embargo_id):
            self.feedback_message = (
                f"'{self._invitee_id}' is SIGNATORY to embargo"
                f" '{embargo_id}'; no Invite owed"
            )
            return Status.SUCCESS
        self._embargo_id = embargo_id
        self._recipients = [self._invitee_id]
        return super().update()


__all__ = [
    "InviteReinstatedParticipantToEmbargoNode",
    "ReinviteStaleAccepterNode",
]
