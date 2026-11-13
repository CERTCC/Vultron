"""Use cases for case and participant status activities."""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.received_run import (
    OutcomeReader,
    ReceivedOutcome,
    find_named,
    node_failed,
    run_received_tree,
)
from vultron.core.behaviors.status.add_case_status_tree import (
    add_case_status_tree,
)
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.behaviors.status.nodes.participant_status_acceptance import (
    CheckParticipantStatusAcceptableNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.events.status import (
    AddCaseStatusToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases.received._bt_verdict import (
    case_manager_verdict,
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


def _status_refused(tree: py_trees.behaviour.Behaviour) -> bool:
    """Return True if CheckParticipantStatusAcceptableNode refused the status.

    Used by AddParticipantStatusToParticipantReceivedUseCase to tell a refused
    status from other BT failure causes (RSH-09-008, ISSUE-3199): a
    sender-not-a-participant or authorization failure does not say the status
    itself was refused.
    """
    return node_failed(tree, CheckParticipantStatusAcceptableNode)


def _adoption_gate_blocked(tree: py_trees.behaviour.Behaviour) -> bool:
    """True when the StatusAdoptionGate withheld adoption (returned FAILURE)."""
    gate = find_named(tree, "StatusAdoptionGate")
    return gate is not None and gate.status == Status.FAILURE


def _participant_status_reader(
    status_id: str, activity_id: str
) -> OutcomeReader:
    """The participant-status tree's own reading of its run.

    - The raw claim is on the participant record, but the StatusAdoptionGate
      withheld its adoption as canonical (RSH-01-001, RSH-01-002).  That is
      not a refusal of the assertion's content (RSH-09-008), so the act
      keeps its entry and the append, no fault is sent, and the run is
      ``SKIPPED``.
    - The status itself was refused (RSH-09-008, ISSUE-3199): the reason
      says so.  The tree's refusal notice is the one answer (CLP-05-001); no
      ProcessingFault is sent as well (#4756).
    """

    def read(outcome: ReceivedOutcome) -> HandlerResult | None:
        if outcome.succeeded and _adoption_gate_blocked(outcome.tree):
            return HandlerResult.skipped(
                f"ParticipantStatus '{status_id}' recorded but not"
                " adopted: CASE_OWNER approval required (RSH-01-002)"
            )
        if not outcome.succeeded and _status_refused(outcome.tree):
            return HandlerResult.refused(
                f"ParticipantStatus refused for activity"
                f" '{activity_id}': {outcome.refusal_reason}"
            )
        return None

    return read


class AddCaseStatusToCaseReceivedUseCase:
    """Process a received ``Add(CaseStatus)[target=VulnerabilityCase]`` (CP, CX, CA).

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
        trigger_activity: TriggerActivityPort | None = None,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AddCaseStatusToCaseReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        # An Add missing its status id or case id gets the incomplete-
        # activity tree, whose guard refuses it (CLP-10-018).
        tree = add_case_status_tree(
            request=request,
            sender_rule=self.sender_entitlement,
        )
        # A redelivered status fails the idempotency guard as a repeat, which
        # the runner reports SKIPPED with no refusal notice (HP-01-014,
        # CLP-10-042).  A door refusal gets no reply and no fault (CM-23-045);
        # a precondition refusal is answered by the tree's refusal notice
        # alone, and a sender-guard refusal by nothing (CLP-05-001,
        # HP-01-006); no ProcessingFault is sent as well (#4756).
        return run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="AddCaseStatusToCaseBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
        )


class AddParticipantStatusToParticipantReceivedUseCase:
    """Process a received Add(ParticipantStatus)[target=CaseParticipant] message.

    Delegates DEMOMA-07-003 steps to the ``AddParticipantStatusBT``
    behavior tree:
    1. Verify the sender: at the CASE_MANAGER, the participant the target
       record names, or the CASE_MANAGER or Case Owner asserting on its
       behalf (RSH-08-014); at a participant replica, the CASE_MANAGER
       alone (PCR-03-001).
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

    # Participant status is self-declared: the participant the target record
    # names sends it, or the CASE_MANAGER or Case Owner asserts an on-behalf
    # v→V or d→D for it, whose shape the tree checks (RSH-08-014,
    # PRM-06-003/004).  It is sent to the CASE_MANAGER alone: a replica
    # takes participant status from the ledger, never from an Add
    # (PCR-03-001, RSH-08-003), so the rule names the CASE_MANAGER side only.
    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_case_manager=any_of(
            SenderEntitlementKind.CASE_MANAGER,
            SenderEntitlementKind.CASE_OWNER,
            SenderEntitlementKind.AUTHOR,
        )
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddParticipantStatusToParticipantReceivedEvent,
        trigger_activity: TriggerActivityPort | None = None,
        sync_port: SyncActivityPort | None = None,
        call_out: StatusAuthorizationCallOutBundle | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AddParticipantStatusToParticipantReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port
        self._call_out = call_out

    def execute(self) -> HandlerResult:
        request = self._request
        # The status says which case it applies to: the tree is built on the
        # carried status's own ``context``.  Its target door admits the
        # delivery only when the receiver's record of the target participant
        # names that case, so the status joins only its target's own case
        # and no store is read here (HP-08-008, HP-08-013, HP-08-014).  A status carried by
        # reference names no case, which the path stage refuses.
        case_id = _as_id(getattr(request.status, "context", None)) or None

        call_out_kwargs = (
            {"call_out": self._call_out} if self._call_out is not None else {}
        )
        tree = add_participant_status_tree(
            request=request,
            case_id=case_id,
            sender_rule=self.sender_entitlement,
            **call_out_kwargs,
        )
        verdict = run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label="AddParticipantStatusBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            # An Add missing its status id runs the incomplete-activity
            # tree, which has no status to read (CS-08-002).
            reader=(
                _participant_status_reader(
                    request.status_id, request.activity_id
                )
                if request.status_id
                else None
            ),
        )
        if case_id is not None:
            # Only the CASE_MANAGER adjudicates the status (HP-01-005).  With
            # no case the sender guard has already refused.
            verdict = case_manager_verdict(tree, verdict, self._dl, case_id)
        return verdict
