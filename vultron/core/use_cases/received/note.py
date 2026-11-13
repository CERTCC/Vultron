"""Use cases for case note activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.case.received_run import run_received_tree
from vultron.core.behaviors.note.add_note_received_tree import (
    create_add_note_to_case_received_tree,
)
from vultron.core.behaviors.note.remove_note_received_tree import (
    create_remove_note_from_case_received_tree,
)
from vultron.core.models.events.note import (
    AddNoteToCaseReceivedEvent,
    RemoveNoteFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.use_cases.received._bt_verdict import (
    case_manager_verdict,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.services.receiving_actor import resolve_receiving_actor_id

logger = logging.getLogger(__name__)


class AddNoteToCaseReceivedUseCase:
    """Attach a received note to the case and commit a canonical ledger entry.

    Only the actor holding ``CVDRole.CASE_MANAGER`` attaches the note to
    ``VulnerabilityCase.notes`` and commits a ``CaseLedgerEntry``.  Other
    receivers MUST NOT update their case replica directly from
    ``Add(Note)[target=VulnerabilityCase]`` messages — they receive note attachment notifications
    exclusively via ``Announce(CaseLedgerEntry)`` fan-out from the
    CASE_MANAGER (SYNC-02-001, SYNC-02-003).

    The ``CheckIsCaseManagerNode`` guard inside the BT enforces this: a
    non-manager takes the skip arm and neither attaches nor commits
    (CLP-10-003).  The handler reports that as a refusal (HP-01-005): the
    note was addressed to the wrong party.

    The sender must be an active participant whose closure the case does
    not record; anyone else is refused before anything is committed or sent
    (CM-23-018, HP-01-006).
    """

    # A note is case content: an active participant asks the CASE_MANAGER,
    # and a replica takes the attachment from the CASE_MANAGER alone
    # (CM-10-004, CM-23-018, PCR-03-001, PCR-08-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.ACTIVE_PARTICIPANT
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddNoteToCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._request: AddNoteToCaseReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> HandlerResult:
        request = self._request
        # Resolved before any read, so a delivery with no resolvable
        # receiver raises as a wiring fault rather than being refused
        # (BT-17-009, ARCH-15-001); the runner resolves it again for the run.
        resolve_receiving_actor_id(self._dl, request.receiving_actor_id)
        note = request.note
        case_id = request.case_id
        if note is None or case_id is None:
            logger.warning("add_note_to_case: missing inline note or case_id")
            return HandlerResult.refused(
                "Add(Note)[target=VulnerabilityCase] is missing its inline note or case id"
            )

        # The CASE_MANAGER gate reads a missing case as "not the manager" and
        # skips, which would hide an Add aimed at a case this actor lacks.
        if self._dl.read_case(case_id) is None:
            logger.warning("add_note_to_case: case '%s' not found", case_id)
            return HandlerResult.refused(f"case '{case_id}' not found")

        tree = create_add_note_to_case_received_tree(
            note_obj=note,
            case_id=case_id,
            sender_id=request.actor_id,
            activity_id=request.activity_id,
            sender_rule=self.sender_entitlement,
        )
        # A redelivered Add fails the note-id guard as a repeat, which the
        # runner reports SKIPPED (HP-01-003, HP-08-006).
        verdict = run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="GuardedAttachAndCommitBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )
        # Only the CASE_MANAGER attaches; others learn of the note through
        # Announce(CaseLedgerEntry) fan-out (SYNC-02-001, SYNC-02-003).
        return case_manager_verdict(tree, verdict, self._dl, case_id)


class RemoveNoteFromCaseReceivedUseCase:
    """Detach a note from the case and commit a canonical ledger entry.

    Mirror of :class:`AddNoteToCaseReceivedUseCase`: only the CASE_MANAGER
    detaches the note and commits; replicas apply the ledger fan-out.  The
    sender must be the note's author (while an active participant) or the Case
    Owner; anyone else is ``REFUSED`` with the note left in place (CM-30-004).
    A note the case does not hold is ``SKIPPED``.
    """

    # The note's author or the Case Owner asks the CASE_MANAGER; a
    # participant takes the removal from the CASE_MANAGER alone (CM-30-003,
    # PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.AUTHOR, SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RemoveNoteFromCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: RemoveNoteFromCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        # Resolved before any read, so a delivery with no resolvable
        # receiver raises as a wiring fault rather than being refused
        # (BT-17-009, ARCH-15-001); the runner resolves it again for the run.
        resolve_receiving_actor_id(self._dl, request.receiving_actor_id)
        note_id = request.note_id
        case_id = request.case_id
        if note_id is None or case_id is None:
            logger.warning("remove_note_from_case: missing note_id or case_id")
            return HandlerResult.refused(
                "Remove(Note)[target=VulnerabilityCase] is missing its note id or case id"
            )
        if self._dl.read_case(case_id) is None:
            logger.warning(
                "remove_note_from_case: case '%s' not found", case_id
            )
            return HandlerResult.refused(f"case '{case_id}' not found")

        tree = create_remove_note_from_case_received_tree(
            note_id=note_id,
            case_id=case_id,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        # A note the case does not hold fails the reference guard as a
        # repeat, which the runner reports SKIPPED.
        verdict = run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="GuardedDetachAndCommitBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )
        return case_manager_verdict(tree, verdict, self._dl, case_id)
