"""Use case for unknown/unrecognized activities."""

import logging

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.events.unknown import (
    UnknownReceivedEvent,
    UnresolvableObjectReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import (
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import verdict_from_bt

logger = logging.getLogger(__name__)


class UnknownUseCase:
    """Logs a warning for any activity that could not be matched to a known
    semantic type.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: UnknownReceivedEvent,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: UnknownReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        logger.warning("unknown use case called for event: %s", request)
        return HandlerResult.refused("unrecognized activity semantics")


class UnresolvableObjectUseCase:
    """Stores a dead-letter record for activities whose object_ URI could not
    be resolved after rehydration.

    See ``specs/semantic-extraction.yaml`` SE-04-002, SE-04-003.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: UnresolvableObjectReceivedEvent,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request = request

    def execute(self) -> HandlerResult:
        # Cycle break: dead_letter_tree -> inbox pipeline nodes -> semantic
        # registry -> this module.
        from vultron.core.behaviors.inbox.dead_letter_tree import (  # noqa: PLC0415  # ruff-baseline #3950
            create_store_dead_letter_tree,
        )

        request = self._request
        unresolvable_uri = request.object_id or ""
        logger.warning(
            "Unresolvable object_ URI '%s' in activity '%s' (actor '%s'); "
            "storing dead-letter record.",
            unresolvable_uri,
            request.activity_id,
            request.actor_id,
        )
        tree = create_store_dead_letter_tree(request=request)
        bridge = BTBridge(
            datalayer=self._dl, wire_render_port=self._wire_render_port
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
        verdict = verdict_from_bt(tree, result, label="StoreDeadLetterBT")
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "StoreDeadLetterBT did not store a record for activity '%s':"
                " %s",
                request.activity_id,
                verdict.reason,
            )
            return verdict
        # The record is bookkeeping; the activity itself was not processed
        # (SE-04-002), so the sender sees it rejected (HP-01-003).
        return HandlerResult.refused(
            f"unresolvable object '{unresolvable_uri}'; dead-lettered"
        )
