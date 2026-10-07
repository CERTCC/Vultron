"""Use cases for case participant management activities."""

import logging
from typing import ClassVar

import py_trees

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.case_participant_received_tree import (
    create_add_case_participant_received_tree,
    create_remove_case_participant_received_tree,
)
from vultron.core.behaviors.case.nodes.case_participant_received import (
    EmitParticipantRemovalNoticeNode,
    ParticipantNotYetRemovedNode,
)
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    SenderEntitlementKind,
    exempt,
)
from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    failure_reason,
    node_failed,
    not_case_manager,
    verdict_from_bt,
)
from vultron.core.use_cases.received._store_only import (
    refuse_after_intake,
    run_store_only,
    store_only_verdict,
)
from vultron.errors import VultronBTInternalError

logger = logging.getLogger(__name__)


class CreateCaseParticipantReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4070", "no sender check for case participant operations"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateCaseParticipantReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: CreateCaseParticipantReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        tree, result = run_store_only(
            self._dl,
            request,
            name="CreateCaseParticipantReceivedBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            store_node=StoreReceivedObjectNode(
                request.object_type,
                request.participant_id,
                request.participant,
                "CaseParticipant",
                request.activity_id,
            ),
        )
        return store_only_verdict(
            tree, result, label="CreateCaseParticipantReceivedBT"
        )


class AddCaseParticipantToCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = exempt(
        "#4070", "no sender check for case participant operations"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AddCaseParticipantToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AddCaseParticipantToCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        participant_id = request.participant_id
        case_id = request.case_id
        if participant_id is None or case_id is None:
            logger.warning(
                "add_case_participant_to_case: missing participant_id or case_id"
            )
            return refuse_after_intake(
                self._dl,
                request,
                "Add(CaseParticipant, Case) is missing its participant id or"
                " case id",
                name="AddCaseParticipantReceivedBT",
                sync_port=self._sync_port,
                wire_render_port=self._wire_render_port,
            )
        tree = create_add_case_participant_received_tree(
            participant_id=participant_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="AddCaseParticipantReceivedBT"
        )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            # The participant was not added: an unknown case or participant
            # is a rejection of the message, not an internal error (#2255).
            logger.warning(
                "AddCaseParticipantReceivedBT did not add participant '%s'"
                " to case '%s': %s",
                participant_id,
                case_id,
                verdict.reason,
            )
            return verdict
        logger.info(
            "Added participant '%s' to case '%s'",
            participant_id,
            case_id,
        )
        return HandlerResult.applied()


class RemoveCaseParticipantFromCaseReceivedUseCase:
    """The Case Owner asks the CASE_MANAGER to remove a participant (CM-31-004).

    At the CASE_MANAGER: a sender that does not hold ``CASE_OWNER``, a
    removal naming the CASE_MANAGER's or the Case Owner's participant, and
    one naming no participant of the case are ``REFUSED``; removing an
    already-removed participant is ``SKIPPED``.  An accepted removal commits
    the owner's activity as the one ledger entry (CM-31-005), sets the
    removal fact while keeping the record (CM-31-001), and sends the removed
    participant a direct notice (CM-31-006).

    At any other replica the activity is stored and nothing else is written
    (RSH-08-003): the CASE_MANAGER's notice is ``SKIPPED`` — the replica
    takes the removal from the ledger entry (CM-31-007) — and a removal from
    anyone else is ``REFUSED`` by the sender guard.
    """

    # The declared kind names the floor; the tree's role-scoped sender guard
    # (the Case Owner at the manager, the CASE_MANAGER at a replica) is the
    # full rule, and the only place it is defined (HP-01-006/007).
    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: RemoveCaseParticipantFromCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._request: RemoveCaseParticipantFromCaseReceivedEvent = request

    def _refuse(self, reason: str) -> HandlerResult:
        logger.warning("remove_case_participant_from_case: %s", reason)
        return refuse_after_intake(
            self._dl,
            self._request,
            reason,
            name="RemoveCaseParticipantReceivedBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )

    def execute(self) -> HandlerResult:
        request = self._request
        participant_id = request.participant_id
        case_id = request.case_id
        if participant_id is None or case_id is None:
            return self._refuse(
                "Remove(CaseParticipant, Case) is missing its participant id"
                " or case id"
            )
        if self._dl.read_case(case_id) is None:
            return self._refuse(f"unknown case '{case_id}'")
        tree = create_remove_case_participant_received_tree(
            participant_id=participant_id,
            case_id=case_id,
            sender_id=request.actor_id,
            removal_activity_id=request.activity_id,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        return self._verdict(tree, result, participant_id, case_id)

    def _verdict(
        self,
        tree: py_trees.behaviour.Behaviour,
        result: BTExecutionResult,
        participant_id: str,
        case_id: str,
    ) -> HandlerResult:
        label = "RemoveCaseParticipantReceivedBT"
        if node_failed(tree, ParticipantNotYetRemovedNode):
            return HandlerResult.skipped(failure_reason(tree, result))
        if node_failed(tree, EmitParticipantRemovalNoticeNode):
            # The removal is committed and applied by now; a notice that
            # could not be built or queued is our fault, not the sender's
            # (ADR-0095, BT-14-001).
            raise VultronBTInternalError(
                f"{label}: {failure_reason(tree, result)}"
            )
        verdict = verdict_from_bt(tree, result, label=label)
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s did not remove participant '%s' from case '%s': %s",
                label,
                participant_id,
                case_id,
                verdict.reason,
            )
            return verdict
        if not_case_manager(tree):
            case = self._dl.read_case(case_id)
            if case is None or resolve_case_manager_id(case, self._dl) is None:
                # No arm for a case without a CASE_MANAGER (CM-24-006): the
                # sender guard let it through only as the bootstrap window.
                return HandlerResult.refused(
                    f"{label}: case '{case_id}' has no CASE_MANAGER"
                )
            # Only the CASE_MANAGER's notice passes the replica's sender
            # guard; the replica stored it and applies the removal from the
            # ledger entry instead (CM-31-007, RSH-08-003).
            return HandlerResult.skipped(
                f"{label}: removal notice for '{participant_id}' stored;"
                " a replica applies the removal from its ledger entry"
            )
        logger.info(
            "Removed participant '%s' from active participation in case '%s'",
            participant_id,
            case_id,
        )
        return verdict
