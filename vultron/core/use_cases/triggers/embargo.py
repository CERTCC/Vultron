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

import logging

from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.use_cases.triggers._helpers import (
    _coerce_embargo_event,
    _is_case_owner,
    _resolve_embargo_id_from_proposal,
    _resolve_embargo_proposal,
    resolve_actor,
    resolve_case,
    send_case_actor_activity,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    RejectEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)


class SvcProposeEmbargoUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: ProposeEmbargoTriggerRequest,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: ProposeEmbargoTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        end_time = request.end_time
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        embargo_kwargs: dict = {"context": case.id_}
        if end_time is not None:
            embargo_kwargs["end_time"] = end_time

        embargo = EmbargoEvent(**embargo_kwargs)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcProposeEmbargoUseCase requires a TriggerActivityPort"
            )

        lifecycle = EmbargoLifecycle(persistence=dl)
        lifecycle_result = lifecycle.propose_embargo(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )

        try:
            dl.create(embargo)
        except ValueError:
            logger.warning("EmbargoEvent '%s' already exists", embargo.id_)

        factory = self._trigger_activity
        captured: dict = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            proposal_id, proposal_dict = factory.propose_embargo(
                embargo_id=embargo.id_,
                case_id=case.id_,
                actor=actor_id,
                to=[case_manager_id],
            )
            captured["activity"] = proposal_dict
            return [proposal_id]

        send_case_actor_activity(
            dl=dl,
            case_id=case.id_,
            actor_id=actor_id,
            trigger_activity=factory,
            failure_label="ProposeEmbargo",
            activity_builder=_build_activities,
        )

        if lifecycle_result.em_after != lifecycle_result.em_before:
            logger.info(
                "Actor '%s' proposed embargo '%s' on case '%s' (EM %s → %s)",
                actor_id,
                embargo.id_,
                case.id_,
                lifecycle_result.em_before,
                lifecycle_result.em_after,
            )
        else:
            logger.info(
                "Actor '%s' counter-proposed embargo '%s' on case '%s'"
                " (EM %s, no state change)",
                actor_id,
                embargo.id_,
                case.id_,
                lifecycle_result.em_before,
            )

        return {"activity": captured.get("activity")}


class SvcAcceptEmbargoUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptEmbargoTriggerRequest,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: AcceptEmbargoTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        dl = self._dl

        actor = resolve_actor(request.actor_id, dl)
        actor_id = actor.id_
        case = resolve_case(request.case_id, dl)
        proposal = _resolve_embargo_proposal(case, request.proposal_id, dl)
        embargo_id = _resolve_embargo_id_from_proposal(proposal)

        embargo = dl.read(embargo_id)
        if embargo is None:
            raise VultronValidationError(
                f"Could not resolve EmbargoEvent '{embargo_id}'."
            )

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcAcceptEmbargoUseCase requires a TriggerActivityPort"
            )

        lifecycle = EmbargoLifecycle(persistence=dl)
        lifecycle_result = lifecycle.accept_embargo_invite(
            case_id=case.id_,
            embargo_id=embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )

        factory = self._trigger_activity
        captured: dict = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            accept_id, accept_dict = factory.accept_embargo(
                proposal_id=proposal.id_,
                case_id=case.id_,
                actor=actor_id,
                to=[case_manager_id],
            )
            captured["activity"] = accept_dict
            return [accept_id]

        send_case_actor_activity(
            dl=dl,
            case_id=case.id_,
            actor_id=actor_id,
            trigger_activity=factory,
            failure_label="AcceptEmbargo",
            activity_builder=_build_activities,
        )

        if (
            _is_case_owner(case, actor_id)
            and lifecycle_result.em_after != lifecycle_result.em_before
        ):
            logger.info(
                "Actor '%s' accepted embargo proposal '%s'; activated embargo"
                " '%s' on case '%s' (EM %s → %s)",
                actor_id,
                proposal.id_,
                embargo_id,
                case.id_,
                lifecycle_result.em_before,
                lifecycle_result.em_after,
            )
        else:
            logger.info(
                "Actor '%s' accepted embargo proposal '%s'; recorded"
                " participant consent for embargo '%s' on case '%s'"
                " (EM unchanged at %s)",
                actor_id,
                proposal.id_,
                embargo_id,
                case.id_,
                lifecycle_result.em_after,
            )

        return {"activity": captured.get("activity")}


class SvcTerminateEmbargoUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: TerminateEmbargoTriggerRequest,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: TerminateEmbargoTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        if case.active_embargo is None:
            logger.warning(
                "Invalid EM state transition: actor '%s' cannot TERMINATE:"
                " case '%s' has no active embargo.",
                actor_id,
                case.id_,
            )
            raise VultronInvalidStateTransitionError(
                f"Case '{case.id_}' has no active embargo to terminate."
            )

        embargo_id = (
            case.active_embargo
            if isinstance(case.active_embargo, str)
            else getattr(case.active_embargo, "id_", None)
        )
        if embargo_id is None:
            raise VultronValidationError(
                f"Active embargo on case '{case.id_}' is missing an ID."
            )

        _coerce_embargo_event(dl.read(embargo_id), embargo_id)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcTerminateEmbargoUseCase requires a TriggerActivityPort"
            )

        lifecycle = EmbargoLifecycle(persistence=dl)
        lifecycle_result = lifecycle.terminate_active_embargo(
            case_id=case.id_,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )

        factory = self._trigger_activity
        captured: dict = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            announce_id, announce_dict = factory.terminate_embargo(
                embargo_id=embargo_id,
                case_id=case.id_,
                actor=actor_id,
                to=[case_manager_id],
            )
            captured["activity"] = announce_dict
            return [announce_id]

        send_case_actor_activity(
            dl=dl,
            case_id=case.id_,
            actor_id=actor_id,
            trigger_activity=factory,
            failure_label="TerminateEmbargo",
            activity_builder=_build_activities,
        )

        logger.info(
            "Actor '%s' terminated embargo '%s' on case '%s' (EM %s → %s)",
            actor_id,
            embargo_id,
            case.id_,
            lifecycle_result.em_before,
            lifecycle_result.em_after,
        )

        return {"activity": captured.get("activity")}


SvcEvaluateEmbargoUseCase = SvcAcceptEmbargoUseCase


class SvcRejectEmbargoUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectEmbargoTriggerRequest,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: RejectEmbargoTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        dl = self._dl

        actor = resolve_actor(request.actor_id, dl)
        actor_id = actor.id_
        case = resolve_case(request.case_id, dl)
        proposal = _resolve_embargo_proposal(case, request.proposal_id, dl)
        embargo_id = _resolve_embargo_id_from_proposal(proposal)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcRejectEmbargoUseCase requires a TriggerActivityPort"
            )

        lifecycle = EmbargoLifecycle(persistence=dl)
        lifecycle_result = lifecycle.reject_embargo_invite(
            case_id=case.id_,
            embargo_id=embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )

        factory = self._trigger_activity
        captured: dict = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            reject_id, reject_dict = factory.reject_embargo(
                proposal_id=proposal.id_,
                case_id=case.id_,
                actor=actor_id,
                to=[case_manager_id],
            )
            captured["activity"] = reject_dict
            return [reject_id]

        send_case_actor_activity(
            dl=dl,
            case_id=case.id_,
            actor_id=actor_id,
            trigger_activity=factory,
            failure_label="RejectEmbargo",
            activity_builder=_build_activities,
        )

        if (
            _is_case_owner(case, actor_id)
            and lifecycle_result.em_after != lifecycle_result.em_before
        ):
            logger.info(
                "Actor '%s' rejected embargo proposal '%s' on case '%s'"
                " (EM %s → %s)",
                actor_id,
                proposal.id_,
                case.id_,
                lifecycle_result.em_before,
                lifecycle_result.em_after,
            )
        else:
            logger.info(
                "Actor '%s' rejected embargo proposal '%s'; recorded"
                " participant consent for embargo '%s' on case '%s'"
                " (EM unchanged at %s)",
                actor_id,
                proposal.id_,
                embargo_id,
                case.id_,
                lifecycle_result.em_after,
            )

        return {"activity": captured.get("activity")}


class SvcProposeEmbargoRevisionUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: ProposeEmbargoRevisionTriggerRequest,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: ProposeEmbargoRevisionTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        end_time = request.end_time
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        em_state = case.current_status.em_state
        if em_state not in (EM.ACTIVE, EM.REVISE):
            raise VultronInvalidStateTransitionError(
                f"Cannot propose embargo revision: case '{case.id_}' EM state"
                f" '{em_state}' does not allow a revision proposal."
                f" Use propose-embargo for initial proposals."
            )

        embargo_kwargs: dict = {"context": case.id_}
        if end_time is not None:
            embargo_kwargs["end_time"] = end_time

        embargo = EmbargoEvent(**embargo_kwargs)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcProposeEmbargoRevisionUseCase requires a"
                " TriggerActivityPort"
            )

        lifecycle = EmbargoLifecycle(persistence=dl)
        lifecycle_result = lifecycle.propose_embargo(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )

        try:
            dl.create(embargo)
        except ValueError:
            logger.warning("EmbargoEvent '%s' already exists", embargo.id_)

        factory = self._trigger_activity
        captured: dict = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            proposal_id, proposal_dict = factory.propose_embargo(
                embargo_id=embargo.id_,
                case_id=case.id_,
                actor=actor_id,
                to=[case_manager_id],
            )
            captured["activity"] = proposal_dict
            return [proposal_id]

        send_case_actor_activity(
            dl=dl,
            case_id=case.id_,
            actor_id=actor_id,
            trigger_activity=factory,
            failure_label="ProposeEmbargoRevision",
            activity_builder=_build_activities,
        )

        logger.info(
            "Actor '%s' proposed embargo revision '%s' on case '%s'"
            " (EM %s → %s)",
            actor_id,
            embargo.id_,
            case.id_,
            lifecycle_result.em_before,
            lifecycle_result.em_after,
        )

        return {"activity": captured.get("activity")}
