#!/usr/bin/env python
"""FastAPI adapter implementations for inbox orchestration.

Provides concrete adapter classes that implement the
:mod:`vultron.core.behaviors.inbox` protocols using the FastAPI
DataLayer and dispatcher infrastructure:

- :class:`FastAPIIngressAdapter` — parse (wire) + rehydrate (DataLayer)
- :class:`StoredActivityIngressAdapter` — rehydrate only (stored by ID)
- :class:`FastAPIDispatchAdapter` — wraps the dispatcher port
- :class:`FastAPIQueuePort` — wraps pending-case queue helpers

These adapters are constructed in the inbox background task and passed to
:func:`~vultron.core.behaviors.inbox.process_payload` (IO-03-001,
IO-03-003).
"""

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

import logging
from typing import Any, cast

from vultron.adapters.driving.fastapi.inbox_handler import dispatch
from vultron.adapters.driving.fastapi.inbox_pending_queue import (
    _expire_pending_case_activities,
    _queue_pending_case_activity,
    _replay_pending_case_activities,
)
from vultron.adapters.driving.fastapi.routers.actors._inbox import (
    _store_inbox_activity,
    _store_nested_inbox_object,
)
from vultron.core.models.events import VultronEvent
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.datalayer import ActorScopedDataLayer, DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.wire.as2.errors import VultronParseError
from vultron.wire.as2.parser import parse_activity as _parse_activity
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


def _is_inline_ledger_entry_announce(activity: as_Activity) -> bool:
    """Return True for an ``Announce`` carrying an inline ``CaseLedgerEntry``.

    Used to select the in-memory rehydration path that does not depend on the
    entry being pre-stored (SYNC-13-002/003).  Detected structurally via the
    inline object's ``type_`` so no domain import is needed here.
    """
    if getattr(activity, "type_", None) != "Announce":
        return False
    nested = getattr(activity, "object_", None)
    return getattr(nested, "type_", None) == "CaseLedgerEntry"


class FastAPIIngressAdapter:
    """Ingress adapter for the FastAPI driving adapter.

    ``parse`` parses a raw JSON request-body dict into a typed
    ``as_Activity`` and stores the activity in the shared DataLayer so
    later rehydration can resolve references.  ``rehydrate`` deep-hydrates
    the *in-memory* parsed activity's reference fields via the DataLayer.

    ``rehydrate`` intentionally hydrates the in-memory activity rather than
    re-reading it by ID from the DataLayer.  A by-ID re-read would collapse an
    inline ``object_`` to a bare ID string whenever that object was not
    pre-stored — and per SYNC-13-002 a ``CaseLedgerEntry`` is deliberately not
    pre-stored by ingress.  Carrying the typed inline object forward in-memory
    (SYNC-13-003) keeps semantic routing of ``Announce(CaseLedgerEntry)``
    unambiguous on first delivery (SYNC-13-004) without the adapter ever
    writing the ledger.

    Args:
        dl: Shared DataLayer (for storing activities and rehydration).
        body: Raw request-body dict, used to re-parse inline nested
            objects with their specific vocabulary classes.
    """

    def __init__(
        self, dl: DataLayer, body: dict[str, Any] | None = None
    ) -> None:
        self._dl = dl
        self._body = body or {}

    def parse(
        self,
        payload: dict[str, Any] | bytes | str | Any,
    ) -> as_Activity | None:
        """Parse *payload* as an AS2 activity and store to DataLayer.

        Returns ``None`` on parse failure; never raises.
        """
        if isinstance(payload, as_Activity):
            # Already parsed (e.g., passed directly from the router DI).
            _store_nested_inbox_object(self._dl, payload, self._body)
            _store_inbox_activity(self._dl, payload)
            return payload

        if not isinstance(payload, dict):
            logger.warning(
                "FastAPIIngressAdapter.parse: unsupported payload type %s",
                type(payload).__name__,
            )
            return None

        try:
            activity = _parse_activity(payload)
        except VultronParseError as exc:
            logger.warning(
                "FastAPIIngressAdapter.parse: parse failed — %s", exc
            )
            return None

        _store_nested_inbox_object(self._dl, activity, payload)
        _store_inbox_activity(self._dl, activity)
        return activity

    def rehydrate(self, activity: as_Activity) -> as_Activity:
        """Resolve nested object references for the activity.

        For most activities this re-reads the stored activity by ID through the
        canonical DataLayer pipeline (``_from_row`` → field expansion → semantic
        coercion), preserving established behavior.

        An ``Announce(CaseLedgerEntry)`` is the exception: per SYNC-13-002 the
        inline entry is deliberately NOT pre-stored, so a by-ID re-read would
        collapse ``object_`` to a bare ID string and mis-route the message
        (SYNC-13-004).  For that case the already-typed in-memory activity is
        hydrated in place (:meth:`DataLayer.hydrate` expands any scalar/list ID
        references) and returned, so routing sees the typed ``CaseLedgerEntry``
        without the adapter ever writing the ledger.
        """
        if _is_inline_ledger_entry_announce(activity):
            try:
                hydrated = self._dl.hydrate(activity)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "FastAPIIngressAdapter.rehydrate: hydrate failed (%s);"
                    " returning parsed activity unchanged.",
                    exc,
                )
                return activity
            if isinstance(hydrated, as_Activity):
                return hydrated
            return activity

        result = rehydrate(activity.id_, dl=self._dl)
        if isinstance(result, as_Activity):
            return result
        return activity


class StoredActivityIngressAdapter:
    """Ingress adapter for replay of already-stored activities.

    Used when the payload is an activity-ID string (e.g., when
    replaying activities that were deferred pending case bootstrap).

    ``parse`` reads and rehydrates the stored activity by ID.
    ``rehydrate`` is a no-op (parse already returns the rehydrated form).

    Args:
        dl: Shared DataLayer for activity lookup and rehydration.
    """

    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def parse(
        self,
        payload: dict[str, Any] | bytes | str | Any,
    ) -> as_Activity | None:
        """Read and rehydrate a stored activity by ID.

        Returns ``None`` when the ID does not resolve to an Activity.
        """
        if isinstance(payload, as_Activity):
            return payload

        activity_id = str(payload) if payload is not None else None
        if not activity_id:
            logger.warning("StoredActivityIngressAdapter.parse: empty payload")
            return None

        result = rehydrate(activity_id, dl=self._dl)
        if isinstance(result, as_Activity):
            return result

        logger.warning(
            "StoredActivityIngressAdapter.parse: rehydrate('%s') returned %s",
            activity_id,
            type(result).__name__,
        )
        return None

    def rehydrate(self, activity: as_Activity) -> as_Activity:
        """No-op: parse already returns the rehydrated activity."""
        return activity


class FastAPIDispatchAdapter:
    """Dispatch adapter wrapping the inbox dispatcher port.

    Args:
        dl: Shared DataLayer for use-case dispatch.
        actor_id: Canonical URI of the receiving actor; injected into
            the domain event before dispatch.
        dispatcher: Optional per-app dispatcher.  Falls back to the
            module-level dispatcher when ``None``.
    """

    def __init__(
        self,
        dl: DataLayer,
        actor_id: str,
        dispatcher: ActivityDispatcher | None = None,
    ) -> None:
        self._dl = dl
        self._actor_id = actor_id
        self._dispatcher = dispatcher

    def dispatch(self, event: VultronEvent) -> None:
        """Inject receiving actor ID and dispatch the event."""
        scoped_event = event.model_copy(
            update={"receiving_actor_id": self._actor_id}
        )
        dispatch(
            event=scoped_event,
            dl=self._dl,
            dispatcher=self._dispatcher,
        )


class FastAPIQueuePort:
    """Pending-case queue port wrapping the adapter-layer helpers.

    Args:
        dl: Shared DataLayer (for case reads and Question persistence).
        actor_dl: Actor-scoped DataLayer for queue management.
        actor_id: Canonical URI of the receiving actor; used when
            building a replay Question on expiry.
    """

    def __init__(
        self,
        dl: DataLayer,
        actor_dl: ActorScopedDataLayer,
        actor_id: str,
    ) -> None:
        self._dl = dl
        self._actor_dl = cast(ActorScopedDataLayer, actor_dl)
        self._actor_id = actor_id

    def is_case_known(self, case_id: str) -> bool:
        """Return ``True`` if the case replica is locally available."""
        return is_case_model(self._dl.read(case_id))

    def queue(
        self,
        activity_id: str,
        case_id: str,
        case_actor_id: str | None = None,
    ) -> None:
        """Persist *activity_id* in the deferred queue for *case_id*."""
        _queue_pending_case_activity(
            queue_dl=self._actor_dl,
            case_id=case_id,
            activity_id=activity_id,
            case_actor_id=case_actor_id,
        )

    def check_and_expire(self, case_id: str) -> bool:
        """Check expiry; drop queue and return ``True`` when expired."""
        return _expire_pending_case_activities(
            case_id=case_id,
            actor_id=self._actor_id,
            dl=self._dl,
            queue_dl=self._actor_dl,
        )

    def replay(self, case_id: str) -> None:
        """Move deferred activities for *case_id* back to the live inbox."""
        _replay_pending_case_activities(
            case_id=case_id,
            dl=self._dl,
            queue_dl=self._actor_dl,
            actor_id=self._actor_id,
        )


async def run_inbox_pipeline(
    payload: dict[str, Any] | bytes | str | Any,
    body: dict[str, Any] | None,
    dl: DataLayer,
    actor_dl: ActorScopedDataLayer,
    actor_id: str,
    dispatcher: ActivityDispatcher | None,
    emitter: Any,
) -> None:
    """Adapter-layer background task: construct adapters and run pipeline.

    Calls :func:`~vultron.core.behaviors.inbox.process_payload` for the
    immediate payload, then processes any replayed activities that were
    pushed back to the inbox queue (e.g., after bootstrap dispatch), and
    finally drains the outbox.

    This function is the background task scheduled by ``post_actor_inbox``.
    It is the ONLY place that constructs the adapter instances, satisfying
    IO-03-003.

    Args:
        payload: Raw inbox payload (JSON body dict or as_Activity).
        body: Raw JSON request body dict, forwarded from the endpoint for
            nested-object re-parsing (preserves domain-specific fields).
        dl: Shared DataLayer.
        actor_dl: Actor-scoped DataLayer for inbox/outbox queues.
        actor_id: Canonical URI of the receiving actor.
        dispatcher: Optional per-app dispatcher.
        emitter: Optional per-app ActivityEmitter.
    """
    from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
    from vultron.core.behaviors.inbox import process_payload

    ingress = FastAPIIngressAdapter(dl=dl, body=body)
    dispatch_adp = FastAPIDispatchAdapter(
        dl=dl, actor_id=actor_id, dispatcher=dispatcher
    )
    queue = FastAPIQueuePort(
        dl=dl,
        actor_dl=cast(ActorScopedDataLayer, actor_dl),
        actor_id=actor_id,
    )

    outcome = process_payload(payload, ingress, dispatch_adp, queue)
    logger.info(
        "run_inbox_pipeline: status=%s context_id=%s",
        outcome.status,
        outcome.context_id,
    )

    # Process any replayed activities (pushed back to the queue by
    # DeferCheckNode/DispatchNode replay after bootstrap).
    stored_ingress = StoredActivityIngressAdapter(dl=dl)
    while actor_dl.inbox_list():
        item_id = actor_dl.inbox_pop()
        if item_id is None:
            break
        replay_outcome = process_payload(
            item_id, stored_ingress, dispatch_adp, queue
        )
        logger.info(
            "run_inbox_pipeline: replayed status=%s context_id=%s",
            replay_outcome.status,
            replay_outcome.context_id,
        )

    await outbox_handler(actor_id, actor_dl, shared_dl=dl, emitter=emitter)
