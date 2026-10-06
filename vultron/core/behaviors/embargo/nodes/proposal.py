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

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases._helpers import (
    _idempotent_create,
)
from vultron.errors import (
    VultronNotAnEmbargoError,
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

        _idempotent_create(
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


def _unreadable_embargo_id(
    exc: VultronNotFoundError | VultronValidationError,
) -> str | None:
    """The embargo id a fail-closed embargo read named, if *exc* is one.

    :func:`~vultron.core.services.embargo_ordering.read_embargo_event` raises
    :exc:`VultronNotFoundError` for a missing ``EmbargoEvent`` and
    :exc:`VultronNotAnEmbargoError` for a record of another type; any other
    error did not come from an embargo read.
    """
    if (
        isinstance(exc, VultronNotFoundError)
        and exc.resource_type == "EmbargoEvent"
    ):
        return exc.resource_id
    if isinstance(exc, VultronNotAnEmbargoError):
        return exc.embargo_id
    return None


class RecordParticipantAcceptanceNode(DataLayerActionWithPorts):
    """Record participant acceptance of embargo via EmbargoLifecycle.

    Uses EmbargoLifecycle.accept_embargo_invite(OBSERVED) to record the
    acceptance and apply any state transitions.

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
            result = service.accept_embargo_invite(
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=actor_id,
                transition_mode=TransitionMode.OBSERVED,
            )
        except (VultronNotFoundError, VultronValidationError) as exc:
            unreadable_id = _unreadable_embargo_id(exc)
            if unreadable_id is not None and unreadable_id != self.embargo_id:
                # The case names an active embargo its own store cannot read
                # (missing, or not an EmbargoEvent): no path may write that
                # state (EMB-18-003), so this is a broken invariant, refused —
                # never parked for a replay that nothing would drive.
                self.feedback_message = (
                    f"Invariant violation (EMB-18-003): case '{self.case_id}'"
                    f" names active embargo '{unreadable_id}', which this"
                    " store cannot read; refusing the acceptance of embargo"
                    f" '{self.embargo_id}'"
                )
                self.logger.exception(
                    "%s: %s", self.name, self.feedback_message
                )
            else:
                self.feedback_message = str(exc)
                self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if result.em_after == EM.ACTIVE and result.em_before not in (
            EM.PROPOSED,
            EM.REVISE,
        ):
            self.logger.warning(
                "%s: EM transition %s → ACTIVE is not a standard machine"
                " transition for case '%s'; applying state-sync override",
                self.name,
                result.em_before,
                self.case_id,
            )

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
    state: deciding the proposal is the tree's
    :class:`RemoveFromProposedEmbargoesNode`, and the owner's EM move is the
    CASE_MANAGER's adjudication (EP-09-005).

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
