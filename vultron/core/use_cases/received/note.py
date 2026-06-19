"""Use cases for case note activities."""

import logging
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.models.events.note import (
    AddNoteToCaseReceivedEvent,
    CreateNoteReceivedEvent,
    RemoveNoteFromCaseReceivedEvent,
)
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.models.protocols import is_case_model
from vultron.core.use_cases._helpers import _as_id

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort

logger = logging.getLogger(__name__)


class CreateNoteReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CreateNoteReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateNoteReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.note.create_note_tree import (
            create_note_tree,
        )

        note = request.note
        if note is None:
            logger.warning(
                "create_note: no note domain object in event for activity '%s'",
                request.activity_id,
            )
            return

        case_id: str | None = note.context
        actor_id = request.actor_id

        bridge = BTBridge(datalayer=self._dl)
        tree = create_note_tree(note_obj=note, case_id=case_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=request
        )

        if result.status != Status.SUCCESS:
            reason = BTBridge.get_failure_reason(tree)
            logger.warning(
                "CreateNoteBT did not succeed for activity '%s': %s",
                request.activity_id,
                reason or result.feedback_message,
            )


class AddNoteToCaseReceivedUseCase:
    """Attach a received note to the case and commit a canonical ledger entry.

    When the CaseActor receives ``Add(Note, Case)`` it:

    1. Attaches the note ID to ``VulnerabilityCase.notes`` (idempotent).
    2. Commits a ``CaseLedgerEntry`` whose ``Announce`` fan-out (via
       ``sync_port``) notifies all participants — this is the only
       notification mechanism; no separate ``AddNoteToCase`` broadcast
       is emitted (``notes/case-communication-model.md``, SYNC-02-002).

    Non-CaseActor receivers attach the note locally but skip the guarded
    commit via ``CheckIsCaseManagerNode`` (CLP-10-003).
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddNoteToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AddNoteToCaseReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> None:
        request = self._request
        note_id = request.note_id
        case_id = request.case_id
        if note_id is None or case_id is None:
            logger.warning("add_note_to_case: missing note_id or case_id")
            return

        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "add_note_to_case: missing receiving_actor_id"
                " — skipping (CLP-10-005)"
            )
            return

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.note.add_note_received_tree import (
            create_add_note_to_case_received_tree,
        )

        tree = create_add_note_to_case_received_tree(
            note_id=note_id,
            case_id=case_id,
        )
        result = BTBridge(datalayer=self._dl).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )
        if result.status != Status.SUCCESS:
            logger.debug(
                "add_note_to_case: BT did not fully succeed for note '%s'"
                " in case '%s': %s",
                note_id,
                case_id,
                BTBridge.get_failure_reason(tree) or result.feedback_message,
            )


class RemoveNoteFromCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: RemoveNoteFromCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: RemoveNoteFromCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        note_id = request.note_id
        case_id = request.case_id
        if note_id is None or case_id is None:
            logger.warning("remove_note_from_case: missing note_id or case_id")
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "remove_note_from_case: case '%s' not found", case_id
            )
            return

        existing_ids = [_as_id(n) for n in case.notes]
        if note_id not in existing_ids:
            logger.info(
                "Note '%s' not in case '%s' — skipping (idempotent)",
                note_id,
                case_id,
            )
            return

        case.notes = [  # type: ignore[assignment]
            n for n in case.notes if _as_id(n) != note_id
        ]
        self._dl.save(case)
        logger.info("Removed note '%s' from case '%s'", note_id, case_id)
