#!/usr/bin/env python
"""FastAPI adapter implementations for inbox orchestration.

Provides concrete adapter classes that implement the
:mod:`vultron.core.behaviors.inbox` protocols using the FastAPI
DataLayer and dispatcher infrastructure:

- :class:`FastAPIIngressAdapter` — parse (wire) + rehydrate (staged)
- :class:`StoredActivityIngressAdapter` — replay of a held deferred activity
- :class:`FastAPIDispatchAdapter` — wraps the dispatcher port
- :class:`ReplayDispatchAdapter` — the dispatcher port for a replay the inbox
  may retry (IE-06-004)
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
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.adapters.outbox_dead_letter import RetryStore
from vultron.config import get_config
from vultron.config.actor import ActorConfig
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import VultronEvent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.errors import (
    VultronProtocolViolationError,
    VultronWiringError,
)
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


class ReplayAttempt:
    """What one replay attempt of a queued inbox item raised (IE-06-004).

    The replay's ingress and dispatch adapters record the exception here,
    and the dispatch adapter holds the fault ``DispatchNode`` asks for, so
    the queue drain decides after the attempt whether the item is retried,
    dead-lettered or dropped, and whether its sender is answered
    (ASK-07-010).
    """

    def __init__(self) -> None:
        #: The failure reason code and the exception, when the attempt raised.
        self.raised: tuple[str, Exception] | None = None
        #: The fault ``DispatchNode`` asked for: the event and failure class.
        self.fault: tuple[VultronEvent, str] | None = None

    def begin(self) -> None:
        """Forget the previous attempt."""
        self.raised = None
        self.fault = None

    def record_raise(self, reason: str, error: Exception) -> None:
        """Record that the attempt raised *error* at the *reason* stage."""
        self.raised = (reason, error)


class StoredActivityIngressAdapter:
    """Ingress adapter for the replay of a held activity.

    Used when the payload is an activity-ID string popped from the inbox
    queue: an activity deferred pending its case, or a held
    ``Announce(CaseLedgerEntry)`` replayed once its entry applies
    (SYNC-14-009).  Either is held whole, as received, in a
    :class:`~vultron.core.models.deferred_inbox_activity.DeferredInboxActivity`,
    never under its own id (DL-06-006).

    ``parse`` rebuilds the held activity and releases its record.
    ``rehydrate`` is a no-op (parse already returns the rehydrated form).

    Args:
        dl: The receiving actor's own DataLayer, which holds the records.
        staging: The inbox run's inline-object staging, which holds each
            deferred activity for its replay.
        attempt: When given, a rebuild that raises is recorded on it, so the
            queue drain retries the item (IE-06-004).
    """

    def __init__(
        self,
        dl: DataLayer,
        staging: InlineObjectStaging | None = None,
        attempt: ReplayAttempt | None = None,
    ) -> None:
        self._dl = dl
        self._staging = staging or InlineObjectStaging(dl)
        self._attempt = attempt

    def parse(
        self,
        payload: dict[str, Any] | bytes | str | Any,
    ) -> as_Activity | None:
        """Rebuild the held activity *payload* names.

        Returns ``None`` when nothing is held for the id.
        """
        if isinstance(payload, as_Activity):
            return payload

        activity_id = str(payload) if payload is not None else None
        if not activity_id:
            logger.warning("StoredActivityIngressAdapter.parse: empty payload")
            return None

        # ``None`` when nothing is held; the staging logs why.
        try:
            return self._staging.rehydrate_deferred(activity_id)
        except Exception as exc:
            # Recorded for the queue drain's retry decision, then re-raised:
            # ``ParsePayloadNode`` still rejects the attempt (IE-06-004).
            if self._attempt is not None:
                self._attempt.record_raise("rehydration_error", exc)
            raise

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


class ReplayDispatchAdapter(FastAPIDispatchAdapter):
    """Dispatch adapter for a replay of a queued item the inbox may retry.

    A raised dispatch is recorded on *attempt* and re-raised to
    ``DispatchNode``, which rejects the attempt and asks for the sender's
    internal-error fault.  The fault is held, not sent: an attempt that is
    re-queued may still succeed, and a fault sent before that success would
    be false (ASK-07-010, ASK-07-007).  The queue drain sends it only when
    the item is dead-lettered or dropped (:meth:`send_held_fault`).

    Args:
        dl: The receiving actor's DataLayer, for dispatch and the fault.
        actor_id: Canonical URI of the receiving actor.
        attempt: The drain's record of the current attempt.
        dispatcher: Optional per-app dispatcher.
    """

    def __init__(
        self,
        dl: DataLayer,
        actor_id: str,
        attempt: ReplayAttempt,
        dispatcher: ActivityDispatcher | None = None,
    ) -> None:
        super().__init__(dl=dl, actor_id=actor_id, dispatcher=dispatcher)
        self._attempt = attempt

    def dispatch(self, event: VultronEvent) -> HandlerResult:
        """Dispatch, recording a raise before it reaches ``DispatchNode``."""
        try:
            return super().dispatch(event)
        except Exception as exc:
            # Recorded for the queue drain's retry decision, then re-raised:
            # ``DispatchNode`` still logs and rejects it (IE-06-004).
            self._attempt.record_raise("processing_error", exc)
            raise

    def emit_processing_fault(
        self, event: VultronEvent, failure_class: str
    ) -> None:
        """Hold the fault until the drain knows the item is not retried."""
        self._attempt.fault = (event, failure_class)

    def send_held_fault(self) -> None:
        """Queue the fault held for the current attempt, if any (ASK-07-010).

        ``DispatchNode`` holds none for a raised ``Create(ProcessingFault)``,
        and none is held when the attempt raised before dispatch.  A fault
        that cannot be queued is logged, never raised: the item is already
        settled.
        """
        held = self._attempt.fault
        if held is None:
            return
        event, failure_class = held
        try:
            super().emit_processing_fault(event, failure_class)
        except Exception:
            # The drain boundary: a failed fault must not stop the drain.
            logger.exception(
                "ProcessingFault not queued for activity_id=%s actor_id=%s",
                event.activity_id,
                event.actor_id,
            )
            return
        logger.info(
            "Queued ProcessingFault/%s to actor_id=%s for settled inbox item"
            " activity_id=%s (ASK-07-010).",
            failure_class,
            event.actor_id,
            event.activity_id,
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


def _warn_if_rejected(
    outcome: InboxOutcome, actor_id: str, *, replayed: bool
) -> None:
    """Log a rejected outcome at WARNING (UCORG-05-013).

    Every outcome is logged at DEBUG; a refusal is also logged here so it is
    visible in an actor log at the default level. ``processed`` and
    ``deferred`` stay at DEBUG — both are expected, routine outcomes.
    """
    if outcome.status is not InboxOutcomeStatus.REJECTED:
        return
    logger.warning(
        "Inbox activity rejected (actor_id=%s activity_id=%s context_id=%s"
        " replayed=%s): %s",
        actor_id,
        outcome.activity_id,
        outcome.context_id,
        replayed,
        outcome.failure_reason,
    )


def _inbox_retry_or_dead_letter(
    item_id: str,
    actor_id: str,
    reason: str,
    last_error: str,
    queue_dl: DataLayer,
    retry: RetryStore,
    max_attempts: int,
    staging: InlineObjectStaging,
) -> bool:
    """Count a failed attempt; dead-letter on exhaustion, re-queue otherwise.

    Uses the persisted retry and dead-letter store outbox delivery uses
    (IE-06-004, OX-13).

    Args:
        item_id: Activity ID of the failing inbox item.
        actor_id: Canonical URI of the receiving actor (for log context).
        reason: Short machine-readable failure reason code.
        last_error: String representation of the last exception.
        queue_dl: Actor-scoped DataLayer for queue management.
        retry: ``RetryStore`` port used to persist attempt counts and dead
            letters.
        max_attempts: Maximum cumulative attempts before dead-lettering
            (``AppConfig.max_inbox_retry_attempts``).
        staging: The staging whose rebuild released the item's record; a
            re-queued item is held again through it, or the retry would find
            nothing to rebuild (DL-06-006).

    Returns:
        ``True`` when the item was dead-lettered, so no retry follows;
        ``False`` when it was re-queued.
    """
    total = retry.get_inbox_attempt_count(item_id) + 1
    # The rebuild released the record, and the retry, or an operator reading
    # the dead letter, needs the activity it held (DL-06-006).
    staging.hold_again(item_id)
    if total >= max_attempts:
        retry.inbox_dead_letter_append(
            item_id,
            reason=reason,
            total_attempts=total,
            last_error=last_error,
        )
        retry.clear_inbox_attempt_count(item_id)
        logger.error(
            "Inbox item '%s' exhausted %d processing attempts for actor '%s';"
            " moved to dead letter (IE-06-004).",
            item_id,
            total,
            actor_id,
        )
        return True
    retry.set_inbox_attempt_count(item_id, total)
    queue_dl.inbox_append(item_id)
    logger.error(
        "Error processing inbox item '%s' for actor '%s' (attempt %d/%d);"
        " re-queuing for retry (IE-06-004).",
        item_id,
        actor_id,
        total,
        max_attempts,
    )
    return False


def _drain_inbox_queue(
    actor_dl: DataLayer,
    actor_id: str,
    dispatcher: ActivityDispatcher | None,
    queue: FastAPIQueuePort,
    staging: InlineObjectStaging,
    actor_config: ActorConfig | None,
    max_attempts: int,
) -> None:
    """Replay every item queued in *actor_dl*'s inbox, with bounded retry.

    The queue holds activities replayed after their case's bootstrap and
    ledger entries handed back to the inbox (SYNC-14-009).  Each attempt is
    a whole run of :func:`process_payload`: a failed act keeps nothing, so a
    retry re-runs the act from the start (ADR-0151).  An attempt that raises
    is settled here (IE-06-004):

    - a ``VultronProtocolViolationError`` is a permanent failure: the item is
      dropped, and its sender answered;
    - any other exception re-queues the item, unanswered, until
      ``max_attempts`` is used up, then dead-letters it and answers its
      sender with the internal-error fault ``DispatchNode`` asked for
      (ASK-07-010).
    """
    attempt = ReplayAttempt()
    ingress = StoredActivityIngressAdapter(
        dl=actor_dl, staging=staging, attempt=attempt
    )
    dispatch_adp = ReplayDispatchAdapter(
        dl=actor_dl,
        actor_id=actor_id,
        attempt=attempt,
        dispatcher=dispatcher,
    )
    # SqliteDataLayer satisfies RetryStore structurally, as for the outbox.
    retry = cast(RetryStore, actor_dl)
    requeued: set[str] = set()
    while actor_dl.inbox_list():
        item_id = actor_dl.inbox_pop()
        if item_id is None:
            break
        attempt.begin()
        outcome = process_payload(
            item_id,
            ingress,
            dispatch_adp,
            queue,
            actor_config=actor_config,
        )
        logger.debug(
            "run_inbox_pipeline: replayed status=%s context_id=%s",
            outcome.status,
            outcome.context_id,
        )
        _warn_if_rejected(outcome, actor_id, replayed=True)

        if attempt.raised is None or isinstance(
            attempt.raised[1], VultronProtocolViolationError
        ):
            if attempt.raised is not None:
                logger.error(
                    "Inbox item '%s' for actor '%s' raised a protocol"
                    " violation; dropped as a permanent failure (IE-06-004).",
                    item_id,
                    actor_id,
                )
                dispatch_adp.send_held_fault()
            if item_id in requeued:
                # Settled after a retry: its attempt count has no further use.
                requeued.discard(item_id)
                retry.clear_inbox_attempt_count(item_id)
            continue
        reason, error = attempt.raised
        if _inbox_retry_or_dead_letter(
            item_id,
            actor_id,
            reason,
            str(error),
            actor_dl,
            retry,
            max_attempts,
            staging,
        ):
            requeued.discard(item_id)
            dispatch_adp.send_held_fault()
        else:
            requeued.add(item_id)


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
    (:func:`_drain_inbox_queue`, IE-06-004), and finally drains the outbox.
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
        _warn_if_rejected(outcome, actor_id, replayed=False)

        # Replay what this delivery, or an earlier one, queued: activities
        # pushed back by the post-bootstrap replay and ledger hand-backs.
        _drain_inbox_queue(
            actor_dl,
            actor_id,
            dispatcher,
            queue,
            staging,
            actor_config,
            max_attempts,
        )

    async with _get_actor_lock(actor_id):
        # Off the event loop, deliberately.  Starlette runs an ``async``
        # background task on the loop itself, and ``process_payload`` is
        # synchronous — BT ticks, the BT global lock, SQLite I/O.  Called
        # inline it stalls the whole container for every inbound activity: no
        # HTTP response goes out, no delivery from a peer is accepted, the
        # co-hosted OutboxMonitor coroutine cannot drain, and a trigger route
        # waiting on the BT lock from its threadpool thread starves (IE-06-002,
        # BT-11-002).  The rv/rcvcv demo flakes were the CaseActor's outbox
        # paying one full BT tick per delivery on the vendor container (#3033,
        # #2898).  ``asyncio.to_thread`` matches what the sync trigger routes
        # already do; the BT global RLock serialises BT execution across
        # threads, and the per-actor lock above (held across the thread hop)
        # keeps this actor's deliveries FIFO (BT-11-001, #1525).
        await asyncio.to_thread(_process_and_replay)

    await outbox_handler(actor_id, actor_dl, emitter=emitter)
