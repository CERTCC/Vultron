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
            # Do NOT cascade on BT failure here.  Unlike RemoveEmbargo (where
            # FAILURE means "already cleared" — an idempotent, non-error
            # outcome), a status-update BT failure means the update itself was
            # rejected (e.g., participant not found, invalid state transition).
            # Broadcasting a log entry for a rejected update would mislead
            # peers into believing the status was accepted.
            return

        self._commit_log_cascade()

    def _commit_log_cascade(self) -> None:
        """Commit a CaseLogEntry and fan it out to all participants (PCR-08-003).

        Derives case_id from the inline status object's ``context`` field.
        Uses ``receiving_actor_id`` (the CaseActor's canonical ID) when
        available, falling back to a DataLayer lookup for the Service object
        whose ``context`` matches *case_id*.
        """
        from vultron.core.use_cases.received.actor import _find_case_actor_id
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
            extract_activity_snapshot,
        )

        request = self._request

        # Derive case_id from the inline status object (same approach as BT).
        case_id: str | None = None
        if request.status is not None:
            context = getattr(request.status, "context", None)
            if context:
                case_id = str(context)

        # Fallback 1: activity-level context (populated when activity.context
        # is set to the case object by the caller, e.g. add_status_to_participant
        # sets context=case).
        if case_id is None:
            case_id = request.context_id

        # Fallback 2: read the stored ParticipantStatus and check its context.
        # Handles cases where the inline object was omitted and the BT resolved
        # it via a DataLayer lookup (VerifySenderIsParticipantNode._resolve_case_id).
        if case_id is None and request.status_id:
            stored_status = self._dl.read(request.status_id)
            if stored_status is not None:
                ctx = getattr(stored_status, "context", None)
                if ctx:
                    case_id = str(ctx)

        if case_id is None:
            logger.warning(
                "add_participant_status: cannot determine case_id"
                " — skipping log entry cascade (PCR-08-003)"
            )
            return

        actor_id = request.receiving_actor_id
        if actor_id is None:
            actor_id = _find_case_actor_id(self._dl, case_id)
        if actor_id is None:
            logger.warning(
                "add_participant_status: cannot resolve CaseActor for case '%s'"
                " — skipping log entry cascade (PCR-08-003)",
                case_id,
            )
            return

        commit_log_entry_trigger(
            case_id=case_id,
            object_id=request.status_id or request.activity_id,
            event_type="add_participant_status",
            actor_id=actor_id,
            dl=self._dl,
            sync_port=self._sync_port,
            payload_snapshot=extract_activity_snapshot(request),
        )
