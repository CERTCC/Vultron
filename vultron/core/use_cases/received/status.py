"""Use cases for case and participant status activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.add_case_status_tree import (
    add_case_status_tree,
)
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    CASE_STATUS_ALREADY_PRESENT,
)
from vultron.core.behaviors.status.nodes.dimension_filter import (
    FilterParticipantStatusDimensionsNode,
)
from vultron.core.models.events.status import (
    AddCaseStatusToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
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
    door_refusal,
    find_named,
    node_failed,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.status_authorization import (
        StatusAuthorizationCallOutBundle,
    )
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
    any_of,
)

logger = logging.getLogger(__name__)


def _filter_node_wholly_refused(tree: py_trees.behaviour.Behaviour) -> bool:
    """Return True if FilterParticipantStatusDimensionsNode returned FAILURE.

    Used by AddParticipantStatusToParticipantReceivedUseCase to distinguish a
    wholly-refused dimension-filter from other BT failure causes (ISSUE-3199,
    AC-2).  Only the filter's total-refusal path warrants a refusal;
    sender-not-a-participant or authorization failures are
    different failure modes that do not indicate the assertion was wholly refused.
    """
    return node_failed(tree, FilterParticipantStatusDimensionsNode)


def _adoption_gate_blocked(tree: py_trees.behaviour.Behaviour) -> bool:
    """Return True if the StatusAdoptionGate Selector returned FAILURE."""
    gate = find_named(tree, "StatusAdoptionGate")
    return gate is not None and gate.status == Status.FAILURE


class AddCaseStatusToCaseReceivedUseCase:
    """Process a received ``Add(CaseStatus, VulnerabilityCase)`` (CP, CX, CA).

    ``Add(CaseStatus)`` is the CASE_MANAGER's record of the case status it
    adopted, which it alone emits (RSH-04-001).  A receiver admits it only from
    the case's CASE_MANAGER, sent to a participant (RSH-04-005, PCR-03-001);
    a participant reports P, X or A in the ``CaseStatus`` its own
    ``Add(ParticipantStatus)`` embeds, where the StatusAdoptionGate applies
    (RSH-07-001).  An ``Add(CaseStatus)`` from any other sender, or sent to
    the CASE_MANAGER, is ``REFUSED`` before anything is committed, written or
    sent (HP-01-006).
    """

    # Only the CASE_MANAGER sends it, and only to a participant; no sender is
    # entitled at the CASE_MANAGER (RSH-04-005, RSH-04-001, PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_participant=any_of(SenderEntitlementKind.CASE_MANAGER)
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AddCaseStatusToCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AddCaseStatusToCaseReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        status_id = request.status_id
        case_id = request.case_id
        if not status_id or not case_id:
            logger.warning(
                "add_case_status_to_case: missing status_id or case_id"
            )
            return HandlerResult.refused(
                "Add(CaseStatus) is missing its status id or case id"
            )

        tree = add_case_status_tree(
            request=request,
            sender_rule=self.sender_entitlement,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): the guards
            # check the inbound CaseStatus against the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )

        if (refusal := door_refusal(tree)) is not None:
            return refusal  # a door refused: no reply, no fault (CM-23-017)
        if (
            result.status != Status.SUCCESS
            and BTBridge.get_failure_reason(tree)
            == CASE_STATUS_ALREADY_PRESENT
        ):
            logger.info(
                "CaseStatus '%s' already in case '%s' — skipping (idempotent)",
                status_id,
                case_id,
            )
            return HandlerResult.skipped(
                f"CaseStatus '{status_id}' already in case '{case_id}'"
            )
        verdict = verdict_from_bt(tree, result, label="AddCaseStatusToCaseBT")
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "AddCaseStatusToCaseBT refused activity '%s': %s",
                request.activity_id,
                verdict.reason,
            )
            # A precondition refusal is answered by the tree's refusal notice
            # alone, and a sender-guard refusal by nothing (CLP-05-001,
            # HP-01-006); no ProcessingFault is sent as well (#4756).
        return verdict


class AddParticipantStatusToParticipantReceivedUseCase:
    """Process a received Add(ParticipantStatus, CaseParticipant) message.

    Delegates DEMOMA-07-003 steps to the ``AddParticipantStatusBT``
    behavior tree:
    1. Verify the sender: at the CASE_MANAGER, a known case participant;
       at a participant replica, the CASE_MANAGER alone (PCR-03-001).
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

    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.PARTICIPANT
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddParticipantStatusToParticipantReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        call_out: "StatusAuthorizationCallOutBundle | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AddParticipantStatusToParticipantReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port
        self._call_out = call_out

    def execute(self) -> HandlerResult:
        request = self._request
        if not request.status_id or not request.participant_id:
            logger.warning(
                "add_participant_status_to_participant: missing status_id"
                " or participant_id"
            )
            return HandlerResult.refused(
                "Add(ParticipantStatus) is missing its status id or"
                " participant id"
            )

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        # Resolve case_id for the guarded-commit subtree (pre-flight lookup).
        case_id = self._resolve_case_id_for_log_cascade()

        call_out_kwargs = (
            {"call_out": self._call_out} if self._call_out is not None else {}
        )
        tree = add_participant_status_tree(
            request=request,
            case_id=case_id,
            sender_rule=self.sender_entitlement,
            **call_out_kwargs,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )

        if (refusal := door_refusal(tree)) is not None:
            return refusal  # a door refused: no reply, no fault (CM-23-017)
        verdict = verdict_from_bt(tree, result, label="AddParticipantStatusBT")
        if verdict.disposition is HandlerDisposition.REFUSED and (
            _adoption_gate_blocked(tree)
        ):
            # The raw claim is on the participant record; only its adoption as
            # canonical was withheld (RSH-01-001, RSH-01-002).  That is not a
            # refusal of the assertion's content (RSH-05-022), so no fault.
            return HandlerResult.skipped(
                f"ParticipantStatus '{request.status_id}' recorded but not"
                " adopted: CASE_OWNER approval required (RSH-01-002)"
            )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "AddParticipantStatusBT refused activity '%s': %s",
                request.activity_id,
                verdict.reason,
            )
            # The tree's refusal notice is the one answer (CLP-05-001); no
            # ProcessingFault is sent as well (#4756).
            if _filter_node_wholly_refused(tree):
                return HandlerResult.refused(
                    f"ParticipantStatus assertion wholly refused for activity"
                    f" '{request.activity_id}': {verdict.reason}"
                )
        return verdict

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
