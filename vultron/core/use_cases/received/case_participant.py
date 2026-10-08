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
    RemoveCaseParticipantFromCaseReceivedNode,
)
from vultron.core.behaviors.case.nodes.participant_reinstatement import (
    EmitParticipantReinstatementNoticeNode,
    ReinstateCaseParticipantReceivedNode,
)
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    InviteReinstatedParticipantToEmbargoNode,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    SenderEntitlementKind,
    exempt,
)
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    case_manager_absence_refusal,
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


class _CaseOwnerParticipantMoveUseCase[
    MoveEvent: (
        AddCaseParticipantToCaseReceivedEvent,
        RemoveCaseParticipantFromCaseReceivedEvent,
    )
]:
    """Shared frame of the Case Owner's two participant moves (ADR-0116).

    ``Remove(CaseParticipant)`` takes a participant out of active
    participation (CM-31-004) and ``Add(CaseParticipant)`` reinstates it
    (CM-31-011).  Both are the Case Owner's request to the CASE_MANAGER, run
    the same staged tree (intake, sender guard, guards, commit, gated
    effects), and are judged the same way: a guard failure is ``REFUSED``,
    a failed effect after the commit is an internal fault, and at any other
    replica the activity is stored and nothing else is written
    (RSH-08-003) — the CASE_MANAGER's notice is ``SKIPPED``, because the
    replica takes the move from the ledger entry, and the same message from
    anyone else is ``REFUSED`` by the sender guard.
    """

    # The declared kind names the floor; the tree's role-scoped sender guard
    # (the Case Owner at the manager, the CASE_MANAGER at a replica) is the
    # full rule, and the only place it is defined (HP-01-006/007).
    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.CASE_OWNER
    )

    #: The tree's name, for log lines and refusals.
    _LABEL: ClassVar[str]
    #: The move, in the activity's own words, for log lines.
    _MESSAGE: ClassVar[str]
    #: Guards whose ``FAILURE`` is an idempotent repeat, read as ``SKIPPED``.
    _SKIP_GUARDS: ClassVar[tuple[type[py_trees.behaviour.Behaviour], ...]] = ()
    #: Effects whose ``FAILURE`` is an internal fault: the move is committed.
    _EFFECTS: ClassVar[tuple[type[py_trees.behaviour.Behaviour], ...]]

    def __init__(
        self,
        dl: CasePersistence,
        request: MoveEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._request: MoveEvent = request

    def _refuse(self, reason: str) -> HandlerResult:
        logger.warning("%s: %s", self._LABEL, reason)
        return refuse_after_intake(
            self._dl,
            self._request,
            reason,
            name=self._LABEL,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )

    def _claimed_actor_id(self) -> str | None:
        """The actor the inline participant names, when it names one."""
        participant = self._request.participant
        if isinstance(participant, CaseParticipant):
            return _as_id(participant.attributed_to)
        return None

    def _build_tree(
        self, participant_id: str, case_id: str
    ) -> py_trees.behaviour.Behaviour:
        """The move's received tree; subclasses implement it."""
        raise NotImplementedError

    def execute(self) -> HandlerResult:
        request = self._request
        participant_id = request.participant_id
        case_id = request.case_id
        if participant_id is None or case_id is None:
            return self._refuse(
                f"{self._MESSAGE} is missing its participant id or case id"
            )
        if self._dl.read_case(case_id) is None:
            return self._refuse(f"unknown case '{case_id}'")
        tree = self._build_tree(participant_id, case_id)
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
        label = self._LABEL
        if any(node_failed(tree, guard) for guard in self._SKIP_GUARDS):
            return HandlerResult.skipped(failure_reason(tree, result))
        if any(node_failed(tree, effect) for effect in self._EFFECTS):
            # The move is committed by now; a fact that could not be
            # recorded, or a notice that could not be built or queued, is
            # our fault, not the sender's (ADR-0095, BT-14-001).
            raise VultronBTInternalError(
                f"{label}: {failure_reason(tree, result)}"
            )
        verdict = verdict_from_bt(tree, result, label=label)
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s did not apply %s for participant '%s' of case '%s': %s",
                label,
                self._MESSAGE,
                participant_id,
                case_id,
                verdict.reason,
            )
            return verdict
        if not_case_manager(tree):
            # No arm for a case without a CASE_MANAGER (CM-24-006): the
            # sender guard let it through only as the bootstrap window.
            if (
                refusal := case_manager_absence_refusal(self._dl, case_id)
            ) is not None:
                return refusal
            # Only the CASE_MANAGER's notice passes the replica's sender
            # guard; the replica stored it and applies the move from the
            # ledger entry instead (CM-31-007, RSH-08-003).
            return HandlerResult.skipped(
                f"{label}: {self._MESSAGE} notice for '{participant_id}'"
                " stored; a replica applies it from its ledger entry"
            )
        logger.info(
            "%s applied %s for participant '%s' of case '%s'",
            label,
            self._MESSAGE,
            participant_id,
            case_id,
        )
        return verdict


class AddCaseParticipantToCaseReceivedUseCase(
    _CaseOwnerParticipantMoveUseCase[AddCaseParticipantToCaseReceivedEvent]
):
    """The Case Owner asks the CASE_MANAGER to reinstate a participant (CM-31-011).

    ``Add(CaseParticipant)`` only reinstates (ADR-0116, VAM-06-002).  At the
    CASE_MANAGER: a sender that does not hold ``CASE_OWNER``, an ``Add``
    naming no participant of the case, one naming an invitee that never
    joined, and one naming a participant that is not removed are all
    ``REFUSED`` — joining is accepting a stub Invite (ADR-0114).  An
    accepted reinstatement commits the owner's activity as the one ledger
    entry, clears the removal fact without asking the participant to accept
    again, backfills it once it is active (CM-10-006), sends it a direct
    notice, and sends it the active embargo's Invite when it is not
    ``SIGNATORY`` to it (CM-31-013).
    """

    # Re-declared so ``request`` names this handler's own event class, the
    # one its semantic-registry row routes (SE-02).
    def __init__(
        self,
        dl: CasePersistence,
        request: AddCaseParticipantToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        super().__init__(
            dl,
            request,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=wire_render_port,
        )

    _LABEL: ClassVar[str] = "AddCaseParticipantReceivedBT"
    _MESSAGE: ClassVar[str] = "Add(CaseParticipant, Case)"
    _EFFECTS: ClassVar[tuple[type[py_trees.behaviour.Behaviour], ...]] = (
        ReinstateCaseParticipantReceivedNode,
        BackfillAdmittedParticipantsNode,
        EmitParticipantReinstatementNoticeNode,
        InviteReinstatedParticipantToEmbargoNode,
    )

    def _build_tree(
        self, participant_id: str, case_id: str
    ) -> py_trees.behaviour.Behaviour:
        return create_add_case_participant_received_tree(
            participant_id=participant_id,
            case_id=case_id,
            sender_id=self._request.actor_id,
            participant_actor_id=self._participant_actor_id(participant_id),
            claimed_actor_id=self._claimed_actor_id(),
        )

    def _participant_actor_id(self, participant_id: str) -> str:
        """The actor the stored record belongs to, else the one claimed.

        Read from this store, which the guards judge; the claim is only a
        fallback for a replica, where the effects never run.
        """
        record = self._dl.read(participant_id)
        if isinstance(record, CaseParticipant) and (
            actor_id := _as_id(record.attributed_to)
        ):
            return actor_id
        return self._claimed_actor_id() or participant_id


class RemoveCaseParticipantFromCaseReceivedUseCase(
    _CaseOwnerParticipantMoveUseCase[
        RemoveCaseParticipantFromCaseReceivedEvent
    ]
):
    """The Case Owner asks the CASE_MANAGER to remove a participant (CM-31-004).

    At the CASE_MANAGER: a sender that does not hold ``CASE_OWNER``, a
    removal naming the CASE_MANAGER's or the Case Owner's participant, and
    one naming no participant of the case are ``REFUSED``; removing an
    already-removed participant is ``SKIPPED``.  An accepted removal commits
    the owner's activity as the one ledger entry (CM-31-005), sets the
    removal fact while keeping the record (CM-31-001), and sends the removed
    participant a direct notice (CM-31-006).
    """

    # Re-declared so ``request`` names this handler's own event class, the
    # one its semantic-registry row routes (SE-02).
    def __init__(
        self,
        dl: CasePersistence,
        request: RemoveCaseParticipantFromCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        super().__init__(
            dl,
            request,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=wire_render_port,
        )

    _LABEL: ClassVar[str] = "RemoveCaseParticipantReceivedBT"
    _MESSAGE: ClassVar[str] = "Remove(CaseParticipant, Case)"
    _SKIP_GUARDS: ClassVar[tuple[type[py_trees.behaviour.Behaviour], ...]] = (
        ParticipantNotYetRemovedNode,
    )
    _EFFECTS: ClassVar[tuple[type[py_trees.behaviour.Behaviour], ...]] = (
        RemoveCaseParticipantFromCaseReceivedNode,
        EmitParticipantRemovalNoticeNode,
    )

    def _build_tree(
        self, participant_id: str, case_id: str
    ) -> py_trees.behaviour.Behaviour:
        return create_remove_case_participant_received_tree(
            participant_id=participant_id,
            case_id=case_id,
            sender_id=self._request.actor_id,
            removal_activity_id=self._request.activity_id,
            claimed_actor_id=self._claimed_actor_id(),
        )
