"""Use cases for case note activities."""

import logging
from typing import TYPE_CHECKING

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.note.add_note_received_tree import (
    create_add_note_to_case_received_tree,
)
from vultron.core.behaviors.note.create_note_tree import create_note_tree
from vultron.core.models._helpers import _as_id
from vultron.core.models.events.note import (
    AddNoteToCaseReceivedEvent,
    CreateNoteReceivedEvent,
    RemoveNoteFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    not_case_manager_refusal,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


class CreateNoteReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: CreateNoteReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: CreateNoteReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request

        note = request.note
        if note is None:
            logger.warning(
                "create_note: no note domain object in event for activity '%s'",
                request.activity_id,
            )
            return HandlerResult.refused("Create(Note) carries no note object")

        case_id: str | None = note.context
        # The *receiving* actor, not the sender (BT-17-005): a received Note is
        # stored in the receiver's own replica.
        actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        bridge = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        tree = create_note_tree(note_obj=note, case_id=case_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=request
        )

        verdict = verdict_from_bt(tree, result, label="CreateNoteBT")
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "CreateNoteBT refused activity '%s': %s",
                request.activity_id,
                verdict.reason,
            )
        return verdict


class AddNoteToCaseReceivedUseCase:
    """Attach a received note to the case and commit a canonical ledger entry.

    Only the actor holding ``CVDRole.CASE_MANAGER`` attaches the note to
    ``VulnerabilityCase.notes`` and commits a ``CaseLedgerEntry``.  Other
    receivers MUST NOT update their case replica directly from
    ``Add(Note, Case)`` messages — they receive note attachment notifications
    exclusively via ``Announce(CaseLedgerEntry)`` fan-out from the
    CASE_MANAGER (SYNC-02-002).

    The ``CheckIsCaseManagerNode`` guard inside the BT enforces this: a
    non-manager takes the skip arm and neither attaches nor commits
    (CLP-10-003).  The handler reports that as a refusal (HP-01-005): the
    note was addressed to the wrong party.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddNoteToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AddNoteToCaseReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request
        note_id = request.note_id
        case_id = request.case_id
        if note_id is None or case_id is None:
            logger.warning("add_note_to_case: missing note_id or case_id")
            return HandlerResult.refused(
                "Add(Note, Case) is missing its note id or case id"
            )

        # The CASE_MANAGER gate reads a missing case as "not the manager" and
        # skips, which would hide an Add aimed at a case this actor lacks.
        if self._dl.read_case(case_id) is None:
            logger.warning("add_note_to_case: case '%s' not found", case_id)
            return HandlerResult.refused(f"case '{case_id}' not found")

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_add_note_to_case_received_tree(
            note_id=note_id,
            case_id=case_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="GuardedAttachAndCommitBT"
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            # Only the CASE_MANAGER attaches; others learn of the note through
            # Announce(CaseLedgerEntry) fan-out (SYNC-02-002).
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "add_note_to_case: note '%s' in case '%s' refused: %s",
                note_id,
                case_id,
                verdict.reason,
            )
        return verdict


class RemoveNoteFromCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RemoveNoteFromCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: RemoveNoteFromCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        note_id = request.note_id
        case_id = request.case_id
        if note_id is None or case_id is None:
            logger.warning("remove_note_from_case: missing note_id or case_id")
            return HandlerResult.refused(
                "Remove(Note, Case) is missing its note id or case id"
            )
        case = self._dl.read_case(case_id)

        if case is None:
            logger.warning(
                "remove_note_from_case: case '%s' not found", case_id
            )
            return HandlerResult.refused(f"case '{case_id}' not found")

        existing_ids = [_as_id(n) for n in case.notes]
        if note_id not in existing_ids:
            logger.info(
                "Note '%s' not in case '%s' — skipping (idempotent)",
                note_id,
                case_id,
            )
            return HandlerResult.skipped(
                f"note '{note_id}' not in case '{case_id}'"
            )

        case.notes = [  # type: ignore[assignment]
            n for n in case.notes if _as_id(n) != note_id
        ]
        self._dl.save(case)
        logger.info("Removed note '%s' from case '%s'", note_id, case_id)
        return HandlerResult.applied()
