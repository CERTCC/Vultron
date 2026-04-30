"""Use cases for embargo management activities."""

import logging

from transitions import MachineError

from vultron.core.states.em import (
    EM,
    EMAdapter,
    create_em_machine,
    is_valid_em_transition,
)
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    AddEmbargoEventToCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import _as_id, _idempotent_create
from vultron.core.models.protocols import (
    is_case_model,
    is_participant_model,
)

logger = logging.getLogger(__name__)


class CreateEmbargoEventReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CreateEmbargoEventReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateEmbargoEventReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.embargo_id,
            request.embargo,
            "EmbargoEvent",
            request.activity_id,
        )


class AddEmbargoEventToCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: AddEmbargoEventToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddEmbargoEventToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        embargo_id = request.embargo_id
        case_id = request.case_id
        if embargo_id is None or case_id is None:
            logger.warning(
                "add_embargo_event_to_case: missing embargo_id or case_id"
            )
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "add_embargo_event_to_case: case '%s' not found", case_id
            )
            return

        current_embargo_id = _as_id(case.active_embargo)
        if current_embargo_id == embargo_id:
            logger.info(
                "Case '%s' already has embargo '%s' active — skipping (idempotent)",
                case_id,
                embargo_id,
            )
            return

        current_em = case.current_status.em_state
        if not is_valid_em_transition(current_em, EM.ACTIVE):
            # Receive-side state-sync: the sender has activated this embargo;
            # update local state to reflect the sender's assertion even when
            # the transition is not on the standard machine path (e.g., if we
            # missed a PROPOSE step and our local state is still NONE).
            logger.warning(
                "add_embargo_event_to_case: EM transition %s → ACTIVE is not"
                " a standard machine transition for case '%s'; applying"
                " state-sync override",
                current_em,
                case_id,
            )
        case.set_embargo(embargo_id)
        case.current_status.em_state = EM.ACTIVE
        self._dl.save(case)
        logger.info("Activated embargo '%s' on case '%s'", embargo_id, case_id)


class RemoveEmbargoEventFromCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RemoveEmbargoEventFromCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RemoveEmbargoEventFromCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        embargo_id = request.embargo_id
        case_id = request.case_id
        if embargo_id is None or case_id is None:
            logger.warning(
                "remove_embargo_event_from_case: missing embargo_id or case_id"
            )
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "remove_embargo_event_from_case: case '%s' not found",
                case_id,
            )
            return

        # Remove from proposed_embargoes if present.
        proposed = [_as_id(e) for e in case.proposed_embargoes]
        if embargo_id in proposed:
            case.proposed_embargoes = [
                e for e in case.proposed_embargoes if _as_id(e) != embargo_id
            ]
            logger.info(
                "Removed embargo '%s' from proposed_embargoes of case '%s'",
                embargo_id,
                case_id,
            )

        # Clear active_embargo if it matches the removed embargo.
        current_embargo_id = _as_id(case.active_embargo)
        if current_embargo_id != embargo_id:
            self._dl.save(case)
            return

        em_state = case.current_status.em_state
        adapter = EMAdapter(em_state)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_state)

        try:
            # PROPOSED → NONE is a valid machine transition (REJECT trigger).
            getattr(adapter, "reject")()
            new_em_state = EM(adapter.state)
        except MachineError:
            # No machine path back to NONE from this state.
            # NONE is already the target (idempotent); anything else is an
            # administrative override that bypasses the normal EM lifecycle.
            if em_state != EM.NONE:
                logger.warning(
                    "Admin override: resetting EM state from '%s' to NONE on"
                    " case '%s' (no valid machine transition available;"
                    " use SvcTerminateEmbargoUseCase for normal termination)",
                    em_state,
                    case_id,
                )
            new_em_state = EM.NONE

        case.active_embargo = None  # type: ignore[attr-defined]
        case.current_status.em_state = new_em_state
        # Reset all participants' embargo consent state when the active embargo
        # is administratively removed.
        for participant_id in case.case_participants:
            participant = self._dl.read(participant_id)
            if not is_participant_model(participant):
                continue
            if participant.embargo_consent_state != PEC.NO_EMBARGO.value:
                participant.embargo_consent_state = apply_pec_trigger(
                    PEC(participant.embargo_consent_state), PEC_Trigger.RESET
                )
                self._dl.save(participant)
        self._dl.save(case)
        logger.info(
            "Removed active embargo '%s' from case '%s' (EM %s → %s)",
            embargo_id,
            case_id,
            em_state,
            new_em_state,
        )


class AnnounceEmbargoEventToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceEmbargoEventToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AnnounceEmbargoEventToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Received embargo announcement '%s' on case '%s'",
            request.activity_id,
            request.case_id,
        )


class InviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: InviteToEmbargoOnCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: InviteToEmbargoOnCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "InviteToEmbargoOnCase",
            request.activity_id,
        )

        # Advance the invitee's consent state to INVITED so they can later
        # accept or decline via the PEC machine.
        invitee_id = request.receiving_actor_id
        case_id = _as_id(getattr(request.activity, "context_", None))
        if not invitee_id or not case_id:
            return

        case = self._dl.read(case_id)
        if not is_case_model(case):
            return

        participant_id = case.actor_participant_index.get(invitee_id)
        if not participant_id:
            return

        participant = self._dl.read(participant_id)
        if not is_participant_model(participant):
            return

        new_state = apply_pec_trigger(
            PEC(participant.embargo_consent_state), PEC_Trigger.INVITE
        )
        participant.embargo_consent_state = new_state
        self._dl.save(participant)
        logger.info(
            "Set participant '%s' (actor '%s') embargo consent to INVITED"
            " (case '%s')",
            participant_id,
            invitee_id,
            case_id,
        )


class AcceptInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptInviteToEmbargoOnCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteToEmbargoOnCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        embargo_id = request.embargo_id
        if embargo_id is None:
            logger.error(
                "accept_invite_to_embargo_on_case: missing embargo_id on request"
            )
            return

        if request.case_id:
            case = self._dl.read(request.case_id)
        else:
            if request.invite_id is None:
                logger.error(
                    "accept_invite_to_embargo_on_case: missing invite_id on request"
                )
                return
            invite = self._dl.read(request.invite_id)
            if invite is None:
                logger.error(
                    "accept_invite_to_embargo_on_case: invite '%s' not found",
                    request.invite_id,
                )
                return
            context_id = getattr(invite, "context", None)
            context_id = _as_id(context_id)
            if context_id is None:
                logger.error(
                    "accept_invite_to_embargo_on_case: cannot determine case from invite '%s'",
                    request.invite_id,
                )
                return
            case = self._dl.read(context_id)

        if not is_case_model(case):
            logger.error("accept_invite_to_embargo_on_case: case not found")
            return
        case_id = case.id_

        accepting_actor_id = request.actor_id

        # Only the case owner's acceptance should activate the shared EM state.
        is_case_owner = _as_id(case.attributed_to) == accepting_actor_id

        current_embargo_id = _as_id(case.active_embargo)
        case_already_active = current_embargo_id == embargo_id

        if is_case_owner and not case_already_active:
            current_em = case.current_status.em_state
            if not is_valid_em_transition(current_em, EM.ACTIVE):
                # Receive-side state-sync: the sender accepted an embargo invite;
                # update local state to reflect the sender's assertion even when
                # the transition is not on the standard machine path.
                logger.warning(
                    "accept_invite_to_embargo_on_case: EM transition %s → ACTIVE"
                    " is not a standard machine transition for case '%s';"
                    " applying state-sync override",
                    current_em,
                    case_id,
                )
            case.set_embargo(embargo_id)
            case.current_status.em_state = EM.ACTIVE
        elif not is_case_owner and not case_already_active:
            logger.info(
                "accept_invite_to_embargo_on_case: actor '%s' accepted embargo"
                " '%s' on case '%s' but is not the case owner — recording"
                " consent only (EM state unchanged)",
                accepting_actor_id,
                embargo_id,
                case_id,
            )
        elif case_already_active:
            logger.info(
                "Case '%s' already has embargo '%s' active — "
                "still recording participant acceptance",
                case_id,
                embargo_id,
            )

        if is_case_owner and not case_already_active:
            case.record_event(embargo_id, "embargo_accepted")

        participant_id = case.actor_participant_index.get(accepting_actor_id)
        if participant_id:
            participant = self._dl.read(participant_id)
            if is_participant_model(participant):
                if embargo_id not in participant.accepted_embargo_ids:
                    participant.accepted_embargo_ids.append(embargo_id)
                new_state = apply_pec_trigger(
                    PEC(participant.embargo_consent_state), PEC_Trigger.ACCEPT
                )
                participant.embargo_consent_state = new_state
                self._dl.save(participant)
                logger.info(
                    "Recorded embargo acceptance '%s' for participant '%s'"
                    " (consent state: %s)",
                    embargo_id,
                    accepting_actor_id,
                    new_state,
                )
        else:
            logger.warning(
                "Accepting actor '%s' has no CaseParticipant in case '%s' — "
                "cannot record embargo acceptance",
                accepting_actor_id,
                case_id,
            )

        self._dl.save(case)
        logger.info(
            "Accepted embargo proposal '%s'; actor '%s' recorded as SIGNATORY"
            " for embargo '%s' on case '%s'",
            request.invite_id,
            accepting_actor_id,
            embargo_id,
            case_id,
        )


class RejectInviteToEmbargoOnCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RejectInviteToEmbargoOnCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectInviteToEmbargoOnCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        rejecting_actor_id = request.actor_id
        invite_id = request.invite_id
        logger.info(
            "Actor '%s' rejected embargo proposal '%s'",
            rejecting_actor_id,
            invite_id,
        )

        # Update the rejecting actor's embargo consent state to DECLINED.
        # Extract case and embargo IDs from the stored invite activity.
        case_id: str | None = None
        embargo_id: str | None = None
        if invite_id:
            invite = self._dl.read(invite_id)
            if invite is not None:
                case_id = _as_id(getattr(invite, "context_", None))
                embargo_id = _as_id(getattr(invite, "object_", None))

        if not case_id:
            return
        case = self._dl.read(case_id)
        if not is_case_model(case):
            return

        participant_id = case.actor_participant_index.get(rejecting_actor_id)
        if not participant_id:
            return

        participant = self._dl.read(participant_id)
        if not is_participant_model(participant):
            return

        # Remove any stale embargo acceptance entry (pocket-veto semantics).
        if embargo_id and embargo_id in participant.accepted_embargo_ids:
            participant.accepted_embargo_ids.remove(embargo_id)

        new_state = apply_pec_trigger(
            PEC(participant.embargo_consent_state), PEC_Trigger.DECLINE
        )
        participant.embargo_consent_state = new_state
        self._dl.save(participant)
        logger.info(
            "Set participant '%s' (actor '%s') embargo consent to DECLINED",
            participant_id,
            rejecting_actor_id,
        )
