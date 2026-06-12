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
from datetime import timezone
from typing import Any, cast

from vultron.config import get_config
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.wire.as2.factories.case import bootstrap_replay_question_activity
from vultron.wire.as2.rehydration import rehydrate
from vultron.core.dispatcher import get_dispatcher
from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.datalayer import ActorScopedDataLayer, DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.core.ports.emitter import ActivityEmitter
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
    """Create a ``SyncActivityAdapter`` from the current DataLayer.

    ``dl`` at runtime is an ``ActorScopedDataLayer`` (satisfies
    ``CaseOutboxPersistence``) — the cast is safe (ARCH-13-002).
    """
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )

    return {"sync_port": SyncActivityAdapter(cast(CaseOutboxPersistence, dl))}


def _trigger_activity_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create a ``TriggerActivityAdapter`` from the current DataLayer.

    ``dl`` at runtime is an ``ActorScopedDataLayer`` (satisfies
    ``CaseOutboxPersistence``) — the cast is safe (ARCH-13-002).
    """
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    return {
        "trigger_activity": TriggerActivityAdapter(
            cast(CaseOutboxPersistence, dl)
        )
    }


def _sync_and_trigger_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create both a ``SyncActivityAdapter`` and a ``TriggerActivityAdapter``.

    Used for semantics that require both ports — specifically
    ``ADD_PARTICIPANT_STATUS_TO_PARTICIPANT``, which must sync the log entry to
    participants *and* trigger the downstream participant-status activity.
    """
    return {**_sync_port_factory(dl), **_trigger_activity_port_factory(dl)}


_SYNC_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE,
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY,
        MessageSemantics.CREATE_EMBARGO_EVENT,
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.REJECT_CASE_LEDGER_ENTRY,
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
    }
)

_TRIGGER_ACTIVITY_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ACCEPT_CASE_MANAGER_ROLE,
        MessageSemantics.DEFER_CASE,
        MessageSemantics.ENGAGE_CASE,
        MessageSemantics.OFFER_CASE_MANAGER_ROLE,
        MessageSemantics.SUBMIT_REPORT,
        MessageSemantics.SUGGEST_ACTOR_TO_CASE,
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        MessageSemantics.VALIDATE_REPORT,
    }
)

# Semantics that require both a sync port and a trigger-activity port.
_SYNC_AND_TRIGGER_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ADD_NOTE_TO_CASE,
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
    }
)


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
    queue_dl: DataLayer,
    case_id: str,
    activity_id: str,
    case_actor_id: str | None = None,
) -> None:
    """Persist *activity_id* in the deferred queue for *case_id*.

    Records *case_actor_id* on the first write so that the expiry handler
    knows where to send a replay ``Question`` (CBT-03-004).
    """
    pending_id = VultronPendingCaseInbox.build_id(case_id)
    pending = queue_dl.read(pending_id)
    if isinstance(pending, VultronPendingCaseInbox):
        if activity_id in pending.activity_ids:
            return
        pending.activity_ids.append(activity_id)
        queue_dl.save(pending)
        return

    queue_dl.save(
        VultronPendingCaseInbox(
            case_id=case_id,
            activity_ids=[activity_id],
            case_actor_id=case_actor_id,
        )
    )


def _expire_pending_case_activities(
    case_id: str,
    actor_id: str,
    dl: DataLayer,
    queue_dl: ActorScopedDataLayer,
    timeout_seconds: int | None = None,
) -> bool:
    """Drop an expired pre-bootstrap queue and emit a replay ``Question``.

    Checks whether the ``VultronPendingCaseInbox`` for *case_id* has been
    held for longer than *timeout_seconds* (defaults to
    ``AppConfig.pre_bootstrap_queue_timeout_seconds``).  When expired:

    1. Logs a WARNING for each dropped activity ID (CBT-03-003).
    2. Deletes the queue record.
    3. Emits a ``Question`` to the recorded ``case_actor_id`` asking for
       the bootstrap ``Create(VulnerabilityCase)`` to be resent
       (CBT-03-004, SHOULD).

    Args:
        case_id: URI of the case whose pending queue should be checked.
        actor_id: Canonical URI of the receiving actor (Question sender).
        dl: Shared DataLayer used to save the outbound Question.
        queue_dl: Actor-scoped DataLayer used to read/delete the queue
            and enqueue the outbound Question.
        timeout_seconds: Expiry window in seconds.  ``None`` reads from
            ``get_config().pre_bootstrap_queue_timeout_seconds``.

    Returns:
        ``True`` if the queue was expired and dropped; ``False`` if the
        queue is still within the window or does not exist.

    Trigger: this check is called on inbox receipt so that any inbound
    activity for a pending case triggers expiry cleanup (AC-4).  Cold
    queues (no subsequent traffic) are reclaimed when bootstrap or a new
    activity arrives.
    """
    from datetime import datetime

    if timeout_seconds is None:
        timeout_seconds = get_config().pre_bootstrap_queue_timeout_seconds

    pending_id = VultronPendingCaseInbox.build_id(case_id)
    pending = queue_dl.read(pending_id)
    if not isinstance(pending, VultronPendingCaseInbox):
        return False

    now = datetime.now(timezone.utc)
    queued_at = pending.queued_at
    if queued_at.tzinfo is None:
        queued_at = queued_at.replace(tzinfo=timezone.utc)
    age_seconds = (now - queued_at).total_seconds()
    if age_seconds < timeout_seconds:
        return False

    for activity_id in pending.activity_ids:
        logger.warning(
            "Dropping expired pre-bootstrap activity '%s' for case '%s' "
            "(age %.0fs > timeout %ds) — resend required after bootstrap "
            "(CBT-03-003)",
            activity_id,
            case_id,
            age_seconds,
            timeout_seconds,
        )
    queue_dl.delete("PendingCaseInbox", pending_id)
    logger.warning(
        "Pre-bootstrap queue for case '%s' expired after %.0fs; "
        "%d activity ID(s) dropped",
        case_id,
        age_seconds,
        len(pending.activity_ids),
    )

    if pending.case_actor_id:
        try:
            question = bootstrap_replay_question_activity(
                actor=actor_id,
                to=pending.case_actor_id,
                case_id=case_id,
            )
            dl.save(question)
            queue_dl.outbox_append(question.id_)
            logger.info(
                "Sent bootstrap replay Question '%s' to '%s' for case '%s'",
                question.id_,
                pending.case_actor_id,
                case_id,
            )
        except Exception:
            logger.warning(
                "Could not construct replay Question for case '%s'; "
                "manual intervention required (CBT-03-004)",
                case_id,
                exc_info=True,
            )
    else:
        logger.warning(
            "No case_actor_id recorded for case '%s'; "
            "cannot send replay Question (CBT-03-004)",
            case_id,
        )

    return True


def _replay_pending_case_activities(
    case_id: str,
    dl: DataLayer,
    queue_dl: ActorScopedDataLayer,
    actor_id: str | None = None,
) -> None:
    """Move deferred activities for *case_id* back onto the live inbox queue.

    Before replaying, checks whether the pending queue has expired.  If it
    has, the queue is dropped instead of replayed (CBT-03-003).  This
    handles the case where bootstrap arrives after the expiry window — the
    bootstrap itself is accepted, but the stale queued items are discarded.

    Args:
        case_id: URI of the case whose pending queue should be drained.
        dl: Shared DataLayer used for case lookup and Question persistence.
        queue_dl: Actor-scoped DataLayer for queue management.
        actor_id: Canonical URI of the receiving actor, used when building
            a replay Question on expiry.  Defaults to ``""`` when not
            provided (best-effort; expiry Warning is still logged).
    """
    if not is_case_model(dl.read(case_id)):
        return

    pending_id = VultronPendingCaseInbox.build_id(case_id)
    pending = queue_dl.read(pending_id)
    if not isinstance(pending, VultronPendingCaseInbox):
        return

    if _expire_pending_case_activities(
        case_id=case_id,
        actor_id=actor_id or "",
        dl=dl,
        queue_dl=queue_dl,
    ):
        logger.warning(
            "Bootstrap arrived for case '%s' but pre-bootstrap queue had "
            "already expired; dropped %d activity ID(s) — a fresh "
            "re-delivery is required",
            case_id,
            len(pending.activity_ids),
        )
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
