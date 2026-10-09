"""Received case-owner decisions on an embargo proposal (ADR-0122).

``Accept(EmbargoEvent, target=Case)`` activates a proposal and
``Reject(EmbargoEvent, target=Case)`` rejects it.  Only the case owner may
send either (EP-09-005, HP-01-006); the CASE_MANAGER applies and commits the
decision, and every replica learns it from the ledger (EP-09-007).
"""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.owner_decision_tree import (
    activate_embargo_on_case_tree,
    reject_embargo_proposal_on_case_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    SenderEntitlementKind,
)
from vultron.core.models.events.embargo import (
    ActivateEmbargoOnCaseReceivedEvent,
    RejectEmbargoProposalOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
    unaddressed_copy_refusal,
)
from vultron.core.use_cases.received._bt_verdict import (
    not_case_manager_refusal,
    verdict_from_bt,
)

logger = logging.getLogger(__name__)


class _OwnerDecisionReceivedUseCase:
    """Shared frame of both owner-decision handlers.

    Shape checks that write nothing, then the door check (HP-01-005,
    ADR-0118), then the tree; the tree's sender guard refuses anyone but the
    case owner (HP-01-006).  Only the CASE_MANAGER applies the decision, so
    a receiver whose gate turns it away reports a refusal (BT-17-001).
    Subclasses name their tree in :meth:`_build_tree`, so the ledger-commit
    inventory sees which received tree each one runs.
    """

    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.CASE_OWNER
    )
    _label: ClassVar[str]
    _tree_label: ClassVar[str]

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: (
            ActivateEmbargoOnCaseReceivedEvent
            | RejectEmbargoProposalOnCaseReceivedEvent
        ),
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._actor_config = actor_config

    def _build_tree(
        self, case_id: str, embargo_id: str, sender_actor_id: str
    ) -> py_trees.behaviour.Behaviour:
        raise NotImplementedError

    def execute(self) -> HandlerResult:
        request, label = self._request, self._label
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        embargo_id, case_id = request.embargo_id, request.case_id
        if embargo_id is None or case_id is None:
            logger.warning("%s: missing embargo_id or case_id", label)
            return HandlerResult.refused(
                f"{label} is missing its embargo id or case id"
            )
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id, request, label=label
            )
        ) is not None:
            return refusal

        tree = self._build_tree(case_id, embargo_id, request.actor_id)
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            # The commit fans the entry out to every participant replica
            # (EP-09-007, RSH-08-004); without the port nothing replays it.
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005).
            actor_id=receiving_actor_id,
            activity=request,
        )
        verdict = verdict_from_bt(tree, result, label=self._tree_label)
        if verdict.disposition is HandlerDisposition.APPLIED:
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict


class ActivateEmbargoOnCaseReceivedUseCase(_OwnerDecisionReceivedUseCase):
    """The case owner's ``Accept(EmbargoEvent, target=Case)`` (EA / EC)."""

    _label = "Accept(EmbargoEvent)"
    _tree_label = "ActivateEmbargoOnCaseBT"

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: ActivateEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        # The activation tree emits: stub-Invite re-issue (CM-11-016) and the
        # embargo-ending notices (CM-31-009) both need the trigger port, and
        # their RSVP windows come from the actor's config (CM-11-014).
        super().__init__(
            dl,
            request,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=wire_render_port,
            actor_config=actor_config,
        )

    def _build_tree(
        self, case_id: str, embargo_id: str, sender_actor_id: str
    ) -> py_trees.behaviour.Behaviour:
        return activate_embargo_on_case_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            sender_actor_id=sender_actor_id,
            actor_config=self._actor_config,
        )


class RejectEmbargoProposalOnCaseReceivedUseCase(
    _OwnerDecisionReceivedUseCase
):
    """The case owner's ``Reject(EmbargoEvent, target=Case)`` (ER / EJ).

    Takes the trigger-activity port: the owner's rejection of the last open
    revision after disclosure ends the embargo, and the CASE_MANAGER tells
    the participants (EMB-04-002).
    """

    _label = "Reject(EmbargoEvent)"
    _tree_label = "RejectEmbargoProposalOnCaseBT"

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectEmbargoProposalOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        super().__init__(
            dl,
            request,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=wire_render_port,
            actor_config=actor_config,
        )

    def _build_tree(
        self, case_id: str, embargo_id: str, sender_actor_id: str
    ) -> py_trees.behaviour.Behaviour:
        return reject_embargo_proposal_on_case_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            sender_actor_id=sender_actor_id,
            actor_config=self._actor_config,
        )


__all__ = [
    "ActivateEmbargoOnCaseReceivedUseCase",
    "RejectEmbargoProposalOnCaseReceivedUseCase",
]
