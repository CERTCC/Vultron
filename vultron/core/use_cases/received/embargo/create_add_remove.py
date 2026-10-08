"""Received Create, Add and Remove of an ``EmbargoEvent``."""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    add_embargo_to_case_tree,
    remove_embargo_from_case_tree,
)
from vultron.core.models.events.embargo import (
    AddEmbargoEventToCaseReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
    unaddressed_copy_refusal,
)
from vultron.core.use_cases.received._bt_verdict import (
    verdict_from_bt,
)
from vultron.core.use_cases.received._sender_preflight import sender_refusal
from vultron.core.use_cases.received._store_only import (
    run_store_only,
    store_only_verdict,
)

if TYPE_CHECKING:
    from vultron.config.actor import ActorConfig
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    SenderEntitlementKind,
    SenderMayAssertEmbargoNode,
)

logger = logging.getLogger(__name__)


class CreateEmbargoEventReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateEmbargoEventReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: CreateEmbargoEventReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        # Door check before any tree or write: an unaddressed copy is
        # refused (HP-01-005, ADR-0118).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id, request, label="Create(EmbargoEvent)"
            )
        ) is not None:
            return refusal
        # The store-only tree carries no sender guard, so it runs ahead of the
        # write: the Case Owner at the CASE_MANAGER, the CASE_MANAGER at any
        # other replica (EP-09-005, PCR-03-001, ADR-0115).
        if (
            refusal := sender_refusal(
                self._dl,
                receiving_actor_id,
                SenderMayAssertEmbargoNode(
                    case_id=request.context_id,
                    sender_actor_id=request.actor_id,
                    manager_arm=SenderEntitlementKind.CASE_OWNER,
                ),
                label="Create(EmbargoEvent)",
                sync_port=self._sync_port,
            )
        ) is not None:
            return refusal
        tree, result = run_store_only(
            self._dl,
            request,
            name="CreateEmbargoEventReceivedBT",
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            store_node=StoreReceivedObjectNode(
                request.object_type,
                request.embargo_id,
                request.embargo,
                "EmbargoEvent",
                request.activity_id,
            ),
        )
        return store_only_verdict(
            tree, result, label="CreateEmbargoEventReceivedBT"
        )


class AddEmbargoEventToCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddEmbargoEventToCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        actor_config: "ActorConfig | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AddEmbargoEventToCaseReceivedEvent = request
        self._sync_port = sync_port
        # The CASE_MANAGER re-issues outstanding stub Invites when the active
        # embargo changes (CM-11-016), so it must be able to emit.
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
                "add_embargo_event_to_case: missing embargo_id or case_id"
            )
            return HandlerResult.refused(
                "Add(EmbargoEvent) is missing its embargo id or case id"
            )

        # Door check before any tree or write, after the shape checks
        # that write nothing: an unaddressed copy is refused (HP-01-005,
        # ADR-0118).
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id, request, label="Add(EmbargoEvent)"
            )
        ) is not None:
            return refusal

        tree = add_embargo_to_case_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            sender_actor_id=request.actor_id,
            actor_config=self._actor_config,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            # The commit fans the entry out to every participant replica
            # (EP-09-007, RSH-08-004); without the port nothing replays it.
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=receiving_actor_id,
            activity=request,
        )

        verdict = verdict_from_bt(tree, result, label="AddEmbargoToCaseBT")
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict


class RemoveEmbargoEventFromCaseReceivedUseCase:
    sender_entitlement: ClassVar[SenderEntitlement] = (
        SenderEntitlementKind.CASE_OWNER
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
        # embargo changes (CM-11-016), so it must be able to emit.
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

        # Door check before any tree or write, after the shape checks
        # that write nothing: an unaddressed copy is refused (HP-01-005,
        # ADR-0118).
        if (
            refusal := unaddressed_copy_refusal(
                receiving_actor_id, request, label="Remove(EmbargoEvent)"
            )
        ) is not None:
            return refusal

        # The tree embeds the guarded commit as its final step (ADR-0021,
        # CLP-10-002, CLP-10-003).  Running it with actor_id=receiving_actor_id
        # means CheckIsCaseManagerNode naturally fires only when the receiving
        # actor holds the CASE_MANAGER role — no identity comparison in Python.
        tree = remove_embargo_from_case_tree(
            case_id=case_id,
            embargo_id=embargo_id,
            sender_actor_id=request.actor_id,
            actor_config=self._actor_config,
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
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict
