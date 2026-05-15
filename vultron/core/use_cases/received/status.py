"""Use cases for case and participant status activities."""

import logging
from typing import TYPE_CHECKING, Any

from py_trees.common import Status

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
from vultron.core.use_cases._helpers import _as_id, _idempotent_create
from vultron.core.models.protocols import (
    is_case_model,
)

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

    Delegates all five DEMOMA-07-003 steps to the ``AddParticipantStatusBT``
    behavior tree:
    1. Verify sender is a known case participant.
    2. Append the ParticipantStatus to the CaseParticipant record.
    3. Broadcast the status update to all other case participants.
    4. If the new status signals public awareness (CS.P) and the sender
       holds the CASE_OWNER role, initiate embargo teardown.
    5. If all participant RM states are CLOSED, log case closure
       (prototype: log-only).

    Per specs/multi-actor-demo.yaml DEMOMA-07-003,
        specs/behavior-tree-integration.yaml BT-06-001.
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
        if request.status_id is None or request.participant_id is None:
            logger.warning(
                "add_participant_status_to_participant: missing status_id"
                " or participant_id"
            )
            return

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.status.add_participant_status_tree import (
            add_participant_status_tree,
        )

        tree = add_participant_status_tree(
            request=request,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )

        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            logger.warning(
                "AddParticipantStatusBT did not succeed for activity '%s': %s",
                request.activity_id,
                reason or result.feedback_message,
            )
