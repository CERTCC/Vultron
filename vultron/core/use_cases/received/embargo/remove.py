"""Received Remove of an ``EmbargoEvent``.

This implementation does not support a received ``Create(EmbargoEvent)``:
the proposal's ``Invite`` carries the event inline.

The case owner's activation of an embargo is
``Accept(EmbargoEvent, target=Case)`` (:mod:`.owner_decision`, ADR-0122);
there is no direct activation by ``Add``.
"""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    remove_embargo_from_case_tree,
)
from vultron.core.models.events.embargo import (
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    addressee_refusal,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)

logger = logging.getLogger(__name__)


class RemoveEmbargoEventFromCaseReceivedUseCase:
    # The Case Owner decides the embargo (EP-09-005) and asks the
    # CASE_MANAGER, which also acts on its own Remove (a delegated
    # termination); a participant takes the change from the CASE_MANAGER
    # alone (PCR-03-001).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.CASE_MANAGER, SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RemoveEmbargoEventFromCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: RemoveEmbargoEventFromCaseReceivedEvent = request
        self._sync_port = sync_port
        # The CASE_MANAGER re-issues outstanding stub Invites when the active
        # embargo changes (CM-11-016) and sends the embargo-ending notices to
        # the bound signatories the ledger no longer reaches (CM-31-009), so
        # it must be able to emit.
        self._trigger_activity = trigger_activity
        self._actor_config = actor_config

    def execute(self) -> HandlerResult:
        request = self._request
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        embargo_id = request.embargo_id
        case_id = request.case_id
        if embargo_id is None or case_id is None:
            logger.warning(
                "remove_embargo_from_case: missing embargo_id or case_id"
            )
            return HandlerResult.refused(
                "Remove(EmbargoEvent) is missing its embargo id or case id"
            )

        # One tree: its door guards refuse a closed case, an unaddressed
        # copy (HP-01-005, ADR-0118) and a sender without standing first.
        # The tree embeds the guarded commit as its final step (ADR-0021,
        # CLP-10-002, CLP-10-003).  Running it with actor_id=receiving_actor_id
        # means CheckIsCaseManagerNode naturally fires only when the receiving
        # actor holds the CASE_MANAGER role — no identity comparison in Python.
        tree = remove_embargo_from_case_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            sender_actor_id=request.actor_id,
            termination_reason=request.termination_reason,
            terminated_at=(
                request.activity.published
                if request.activity is not None
                else None
            ),
            actor_config=self._actor_config,
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
            actor_id=receiving_actor_id,
            activity=request,
        )

        verdict = verdict_from_bt(
            tree, result, label="RemoveEmbargoFromCaseBT"
        )
        if (refusal := addressee_refusal(tree)) is not None:
            verdict = refusal
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict
