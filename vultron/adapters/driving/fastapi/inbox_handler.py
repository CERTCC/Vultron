#!/usr/bin/env python
"""
Vultron Actor Inbox Handler
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import logging
from typing import Any, cast

from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.wire.as2.rehydration import rehydrate
from vultron.core.dispatcher import get_dispatcher
from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.semantic_registry import (
    extract_event,
    use_case_map as _use_case_map,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler

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


def _sync_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create a ``SyncActivityAdapter`` from the current DataLayer."""
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )

    return {"sync_port": SyncActivityAdapter(dl)}


def _trigger_activity_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create a ``TriggerActivityAdapter`` from the current DataLayer."""
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    return {"trigger_activity": TriggerActivityAdapter(dl)}


_SYNC_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ANNOUNCE_CASE_LOG_ENTRY,
        MessageSemantics.REJECT_CASE_LOG_ENTRY,
    }
)

_TRIGGER_ACTIVITY_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ACCEPT_CASE_MANAGER_ROLE,
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        MessageSemantics.OFFER_CASE_MANAGER_ROLE,
        MessageSemantics.SUBMIT_REPORT,
        MessageSemantics.SUGGEST_ACTOR_TO_CASE,
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
    }
)


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
    port_factories = {sem: _sync_port_factory for sem in _SYNC_PORT_SEMANTICS}
    port_factories.update(
        {
            sem: _trigger_activity_port_factory
            for sem in _TRIGGER_ACTIVITY_PORT_SEMANTICS
        }
    )
    _DISPATCHER = get_dispatcher(
        use_case_map=_use_case_map(),
        port_factories=port_factories,
    )
    logger.info("Initialised inbox dispatcher: %s", type(_DISPATCHER).__name__)


def dispatch(event: VultronEvent, dl: DataLayer) -> None:
    """Dispatch the given domain event using the module-level dispatcher.

    Args:
        event: The domain event to dispatch.
        dl: The DataLayer instance scoped to the current actor.
    Raises:
        RuntimeError: If the dispatcher has not been initialised via
            :func:`init_dispatcher`.
    """
    if _DISPATCHER is None:
        raise RuntimeError(
            "Inbox dispatcher not initialised. "
            "Call init_dispatcher() during application startup."
        )
    logger.debug(
        "Dispatching activity '%s' with semantics '%s'",
        event.activity_id,
        event.semantic_type,
    )
    _DISPATCHER.dispatch(event, dl)


def handle_inbox_item(actor_id: str, obj: as_Activity, dl: DataLayer) -> None:
    """Handle a single item in the Actor's inbox.

    Args:
        actor_id: The canonical URI of the Actor whose inbox is being processed.
        obj: The Activity item to process.
        dl: The DataLayer instance used for reads and dispatch.
    """
    logger.info("Processing item '%s' for actor '%s'", obj.name, actor_id)
    logger.debug(
        "Validated object:\n%s",
        obj.model_dump_json(indent=2, exclude_none=True),
    )
    event = prepare_for_dispatch(activity=obj)
    event = event.model_copy(update={"receiving_actor_id": actor_id})
    dispatch(event=event, dl=dl)


def _activity_context_id(
    activity: as_Activity, event: VultronEvent
) -> str | None:
    """Return the case context ID carried by an activity, if any."""
    if event.context_id is not None:
        return event.context_id
    context = getattr(activity, "context", None)
    if isinstance(context, str) and context:
        return context
    return getattr(context, "id_", None)


def _queue_pending_case_activity(
    queue_dl: DataLayer, case_id: str, activity_id: str
) -> None:
    """Persist *activity_id* in the deferred queue for *case_id*."""
    pending_id = VultronPendingCaseInbox.build_id(case_id)
    pending = queue_dl.read(pending_id)
    if isinstance(pending, VultronPendingCaseInbox):
        if activity_id in pending.activity_ids:
            return
        pending.activity_ids.append(activity_id)
        queue_dl.save(pending)
        return

    queue_dl.save(
        VultronPendingCaseInbox(case_id=case_id, activity_ids=[activity_id])
    )


def _replay_pending_case_activities(
    case_id: str, dl: DataLayer, queue_dl: DataLayer
) -> None:
    """Move deferred activities for *case_id* back onto the live inbox queue."""
    if not is_case_model(dl.read(case_id)):
        return

    pending_id = VultronPendingCaseInbox.build_id(case_id)
    pending = queue_dl.read(pending_id)
    if not isinstance(pending, VultronPendingCaseInbox):
        return

    for activity_id in pending.activity_ids:
        queue_dl.inbox_append(activity_id)
    queue_dl.delete("PendingCaseInbox", pending_id)
    logger.info(
        "Queued %d deferred inbox activities for case '%s' after replica sync",
        len(pending.activity_ids),
        case_id,
    )


def _dispatch_or_defer_inbox_item(
    actor_id: str,
    obj: as_Activity,
    dl: DataLayer,
    queue_dl: DataLayer,
) -> VultronEvent | None:
    """Dispatch an inbox item or defer it until its case replica exists."""
    event = prepare_for_dispatch(activity=obj)
    event = event.model_copy(update={"receiving_actor_id": actor_id})

    case_id = _activity_context_id(obj, event)
    if (
        case_id is not None
        and event.semantic_type != MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
        and not is_case_model(dl.read(case_id))
    ):
        logger.warning(
            "Unknown case context '%s' for activity '%s' — queuing for replay",
            case_id,
            event.activity_id,
        )
        _queue_pending_case_activity(queue_dl, case_id, event.activity_id)
        return None

    dispatch(event=event, dl=dl)
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
    queue_dl: DataLayer,
) -> bool:
    """Dispatch one inbox activity and return ``True`` on success."""
    _log_rehydrated_item(item)

    try:
        event = _dispatch_or_defer_inbox_item(
            actor_id=canonical_actor_id,
            obj=item,
            dl=dl,
            queue_dl=queue_dl,
        )
        if event is not None:
            case_id = _activity_context_id(item, event)
            if (
                event.semantic_type
                == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
                and case_id is not None
            ):
                _replay_pending_case_activities(case_id, dl, queue_dl)
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
    actor_id: str, dl: DataLayer, actor_dl: DataLayer | None = None
) -> None:
    """Process the inbox for the given actor.

    Reads pending activity IDs from the actor-scoped DataLayer inbox queue,
    rehydrates each one into a full AS2 Activity object using the shared
    DataLayer, and dispatches it.

    Args:
        actor_id: The short ID of the Actor whose inbox is being processed.
        dl: The shared DataLayer for activity storage and use-case dispatch.
        actor_dl: The actor-scoped DataLayer for inbox queue management.
            Defaults to ``dl`` when not provided (backward-compatible).
    """
    queue_dl = actor_dl if actor_dl is not None else dl
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
        ):
            err_count += 1
            if err_count > 3:
                logger.error(
                    "Too many errors processing inbox for actor %s, aborting.",
                    actor_id,
                )
                break

    # OX-1.2 / OX-03-002: trigger outbox delivery after inbox processing completes
    await outbox_handler(actor_id, queue_dl, shared_dl=dl)
