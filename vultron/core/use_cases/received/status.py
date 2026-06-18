"""Use cases for case and participant status activities."""

import logging
from typing import TYPE_CHECKING

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
from vultron.core.use_cases._helpers import _idempotent_create

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


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

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.status.add_case_status_tree import (
            add_case_status_tree,
        )
        from vultron.core.behaviors.status.nodes import (
            CASE_STATUS_ALREADY_PRESENT,
        )

        tree = add_case_status_tree(request=request)
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )

        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            reason_str = reason or result.feedback_message or ""
            if reason_str == CASE_STATUS_ALREADY_PRESENT:
                logger.info(
                    "CaseStatus '%s' already in case '%s'"
                    " — skipping (idempotent)",
                    status_id,
                    case_id,
                )
            else:
                logger.warning(
                    "AddCaseStatusToCaseBT did not succeed for activity"
                    " '%s': %s",
                    request.activity_id,
                    reason_str,
                )


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

    Delegates DEMOMA-07-003 steps to the ``AddParticipantStatusBT``
    behavior tree:
    1. Verify sender is a known case participant.
    2. Append the ParticipantStatus to the CaseParticipant record.
    3. If the new status signals public awareness (CS.P) and the sender
       holds the CASE_OWNER role, initiate embargo teardown.
    4. If all participant RM states are CLOSED and this actor is the
       CASE_MANAGER, emit Leave(VulnerabilityCase) to trigger case closure.

    The tree runs with ``actor_id=receiving_actor_id`` so that
    ``CheckIsCaseManagerNode`` (step 4 gate) correctly evaluates the
    executing actor, not the sender.  Sender identity is supplied via
    constructor args to the relevant nodes.

    Per specs/multi-actor-demo.yaml DEMOMA-07-003,
        specs/behavior-tree-integration.yaml BT-06-001.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddParticipantStatusToParticipantReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AddParticipantStatusToParticipantReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port

    def execute(self) -> None:
        request = self._request
        if request.status_id is None or request.participant_id is None:
            logger.warning(
                "add_participant_status_to_participant: missing status_id"
                " or participant_id"
            )
            return

        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "AddParticipantStatusToParticipantReceivedUseCase:"
                " receiving_actor_id not set — skipping (CLP-10-005)"
            )
            return

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.status.add_participant_status_tree import (
            add_participant_status_tree,
        )

        # Resolve case_id for the guarded-commit subtree (pre-flight lookup).
        case_id = self._resolve_case_id_for_log_cascade()

        tree = add_participant_status_tree(
            request=request,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )

        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            logger.warning(
                "AddParticipantStatusBT did not succeed for activity '%s': %s",
                request.activity_id,
                reason or result.feedback_message,
            )

    def _resolve_case_id_for_log_cascade(self) -> str | None:
        request = self._request

        if request.status is not None:
            context = getattr(request.status, "context", None)
            if context:
                return str(context)

        if request.context_id is not None:
            return request.context_id

        if request.status_id:
            stored_status = self._dl.read(request.status_id)
            if stored_status is not None:
                context = getattr(stored_status, "context", None)
                if context:
                    return str(context)
        return None
