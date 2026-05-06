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

"""
Class-based use cases for embargo-level trigger behaviors.

No HTTP framework imports permitted here.
"""

import logging
from typing import TYPE_CHECKING, Any

from transitions import MachineError

from vultron.core.models.embargo_event import VultronEmbargoEvent
from vultron.core.states.em import EM, EMAdapter, create_em_machine
from vultron.core.models.protocols import (
    CaseModel,
    PersistableModel,
    is_case_model,
    is_participant_model,
)
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)
from vultron.core.use_cases._helpers import _as_id, case_addressees
from vultron.core.use_cases.triggers._helpers import (
    add_activity_to_outbox,
    find_embargo_proposal,
    resolve_actor,
    resolve_case,
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
    VultronNotFoundError,
    VultronValidationError,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def _coerce_embargo_event(raw_embargo: object, embargo_id: str) -> Any:
    """Normalize a persisted embargo record; raise domain errors on failure.

    Validates that the result has type ``"EmbargoEvent"`` by checking the
    ``type_`` attribute rather than using a wire-type isinstance check.
    """
    if getattr(raw_embargo, "type_", "") == "EmbargoEvent":
        return raw_embargo
    if raw_embargo is None:
        raise VultronNotFoundError("EmbargoEvent", embargo_id)
    raise VultronValidationError(
        f"Could not resolve EmbargoEvent '{embargo_id}'."
    )


def _cascade_pec_revise(
    case: PersistableModel | None, dl: CasePersistence
) -> None:
    """Transition all SIGNATORY participants to LAPSED.

    Called when an embargo transitions to REVISE state, meaning the embargo
    terms are being renegotiated.  Existing signatories temporarily lapse
    until they accept the revised terms.
    """
    if not is_case_model(case):
        return
    for participant_id in case.case_participants:
        participant = dl.read(participant_id)
        if not is_participant_model(participant):
            continue
        if participant.embargo_consent_state == PEC.SIGNATORY.value:
            participant.embargo_consent_state = apply_pec_trigger(
                PEC.SIGNATORY, PEC_Trigger.REVISE
            )
            dl.save(participant)


def _cascade_pec_reset(
    case: PersistableModel | None, dl: CasePersistence
) -> None:
    """Reset all participants' embargo consent state to NO_EMBARGO.

    Called when an embargo is terminated or removed.
    """
    if not is_case_model(case):
        return
    for participant_id in case.case_participants:
        participant = dl.read(participant_id)
        if not is_participant_model(participant):
            continue
        if participant.embargo_consent_state != PEC.NO_EMBARGO.value:
            participant.embargo_consent_state = apply_pec_trigger(
                PEC(participant.embargo_consent_state), PEC_Trigger.RESET
            )
            dl.save(participant)


def _is_case_owner(case: PersistableModel | None, actor_id: str) -> bool:
    """Return True when ``actor_id`` matches the case owner.

    Cases created before owner attribution was consistently populated still
    need a sensible single-actor default, so ``None`` falls back to treating
    the triggering actor as the owner.
    """
    if not is_case_model(case):
        return False
    owner_id = _as_id(case.attributed_to)
    return owner_id is None or owner_id == actor_id


def _update_participant_embargo_acceptance(
    case: PersistableModel | None,
    actor_id: str,
    embargo_id: str,
    dl: CaseOutboxPersistence,
) -> None:
    """Persist a participant-level embargo acceptance without re-driving EM."""
    if not is_case_model(case):
        return

    participant_id = case.actor_participant_index.get(actor_id)
    if not participant_id:
        logger.warning(
            "Actor '%s' has no CaseParticipant in case '%s' — cannot record"
            " embargo acceptance",
            actor_id,
            case.id_,
        )
        return

    participant = dl.read(participant_id)
    if not is_participant_model(participant):
        logger.warning(
            "CaseParticipant '%s' for actor '%s' on case '%s' is missing or"
            " invalid — cannot record embargo acceptance",
            participant_id,
            actor_id,
            case.id_,
        )
        return

    participant.accepted_embargo_ids = list(
        dict.fromkeys(participant.accepted_embargo_ids + [embargo_id])
    )
    current_state = PEC(participant.embargo_consent_state)
    if current_state != PEC.SIGNATORY:
        participant.embargo_consent_state = apply_pec_trigger(
            current_state, PEC_Trigger.ACCEPT
        )
    dl.save(participant)


def _update_participant_embargo_rejection(
    case: PersistableModel | None,
    actor_id: str,
    embargo_id: str,
    dl: CaseOutboxPersistence,
) -> None:
    """Persist a participant-level embargo rejection without re-driving EM."""
    if not is_case_model(case):
        return

    participant_id = case.actor_participant_index.get(actor_id)
    if not participant_id:
        logger.warning(
            "Actor '%s' has no CaseParticipant in case '%s' — cannot record"
            " embargo rejection",
            actor_id,
            case.id_,
        )
        return

    participant = dl.read(participant_id)
    if not is_participant_model(participant):
        logger.warning(
            "CaseParticipant '%s' for actor '%s' on case '%s' is missing or"
            " invalid — cannot record embargo rejection",
            participant_id,
            actor_id,
            case.id_,
        )
        return

    if embargo_id in participant.accepted_embargo_ids:
        participant.accepted_embargo_ids.remove(embargo_id)
    current_state = PEC(participant.embargo_consent_state)
    if current_state != PEC.DECLINED:
        participant.embargo_consent_state = apply_pec_trigger(
            current_state, PEC_Trigger.DECLINE
        )
    dl.save(participant)


def _resolve_embargo_proposal(
    case: CaseModel, proposal_id: str | None, dl: CaseOutboxPersistence
) -> Any:
    if proposal_id:
        proposal = dl.read(proposal_id)
        if proposal is None:
            raise VultronNotFoundError("EmbargoProposal", proposal_id)
    else:
        proposal = find_embargo_proposal(case.id_, dl)
        if proposal is None:
            raise VultronNotFoundError(
                "EmbargoProposal",
                f"(pending for case '{case.id_}')",
            )

    if getattr(proposal, "type_", "") != "Invite":
        raise VultronValidationError(
            f"Expected an EmProposeEmbargoActivity (embargo proposal), got "
            f"type '{getattr(proposal, 'type_', 'unknown')}'."
        )
    return proposal


def _resolve_embargo_id_from_proposal(proposal: Any) -> str:
    embargo_id = getattr(proposal.object_, "id_", None)
    if embargo_id is not None and not isinstance(embargo_id, str):
        raise VultronValidationError(
            "Proposal embargo event reference must have a string ID."
        )
    if not embargo_id:
        raise VultronValidationError(
            "Proposal is missing an embargo event reference."
        )
    return embargo_id


def _apply_owner_embargo_acceptance(
    case: CaseModel,
    actor_id: str,
    proposal_id: str,
    embargo_id: str,
) -> tuple[EM, bool]:
    em_state = case.current_status.em_state
    if not _is_case_owner(case, actor_id):
        return em_state, False

    active_embargo_id = _as_id(case.active_embargo)
    if em_state == EM.ACTIVE and active_embargo_id == embargo_id:
        return em_state, False

    adapter = EMAdapter(em_state)
    em_machine = create_em_machine()
    em_machine.add_model(adapter, initial=em_state)
    try:
        getattr(adapter, "accept")()
    except MachineError:
        logger.warning(
            "Invalid EM state transition: actor '%s' cannot ACCEPT proposal "
            "'%s' on case '%s' (EM state '%s').",
            actor_id,
            proposal_id,
            case.id_,
            em_state,
        )
        raise VultronInvalidStateTransitionError(
            f"Cannot accept embargo: case '{case.id_}' EM state '{em_state}' "
            "does not allow an ACCEPT transition."
        )

    new_em_state = EM(adapter.state)
    case.set_embargo(embargo_id)
    case.current_status.em_state = new_em_state
    return new_em_state, True


def _apply_owner_embargo_rejection(
    case: CaseModel, actor_id: str, proposal_id: str
) -> tuple[EM, bool]:
    em_state = case.current_status.em_state
    if not _is_case_owner(case, actor_id):
        return em_state, False

    adapter = EMAdapter(em_state)
    em_machine = create_em_machine()
    em_machine.add_model(adapter, initial=em_state)
    try:
        getattr(adapter, "reject")()
    except MachineError:
        logger.warning(
            "Invalid EM state transition: actor '%s' cannot REJECT proposal "
            "'%s' on case '%s' (EM state '%s').",
            actor_id,
            proposal_id,
            case.id_,
            em_state,
        )
        raise VultronInvalidStateTransitionError(
            f"Cannot reject embargo: case '{case.id_}' EM state '{em_state}' "
            "does not allow a REJECT transition."
        )

    new_em_state = EM(adapter.state)
    case.current_status.em_state = new_em_state
    return new_em_state, True


class SvcProposeEmbargoUseCase:
    """Propose an embargo on a case."""

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: ProposeEmbargoTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
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

        em_state = case.current_status.em_state

        adapter = EMAdapter(em_state)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_state)

        try:
            getattr(adapter, "propose")()
        except MachineError:
            logger.warning(
                "Invalid EM state transition: actor '%s' cannot PROPOSE on"
                " case '%s' (EM state '%s').",
                actor_id,
                case.id_,
                em_state,
            )
            raise VultronInvalidStateTransitionError(
                f"Cannot propose embargo: case '{case.id_}' EM state"
                f" '{em_state}' does not allow a PROPOSE transition."
            )

        new_em_state = EM(adapter.state)

        embargo_kwargs: dict = {"context": case.id_}
        if end_time is not None:
            embargo_kwargs["end_time"] = end_time

        embargo = VultronEmbargoEvent(**embargo_kwargs)

        try:
            dl.create(embargo)
        except ValueError:
            logger.warning(
                "VultronEmbargoEvent '%s' already exists", embargo.id_
            )

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcProposeEmbargoUseCase requires a TriggerActivityPort"
            )

        proposal_id, proposal_dict = self._trigger_activity.propose_embargo(
            embargo_id=embargo.id_,
            case_id=case.id_,
            actor=actor_id,
            to=case_addressees(case, actor_id) or None,
        )

        case.current_status.em_state = new_em_state
        # When transitioning from ACTIVE to REVISE, all current signatories
        # lapse — the embargo terms are being renegotiated.
        if em_state == EM.ACTIVE and new_em_state == EM.REVISE:
            _cascade_pec_revise(case, dl)
        if new_em_state != em_state:
            logger.info(
                "Actor '%s' proposed embargo '%s' on case '%s' (EM %s → %s)",
                actor_id,
                embargo.id_,
                case.id_,
                em_state,
                new_em_state,
            )
        else:
            logger.info(
                "Actor '%s' counter-proposed embargo '%s' on case '%s'"
                " (EM %s, no state change)",
                actor_id,
                embargo.id_,
                case.id_,
                em_state,
            )

        case.proposed_embargoes.append(embargo.id_)
        dl.save(case)

        add_activity_to_outbox(actor_id, proposal_id, dl)

        return {"activity": proposal_dict}


class SvcAcceptEmbargoUseCase:
    """Accept an embargo proposal (accept-embargo)."""

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptEmbargoTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
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

        accept_id, accept_dict = self._trigger_activity.accept_embargo(
            proposal_id=proposal.id_,
            case_id=case.id_,
            actor=actor_id,
            to=case_addressees(case, actor_id) or None,
        )

        em_state = case.current_status.em_state
        new_em_state, owner_activated = _apply_owner_embargo_acceptance(
            case,
            actor_id,
            proposal.id_,
            embargo_id,
        )

        _update_participant_embargo_acceptance(case, actor_id, embargo_id, dl)
        dl.save(case)
        add_activity_to_outbox(actor_id, accept_id, dl)

        if owner_activated:
            logger.info(
                "Actor '%s' accepted embargo proposal '%s'; activated embargo"
                " '%s' on case '%s' (EM %s → %s)",
                actor_id,
                proposal.id_,
                embargo_id,
                case.id_,
                em_state,
                new_em_state,
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
                new_em_state,
            )

        return {"activity": accept_dict}


class SvcTerminateEmbargoUseCase:
    """Terminate the active embargo on a case."""

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: TerminateEmbargoTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
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

        em_state = case.current_status.em_state
        adapter = EMAdapter(em_state)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_state)

        try:
            getattr(adapter, "terminate")()
        except MachineError:
            logger.warning(
                "Invalid EM state transition: actor '%s' cannot TERMINATE on"
                " case '%s' (EM state '%s').",
                actor_id,
                case.id_,
                em_state,
            )
            raise VultronInvalidStateTransitionError(
                f"Cannot terminate embargo: case '{case.id_}' EM state"
                f" '{em_state}' does not allow a TERMINATE transition."
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

        announce_id, announce_dict = self._trigger_activity.announce_embargo(
            embargo_id=embargo_id,
            case_id=case.id_,
            actor=actor_id,
            to=case_addressees(case, actor_id) or None,
        )

        case.current_status.em_state = EM(adapter.state)
        case.active_embargo = None
        # Reset all participants' embargo consent state.
        _cascade_pec_reset(case, dl)
        dl.save(case)

        add_activity_to_outbox(actor_id, announce_id, dl)

        logger.info(
            "Actor '%s' terminated embargo '%s' on case '%s' (EM %s → %s)",
            actor_id,
            embargo_id,
            case.id_,
            em_state,
            adapter.state,
        )

        return {"activity": announce_dict}


# Backward-compatible alias
SvcEvaluateEmbargoUseCase = SvcAcceptEmbargoUseCase


class SvcRejectEmbargoUseCase:
    """Reject an embargo proposal (reject-embargo).

    Valid EM transitions: PROPOSED → NO_EMBARGO or REVISE → ACTIVE.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectEmbargoTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
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
        em_state = case.current_status.em_state
        new_em_state, owner_rejected = _apply_owner_embargo_rejection(
            case,
            actor_id,
            proposal.id_,
        )

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcRejectEmbargoUseCase requires a TriggerActivityPort"
            )

        reject_id, reject_dict = self._trigger_activity.reject_embargo(
            proposal_id=proposal.id_,
            case_id=case.id_,
            actor=actor_id,
            to=case_addressees(case, actor_id) or None,
        )

        _update_participant_embargo_rejection(case, actor_id, embargo_id, dl)
        dl.save(case)

        add_activity_to_outbox(actor_id, reject_id, dl)

        if owner_rejected:
            logger.info(
                "Actor '%s' rejected embargo proposal '%s' on case '%s'"
                " (EM %s → %s)",
                actor_id,
                proposal.id_,
                case.id_,
                em_state,
                new_em_state,
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
                new_em_state,
            )

        return {"activity": reject_dict}


class SvcProposeEmbargoRevisionUseCase:
    """Propose a revision to an active embargo (propose-embargo-revision).

    Valid EM transitions: ACTIVE → REVISE or REVISE → REVISE.
    Rejects with an invalid-state error if EM state is NO_EMBARGO or PROPOSED
    (use propose-embargo for initial proposals).
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: ProposeEmbargoRevisionTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
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

        adapter = EMAdapter(em_state)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_state)

        try:
            getattr(adapter, "propose")()
        except MachineError:
            logger.warning(
                "Invalid EM state transition: actor '%s' cannot PROPOSE"
                " revision on case '%s' (EM state '%s').",
                actor_id,
                case.id_,
                em_state,
            )
            raise VultronInvalidStateTransitionError(
                f"Cannot propose embargo revision: case '{case.id_}' EM state"
                f" '{em_state}' does not allow a PROPOSE transition."
            )

        new_em_state = EM(adapter.state)

        embargo_kwargs: dict = {"context": case.id_}
        if end_time is not None:
            embargo_kwargs["end_time"] = end_time

        embargo = VultronEmbargoEvent(**embargo_kwargs)

        try:
            dl.create(embargo)
        except ValueError:
            logger.warning(
                "VultronEmbargoEvent '%s' already exists", embargo.id_
            )

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcProposeEmbargoRevisionUseCase requires a"
                " TriggerActivityPort"
            )

        proposal_id, proposal_dict = self._trigger_activity.propose_embargo(
            embargo_id=embargo.id_,
            case_id=case.id_,
            actor=actor_id,
            to=case_addressees(case, actor_id) or None,
        )

        case.current_status.em_state = new_em_state
        case.proposed_embargoes.append(embargo.id_)
        dl.save(case)

        add_activity_to_outbox(actor_id, proposal_id, dl)

        logger.info(
            "Actor '%s' proposed embargo revision '%s' on case '%s'"
            " (EM %s → %s)",
            actor_id,
            embargo.id_,
            case.id_,
            em_state,
            new_em_state,
        )

        return {"activity": proposal_dict}
