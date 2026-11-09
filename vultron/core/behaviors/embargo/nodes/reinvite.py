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

"""The CASE_MANAGER's EMB-17-003 re-invite of a late accepter.

A late ``Accept`` names an embargo the case can no longer answer, so the
manager asks the accepter about the case's terms instead: its Active Embargo,
or else its earliest-expiring open proposal (EMB-17-003).  The
re-invite is a relay (:class:`~vultron.core.behaviors.embargo.nodes.relay.RelayEmbargoInviteToEachNode`),
narrowed to one fixed recipient: ``attributedTo`` names the current embargo's
proposer, and it is committed as ``invite_to_embargo_on_case`` (ADR-0152).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.late_accept import (
    late_accept_terms,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    RelayEmbargoInviteToEachNode,
)
from vultron.core.behaviors.embargo.proposer import embargo_proposer_id
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.recipients import invitation_recipients
from vultron.core.services.embargo_lifecycle.pec import (
    find_actor_participant,
)
from vultron.core.states.participant_embargo_consent import (
    PEC_Trigger,
    consent_trigger_is_legal,
)
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import BtNodePreconditionError, VultronNotFoundError

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig


class ReinviteStaleAccepterNode(RelayEmbargoInviteToEachNode):
    """Commit and send the CASE_MANAGER's EMB-17-003 re-invite of one accepter.

    A late ``Accept`` named an embargo the case can no longer answer, so the
    manager asks the accepter about the case's terms instead (EMB-17-003).
    The re-invite is a relay (ADR-0152): the frame is the relay's — stamp
    a fresh deadline (ASK-03-004, CM-28-012), build, queue,
    commit once queued (ADR-0119), apply PEC ``INVITE`` and record the
    deadline (CM-18-003, CM-28-013) — with ``attributedTo`` naming the
    embargo's proposer, read from the case's ledger
    (:func:`~vultron.core.behaviors.embargo.proposer.embargo_proposer_id`),
    or the CASE_MANAGER itself when it made the embargo without a proposal,
    as it makes the protocol default.  It is committed as
    ``invite_to_embargo_on_case``, and a replica applies it through the relay
    slot: the register already holds the embargo it names, so it proposes
    nothing and EM does not move (EP-09-007, RSH-08-004).  The recipient and
    embargo are fixed at construction; the collect node and the recipients
    key are not used.  *answers* is the received activity the re-invite
    answers (the late ``Accept``, or the ``Add(CaseParticipant)`` that
    reinstated the invitee): given, the Invite's id is derived from it, so a
    redelivery after a send whose commit failed rebuilds the same Invite
    (OX-06-002).

    The one recipient is still judged by
    :func:`~vultron.core.participants.recipients.invitation_recipients`
    (CM-10-009): a removed or RM ``CLOSED`` invitee is sent nothing, and the
    node succeeds without an Invite (CM-31-013, ADR-0116).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        invitee_id: str,
        name: str | None = None,
        actor_config: "ActorConfig | None" = None,
        *,
        answers: str | None = None,
    ) -> None:
        # The proposer is read from the ledger once the embargo is known.
        super().__init__(
            case_id=case_id,
            embargo_id=embargo_id,
            proposer_id="",
            name=name or self.__class__.__name__,
            actor_config=actor_config,
            answers=answers,
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
        self._recipients = []

    def _invite_owed(self, case: VulnerabilityCase) -> bool:
        """Fix the embargo and invitee for this tick; ``False`` when none is owed.

        The stale accepter's embargo and invitee are fixed at construction.

        Raises:
            VultronNotFoundError: A subclass cannot resolve its invitee in
                the CASE_MANAGER's own store; the node fails.
            BtNodePreconditionError: A subclass finds no terms where its
                route promised some; the node fails.
        """
        return True

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        precondition: BtNodePreconditionError | None = None
        try:
            if not self._invite_owed(case):
                return Status.SUCCESS
        except BtNodePreconditionError as exc:
            precondition = exc
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.exception("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if precondition is not None:
            # The node's own finding, not a fault below it: no traceback.
            self.feedback_message = str(precondition)
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if self._invitee_id not in invitation_recipients(case, self.datalayer):
            self.feedback_message = (
                f"'{self._invitee_id}' is not an invitation recipient of case"
                f" '{self._case_id}' (removed or RM CLOSED); no Invite sent"
                " (CM-31-013)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        self._recipients = [self._invitee_id]
        # Whose terms these are (CM-24-002): the CASE_MANAGER's own when it
        # made the embargo without a proposal (ADR-0152).
        self._proposer_id = (
            embargo_proposer_id(
                recorded_entries_for_case(
                    case_id=self._case_id, dl=self.datalayer
                ),
                self._embargo_id,
            )
            or self.actor_id
        )
        return super().update()


class ReinviteLateAccepterNode(ReinviteStaleAccepterNode):
    """Re-invite a late accepter to the case's terms (EMB-17-003).

    The late Accept's routing arm (CLP-10-026): the case cannot answer the
    accepted embargo, so the CASE_MANAGER asks the accepter about the terms
    it holds — its Active Embargo, or with none its earliest-expiring open
    proposal whose embargo has not ended at *now*
    (:func:`~vultron.core.behaviors.embargo.nodes.late_accept.late_accept_terms`,
    EP-08-002).  Which terms are read when the node runs, after the Invite
    expiry was recorded.  The Accept is never recorded as consent
    (EMB-17-005, EMB-17-006).

    Nothing is sent, and the node succeeds, when the accepter's row for those
    terms takes no ``INVITE`` — it is already ``INVITED`` or ``AGREED``, so
    it has been asked, or has answered, and asking again would undo nothing
    (CM-18-003; the EP-09-011 guard) — logged at INFO; or when this actor
    was composed without the trigger-activity port that builds the Invite,
    logged at WARNING.  The route sends a late Accept here only when the
    case holds terms, so finding none is a routing bug: the node fails
    (ARCH-15).
    """

    def __init__(
        self,
        case_id: str,
        invitee_id: str,
        name: str | None = None,
        actor_config: "ActorConfig | None" = None,
        *,
        now: datetime,
        answers: str | None = None,
    ) -> None:
        # The embargo is resolved at tick time.
        super().__init__(
            case_id=case_id,
            embargo_id="",
            invitee_id=invitee_id,
            name=name or self.__class__.__name__,
            actor_config=actor_config,
            answers=answers,
        )
        self._now = now

    def _invite_owed(self, case: VulnerabilityCase) -> bool:
        assert self.datalayer is not None
        embargo_id = late_accept_terms(self.datalayer, case, self._now)
        if embargo_id is None:
            raise BtNodePreconditionError(
                f"late Accept for case '{self._case_id}' routed to the"
                f" re-invite, but the case holds no terms to invite"
                f" '{self._invitee_id}' to (EMB-17-003)"
            )
        if self.trigger_activity_factory is None:
            self.feedback_message = (
                f"late Accept for a stale embargo on case '{self._case_id}'"
                " — trigger_activity unavailable, re-invite not emitted"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return False
        consent = self._invitee_record(case).consent_for(embargo_id)
        if not consent_trigger_is_legal(consent, PEC_Trigger.INVITE):
            self.feedback_message = (
                f"'{self._invitee_id}' is already {consent} for embargo"
                f" '{embargo_id}' on case '{self._case_id}'; no re-invite"
                " sent (CM-18-003)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return False
        self._embargo_id = embargo_id
        return True

    def _invitee_record(self, case: VulnerabilityCase) -> CaseParticipant:
        """The accepter's participant record in the CASE_MANAGER's store.

        Read through the one actor-to-participant lookup (CM-19-003).

        Raises:
            VultronNotFoundError: The case indexes no record for the
                accepter, or the record is not a ``CaseParticipant``.
        """
        assert self.datalayer is not None
        resolved = find_actor_participant(
            self.datalayer, case, self._invitee_id
        )
        if resolved is None:
            raise VultronNotFoundError(
                "CaseParticipant",
                f"'{self._invitee_id}' on case '{self._case_id}'",
            )
        return resolved[1]


class InviteReinstatedParticipantToEmbargoNode(ReinviteStaleAccepterNode):
    """Invite a reinstated participant to the active embargo it is not bound by.

    A participant reinstated into a case whose active embargo it has not
    accepted stays inert, so the CASE_MANAGER asks it (CM-31-040, ADR-0116):
    the same one-recipient Invite as the EMB-17-003 re-invite, the manager's
    relayed ask about the embargo in force, attributed to its proposer and
    committed as ``invite_to_embargo_on_case`` (ADR-0152).
    Its CM-10-006 backfill waits for its consent: the honored ``Accept``
    admits it, and that tree backfills it.

    Which embargo, which actor, and whether any Invite is owed are read at
    tick time: the invitee is the actor the stored record belongs to, and
    nothing is sent when no embargo is active or the participant is already
    a signatory to it, since it is then active and was backfilled.
    ``FAILURE`` when the record is gone or names no actor: the guards found
    it moments earlier in the CASE_MANAGER's own store (Regime 1, ADR-0087),
    so the handler reads it as an internal fault.
    """

    def __init__(
        self,
        case_id: str,
        participant_id: str,
        name: str | None = None,
        actor_config: "ActorConfig | None" = None,
        *,
        answers: str | None = None,
    ) -> None:
        # The embargo and the invitee are resolved at tick time.
        super().__init__(
            case_id=case_id,
            embargo_id="",
            invitee_id="",
            name=name or self.__class__.__name__,
            actor_config=actor_config,
            answers=answers,
        )
        self._participant_id = participant_id

    def _invite_owed(self, case: VulnerabilityCase) -> bool:
        assert self.datalayer is not None
        record = self.datalayer.read(self._participant_id)
        invitee_id = (
            _as_id(record.attributed_to)
            if isinstance(record, CaseParticipant)
            else None
        )
        if not invitee_id:
            raise VultronNotFoundError(
                "CaseParticipant",
                f"'{self._participant_id}' names no actor on case"
                f" '{self._case_id}'",
            )
        assert isinstance(record, CaseParticipant)
        self._invitee_id = invitee_id
        embargo_id = case.active_embargo_id
        if not case.embargo_in_force or embargo_id is None:
            self.feedback_message = (
                f"case '{self._case_id}' has no active embargo; no Invite owed"
            )
            return False
        if record.is_signatory(embargo_id):
            self.feedback_message = (
                f"'{invitee_id}' is a signatory to embargo '{embargo_id}';"
                " no Invite owed"
            )
            return False
        self._embargo_id = embargo_id
        return True


__all__ = [
    "InviteReinstatedParticipantToEmbargoNode",
    "ReinviteLateAccepterNode",
    "ReinviteStaleAccepterNode",
]
