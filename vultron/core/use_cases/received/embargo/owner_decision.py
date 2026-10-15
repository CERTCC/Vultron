"""Received case-owner decisions on an embargo proposal (ADR-0122).

``Accept(EmbargoEvent, target=Case)`` activates a proposal and
``Reject(EmbargoEvent, target=Case)`` rejects it.  Only the case owner may
send either (EP-09-005, HP-01-006); the CASE_MANAGER applies and commits the
decision, and every replica learns it from the ledger (EP-09-007).
"""

from typing import TYPE_CHECKING, ClassVar

import py_trees

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.embargo.owner_decision_tree import (
    activate_embargo_on_case_tree,
    reject_embargo_proposal_on_case_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.events.embargo import (
    ActivateEmbargoOnCaseReceivedEvent,
    RejectEmbargoProposalOnCaseReceivedEvent,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.use_cases.received.embargo._embargo_event_frame import (
    _EmbargoEventReceivedUseCase,
)


class _OwnerDecisionReceivedUseCase(_EmbargoEventReceivedUseCase):
    """Shared frame of both owner-decision handlers.

    The tree's sender guard refuses anyone but the case owner (HP-01-006).
    The activation and rejection trees emit, so both take the trigger port
    and the actor's configuration.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.CASE_OWNER
    )

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
        super().__init__(
            dl,
            request,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=wire_render_port,
        )
        self._actor_config = actor_config


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
            sender_rule=self.sender_entitlement,
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
            sender_rule=self.sender_entitlement,
        )


__all__ = [
    "ActivateEmbargoOnCaseReceivedUseCase",
    "RejectEmbargoProposalOnCaseReceivedUseCase",
]
