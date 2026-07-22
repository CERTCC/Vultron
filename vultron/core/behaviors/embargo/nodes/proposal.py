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

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)


class UpdateParticipantEmbargoPecNode(DataLayerAction):
    """Apply a PEC trigger to participant.embargo_consent_state.

    Reads participant from blackboard 'participant' key. If participant not found,
    returns SUCCESS without updating (idempotent). This supports the lenient
    OptionalLookupParticipantNode pattern: when participant doesn't exist on this
    peer, skip the PEC update but continue to cascade log entry to all peers.

    Always returns SUCCESS (idempotent best-effort update). Actual PEC state is
    only updated if participant exists on the local blackboard. Missing
    participant is treated as a temporary local state gap that will be resolved
    by peer broadcast.
    """

    def __init__(
        self,
        pec_trigger: PEC_Trigger,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.pec_trigger = pec_trigger

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="participant", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.SUCCESS

        try:
            participant = self.blackboard.participant
        except KeyError:
            self.logger.warning(
                "%s: participant not found in blackboard", self.name
            )
            return Status.SUCCESS

        if not isinstance(participant, CaseParticipant):
            self.logger.warning(
                "%s: invalid participant on blackboard", self.name
            )
            return Status.SUCCESS

        new_state = apply_pec_trigger(
            PEC(participant.embargo_consent_state), self.pec_trigger
        )
        participant.embargo_consent_state = new_state
        self.datalayer.save(participant)

        self.feedback_message = (
            f"Updated participant '{participant.id_}' embargo consent"
            f" state via {self.pec_trigger.name} trigger"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class CreateAndStoreInviteNode(DataLayerAction):
    """Idempotent storage of an InviteToEmbargoOnCase activity.

    Reads the request from the blackboard 'activity' key and uses
    request.activity_type, request.activity_id, and request.activity to
    idempotently create the invite activity in the DataLayer.

    Always returns SUCCESS (idempotent create).
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.SUCCESS

        try:
            request = self.blackboard.activity
        except KeyError:
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


class RecordParticipantAcceptanceNode(DataLayerAction):
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

        # AC-1: read em_state via named BT node before calling the service.
        from vultron.core.behaviors.embargo.nodes.em_state import (
            ReadEmStateNode,
            WriteEmStateNode,
        )

        em_result_out: dict[str, object] = {}
        read_node = ReadEmStateNode(
            case_id=self.case_id, result_out=em_result_out
        )
        read_node.datalayer = self.datalayer
        if read_node.update() != Status.SUCCESS:
            self.feedback_message = read_node.feedback_message
            return Status.FAILURE
        em_before = em_result_out["em_before"]
        assert isinstance(em_before, EM)

        service = EmbargoLifecycle(persistence=self.datalayer)
        result = service.accept_embargo_invite(
            case_id=self.case_id,
            embargo_id=self.embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.OBSERVED,
            em_before=em_before,
        )

        if result.em_after != em_before:
            em_result_out["em_after"] = result.em_after
            write_node = WriteEmStateNode(
                case_id=self.case_id, result_out=em_result_out
            )
            write_node.datalayer = self.datalayer
            if write_node.update() != Status.SUCCESS:
                self.feedback_message = write_node.feedback_message
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


class RemoveStaleAcceptanceNode(DataLayerAction):
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

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="participant", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            return Status.SUCCESS

        try:
            participant = self.blackboard.participant
        except KeyError:
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
