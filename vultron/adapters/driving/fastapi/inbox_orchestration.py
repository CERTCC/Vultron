#!/usr/bin/env python
"""FastAPI adapter implementations for inbox orchestration.

Provides concrete adapter classes that implement the
:mod:`vultron.core.behaviors.inbox` protocols using the FastAPI
DataLayer and dispatcher infrastructure:

- :class:`FastAPIIngressAdapter` — parse (wire) + rehydrate (staged)
- :class:`FastAPIDispatchAdapter` — wraps the dispatcher port
- :class:`FastAPIQueuePort` — wraps pending-case queue helpers

The replay of the inbox queue, with its bounded retry and dead letter, and
its ``StoredActivityIngressAdapter`` live in
:mod:`~vultron.adapters.driving.fastapi.inbox_replay` (IE-06-004).

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

import asyncio
import logging
from typing import Any, cast

from vultron.adapters.driving.fastapi import inbox_port_factories
from vultron.adapters.driving.fastapi.inbox_handler import (
    dispatch,
    emit_processing_fault,
)
from vultron.adapters.driving.fastapi.inbox_pending_queue import (
    _expire_pending_case_activities,
    _queue_pending_case_activity,
    _replay_pending_case_activities,
)
from vultron.adapters.driving.fastapi.inbox_replay import (
    drain_inbox_queue,
    warn_if_rejected,
)
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.config import get_config
from vultron.core.behaviors.inbox import process_payload
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import VultronEvent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.errors import VultronWiringError
from vultron.wire.as2.errors import VultronParseError
from vultron.wire.as2.parser import parse_activity as _parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)

# Per-actor asyncio locks that serialise concurrent inbox background tasks.
# When multiple HTTP POSTs arrive for the same actor simultaneously, each
# creates a separate asyncio Task (BackgroundTask).  Without serialisation,
# the second task's process_payload can run before the first has stored its
# ledger entry, causing a hash-chain mismatch → spurious Reject → Replay loop
# that may not converge within the demo timeout (issue #1525).
_actor_inbox_locks: dict[str, asyncio.Lock] = {}


def _get_actor_lock(actor_id: str) -> asyncio.Lock:
    """Return the per-actor asyncio.Lock for *actor_id*, creating it on first use."""
    if actor_id not in _actor_inbox_locks:
        _actor_inbox_locks[actor_id] = asyncio.Lock()
    return _actor_inbox_locks[actor_id]


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


def _carry_received_evidence(
    artifact: as_Activity, routing_copy: as_Activity
) -> as_Activity:
    """Give the hydrated routing copy (B) its artifact's (A) received evidence.

    The rebuild reads B back through the store's read pipeline, which never
    keeps the body, so without this the evidence sealed at parse would stop at
    the first pipeline step and core would only ever see the rebuilt form
    (VM-08-002, ISSUE-3584).
    The evidence is the artifact's; B only carries it, which is why the text is
    copied rather than re-derived from B.
    """
    evidence = artifact.received_evidence_json
    if evidence is not None:
        routing_copy.seal_received_evidence(evidence)
    return routing_copy


class FastAPIIngressAdapter:
    """Ingress adapter for the FastAPI driving adapter.

    ``parse`` parses a raw JSON request-body dict into a typed
    ``as_Activity``.  It writes nothing to the receiving actor's DataLayer
    (ADR-0073: the ``dl`` handed in is already one actor's own): not the
    activity, which the receiver never holds under the id its sender chose
    (DL-06-006), and not the objects it carries inline, from which only the
    handler, after its guards, writes a record (CLP-10-017, #3763).  Intake
    archives the activity under the receiver's key once it is routed.

    ``rehydrate`` rebuilds the parsed activity with it and its inline objects
    staged in a throwaway store (:mod:`.inbox_staging`).  A redelivery is
    detected there, from what the receiver holds under a key it derives from
    the activity id (IE-10-001): the deferred record when the first delivery
    is still waiting on its case, else intake's ``ReceivedActivityRecord``.

    Args:
        dl: The receiving actor's own DataLayer, read to rebuild the activity.
        staging: The inbox run's inline-object staging, shared with its queue
            port so a deferred delivery is held whole for replay.
    """

    def __init__(
        self, dl: DataLayer, staging: InlineObjectStaging | None = None
    ) -> None:
        self._dl = dl
        self._staging = staging or InlineObjectStaging(dl)

    def parse(
        self,
        payload: dict[str, Any] | bytes | str | Any,
    ) -> as_Activity | None:
        """Parse *payload* as an AS2 activity, writing nothing.

        Returns ``None`` on parse failure; never raises.
        """
        if isinstance(payload, as_Activity):
            # Already parsed (e.g., passed directly from the router DI).
            return payload

        if not isinstance(payload, dict):
            logger.warning(
                "FastAPIIngressAdapter.parse: unsupported payload type %s",
                type(payload).__name__,
            )
            return None

        try:
            return _parse_activity(payload)
        except VultronParseError as exc:
            logger.warning(
                "FastAPIIngressAdapter.parse: parse failed — %s", exc
            )
            return None

    def rehydrate(self, activity: as_Activity) -> as_Activity:
        """Resolve nested object references for the activity.

        For most activities this stages the parsed activity's row and its
        inline objects in a throwaway store and reads the activity back by id
        through the canonical DataLayer pipeline (``_from_row`` → field
        expansion → semantic coercion).  The staging store reads through to
        the receiver's own store for every other id, so an object the
        receiver already holds is the one routing sees
        (:class:`~.inbox_staging.InlineObjectStaging`).  Nothing staged
        reaches the receiver's store (DL-06-006, IO-03-004).

        A redelivery is routed in place of this body, as the copy the
        receiver already holds (VM-08-002, IE-10-001):

        - when the first delivery is still deferred, its held copy is routed
          without received evidence, and the record holding it is kept for
          the replay, which carries it;
        - when intake already archived it, the archived body is parsed and
          routed (ADR-0149) with that body as its received evidence: it is
          the first delivery's sealed body.  The handlers' own idempotency
          guards answer the repeat (ID-04): a committed act is ``SKIPPED``,
          and an act that never committed, such as one that failed, runs as
          a first delivery and commits with the archived body (ADR-0151).

        When either held copy rebuilds, this delivery's own body is
        never routed, and is left untouched for whatever compares it with
        the held one (#3762).  Only when the held copy does not rebuild is
        this delivery's body routed in its place, without received evidence.

        An ``Announce(CaseLedgerEntry)`` is the exception to the staged
        rebuild: per SYNC-13-002 the inline entry is deliberately NOT staged,
        so a by-ID re-read would collapse ``object_`` to a bare ID string and
        mis-route the message (SYNC-13-004).  For that case the already-typed
        in-memory activity is hydrated in place (:meth:`DataLayer.hydrate`
        expands any scalar/list ID references) and returned, so routing sees
        the typed ``CaseLedgerEntry`` without the adapter ever writing the
        ledger.

        The same hazard bit ``Create(CaseProposal)``, which inlines the
        vulnerability report inside the proposal (CP-01-004): the report was never
        staged, so the by-ID re-read collapsed it and the receiver had no report
        (#2482). That is fixed neither here nor at ingress, but in *storage*: the
        proposal declares ``object_`` in ``inline_required_refs``, so persistence
        keeps the report inline instead of dehydrating it to an id that nothing
        could resolve. The re-read is correct once the staged row is faithful to
        what the sender inlined.

        Resist adding activity types to the exception above. An in-place hydration
        skips the wire→core normalisation the by-ID path performs, so routing
        downstream sees `as_`-prefixed types and fails with "Expected
        VulnerabilityCase, got as_VulnerabilityCase". Fix what the store keeps, not
        the read.
        """
        if _is_inline_ledger_entry_announce(activity):
            # A repeat entry is the SYNC-12-003 already-stored gate's to
            # answer, not this adapter's (SYNC-13-004).  The inbox may still
            # defer it, so the staging keeps it to hold for the replay.
            self._staging.note_routed_in_place(activity)
            return _carry_received_evidence(
                activity, self._hydrate_in_place(activity)
            )

        redelivery = self._held_copy_kind(activity.id_)
        if redelivery == "deferred":
            held = self._staging.rehydrate_held(activity.id_)
            if held is not None:
                self._log_redelivery(activity, redelivery)
                return held
        if redelivery == "archived":
            archived = self._staging.rehydrate_archived(activity.id_)
            if archived is not None:
                self._log_redelivery(activity, redelivery)
                return archived

        if redelivery is not None:
            # The held copy did not rebuild.  This delivery's own body is
            # routed in its place, still without received evidence, and
            # staged as no delivery's body, so a deferral holds no evidence
            # either: the delivery routed is a resend, not the one held
            # (VM-08-002).
            result = self._staging.rehydrate_resend(activity)
            if result is None:
                raise VultronWiringError(
                    f"redelivered activity '{activity.id_}' is held"
                    f" ({redelivery}) but neither the held copy nor this body"
                    " rebuilds"
                )
            logger.warning(
                "FastAPIIngressAdapter.rehydrate: the %s copy of activity %s"
                " did not rebuild; routing this delivery's body without its"
                " received evidence (VM-08-002).",
                redelivery,
                activity.id_,
            )
            return result
        result = self._staging.rehydrate_parsed(activity)
        if result is None:
            return activity
        return _carry_received_evidence(activity, result)

    def _held_copy_kind(self, activity_id: str) -> str | None:
        """Which receiver-keyed copy of *activity_id* is held, if any."""
        if self._staging.held(activity_id) is not None:
            return "deferred"
        if isinstance(
            self._dl.read(ReceivedActivityRecord.build_id(activity_id)),
            ReceivedActivityRecord,
        ):
            return "archived"
        return None

    @staticmethod
    def _log_redelivery(activity: as_Activity, kind: str) -> None:
        evidence = (
            "with the archived body as its received evidence"
            if kind == "archived"
            else "without received evidence"
        )
        logger.info(
            "FastAPIIngressAdapter.rehydrate: activity %s (actor %s) is"
            " already held (%s); routing the held copy, %s"
            " (IE-10-001, VM-08-002).",
            activity.id_,
            getattr(activity.actor, "id_", activity.actor),
            kind,
            evidence,
        )

    def _hydrate_in_place(self, activity: as_Activity) -> as_Activity:
        """Expand reference fields on the *parsed* activity, without a re-read."""
        try:
            hydrated = self._dl.hydrate(activity)
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3326  # pragma: no cover - defensive
            logger.warning(
                "FastAPIIngressAdapter.rehydrate: hydrate failed (%s);"
                " returning parsed activity unchanged.",
                exc,
            )
            return activity
        if isinstance(hydrated, as_Activity):
            return hydrated
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

    def dispatch(self, event: VultronEvent) -> HandlerResult:
        """Inject receiving actor ID, dispatch, and return the verdict."""
        scoped_event = event.model_copy(
            update={"receiving_actor_id": self._actor_id}
        )
        return dispatch(
            event=scoped_event,
            dl=self._dl,
            dispatcher=self._dispatcher,
        )

    def emit_processing_fault(
        self, event: VultronEvent, failure_class: str
    ) -> None:
        """Queue the receiving actor's fault to *event*'s sender (ASK-07-010)."""
        emit_processing_fault(
            self._dl,
            self._actor_id,
            event.activity_id,
            event.actor_id,
            failure_class,
        )


class FastAPIQueuePort:
    """Pending-case queue port wrapping the adapter-layer helpers.

    Args:
        dl: Shared DataLayer (for case reads and Question persistence).
        actor_dl: Actor-scoped DataLayer for queue management.
        actor_id: Canonical URI of the receiving actor; used when
            building a replay Question on expiry.
        staging: The inbox run's inline-object staging; a deferred activity's
            staged inline objects are held through it for the replay.
    """

    def __init__(
        self,
        dl: DataLayer,
        actor_dl: DataLayer,
        actor_id: str,
        staging: InlineObjectStaging | None = None,
    ) -> None:
        self._dl = dl
        self._actor_dl = cast(DataLayer, actor_dl)
        self._actor_id = actor_id
        self._staging = staging or InlineObjectStaging(actor_dl)

    def is_case_known(self, case_id: str) -> bool:
        """Return ``True`` if the case replica is locally available."""
        return isinstance(self._dl.read(case_id), VulnerabilityCase)

    def queue(
        self,
        activity_id: str,
        case_id: str,
        case_actor_id: str | None = None,
    ) -> None:
        """Persist *activity_id* in the deferred queue for *case_id*.

        The activity is held whole with its staged inline objects, because
        the replay rebuilds it after this delivery's staging is gone, and the
        receiver keeps no copy under its id (DL-06-006).  It is held before
        it is queued, so a failed hold queues nothing.
        """
        self._staging.hold_for_replay(activity_id)
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
    actor_dl: DataLayer,
    actor_id: str,
    dispatcher: ActivityDispatcher | None,
    emitter: Any,
) -> None:
    """Adapter-layer background task: construct adapters and run pipeline.

    Calls :func:`~vultron.core.behaviors.inbox.process_payload` for the
    immediate payload, then replays every activity queued in the inbox
    (e.g., after bootstrap dispatch) with bounded retry and dead letter
    (:func:`~vultron.adapters.driving.fastapi.inbox_replay.drain_inbox_queue`,
    IE-06-004), and finally drains the outbox.
    The synchronous BT work runs in a worker thread so the ASGI event loop
    keeps serving while a handler executes (IE-06-002, BT-11-002); only the
    outbox drain, which is async I/O, runs on the loop.

    This function is the background task scheduled by ``post_actor_inbox``.
    It is the ONLY place that constructs the adapter instances, satisfying
    IO-03-003.

    Args:
        payload: Raw inbox payload (JSON body dict or as_Activity).
        actor_dl: The receiving actor's DataLayer — ingress, dispatch, queues
            and stored activities alike.  Before ADR-0073 a separate shared
            DataLayer was threaded alongside it; the two only differed because
            the shared pool could see every actor's rows.
        actor_id: Canonical URI of the receiving actor.
        dispatcher: Optional per-app dispatcher.
        emitter: Optional per-app ActivityEmitter.
    """
    staging = InlineObjectStaging(actor_dl)
    ingress = FastAPIIngressAdapter(dl=actor_dl, staging=staging)
    dispatch_adp = FastAPIDispatchAdapter(
        dl=actor_dl, actor_id=actor_id, dispatcher=dispatcher
    )
    queue = FastAPIQueuePort(
        dl=actor_dl,
        actor_dl=cast(DataLayer, actor_dl),
        actor_id=actor_id,
        staging=staging,
    )

    # Serialise concurrent inbox background tasks for this actor so that
    # process_payload for entry N+1 never starts before entry N has been
    # stored.  Without this lock, two HTTP POSTs that arrive close together
    # create two asyncio Tasks that can run in any order; if entry N+1's
    # task runs first, the hash-chain check fails → spurious Reject (issue #1525).
    # The receiving actor's RSVP windows govern inbound embargo invites
    # (EP-07-001, EP-07-002); None applies the protocol defaults.
    actor_config = inbox_port_factories._resolve_actor_config()

    max_attempts = get_config().max_inbox_retry_attempts

    def _process_and_replay() -> None:
        """The synchronous BT work for one delivery, plus its replays.

        Runs on a worker thread (see below), so it must not touch asyncio.
        """
        outcome = process_payload(
            payload, ingress, dispatch_adp, queue, actor_config=actor_config
        )
        logger.debug(
            "run_inbox_pipeline: status=%s context_id=%s",
            outcome.status,
            outcome.context_id,
        )
        warn_if_rejected(outcome, actor_id, replayed=False)

        # Replay what this delivery, or an earlier one, queued: activities
        # pushed back by the post-bootstrap replay and ledger hand-backs.
        drain_inbox_queue(
            actor_dl,
            actor_id,
            dispatch_adp,
            queue,
            staging,
            actor_config,
            max_attempts,
        )

    try:
        async with _get_actor_lock(actor_id):
            # Off the event loop, deliberately.  Starlette runs an
            # ``async`` background task on the loop itself, and
            # ``process_payload`` is synchronous — BT ticks, the BT global
            # lock, SQLite I/O.  Called inline it stalls the whole container
            # for every inbound activity: no HTTP response goes out, no
            # delivery from a peer is accepted, the co-hosted OutboxMonitor
            # coroutine cannot drain, and a trigger route waiting on the BT
            # lock from its threadpool thread starves (IE-06-002,
            # BT-11-002).  The rv/rcvcv demo flakes were the CaseActor's
            # outbox paying one full BT tick per delivery on the vendor
            # container (#3033, #2898).  ``asyncio.to_thread`` matches what
            # the sync trigger routes already do; the BT global RLock
            # serialises BT execution across threads, and the per-actor lock
            # above (held across the thread hop) keeps this actor's
            # deliveries FIFO (BT-11-001, #1525).
            await asyncio.to_thread(_process_and_replay)
    finally:
        # The delivery's replies, and any fault a settled replay queued, are
        # already in the outbox: a store write that raised while settling a
        # replay must not leave them undelivered.
        await outbox_handler(actor_id, actor_dl, emitter=emitter)
