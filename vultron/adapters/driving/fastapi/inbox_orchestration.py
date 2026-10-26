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
:mod:`~vultron.adapters.driving.fastapi.inbox_queue_drain` (IE-06-004).

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
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, cast

from vultron.adapters.driven.http_object_fetch import (
    HttpObjectFetcher,
    ObjectFetcher,
    ObjectFetchResult,
)
from vultron.adapters.driving.fastapi import inbox_port_factories
from vultron.adapters.driving.fastapi.inbox_dereference import (
    FastAPIDereferencePort,
    open_fetches,
    settle_fetch,
)
from vultron.adapters.driving.fastapi.inbox_handler import (
    dispatch,
    emit_processing_fault,
)
from vultron.adapters.driving.fastapi.inbox_pending_queue import (
    _expire_pending_case_activities,
    _queue_pending_case_activity,
    _replay_pending_case_activities,
)
from vultron.adapters.driving.fastapi.inbox_queue_drain import (
    drain_inbox_queue,
    log_if_rejected,
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
from vultron.core.ports.emitter import ActivityEmitter
from vultron.errors import VultronReusedActivityIdError, VultronWiringError
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


@dataclass(frozen=True)
class _HeldBody:
    """The sealed body the receiver holds for an activity id, and where."""

    kind: Literal["deferred", "archived"]
    body: str


def _sender_id(activity: as_Activity) -> str | None:
    """The id of the actor *activity* names as its sender, if any."""
    actor = activity.actor
    if actor is None:
        return None
    return str(getattr(actor, "id_", actor))


def _body_digest(sealed_text: str) -> str:
    """The SHA-256 digest of a sealed received text (IE-10-002)."""
    return hashlib.sha256(sealed_text.encode("utf-8")).hexdigest()


def _refuse_a_different_body(activity: as_Activity, held: _HeldBody) -> None:
    """Refuse *activity* unless its sealed body is exactly *held*'s.

    The match is exact, digest against digest, with no normalisation
    (IE-10-002).  A same-body delivery returns, to be routed as a
    redelivery (IE-10-001).

    Raises:
        VultronWiringError: When *activity* carries no sealed body.  Every
            delivery the inbox parses is sealed (VM-08-002), so only an
            activity handed to the inbox in process can lack one.
        VultronReusedActivityIdError: When the bodies differ.  It is logged
            here, at WARNING, with the activity id and the sender.
    """
    evidence = activity.received_evidence_json
    if evidence is None:
        raise VultronWiringError(
            f"a delivery of held activity '{activity.id_}' carries no sealed"
            " body, so it cannot be compared with the held one (VM-08-002,"
            " IE-10-002)"
        )
    if _body_digest(evidence) == _body_digest(held.body):
        return
    sender = _sender_id(activity)
    logger.warning(
        "FastAPIIngressAdapter.rehydrate: refusing activity %s (actor %s):"
        " its id is already held (%s) with a different body, so neither"
        " body is routed and nothing is written (IE-10-002).",
        activity.id_,
        sender,
        held.kind,
    )
    raise VultronReusedActivityIdError(activity.id_, sender)


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

        When the receiver already holds the activity id, under a key it
        derives from it, this delivery's sealed body is compared with the
        body held for it first, by the SHA-256 digest of each text, exactly
        (IE-10-002, #3762):

        - a different body is not a redelivery: it is refused with
          :exc:`~vultron.errors.VultronReusedActivityIdError`, logged at
          WARNING with the activity id and the sender.  Neither body is
          routed and nothing is written, so the held record stays as it was.
          No normalisation precedes the match, so a body re-serialized with
          another key order is refused too (IE-10-002 ``note:``);
        - the same body is a redelivery, routed in place of this one as the
          copy the receiver already holds (VM-08-002, IE-10-001).  When the
          first delivery is still deferred, its held copy is routed without
          received evidence, and the record holding it is kept for the
          replay, which carries it.  When intake already archived it, the
          archived body is parsed and routed (ADR-0149) with that body as its
          received evidence: it is the first delivery's sealed body.  The
          handlers' own idempotency guards answer the repeat (ID-04): a
          committed act is ``SKIPPED``, and an act that never committed, such
          as one that failed, runs as a first delivery and commits with the
          archived body (ADR-0151).

        Production deliveries always carry a sealed body, and a held record
        always holds one, so meeting either side without one is a wiring
        fault (ARCH-15-001), as is a held copy that does not rebuild: it is
        the same text as this delivery's.

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
        held = self._held_body(activity.id_)
        if held is not None:
            _refuse_a_different_body(activity, held)

        if _is_inline_ledger_entry_announce(activity):
            # A repeat entry is the SYNC-12-003 already-stored gate's to
            # answer, not this adapter's (SYNC-13-004).  The inbox may still
            # defer it, so the staging keeps it to hold for the replay.
            self._staging.note_routed_in_place(activity)
            return _carry_received_evidence(
                activity, self._hydrate_in_place(activity)
            )

        if held is None:
            result = self._staging.rehydrate_parsed(activity)
            if result is None:
                return activity
            return _carry_received_evidence(activity, result)

        routed = (
            self._staging.rehydrate_held(activity.id_)
            if held.kind == "deferred"
            else self._staging.rehydrate_archived(activity.id_)
        )
        if routed is None:
            # The held copy is this delivery's own text, so this body would
            # not rebuild either.
            raise VultronWiringError(
                f"redelivered activity '{activity.id_}' is held"
                f" ({held.kind}) but its held copy does not rebuild"
            )
        self._log_redelivery(activity, held.kind)
        return routed

    def _held_body(self, activity_id: str) -> _HeldBody | None:
        """The body held for *activity_id* under the receiver's key, if any.

        The deferred record's while the first delivery is still deferred,
        else the body intake archived (IE-10-001, IE-10-002).
        """
        pending = self._staging.held(activity_id)
        if pending is not None:
            return _HeldBody("deferred", pending.received_body)
        record = self._dl.read(ReceivedActivityRecord.build_id(activity_id))
        if isinstance(record, ReceivedActivityRecord):
            return _HeldBody("archived", record.received_body)
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
            _sender_id(activity),
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


class _InboxRun:
    """The adapters one inbox run of an actor shares (IO-03-003).

    The ingress adapter and the queue port share one staging, so a delivery
    the queue defers is held whole for its replay.
    """

    def __init__(
        self,
        actor_dl: DataLayer,
        actor_id: str,
        dispatcher: ActivityDispatcher | None,
    ) -> None:
        self.actor_dl = actor_dl
        self.actor_id = actor_id
        self.staging = InlineObjectStaging(actor_dl)
        self.ingress = FastAPIIngressAdapter(dl=actor_dl, staging=self.staging)
        self.dispatch = FastAPIDispatchAdapter(
            dl=actor_dl, actor_id=actor_id, dispatcher=dispatcher
        )
        self.queue = FastAPIQueuePort(
            dl=actor_dl,
            actor_dl=cast(DataLayer, actor_dl),
            actor_id=actor_id,
            staging=self.staging,
        )
        # Shares the staging too: an activity waiting on a fetch is held
        # whole for its replay, as a deferred one is (AKM-05-007).
        self.dereference = FastAPIDereferencePort(
            actor_dl, actor_id, self.staging
        )
        # The receiving actor's RSVP windows govern inbound embargo invites
        # (EP-07-001, EP-07-002); None applies the protocol defaults.
        self.actor_config = inbox_port_factories._resolve_actor_config()
        self.max_attempts = get_config().max_inbox_retry_attempts

    def drain_queue(self) -> None:
        """Replay every item queued in the actor's inbox (IE-06-004)."""
        drain_inbox_queue(
            self.actor_dl,
            self.actor_id,
            self.dispatch,
            self.queue,
            self.staging,
            self.actor_config,
            self.max_attempts,
            self.dereference,
        )


async def _run_serialised(
    actor_dl: DataLayer,
    actor_id: str,
    emitter: ActivityEmitter | None,
    work: Callable[[], None],
) -> None:
    """Run *work* under the actor's inbox lock, off the loop, then drain.

    Off the event loop, deliberately.  Starlette runs an ``async``
    background task on the loop itself, and ``process_payload`` is
    synchronous — BT ticks, the BT global lock, SQLite I/O.  Called inline
    it stalls the whole container for every inbound activity: no HTTP
    response goes out, no delivery from a peer is accepted, the co-hosted
    OutboxMonitor coroutine cannot drain, and a trigger route waiting on the
    BT lock from its threadpool thread starves (IE-06-002, IE-06-003,
    BT-11-002).  The rv/rcvcv demo flakes were the CaseActor's outbox paying
    one full BT tick per delivery on the vendor container (#3033, #2898).
    ``asyncio.to_thread`` matches what the sync trigger routes already do;
    the BT global RLock serialises BT execution across threads, and the
    per-actor lock (held across the thread hop) keeps this actor's
    deliveries FIFO (BT-11-001, #1525): process_payload for entry N+1 never
    starts before entry N has been stored, or the hash-chain check fails and
    a spurious Reject follows.
    """
    try:
        async with _get_actor_lock(actor_id):
            await asyncio.to_thread(work)
    finally:
        # The delivery's replies, and any fault a settled replay queued, are
        # already in the outbox: a store write that raised while settling a
        # replay must not leave them undelivered.
        await outbox_handler(actor_id, actor_dl, emitter=emitter)


async def run_serialised_actor_work(
    actor_dl: DataLayer,
    actor_id: str,
    emitter: ActivityEmitter | None,
    work: Callable[[], None],
) -> None:
    """Run *work* as this actor's deliveries run: serialised, then drained.

    For actor-initiated work that is not a delivery, such as the ledger
    position statements a participant sends after a restart (SYNC-17-007).
    It takes the actor's inbox lock, so it never interleaves with a delivery
    being processed, runs off the event loop, and drains the outbox after
    (see :func:`_run_serialised`).
    """
    await _run_serialised(actor_dl, actor_id, emitter, work)


async def run_inbox_pipeline(
    payload: dict[str, Any] | bytes | str | Any,
    actor_dl: DataLayer,
    actor_id: str,
    dispatcher: ActivityDispatcher | None,
    emitter: ActivityEmitter | None,
    fetcher: ObjectFetcher | None = None,
) -> None:
    """Adapter-layer background task: construct adapters and run pipeline.

    Calls :func:`~vultron.core.behaviors.inbox.process_payload` for the
    immediate payload, then replays every activity queued in the inbox
    (e.g., after bootstrap dispatch) with bounded retry and dead letter
    (:func:`~vultron.adapters.driving.fastapi.inbox_queue_drain.drain_inbox_queue`,
    IE-06-004), and finally drains the outbox.  Last, it makes every fetch
    an activity waits on and replays the activities each one settles
    (:func:`resolve_open_fetches`, AKM-05-007).
    The synchronous BT work runs in a worker thread so the ASGI event loop
    keeps serving while a handler executes (IE-06-002, BT-11-002); only the
    outbox drain, which is async I/O, runs on the loop.

    This function is the background task scheduled by ``post_actor_inbox``.
    It and the startup replay (:func:`replay_inbox_queue`) construct the
    adapter instances, through :class:`_InboxRun` (IO-03-003).

    Args:
        payload: Raw inbox payload (JSON body dict or as_Activity).
        actor_dl: The receiving actor's DataLayer — ingress, dispatch, queues
            and stored activities alike.  Before ADR-0073 a separate shared
            DataLayer was threaded alongside it; the two only differed because
            the shared pool could see every actor's rows.
        actor_id: Canonical URI of the receiving actor.
        dispatcher: Optional per-app dispatcher.
        emitter: Optional per-app ActivityEmitter.
        fetcher: The object fetcher; ``None`` uses the HTTP one
            (:func:`default_object_fetcher`).
    """
    run = _InboxRun(actor_dl, actor_id, dispatcher)

    def _process_and_replay() -> None:
        """The synchronous BT work for one delivery, plus its replays.

        Runs on a worker thread (see :func:`_run_serialised`), so it must not
        touch asyncio.
        """
        outcome = process_payload(
            payload,
            run.ingress,
            run.dispatch,
            run.queue,
            actor_config=run.actor_config,
            dereference_port=run.dereference,
        )
        logger.debug(
            "run_inbox_pipeline: status=%s context_id=%s",
            outcome.status,
            outcome.context_id,
        )
        log_if_rejected(outcome, actor_id, replayed=False)

        # Replay what this delivery, or an earlier one, queued: activities
        # pushed back by the post-bootstrap replay, and held ledger
        # Announces replayed once their entry applies (SYNC-14-009).
        run.drain_queue()

    await _run_serialised(actor_dl, actor_id, emitter, _process_and_replay)
    await resolve_open_fetches(run, emitter, fetcher)


#: Rounds of fetching one run makes: a replay a fetch released may itself
#: wait on another object, and this bounds how far one run chases them.
MAX_FETCH_ROUNDS = 4


def default_object_fetcher() -> HttpObjectFetcher:
    """The HTTP fetcher, bounded by the configured attempts (AKM-05-008)."""
    config = get_config()
    return HttpObjectFetcher(
        max_attempts=config.max_object_fetch_attempts,
        timeout=config.object_fetch_timeout_seconds,
    )


async def resolve_open_fetches(
    run: _InboxRun,
    emitter: ActivityEmitter | None,
    fetcher: ObjectFetcher | None = None,
) -> None:
    """Make every open fetch of *run*'s actor, then replay what waited on it.

    The fetches run on the event loop, outside the actor's inbox lock: a
    fetch may wait out its retries, and the actor's deliveries must not wait
    with it (IE-06-002).  Each result is settled under the lock, off the
    loop, and the inbox queue drained, as for a delivery
    (:func:`_run_serialised`, AKM-05-007, AKM-05-008).  A replay may open a
    fetch of its own, so the open fetches are read again, up to
    :data:`MAX_FETCH_ROUNDS` times; a fetch still open after that is made by
    the actor's next inbox run.
    """
    active = fetcher
    for _ in range(MAX_FETCH_ROUNDS):
        pending = await asyncio.to_thread(open_fetches, run.actor_dl)
        if not pending:
            return
        if active is None:
            active = default_object_fetcher()
        for fetch in pending:
            result = await active.fetch(fetch.reference, run.actor_id)

            def _settle(
                object_id: str = fetch.object_id,
                settled: ObjectFetchResult = result,
            ) -> None:
                settle_fetch(run.actor_dl, run.actor_id, object_id, settled)
                run.drain_queue()

            await _run_serialised(run.actor_dl, run.actor_id, emitter, _settle)


async def replay_inbox_queue(
    actor_dl: DataLayer,
    actor_id: str,
    dispatcher: ActivityDispatcher | None,
    emitter: ActivityEmitter | None,
    fetcher: ObjectFetcher | None = None,
) -> None:
    """Replay every item queued in *actor_id*'s inbox, with no delivery.

    The startup replay (IE-06-006): the same drain, bounded retry and dead
    letter as a replay after a delivery (IE-06-004), under the same
    per-actor lock as :func:`run_inbox_pipeline` and off the event loop
    (IE-06-003), then the outbox drain.  A fetch an earlier run left open
    is made then, so an activity waiting on it does not wait for the next
    delivery (AKM-05-007).

    Args:
        actor_dl: The receiving actor's DataLayer, which holds the queue.
        actor_id: Canonical URI of the receiving actor.
        dispatcher: Optional per-app dispatcher.
        emitter: Optional per-app ActivityEmitter.
        fetcher: The object fetcher; ``None`` uses the HTTP one.
    """
    run = _InboxRun(actor_dl, actor_id, dispatcher)
    await _run_serialised(actor_dl, actor_id, emitter, run.drain_queue)
    await resolve_open_fetches(run, emitter, fetcher)
