#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Received use case for the CASE_MANAGER's refusal notice (CLP-05-001, ADR-0141).

The notice is a ``Reject`` of an activity this actor sent; the participant
closes the pending assertion it recorded for it (CLP-06-006).
"""

from typing import ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.refusal_notice import (
    ClearRefusedAssertionNode,
    ResumeOutboundSequenceNode,
)
from vultron.core.behaviors.case.refusal_notice_received_tree import (
    refusal_notice_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
    any_of,
)
from vultron.core.models.events.fault import (
    RefusalNoticeReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    find_node,
    verdict_from_bt,
)


class RefusalNoticeReceivedUseCase:
    """Read the CASE_MANAGER's refusal notice for an activity this actor sent.

    The notice is a ``Reject`` of the refused activity, inline (CLP-05-001,
    ADR-0141).  Only the case's CASE_MANAGER sends one, so any other sender,
    and any notice reaching the CASE_MANAGER itself, is refused (HP-01-006).
    From the CASE_MANAGER, the participant closes the pending assertion it
    recorded for the refused activity (CLP-06-006) and logs the refusal at
    WARNING; it writes no case state and re-sends nothing (CLP-06-005).

    ``APPLIED`` when a pending entry was closed; ``SKIPPED`` when none was
    pending (timed out, or never recorded), since nothing changes.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule(
        at_participant=any_of(SenderEntitlementKind.CASE_MANAGER)
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: RefusalNoticeReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._sync_port = sync_port
        self._wire_render_port = wire_render_port
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        tree = refusal_notice_received_tree(
            case_id=request.case_id,
            refused_activity_id=request.refused_activity_id,
            reason=request.reason,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
            expected_sender_sequence=request.expected_sender_sequence,
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
        verdict = verdict_from_bt(
            tree, result, label="RefusalNoticeReceivedBT"
        )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            return verdict
        clear = find_node(tree, ClearRefusedAssertionNode)
        if clear is not None and clear.cleared:
            return verdict
        resume = find_node(tree, ResumeOutboundSequenceNode)
        if resume is not None and resume.moved:
            return verdict
        return HandlerResult.skipped(
            f"refusal notice for '{request.refused_activity_id}': no pending"
            " assertion to close and no sender sequence to resume"
        )
