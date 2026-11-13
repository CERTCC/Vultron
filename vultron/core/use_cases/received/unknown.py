"""Use case for unknown/unrecognized activities."""

import logging
from typing import ClassVar

from vultron.core.behaviors.case.received_run import (
    ReceivedOutcome,
    run_received_tree,
)
from vultron.core.behaviors.dead_letter.dead_letter_tree import (
    create_store_dead_letter_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlement,
    no_sender_check,
)
from vultron.core.models.events.unknown import (
    UnknownReceivedEvent,
    UnresolvableObjectReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


class UnknownUseCase:
    """Logs a warning for any activity that could not be matched to a known
    semantic type.
    """

    # Refused for its semantics alone, whoever sent it: nothing is applied.
    sender_entitlement: ClassVar[SenderEntitlement] = no_sender_check(
        "an activity with no recognized semantics is refused whoever sent"
        " it; nothing is written, committed or sent"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: UnknownReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        # The received baseline supplies the trigger port to every use case;
        # this one runs no tree that builds an activity, so it is unused.
        del trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: UnknownReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        logger.warning("unknown use case called for event: %s", request)
        return HandlerResult.refused("unrecognized activity semantics")


class UnresolvableObjectUseCase:
    """Stores a dead-letter record for activities whose object_ URI could not
    be resolved after rehydration.

    See ``specs/semantic-extraction.yaml`` SE-04-003, SE-04-007.
    """

    # The dead-letter record is the receiver's own diagnostic, not an
    # assertion applied to any case (SE-04-007).
    sender_entitlement: ClassVar[SenderEntitlement] = no_sender_check(
        "the activity's object cannot be resolved, so it has no meaning to"
        " apply: the receiver only stores a dead-letter record for its own"
        " diagnosis, and commits, applies and sends nothing"
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: UnresolvableObjectReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request = request

    def execute(self) -> HandlerResult:
        request = self._request
        unresolvable_uri = request.object_id or ""
        logger.warning(
            "Unresolvable object_ URI '%s' in activity '%s' (actor '%s'); "
            "storing dead-letter record.",
            unresolvable_uri,
            request.activity_id,
            request.actor_id,
        )
        dead_lettered = HandlerResult.refused(
            f"unresolvable object '{unresolvable_uri}'; dead-lettered"
        )

        def read(outcome: ReceivedOutcome) -> HandlerResult | None:
            # The record is bookkeeping; the activity itself was not
            # processed (SE-04-007), so the sender sees it rejected
            # (HP-01-003).
            return dead_lettered if outcome.succeeded else None

        return run_received_tree(
            create_store_dead_letter_tree(request=request),
            dl=self._dl,
            request=request,
            label="StoreDeadLetterBT",
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            reader=read,
        )
