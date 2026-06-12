"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING

from vultron.core.models.events.actor import (
    AcceptInviteActorToCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
)
from vultron.core.models.protocols import is_case_model
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import (
    _as_id,
    _find_case_actor_id,
    _idempotent_create,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class InviteActorToCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: InviteActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: InviteActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "InviteActorToCase",
            request.activity_id,
        )
        # MV-10-004: do NOT create a case from the stub target.  The stub
        # carries only {id, type} for identification; the full case details
        # arrive later in an AnnounceVulnerabilityCase activity (MV-10-003).
        case_stub_id = request.target_id
        if case_stub_id:
            logger.info(
                "InviteActorToCase: received invite with case stub '%s'."
                " Awaiting AnnounceVulnerabilityCase before creating case.",
                case_stub_id,
            )


class AcceptInviteActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteActorToCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteActorToCaseReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        case_id = request.case_id
        invitee_id = request.invitee_id
        if case_id is None or invitee_id is None:
            logger.warning(
                "accept_invite_actor_to_case: missing case_id or invitee_id"
            )
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "accept_invite_actor_to_case: case '%s' not found", case_id
            )
            return

        existing_ids = [_as_id(p) for p in case.case_participants]
        if (
            invitee_id in case.actor_participant_index
            or invitee_id in existing_ids
        ):
            logger.info(
                "Actor '%s' already participant in case '%s' — skipping (idempotent)",
                invitee_id,
                case_id,
            )
            return

        active_embargo_id = _as_id(case.active_embargo)
        em_state = case.current_status.em_state

        participant = VultronParticipant(
            id_=f"{case_id}/participants/{invitee_id.split('/')[-1]}",
            attributed_to=invitee_id,
            context=case_id,
        )
        # Accept(Invite) IS the engage signal (PCR-08-010): pre-seed all three
        # RM states inline so the participant reaches ACCEPTED immediately
        # without a separate engage-case trigger or identity-spoofing BT call.
        participant.append_rm_state(
            RM.RECEIVED, actor=invitee_id, context=case_id
        )
        participant.append_rm_state(
            RM.VALID, actor=invitee_id, context=case_id
        )
        participant.append_rm_state(
            RM.ACCEPTED, actor=invitee_id, context=case_id
        )
        # Only auto-sign embargo consent when the embargo is fully ACTIVE.
        # In REVISE state the terms are under negotiation; auto-signing would
        # commit the new participant to unresolved terms.
        if active_embargo_id and em_state == EM.ACTIVE:
            participant.accepted_embargo_ids.append(active_embargo_id)
            participant.embargo_consent_state = apply_pec_trigger(
                PEC.NO_EMBARGO, PEC_Trigger.ACCEPT
            )
        self._dl.create(participant)

        case.add_participant(participant)
        case.record_event(invitee_id, "participant_joined")
        if active_embargo_id and em_state == EM.ACTIVE:
            case.record_event(active_embargo_id, "embargo_accepted")
        self._dl.save(case)

        # MV-10-003/MV-10-005: emit full case details to the invitee now that
        # embargo consent has been resolved (auto-signed above when ACTIVE).
        # The Case Actor sends Announce(VulnerabilityCase) so the invitee can
        # seed their local DataLayer.
        self._emit_announce_case(case_id, invitee_id, case)

        logger.info(
            "Added participant '%s' to case '%s' via accepted invite"
            " (RM.ACCEPTED inline, PCR-08-010)",
            invitee_id,
            case_id,
        )

    def _emit_announce_case(self, case_id: str, invitee_id: str, case) -> None:
        """Emit Announce(VulnerabilityCase) to the invitee from the CaseActor.

        Per MV-10-003, the case owner sends the full case object after the
        invitee's embargo consent has been verified.
        """
        from vultron.core.use_cases.triggers._helpers import (
            add_activity_to_outbox,
        )

        if self._trigger_activity is None:
            logger.warning(
                "AcceptInviteActorToCase: no TriggerActivityPort;"
                " cannot emit AnnounceVulnerabilityCase for case '%s'",
                case_id,
            )
            return

        case_actor_id = _find_case_actor_id(self._dl, case_id)
        if case_actor_id is None:
            logger.warning(
                "AcceptInviteActorToCase: no CaseActor found;"
                " cannot emit AnnounceVulnerabilityCase for case '%s'",
                case_id,
            )
            return

        try:
            activity_id = self._trigger_activity.announce_vulnerability_case(
                case_id=case_id,
                actor=case_actor_id,
                context_id=case_id,
                to=[invitee_id],
            )
            add_activity_to_outbox(case_actor_id, activity_id, self._dl)
            logger.info(
                "Emitted AnnounceVulnerabilityCase '%s' to '%s' for case '%s'",
                activity_id,
                invitee_id,
                case_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to emit AnnounceVulnerabilityCase for case '%s'"
                " to '%s': %s",
                case_id,
                invitee_id,
                exc,
            )


class RejectInviteActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RejectInviteActorToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectInviteActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            request.actor_id,
            request.invite_id,
        )
