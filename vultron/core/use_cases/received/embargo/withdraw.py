"""Received ``Leave(EmbargoEvent)``: a signatory's withdrawal (MSM-07-010).

A participant whose consent row for the embargo in force is ``AGREED`` ends
its own consent by sending ``Leave(EmbargoEvent)[context=VulnerabilityCase]``
to the CASE_MANAGER (EP-09-013, ADR-0122).  The CASE_MANAGER declines that
row and every open proposal's row the sender had agreed to, commits the
withdrawal and changes no register entry; every replica learns it from the
ledger (EP-09-007).
"""

from typing import TYPE_CHECKING, ClassVar

import py_trees

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.embargo.withdrawal_tree import (
    withdraw_from_embargo_on_case_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.events.embargo import (
    WithdrawFromEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.use_cases.received._bt_verdict import (
    embargo_withdrawal_redelivery_verdict,
)
from vultron.core.use_cases.received.embargo._embargo_event_frame import (
    _EmbargoEventReceivedUseCase,
)


class WithdrawFromEmbargoOnCaseReceivedUseCase(_EmbargoEventReceivedUseCase):
    """The received ``Leave(EmbargoEvent)`` (MSM-07-010).

    The sender must hold a participant record on the case (``PARTICIPANT``):
    standing to withdraw is a signatory's, and the tree's guard decides it,
    refusing with the reason a Leave of an embargo not in force, from a row
    that is not ``AGREED``, or from the case owner (MSM-07-010).  The rule is
    not ``ACTIVE_PARTICIPANT``, which already requires that ``AGREED`` row
    (CM-10-004): it would turn each of those reasons into "not active", and a
    redelivered Leave, whose sender the first delivery made inactive, into a
    refusal.  A redelivery of a Leave already
    ledgered is a benign no-op, reported ``SKIPPED`` (HP-01-003).  Only the
    CASE_MANAGER records the withdrawal, so a receiver whose gate turns it
    away reports a refusal (BT-17-001).
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.PARTICIPANT
    )
    _label = "Leave(EmbargoEvent)"
    _tree_label = "WithdrawFromEmbargoOnCaseBT"

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: WithdrawFromEmbargoOnCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        super().__init__(
            dl,
            request,
            sync_port=sync_port,
            wire_render_port=wire_render_port,
        )

    def _build_tree(
        self, case_id: str, embargo_id: str, sender_actor_id: str
    ) -> py_trees.behaviour.Behaviour:
        return withdraw_from_embargo_on_case_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            withdrawing_actor_id=sender_actor_id,
            activity_id=self._request.activity_id,
            sender_rule=self.sender_entitlement,
        )

    def _refine_verdict(
        self, tree: py_trees.behaviour.Behaviour, verdict: HandlerResult
    ) -> HandlerResult:
        return embargo_withdrawal_redelivery_verdict(tree, verdict)

    def _applied_message(self, embargo_id: str, case_id: str) -> str:
        return (
            f"'{self._request.actor_id}' withdrew from embargo"
            f" '{embargo_id}' on case '{case_id}'"
        )


__all__ = ["WithdrawFromEmbargoOnCaseReceivedUseCase"]
