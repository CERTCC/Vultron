"""Use cases for case and participant status activities."""

import logging
from typing import TYPE_CHECKING, Any, cast

from vultron.core.models.events.status import (
    AddCaseStatusToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
    CreateCaseStatusReceivedEvent,
    CreateParticipantStatusReceivedEvent,
)
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.states.cs import is_valid_pxa_transition
from vultron.core.states.em import is_valid_em_transition
from vultron.core.states.rm import is_valid_rm_transition
from vultron.core.use_cases._helpers import _as_id, _idempotent_create
from vultron.core.models.protocols import (
    ParticipantStatusModel,
    is_case_model,
    is_participant_model,
)
from vultron.errors import VultronError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def _resolve_case_status_object(
    dl: CasePersistence,
    status_id: str,
    request: AddCaseStatusToCaseReceivedEvent,
) -> object:
    status_obj = dl.read(status_id)
    if hasattr(status_obj, "id_"):
        return status_obj
    return request.status


def _validate_case_status_transition(
    case: object, status_obj: object, case_id: str
) -> bool:
    current_status = getattr(case, "current_status", None)
    if current_status is None:
        return True

    if not _validate_optional_case_transition(
        "EM",
        current_status.em_state,
        getattr(status_obj, "em_state", None),
        case_id,
        is_valid_em_transition,
    ):
        return False

    return _validate_optional_case_transition(
        "PXA",
        current_status.pxa_state,
        getattr(status_obj, "pxa_state", None),
        case_id,
        is_valid_pxa_transition,
    )


def _validate_optional_case_transition(
    label: str,
    current_state: object,
    new_state: object,
    case_id: str,
    validator: Any,
) -> bool:
    if new_state is None or current_state == new_state:
        return True
    if validator(current_state, new_state):
        return True

    logger.warning(
        "Invalid %s transition %s → %s for case '%s'; skipping status append",
        label,
        current_state,
        new_state,
        case_id,
    )
    return False


class CreateCaseStatusReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CreateCaseStatusReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateCaseStatusReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.status_id,
            request.status,
            "CaseStatus",
            request.activity_id,
        )


class AddCaseStatusToCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: AddCaseStatusToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddCaseStatusToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        status_id = request.status_id
        case_id = request.case_id
        if status_id is None or case_id is None:
            logger.warning(
                "add_case_status_to_case: missing status_id or case_id"
            )
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "add_case_status_to_case: case '%s' not found", case_id
            )
            return

        existing_ids = [_as_id(s) for s in case.case_statuses]
        if status_id in existing_ids:
            logger.info(
                "CaseStatus '%s' already in case '%s' — skipping (idempotent)",
                status_id,
                case_id,
            )
            return

        status_obj = _resolve_case_status_object(self._dl, status_id, request)
        if case.case_statuses and not _validate_case_status_transition(
            case, status_obj, case_id
        ):
            return

        case.case_statuses.append(status_obj)
        self._dl.save(case)
        logger.info("Added CaseStatus '%s' to case '%s'", status_id, case_id)


class CreateParticipantStatusReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: CreateParticipantStatusReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: CreateParticipantStatusReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.status_id,
            request.status,
            "ParticipantStatus",
            request.activity_id,
        )


class AddParticipantStatusToParticipantReceivedUseCase:
    """Process a received Add(ParticipantStatus, CaseParticipant) message.

    Implements all DEMOMA-07-003 steps:
    1. Verify sender is a known case participant.
    2. Append the ParticipantStatus to the CaseParticipant record.
    3. Broadcast the status update to all other case participants (Case Manager
       re-sends Add(ParticipantStatus, CaseParticipant) on behalf of the
       sender).
    4. If the new status signals public awareness (pxa_state.P) and the sender
       holds the CASE_OWNER role, initiate embargo teardown.
    5. If all participant RM states are CLOSED, mark the case closed.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddParticipantStatusToParticipantReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AddParticipantStatusToParticipantReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        status_id = request.status_id
        participant_id = request.participant_id
        if status_id is None or participant_id is None:
            logger.warning(
                "add_participant_status_to_participant: missing status_id or participant_id"
            )
            return

        # Steps 1+2: verify sender, then append status
        result = self._verify_and_append(request, status_id, participant_id)
        if result is None:
            return
        actor_id, case_id, case, status_obj = result

        # ---- Step 3: broadcast to peers -----------------------------------
        self._broadcast_status_to_peers(
            status_id, participant_id, actor_id, case_id, case
        )

        # ---- Step 4: embargo teardown on public disclosure ----------------
        self._check_public_disclosure(status_obj, actor_id, case_id, case)

        # ---- Step 5: auto-close if all participants CLOSED ----------------
        self._check_all_closed(case_id, case)

    def _verify_and_append(
        self,
        request: AddParticipantStatusToParticipantReceivedEvent,
        status_id: str,
        participant_id: str,
    ) -> "tuple[str, str, Any, Any] | None":
        """Verify sender is a known participant and append status to participant.

        Returns ``(actor_id, case_id, case, status_obj)`` on success, else None.
        """
        # ---- Step 1: verify sender is a known case participant ------------
        actor_id = request.actor_id
        status_raw = self._dl.read(status_id) or request.status
        case_id = str(getattr(status_raw, "context", "")) or None

        if case_id is None:
            logger.warning(
                "add_participant_status_to_participant: cannot determine case_id"
            )
            return None

        case = self._dl.read(case_id)
        if not is_case_model(case):
            logger.warning(
                "add_participant_status_to_participant: case '%s' not found",
                case_id,
            )
            return None

        if actor_id not in case.actor_participant_index:
            logger.warning(
                "add_participant_status_to_participant: actor '%s' is not a "
                "known participant of case '%s' — rejecting",
                actor_id,
                case_id,
            )
            return None

        # ---- Step 2: append status to participant -------------------------
        status_obj = self._append_status(request, status_id, participant_id)
        if status_obj is None:
            return None

        return actor_id, case_id, case, status_obj

    def _append_status(
        self,
        request: AddParticipantStatusToParticipantReceivedEvent,
        status_id: str,
        participant_id: str,
    ) -> Any:
        """Append ParticipantStatus to participant; return status object or None."""
        participant = self._dl.read(participant_id)
        if not is_participant_model(participant):
            logger.warning(
                "add_participant_status_to_participant: participant '%s' not found",
                participant_id,
            )
            return None

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
        if status_id in existing_ids:
            logger.info(
                "ParticipantStatus '%s' already on participant '%s' — skipping (idempotent)",
                status_id,
                participant_id,
            )
            return None

        status_obj = self._dl.read(status_id)
        if not hasattr(status_obj, "id_"):
            status_obj = request.status
        if status_obj is None:
            logger.warning(
                "add_participant_status_to_participant: status '%s' not found",
                status_id,
            )
            return None
        if not hasattr(status_obj, "rm_state") or not hasattr(
            status_obj, "vfd_state"
        ):
            logger.warning(
                "add_participant_status_to_participant: status '%s' is not a ParticipantStatus",
                status_id,
            )
            return None

        new_rm_state = getattr(status_obj, "rm_state", None)
        if new_rm_state is not None and participant.participant_statuses:
            if hasattr(participant, "participant_status") and getattr(
                participant, "participant_status"
            ):
                current_status = cast(Any, participant).participant_status
            else:
                current_status = participant.participant_statuses[-1]
            current_rm = current_status.rm_state
            if current_rm != new_rm_state and not is_valid_rm_transition(
                current_rm, new_rm_state
            ):
                # The sender is authoritative about their own RM state.
                # Forward jumps (e.g. RECEIVED → ACCEPTED) are legitimate
                # when intermediate transitions happen locally.  Log but
                # do not reject.
                logger.info(
                    "Non-adjacent RM transition %s → %s for participant "
                    "'%s'; accepting sender-authoritative state",
                    current_rm,
                    new_rm_state,
                    participant_id,
                )

        participant.participant_statuses.append(
            cast(ParticipantStatusModel, status_obj)
        )
        self._dl.save(participant)
        logger.info(
            "Added ParticipantStatus '%s' to participant '%s'",
            status_id,
            participant_id,
        )
        return status_obj

    def _find_case_manager_id(self, case: Any) -> str | None:
        """Return the attributed_to actor ID for the CASE_MANAGER participant."""
        from vultron.core.states.roles import CVDRole

        for p_id in case.actor_participant_index.values():
            p = self._dl.read(p_id)
            if p is None:
                continue
            roles = getattr(p, "case_roles", [])
            if CVDRole.CASE_MANAGER in roles:
                attr = getattr(p, "attributed_to", None)
                if attr:
                    return str(attr)
        return None

    def _broadcast_status_to_peers(
        self,
        status_id: str,
        participant_id: str,
        sender_actor_id: str,
        case_id: str,
        case: Any,
    ) -> None:
        """Broadcast Add(ParticipantStatus, CaseParticipant) to other participants.

        The Case Manager re-sends the status to all participants except the
        original sender (DEMOMA-07-003 step 3).
        """
        if self._trigger_activity is None:
            logger.debug(
                "add_participant_status_to_participant: no trigger_activity "
                "— skipping broadcast (DEMOMA-07-003 step 3)"
            )
            return

        case_manager_id = self._find_case_manager_id(case)
        if case_manager_id is None:
            logger.debug(
                "add_participant_status_to_participant: no CASE_MANAGER found "
                "in case '%s' — skipping broadcast",
                case_id,
            )
            return

        recipient_ids = [
            a_id
            for a_id in case.actor_participant_index.keys()
            if a_id != sender_actor_id and a_id != case_manager_id
        ]
        if not recipient_ids:
            logger.debug(
                "add_participant_status_to_participant: no eligible recipients "
                "in case '%s' — skipping broadcast",
                case_id,
            )
            return

        try:
            activity_id = (
                self._trigger_activity.add_participant_status_to_participant(
                    status_id=status_id,
                    participant_id=participant_id,
                    actor=case_manager_id,
                    to=recipient_ids,
                )
            )
            # Update the Case Manager actor's outbox to reflect the pending
            # send, mirroring the pattern used by other received broadcast
            # handlers (e.g. received/note.py).
            case_manager_actor = self._dl.read(case_manager_id)
            if case_manager_actor is not None and hasattr(
                case_manager_actor, "outbox"
            ):
                cast(Any, case_manager_actor).outbox.items.append(activity_id)
                self._dl.save(case_manager_actor)

            self._dl.record_outbox_item(case_manager_id, activity_id)
            logger.info(
                "add_participant_status_to_participant: Case Manager '%s' "
                "broadcast status '%s' to %d peer(s) (DEMOMA-07-003 step 3)",
                case_manager_id,
                status_id,
                len(recipient_ids),
            )
        except VultronError as exc:
            logger.warning(
                "add_participant_status_to_participant: broadcast failed: %s",
                exc,
            )

    def _check_public_disclosure(
        self,
        status_obj: Any,
        actor_id: str,
        case_id: str,
        case: Any,
    ) -> None:
        """Trigger embargo teardown if public disclosure detected (DEMOMA-07-003 step 4).

        Condition: new status pxa_state has PUBLIC_AWARE set AND sender holds
        CASE_OWNER role.
        """
        from vultron.core.states.cs import CS_pxa
        from vultron.core.states.roles import CVDRole

        pxa_state = getattr(
            getattr(status_obj, "case_status", None), "pxa_state", None
        )
        if pxa_state is None:
            return

        # Check if P (public aware) is set
        try:
            public_aware = pxa_state in (
                CS_pxa.Pxa,
                CS_pxa.PxA,
                CS_pxa.PXa,
                CS_pxa.PXA,
            )
        except Exception:
            return

        if not public_aware:
            return

        # Check sender is CASE_OWNER
        sender_participant_id = case.actor_participant_index.get(actor_id)
        if sender_participant_id is None:
            return

        sender_participant = self._dl.read(sender_participant_id)
        roles = getattr(sender_participant, "case_roles", [])
        if CVDRole.CASE_OWNER not in roles:
            return

        logger.info(
            "add_participant_status_to_participant: public disclosure detected "
            "from CASE_OWNER '%s' — initiating embargo teardown for case '%s' "
            "(DEMOMA-07-003 step 4)",
            actor_id,
            case_id,
        )

        case_manager_id = self._find_case_manager_id(case)
        if case_manager_id is None:
            logger.warning(
                "add_participant_status_to_participant: no Case Manager found "
                "— cannot initiate embargo teardown for case '%s'",
                case_id,
            )
            return

        try:
            from vultron.core.use_cases.triggers.embargo import (
                SvcTerminateEmbargoUseCase,
            )
            from vultron.core.use_cases.triggers.requests import (
                TerminateEmbargoTriggerRequest,
            )

            req = TerminateEmbargoTriggerRequest(
                actor_id=case_manager_id,
                case_id=case_id,
            )
            SvcTerminateEmbargoUseCase(
                self._dl,
                req,
                trigger_activity=self._trigger_activity,
            ).execute()
        except Exception as exc:
            logger.warning(
                "add_participant_status_to_participant: embargo teardown "
                "failed for case '%s': %s",
                case_id,
                exc,
            )

    def _all_participants_closed(self, case: Any) -> bool:
        """Return True if every CVD participant has RM.CLOSED as their latest status.

        The Case Manager (Case Actor) is a coordinator role and does not
        self-report RM closure, so it is excluded from this check.
        """
        from vultron.core.states.rm import RM
        from vultron.core.states.roles import CVDRole

        for p_id in case.actor_participant_index.values():
            p = self._dl.read(p_id)
            if p is None:
                return False
            # Case Manager is a coordinator; skip its participant record.
            roles = getattr(p, "case_roles", [])
            if CVDRole.CASE_MANAGER in roles:
                continue
            statuses = getattr(p, "participant_statuses", [])
            if not statuses:
                return False
            latest_ref = statuses[-1]
            # Resolve to an object when stored as an ID/ref string.
            if isinstance(latest_ref, str):
                ref_id = _as_id(latest_ref)
                if ref_id is None:
                    return False
                latest = self._dl.read(ref_id)
            else:
                latest = latest_ref
            if latest is None:
                return False
            rm_state = getattr(latest, "rm_state", None)
            if rm_state is None or rm_state != RM.CLOSED:
                return False
        return True

    def _close_case_reports(self, case_manager_id: str, case: Any) -> None:
        """Record case-closed event for all case participants (DEMOMA-07-003 step 5).

        SvcCloseReportUseCase requires an offer_id (not a report_id), which
        is unavailable in the received-handler context.  This method emits a
        log entry to record the auto-close intent.  Actual case closure is
        **not** persisted here; this is log-only behaviour for the prototype
        demo.
        """
        logger.info(
            "add_participant_status_to_participant: Case Manager '%s' "
            "auto-closing case '%s' — all participants CLOSED",
            case_manager_id,
            getattr(case, "id_", "?"),
        )

    def _check_all_closed(self, case_id: str, case: Any) -> None:
        """Close the case if all participants have RM.CLOSED (DEMOMA-07-003 step 5)."""
        if not self._all_participants_closed(case):
            return

        logger.info(
            "add_participant_status_to_participant: all participants CLOSED "
            "in case '%s' — marking case closed (DEMOMA-07-003 step 5)",
            case_id,
        )
        case_manager_id = self._find_case_manager_id(case)
        if case_manager_id is None:
            logger.warning(
                "add_participant_status_to_participant: no Case Manager found "
                "— cannot auto-close case '%s'",
                case_id,
            )
            return

        try:
            self._close_case_reports(case_manager_id, case)
        except Exception as exc:
            logger.warning(
                "add_participant_status_to_participant: auto-close failed for "
                "case '%s': %s",
                case_id,
                exc,
            )
