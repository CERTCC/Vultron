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

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)

logger = logging.getLogger(__name__)


class AddNoteToCaseReceivedUseCase:
    """Attach a received note to the case and commit a canonical ledger entry.

    Only the actor holding ``CVDRole.CASE_MANAGER`` attaches the note to
    ``VulnerabilityCase.notes`` and commits a ``CaseLedgerEntry``.  Other
    receivers MUST NOT update their case replica directly from
    ``Add(Note)[target=VulnerabilityCase]`` messages — they receive note attachment notifications
    exclusively via ``Announce(CaseLedgerEntry)`` fan-out from the
    CASE_MANAGER (SYNC-02-001, SYNC-02-003).

    The tree declares the manager path alone, so its path stage refuses
    any other receiver before anything runs (HP-01-005, HP-01-039): the
    note was addressed to the wrong party.

    The sender must be an active participant whose closure the case does
    not record; anyone else is refused before anything is committed or sent
    (CM-23-018, HP-01-006).
    """

    # A note is case content: an active participant asks the CASE_MANAGER,
    # and no other receiver acts on the Add: a replica takes the note from
    # the ledger (CM-10-004, CM-23-018, PCR-03-001, PCR-08-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
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
        note = request.note
        case_id = request.case_id
        if note is None or case_id is None:
            logger.warning("add_note_to_case: missing inline note or case_id")
            return HandlerResult.refused(
                "Add(Note)[target=VulnerabilityCase] is missing its inline note or case id"
            )

        # A case this store does not hold puts it on the no-case path, which
        # the tree's path stage refuses (HP-01-039).
        tree = create_add_note_to_case_received_tree(
            note_obj=note,
            case_id=case_id,
            sender_id=request.actor_id,
            activity_id=request.activity_id,
            sender_rule=self.sender_entitlement,
        )
        # A redelivered Add fails the note-id guard as a repeat, which the
        # runner reports SKIPPED (HP-01-003, HP-08-006).
        # Only the CASE_MANAGER attaches; the path stage refuses any other
        # receiver, which learns of the note through Announce(CaseLedgerEntry)
        # fan-out (SYNC-02-001, SYNC-02-003, HP-01-005).
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="GuardedAttachAndCommitBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )


class RemoveNoteFromCaseReceivedUseCase:
    """Refuse a received ``Remove(Note)[target=VulnerabilityCase]``.

    Removing a note is not supported: the case ledger is append-only, and
    the protocol does not yet define what removing ledgered content means
    (CM-30-003, #6430).  The tree's own guard refuses every ``Remove(Note)``,
    from an entitled sender too; the note stays attached and nothing is
    committed.  A replica refuses it at its path stage (HP-01-005).
    """

    # The CM-30-001 rule: the note's author or the Case Owner, at the
    # CASE_MANAGER alone.  It is still checked, so a sender with no standing
    # is refused for that, and the sender's number is counted (SYNC-21-008).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
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
        tree = create_remove_note_from_case_received_tree(
            note_id=request.note_id,
            case_id=request.case_id,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="RefuseRemoveNoteBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )
