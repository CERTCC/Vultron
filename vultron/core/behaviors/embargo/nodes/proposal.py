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
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.participant_embargo_consent import PEC_Trigger


class UpdateParticipantEmbargoPecNode(DataLayerActionWithPorts):
    """Apply a PEC trigger to participant.embargo_consent_state.

    Reads participant from blackboard 'participant' key. If participant not found,
    returns SUCCESS without updating (idempotent). This supports the lenient
    OptionalLookupParticipantNode pattern: when participant doesn't exist on this
    peer, skip the PEC update but continue to cascade log entry to all peers.

    Returns SUCCESS when the participant is absent or the DataLayer is
    unavailable. Raises ``VultronInvalidStateTransitionError`` (via
    ``apply_pec_transition``) if the trigger is illegal for the current
    PEC state — callers should ensure the trigger is valid for the
    participant's current consent state before invoking this node.
    """

    def __init__(
        self,
        pec_trigger: PEC_Trigger,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.pec_trigger = pec_trigger

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["participant"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"participant": "/participant"}

    def initialise(self) -> None:
        super().initialise()
        self._participant = None
        try:
            self._participant = self.get_input("participant")
        except (NoDataAvailable, NotImplementedError):
            self._participant = None

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.SUCCESS

        participant = self._participant
        if participant is None:
            self.logger.warning(
                "%s: participant not found in blackboard", self.name
            )
            return Status.SUCCESS

        if not isinstance(participant, CaseParticipant):
            self.logger.warning(
                "%s: invalid participant on blackboard", self.name
            )
            return Status.SUCCESS

        participant.apply_pec_transition(self.pec_trigger)
        self.datalayer.save(participant)

        self.feedback_message = (
            f"Updated participant '{participant.id_}' embargo consent"
            f" state via {self.pec_trigger.name} trigger"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class CreateAndStoreInviteNode(DataLayerActionWithPorts):
    """Idempotent storage of an InviteToEmbargoOnCase activity.

    Reads the request from the blackboard 'activity' key and uses
    request.activity_type, request.activity_id, and request.activity to
    idempotently create the invite activity in the DataLayer.

    Always returns SUCCESS (idempotent create).
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=False)
        return ports

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

        from vultron.core.use_cases._helpers import (
            _idempotent_create,
        )

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
        from vultron.core.states.em import EM

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
        result = service.accept_embargo_invite(
            case_id=self.case_id,
            embargo_id=self.embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.OBSERVED,
        )

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


class RemoveStaleAcceptanceNode(DataLayerActionWithPorts):
    """Remove stale embargo acceptance from participant (pocket-veto).

    Reads participant from blackboard, removes embargo_id from
    accepted_embargo_ids if present (pocket-veto semantics).

    Always returns SUCCESS.
    """

    def __init__(
        self,
        embargo_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.embargo_id = embargo_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["participant"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"participant": "/participant"}

    def initialise(self) -> None:
        super().initialise()
        self._participant = None
        try:
            self._participant = self.get_input("participant")
        except (NoDataAvailable, NotImplementedError):
            self._participant = None

    def update(self) -> Status:
        if self.datalayer is None:
            return Status.SUCCESS

        participant = self._participant
        if participant is None:
            self.logger.debug(
                "%s: participant not found in blackboard", self.name
            )
            return Status.SUCCESS

        if not isinstance(participant, CaseParticipant):
            self.logger.debug(
                "%s: invalid participant on blackboard", self.name
            )
            return Status.SUCCESS

        if self.embargo_id in participant.accepted_embargo_ids:
            participant.accepted_embargo_ids.remove(self.embargo_id)
            self.datalayer.save(participant)
            self.feedback_message = (
                f"Removed stale acceptance '{self.embargo_id}' from"
                f" participant '{participant.id_}' (pocket-veto)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
        else:
            self.feedback_message = (
                f"No stale acceptance '{self.embargo_id}' to remove"
                f" from participant"
            )

        return Status.SUCCESS
