"""Use cases for case note activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.note.add_note_received_tree import (
    create_add_note_to_case_received_tree,
)
from vultron.core.behaviors.note.create_note_tree import create_note_tree
from vultron.core.behaviors.note.remove_note_received_tree import (
    create_remove_note_from_case_received_tree,
)
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
    reference_edit_verdict,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)

logger = logging.getLogger(__name__)


class CreateNoteReceivedUseCase:
    """Store a received note and, at the CASE_MANAGER, post it to its case.

    The note's ``context`` names the case.  An active participant whose
    closure the case does not record posts it to the CASE_MANAGER; a
    participant replica takes it from the CASE_MANAGER alone (CM-23-018,
    PCR-03-001, PCR-08-001).  Any other sender is refused with nothing
    stored, committed or sent, and so is a note naming no case, or a case
    this store does not hold: there is no standing to check it against.
    """

    # A note is case content: only an active participant posts one, to the
    # CASE_MANAGER (CM-10-004, CM-23-018, PCR-08-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.ACTIVE_PARTICIPANT
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateNoteReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: CreateNoteReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request

        # A Create(Note) with no note is refused by the tree itself
        # (CLP-10-005, CLP-10-018).
        note = request.note
        case_id: str | None = note.context if note is not None else None
        # The *receiving* actor, not the sender (BT-17-005): a received Note is
        # stored in the receiver's own replica.
        actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        tree = create_note_tree(
            note_obj=note,
            case_id=case_id,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
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

    The sender must be an active participant whose closure the case does
    not record; anyone else is refused before anything is committed or sent
    (CM-23-018, HP-01-006).
    """

    # Mirror of Create(Note): an active participant asks the CASE_MANAGER,
    # and a replica takes the attachment from the CASE_MANAGER alone
    # (CM-23-018, PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.ACTIVE_PARTICIPANT
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddNoteToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
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
                "Add(Note, Case) is missing its inline note or case id"
            )
        note_id = note.id_

        # The CASE_MANAGER gate reads a missing case as "not the manager" and
        # skips, which would hide an Add aimed at a case this actor lacks.
        if self._dl.read_case(case_id) is None:
            logger.warning("add_note_to_case: case '%s' not found", case_id)
            return HandlerResult.refused(f"case '{case_id}' not found")

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_add_note_to_case_received_tree(
            note_obj=note,
            case_id=case_id,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
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
    """Detach a note from the case and commit a canonical ledger entry.

    Mirror of :class:`AddNoteToCaseReceivedUseCase`: only the CASE_MANAGER
    detaches the note and commits; replicas apply the ledger fan-out.  The
    sender must be the note's author (while an active participant) or the Case
    Owner; anyone else is ``REFUSED`` with the note left in place (CM-30-001).
    A note the case does not hold is ``SKIPPED``.
    """

    # The note's author or the Case Owner asks the CASE_MANAGER; a
    # participant takes the removal from the CASE_MANAGER alone (CM-30-001,
    # PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.AUTHOR, SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RemoveNoteFromCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
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
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = reference_edit_verdict(
            tree,
            verdict_from_bt(tree, result, label="GuardedDetachAndCommitBT"),
            self._dl,
            case_id,
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "remove_note_from_case: note '%s' in case '%s' refused: %s",
                note_id,
                case_id,
                verdict.reason,
            )
        return verdict
