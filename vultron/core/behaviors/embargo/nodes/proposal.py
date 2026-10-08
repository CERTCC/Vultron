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

"""Embargo invitation and proposal workflow nodes."""

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
)
from vultron.core.services.idempotent_store import idempotent_store
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import (
    VultronNotFoundError,
    VultronValidationError,
)

#: Opens the feedback of a :class:`RecordParticipantRejectionNode` FAILURE
#: that is a repeat of a Reject already recorded.  The received reject use
#: case reads it to report ``SKIPPED`` rather than ``REFUSED`` (HP-01-003) —
#: the node's own verdict, not the store's state, names the repeat.
ALREADY_DECLINED_PREFIX = "Already declined"


class CreateAndStoreInviteNode(DataLayerActionWithPorts):
    """Idempotent storage of an InviteToEmbargoOnCase activity.

    Reads the request from the blackboard 'activity' key and uses
    request.activity_type, request.activity_id, and request.activity to
    idempotently create the invite activity in the DataLayer.

    Always returns SUCCESS (idempotent create).
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self._activity = None
        try:
            self._activity = self.get_input("activity")
        except (NoDataAvailable, NotImplementedError):
            self._activity = None

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.SUCCESS

        request = self._activity
        if request is None:
            self.logger.warning(
                "%s: request not found in blackboard", self.name
            )
            return Status.SUCCESS

        activity_type = getattr(request, "activity_type", None)
        activity_id = getattr(request, "activity_id", None)
        activity = getattr(request, "activity", None)

        if not activity_type or not activity_id or not activity:
            self.logger.warning(
                "%s: missing activity_type, activity_id, or activity on request",
                self.name,
            )
            return Status.SUCCESS

        idempotent_store(
            self.datalayer,
            activity_type,
            activity_id,
            activity,
            "InviteToEmbargoOnCase",
            activity_id,
        )

        self.feedback_message = f"Stored invite activity '{activity_id}'"
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class IndexReceivedEmbargoProposalNode(DataLayerActionWithPorts):
    """Record ``embargo_id -> invite_id`` on the case once the Invite is applied.

    Lets the accept/reject triggers correlate an embargo with the Invite that
    proposed it without re-reading the wire activity (ADR-0035 DL-06).  It
    runs last among the effects, so the correlation is written only after
    every other half of the receipt has succeeded (ID-04-005).  A partial
    replica that holds no copy of the case keeps the Invite and indexes
    nothing (Regime 2, ADR-0087), so it still returns ``SUCCESS``.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        invite_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._invite_id = invite_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            record_embargo_proposal_index(
                self.datalayer,
                self._case_id,
                self._embargo_id,
                self._invite_id,
            )
        except VultronNotFoundError:
            self.feedback_message = (
                f"case '{self._case_id}' not held here — proposal"
                f" '{self._invite_id}' not indexed"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        self.feedback_message = (
            f"Indexed proposal '{self._invite_id}' for embargo"
            f" '{self._embargo_id}' on case '{self._case_id}'"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class RecordParticipantAcceptanceNode(DataLayerActionWithPorts):
    """Record a participant's acceptance of an embargo Invite.

    Uses ``EmbargoLifecycle.accept_embargo_invite`` to record the sender's
    own consent — the case owner's included — moving no register entry
    (MSM-07-003, ADR-0122).

    When ``accepting_actor_id`` is provided it is used instead of the BT
    execution ``actor_id`` (which is the receiving actor).  This is the
    ADR-0022 single-BT pattern: the tree executes under
    ``actor_id=receiving_actor_id`` for guarded-commit gating, while the
    acceptance is recorded for the message's actual accepting actor.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        accepting_actor_id: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.accepting_actor_id = accepting_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        # Use accepting_actor_id when provided (ADR-0022 single-BT pattern:
        # tree executes under receiving_actor_id but acceptance is recorded
        # for the actual accepting actor). Fall back to BT execution actor_id.
        actor_id = (
            self.accepting_actor_id
            if self.accepting_actor_id
            else self.actor_id
        )
        if actor_id is None:
            self.feedback_message = "actor_id not available"
            return Status.FAILURE

        service = EmbargoLifecycle(persistence=self.datalayer)
        try:
            service.accept_embargo_invite(
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=actor_id,
            )
        except VultronNotFoundError as exc:
            # The case itself is missing: consent reads no embargo record,
            # so nothing else can fail here (ADR-0122).
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.feedback_message = (
            f"Recorded acceptance of embargo '{self.embargo_id}'"
            f" for case '{self.case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class RecordParticipantRejectionNode(DataLayerActionWithPorts):
    """Record a participant's rejection of an embargo via EmbargoLifecycle.

    The received-side twin of :class:`RecordParticipantAcceptanceNode`: calls
    ``EmbargoLifecycle.record_embargo_rejection`` so the received
    ``Reject(Invite(EmbargoEvent))`` tree applies the same MSM-07-004 rule
    as the trigger side (ADR-0093) — a Reject naming the *active* embargo is
    consent withdrawal (the actor's row for it becomes ``DECLINED``, a
    signatory's included); one naming a *proposed* embargo declines that
    embargo's row only; the owner's EJ changes nobody's record.  Moves no EM
    state: deciding the proposal is the CASE_MANAGER's adjudication
    (``DecideRejectedEmbargoProposalNode``, EP-09-005).

    ``rejecting_actor_id`` names the message's actor (the tree executes as the
    receiving actor, ADR-0022).  Returns SUCCESS when the actor has no
    participant record here (a partial replica) and when the rejection is a
    repeat that changes nothing.  Returns FAILURE — so the handler reports a
    refusal — when the Reject names an embargo that is neither active nor an
    open proposal of the case (a protocol error, not a consent change), or
    when the case is not found.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        rejecting_actor_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.rejecting_actor_id = rejecting_actor_id

    def _already_declined(self, case: VulnerabilityCase) -> bool:
        """True when the rejecting actor's row for the embargo is already DECLINED."""
        assert self.datalayer is not None
        participant_id = case.actor_participant_index.get(
            self.rejecting_actor_id
        )
        participant = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        return (
            isinstance(participant, CaseParticipant)
            and participant.consent_for(self.embargo_id)
            == EmbargoConsentState.DECLINED
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        service = EmbargoLifecycle(persistence=self.datalayer)
        try:
            result = service.record_embargo_rejection(
                case_id=self.case_id,
                actor_id=self.rejecting_actor_id,
                embargo_id=self.embargo_id,
            )
        except (VultronNotFoundError, VultronValidationError) as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if not result.participant_changes and self._already_declined(case):
            # A repeat of a Reject already recorded (HP-01-003, #2255): the
            # handler reads this FAILURE's prefix as SKIPPED.
            self.feedback_message = (
                f"{ALREADY_DECLINED_PREFIX}: '{self.rejecting_actor_id}'"
                f" had declined embargo '{self.embargo_id}' on case"
                f" '{self.case_id}' before this Reject"
            )
            return Status.FAILURE

        self.feedback_message = (
            f"Recorded rejection of embargo '{self.embargo_id}' by"
            f" '{self.rejecting_actor_id}' on case '{self.case_id}'"
            f" ({len(result.participant_changes)} consent row change(s))"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
