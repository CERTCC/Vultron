#!/usr/bin/env python
"""Vultron Actor Inbox Handler.

Dispatcher management, dispatch-prep helpers, and the main per-actor
inbox processing loop.  Port-factory wiring and pending-queue management
are provided by the focused submodules:

- :mod:`~vultron.adapters.driving.fastapi.inbox_port_factories` —
  port factory functions and semantics-set constants
- :mod:`~vultron.adapters.driving.fastapi.inbox_pending_queue` —
  pre-bootstrap pending case queue helpers
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can
#    Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol
#  Prototype is licensed under a MIT (SEI)-style license, please see
#  LICENSE.md distributed with this Software or contact
#  permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States
#  Government (see Acknowledgments file). This program may include
#  and/or can make use of certain third party source code, object code,
#  documentation and other files ("Third Party Software"). See
#  LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered
#  in the U.S. Patent and Trademark Office by Carnegie Mellon University

import logging
from typing import Any, cast

from vultron.wire.as2.rehydration import rehydrate
from vultron.core.dispatcher import get_dispatcher
from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.datalayer import ActorScopedDataLayer, DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.core.ports.emitter import ActivityEmitter
from vultron.semantic_registry import (
    extract_event,
    use_case_map as _use_case_map,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler

# Re-export port factories and semantics sets so existing callers that
# import them from this module continue to work (backward compat).
from vultron.adapters.driving.fastapi.inbox_port_factories import (  # noqa: F401
    _sync_port_factory,
    _trigger_activity_port_factory,
    _sync_and_trigger_port_factory,
    _SYNC_PORT_SEMANTICS,
    _TRIGGER_ACTIVITY_PORT_SEMANTICS,
    _SYNC_AND_TRIGGER_PORT_SEMANTICS,
)

# Re-export pending-queue helpers so existing callers and tests that
# reference them via this module continue to work (backward compat).
from vultron.adapters.driving.fastapi.inbox_pending_queue import (  # noqa: F401
    _activity_context_id,
    _queue_pending_case_activity,
    _expire_pending_case_activities,
    _replay_pending_case_activities,
)

logger = logging.getLogger(__name__)


def prepare_for_dispatch(activity: as_Activity) -> VultronEvent:
    """Extract domain event from an AS2 activity, ready for dispatch."""
    logger.debug(
        "Preparing activity '%s' of type '%s' for dispatch.",
        activity.id_,
        activity.type_,
    )
    event = extract_event(activity)
    logger.debug(
        "Prepared event with semantics '%s' for activity '%s'",
        event.semantic_type,
        event.activity_id,
    )
    return event


_DISPATCHER: ActivityDispatcher | None = None


def make_dispatcher() -> ActivityDispatcher:
    """Create and return a new inbox dispatcher without mutating any global.

    Use this in :func:`create_app` lifespans to build a per-app dispatcher
    that is stored on ``app.state.dispatcher`` instead of the module-level
    ``_DISPATCHER``.  Production code (``app_v2``) continues to call
    :func:`init_dispatcher` so the global is set for backward-compatible
    callers such as the CLI.
    """
    # Guard: the three semantics sets must be mutually disjoint.  An overlap
    # would cause a silent dict.update() overwrite — exactly the class of bug
    # that #628 introduced — so fail fast with an actionable message.
    _all_sets = (
        _SYNC_PORT_SEMANTICS,
        _TRIGGER_ACTIVITY_PORT_SEMANTICS,
        _SYNC_AND_TRIGGER_PORT_SEMANTICS,
    )
    for i, left in enumerate(_all_sets):
        for right in _all_sets[i + 1 :]:
            overlap = left & right
            if overlap:
                raise AssertionError(
                    f"Port-semantics sets overlap: {overlap!r}. "
                    "Add the semantic to _SYNC_AND_TRIGGER_PORT_SEMANTICS "
                    "and remove it from both individual sets."
                )

    port_factories: dict = {
        sem: _sync_port_factory for sem in _SYNC_PORT_SEMANTICS
    }
    port_factories.update(
        {
            sem: _trigger_activity_port_factory
            for sem in _TRIGGER_ACTIVITY_PORT_SEMANTICS
        }
    )
    port_factories.update(
        {
            sem: _sync_and_trigger_port_factory
            for sem in _SYNC_AND_TRIGGER_PORT_SEMANTICS
        }
    )
    d = get_dispatcher(
        use_case_map=_use_case_map(),
        port_factories=port_factories,
    )
    logger.debug("Created inbox dispatcher: %s", type(d).__name__)
    return d


def init_dispatcher(dl: DataLayer | None = None) -> None:
    """Initialise the module-level dispatcher.

    Must be called once during application startup (e.g. from the FastAPI
    lifespan event) before any inbox items are processed.  Calling it more
    than once (e.g. in tests) is allowed — the dispatcher is simply replaced.

    Args:
        dl: Unused; retained for backward compatibility. DataLayer is now
            passed at dispatch time via :func:`dispatch`.
    """
    global _DISPATCHER
    _DISPATCHER = make_dispatcher()
    logger.info("Initialised inbox dispatcher: %s", type(_DISPATCHER).__name__)


def dispatch(
    event: VultronEvent,
    dl: DataLayer,
    dispatcher: ActivityDispatcher | None = None,
) -> None:
    """Dispatch the given domain event.

    Uses *dispatcher* when provided; otherwise falls back to the module-level
    ``_DISPATCHER`` (set by :func:`init_dispatcher`).  Passing an explicit
    dispatcher enables per-app isolation when multiple :func:`create_app`
    instances coexist in the same process (issue #534).

    Args:
        event: The domain event to dispatch.
        dl: The DataLayer instance scoped to the current actor.
        dispatcher: Optional per-app dispatcher.  When ``None`` the
            module-level ``_DISPATCHER`` is used (backward-compatible).
    Raises:
        RuntimeError: If no dispatcher is available (neither *dispatcher*
            nor the module-level ``_DISPATCHER`` has been initialised).
    """
    _d = dispatcher or _DISPATCHER
    if _d is None:
        raise RuntimeError(
            "Inbox dispatcher not initialised. "
            "Call init_dispatcher() during application startup."
        )
    logger.debug(
        "Dispatching activity '%s' with semantics '%s'",
        event.activity_id,
        event.semantic_type,
    )
    _d.dispatch(event, dl)


def handle_inbox_item(
    actor_id: str,
    obj: as_Activity,
    dl: DataLayer,
    dispatcher: ActivityDispatcher | None = None,
) -> None:
    """Handle a single item in the Actor's inbox.

    Args:
        actor_id: The canonical URI of the Actor whose inbox is being processed.
        obj: The Activity item to process.
        dl: The DataLayer instance used for reads and dispatch.
        dispatcher: Optional per-app dispatcher.  When ``None`` the
            module-level ``_DISPATCHER`` is used (backward-compatible).
    """
    logger.info("Processing item '%s' for actor '%s'", obj.name, actor_id)
    logger.debug(
        "Validated object:\n%s",
        obj.model_dump_json(indent=2, exclude_none=True),
    )
    event = prepare_for_dispatch(activity=obj)
    event = event.model_copy(update={"receiving_actor_id": actor_id})
    dispatch(event=event, dl=dl, dispatcher=dispatcher)


def _dispatch_or_defer_inbox_item(
    actor_id: str,
    obj: as_Activity,
    dl: DataLayer,
    queue_dl: ActorScopedDataLayer,
    dispatcher: ActivityDispatcher | None = None,
) -> VultronEvent | None:
    """Dispatch an inbox item or defer it until its case replica exists.

    When deferring, first checks whether the existing pending queue for
    this case has expired.  If the queue has expired, the existing items
    are dropped, a replay ``Question`` is emitted, and the new item is
    also dropped (resend-required semantics, CBT-03-003).  If within the
    window, the item is appended to the existing queue as before.
    """
    event = prepare_for_dispatch(activity=obj)
    event = event.model_copy(update={"receiving_actor_id": actor_id})

    case_id = _activity_context_id(obj, event)
    if (
        case_id is not None
        and event.semantic_type != MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
        and not is_case_model(dl.read(case_id))
    ):
        expired = _expire_pending_case_activities(
            case_id=case_id,
            actor_id=actor_id,
            dl=dl,
            queue_dl=queue_dl,
        )
        if expired:
            logger.warning(
                "Activity '%s' for expired case queue '%s' dropped — "
                "resend required after new bootstrap",
                event.activity_id,
                case_id,
            )
            return None

        logger.warning(
            "Unknown case context '%s' for activity '%s' — queuing for replay",
            case_id,
            event.activity_id,
        )
        _queue_pending_case_activity(
            queue_dl,
            case_id,
            event.activity_id,
            case_actor_id=event.actor_id,
        )
        return None

    dispatch(event=event, dl=dl, dispatcher=dispatcher)
    return event


def _log_rehydrated_item(item: as_Activity) -> None:
    """Log summary details for a rehydrated inbox activity."""
    logger.debug("Rehydrated item from inbox: %s", item.type_)
    if not hasattr(item, "object_"):
        return

    item_with_object = cast(Any, item)
    obj_field = item_with_object.object_
    obj_type_label = (
        obj_field
        if isinstance(obj_field, str)
        else getattr(obj_field, "type_", repr(obj_field))
    )
    logger.debug("Item has transitive object of type: %s", obj_type_label)


def _process_inbox_item(
    actor_id: str,
    canonical_actor_id: str,
    item_id: str,
    item: as_Activity,
    dl: DataLayer,
    queue_dl: ActorScopedDataLayer,
    dispatcher: ActivityDispatcher | None = None,
) -> bool:
    """Dispatch one inbox activity and return ``True`` on success."""
    _log_rehydrated_item(item)

    try:
        event = _dispatch_or_defer_inbox_item(
            actor_id=canonical_actor_id,
            obj=item,
            dl=dl,
            queue_dl=queue_dl,
            dispatcher=dispatcher,
        )
        if event is not None:
            case_id = _activity_context_id(item, event)
            if (
                event.semantic_type
                == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
                and case_id is not None
            ):
                _replay_pending_case_activities(
                    case_id, dl, queue_dl, actor_id=canonical_actor_id
                )
        return True
    except Exception as e:
        logger.error(
            "Error processing inbox item for actor %s: %s", actor_id, e
        )
        logger.debug(
            "Item causing error: %s",
            item.model_dump_json(indent=2, exclude_none=True),
        )
        queue_dl.inbox_append(item_id)
        return False


async def inbox_handler(
    actor_id: str,
    dl: DataLayer,
    actor_dl: ActorScopedDataLayer | None = None,
    emitter: ActivityEmitter | None = None,
    dispatcher: ActivityDispatcher | None = None,
) -> None:
    """Process the inbox for the given actor.

    Reads pending activity IDs from the actor-scoped DataLayer inbox queue,
    rehydrates each one into a full AS2 Activity object using the shared
    DataLayer, and dispatches it.

    After processing, triggers outbox delivery for any outbound activities
    created during dispatch, using *emitter* when provided.

    Args:
        actor_id: The short ID of the Actor whose inbox is being processed.
        dl: The shared DataLayer for activity storage and use-case dispatch.
        actor_dl: The actor-scoped DataLayer for inbox queue management.
            Defaults to ``dl`` when not provided (backward-compatible).
        emitter: Optional ``ActivityEmitter`` to use for outbox delivery.
            When provided (e.g. from ``request.app.state.emitter`` in a
            multi-app deployment), outbound activities are delivered via
            this emitter instead of the module-level default.  This enables
            per-app delivery routing so that co-located actors in the same
            process can each use their own isolated emitter configuration.
        dispatcher: Optional per-app dispatcher (from
            ``request.app.state.dispatcher``).  When provided, inbox items
            are routed through this dispatcher instead of the module-level
            ``_DISPATCHER``, giving each :func:`create_app` instance its
            own fully isolated routing table (issue #534).
    """
    queue_dl: ActorScopedDataLayer = cast(
        ActorScopedDataLayer, actor_dl if actor_dl is not None else dl
    )
    actor = dl.read(actor_id)
    if actor is None:
        actor = dl.find_actor_by_short_id(actor_id)
    if actor is None:
        logger.warning("Actor %s not found in inbox_handler.", actor_id)

    # Normalise to the canonical actor URI so that handle_inbox_item can
    # inject receiving_actor_id that matches activity.to/cc fields (HP-09-001).
    canonical_actor_id = getattr(actor, "id_", None) or actor_id

    logger.info("Processing inbox for actor %s", actor_id)

    err_count = 0

    while queue_dl.inbox_list():
        item_id = queue_dl.inbox_pop()
        if item_id is None:
            break

        item = rehydrate(item_id, dl=dl)
        if not isinstance(item, as_Activity):
            logger.error(
                "Rehydrated inbox item %s is not an Activity: %s",
                item_id,
                type(item).__name__,
            )
            err_count += 1
            continue

        if not _process_inbox_item(
            actor_id=actor_id,
            canonical_actor_id=canonical_actor_id,
            item_id=item_id,
            item=item,
            dl=dl,
            queue_dl=queue_dl,
            dispatcher=dispatcher,
        ):
            err_count += 1
            if err_count > 3:
                logger.error(
                    "Too many errors processing inbox for actor %s, aborting.",
                    actor_id,
                )
                break

    # OX-1.2 / OX-03-002: trigger outbox delivery after inbox processing completes
    await outbox_handler(actor_id, queue_dl, shared_dl=dl, emitter=emitter)
