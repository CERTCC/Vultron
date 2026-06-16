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

        self._commit_log_cascade_bt()

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

    def _is_case_actor_receiver(
        self, *, case_id: str, case_actor_id: str
    ) -> bool:
        receiving_actor_id = self._request.receiving_actor_id
        if receiving_actor_id is None:
            logger.warning(
                "add_participant_status: missing receiving_actor_id for case '%s'"
                " — skipping canonical commit to avoid non-CaseActor append",
                case_id,
            )
            return False
        if receiving_actor_id != case_actor_id:
            logger.debug(
                "add_participant_status: receiving actor is not the CaseActor for"
                " case '%s' — skipping canonical commit",
                case_id,
            )
            return False
        return True

    def _commit_log_cascade_bt(self) -> None:
        """Commit a CaseLedgerEntry via CommitCaseLedgerEntryNode (PCR-08-003).

        Derives case_id from the inline status object's ``context`` field.
        Uses ``receiving_actor_id`` (the CaseActor's canonical ID) when
        available, falling back to a DataLayer lookup for the Service object
        whose ``context`` matches *case_id*.
        """
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.nodes import CommitCaseLedgerEntryNode
        from vultron.core.use_cases.received.actor import _find_case_actor_id

        request = self._request
        case_id = self._resolve_case_id_for_log_cascade()
        if case_id is None:
            logger.warning(
                "add_participant_status: cannot determine case_id"
                " — skipping log entry cascade (PCR-08-003)"
            )
            return

        case_actor_id = _find_case_actor_id(self._dl, case_id)
        if case_actor_id is None:
            logger.warning(
                "add_participant_status: cannot resolve CaseActor for case '%s'"
                " — skipping log entry cascade (PCR-08-003)",
                case_id,
            )
            return
        if not self._is_case_actor_receiver(
            case_id=case_id, case_actor_id=case_actor_id
        ):
            return

        BTBridge(datalayer=self._dl).execute_with_setup(
            tree=CommitCaseLedgerEntryNode(case_id=case_id),
            actor_id=case_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )

        self._commit_close_case_if_all_closed(
            case_id=case_id, case_actor_id=case_actor_id
        )

    def _participant_rm_state(self, participant_id: str) -> object | None:
        """Return the latest RM state for a participant, or None if unavailable."""
        from vultron.core.use_cases._helpers import _as_id

        dl = self._dl
        participant = dl.read(participant_id)
        if participant is None:
            return None
        statuses = getattr(participant, "participant_statuses", [])
        if not statuses:
            return None
        latest_ref = statuses[-1]
        if isinstance(latest_ref, str):
            ref_id = _as_id(latest_ref)
            if ref_id is None:
                return None
            latest = dl.read(ref_id)
        else:
            latest = latest_ref
        if latest is None:
            return None
        return getattr(latest, "rm_state", None)

    def _all_participants_closed(self, case_id: str) -> bool:
        """Return True iff every CVD participant has RM.CLOSED.

        The CASE_MANAGER role is excluded (coordinator role, not a CVD
        participant).  Returns False when any participant is missing, has
        no recorded status, or has not yet reached RM.CLOSED.
        """
        from vultron.core.states.roles import CVDRole
        from vultron.core.states.rm import RM

        case = self._dl.read(case_id)
        if case is None:
            return False

        participant_index = getattr(case, "actor_participant_index", {})
        if not participant_index:
            return False

        for p_id in participant_index.values():
            participant = self._dl.read(p_id)
            if participant is None:
                return False
            roles = getattr(participant, "case_roles", [])
            if CVDRole.CASE_MANAGER in roles:
                continue
            rm_state = self._participant_rm_state(p_id)
            if rm_state is None or rm_state != RM.CLOSED:
                return False
        return True

    def _commit_close_case_if_all_closed(
        self, *, case_id: str, case_actor_id: str
    ) -> None:
        """Commit a ``close_case`` ledger entry when all participants are closed.

        Called after a successful ``add_participant_status`` commit to check
        whether the new status tips every CVD participant into RM.CLOSED.
        When it does, a canonical ``close_case`` ledger entry is appended so
        the case-actor log reflects the protocol-level auto-close event.

        Per DEMOMA-07-003 step 5.
        """
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
        )

        if not self._all_participants_closed(case_id):
            return

        logger.info(
            "close_case: all participants CLOSED for case '%s'"
            " — committing close_case ledger entry (DEMOMA-07-003 step 5)",
            case_id,
        )
        commit_log_entry_trigger(
            case_id=case_id,
            object_id=case_id,
            event_type="close_case",
            actor_id=case_actor_id,
            dl=self._dl,
            sync_port=self._sync_port,
        )
