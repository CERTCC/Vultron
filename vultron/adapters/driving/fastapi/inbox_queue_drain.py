#!/usr/bin/env python
"""The inbox queue replay, with bounded retry and dead letter (IE-06-004).

``run_inbox_pipeline`` processes one delivery, then replays every activity
queued in the receiving actor's inbox: activities deferred until their case
was bootstrapped, and held ``Announce(CaseLedgerEntry)`` deliveries replayed
once their entry applies (SYNC-14-009).
This module owns that replay:

- :class:`StoredActivityIngressAdapter` — rebuilds a held activity by id
- :class:`ReplayAttempt` — what one replay attempt did and raised
- :class:`ReplayDispatchAdapter` — holds the internal-error fault until the
  item is settled (ASK-07-010)
- :func:`drain_inbox_queue` — the replay loop and its retry decision
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

from vultron.adapters.inbox_staging import InlineObjectStaging
from vultron.adapters.outbox_dead_letter import RetryStore
from vultron.config.actor import ActorConfig
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.behaviors.inbox.models import (
    DispatchAdapter,
    PendingCaseQueuePort,
)
from vultron.core.models.events import VultronEvent
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import VultronProtocolViolationError
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


def warn_if_rejected(
    outcome: InboxOutcome, actor_id: str, *, replayed: bool
) -> None:
    """Log a rejected outcome at WARNING (UCORG-05-013).

    Every outcome is logged at DEBUG; a refusal is also logged here so it is
    visible in an actor log at the default level. ``processed`` and
    ``deferred`` stay at DEBUG — both are expected, routine outcomes.  An
    ``unhandled`` outcome (no use case found) is logged at INFO: the
    receiver does not handle the message, which does not make it an anomaly
    (IO-01-005, SE-05-002).
    """
    if outcome.status is not InboxOutcomeStatus.REJECTED:
        return
    if outcome.unhandled:
        logger.info(
            "Inbox activity not handled (actor_id=%s activity_id=%s"
            " context_id=%s replayed=%s): %s",
            actor_id,
            outcome.activity_id,
            outcome.context_id,
            replayed,
            outcome.failure_reason,
        )
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


class ReplayAttempt:
    """What one replay attempt of a queued inbox item did (IE-06-004).

    The replay's ingress and dispatch adapters record on it whether the item
    was rebuilt, whether it reached dispatch, and what either raised.  The
    dispatch adapter also holds the fault ``DispatchNode`` asks for.  The
    queue drain reads it after the attempt to decide whether the item is
    retried, dead-lettered or dropped, and whether its sender is answered
    (ASK-07-010).
    """

    def __init__(self) -> None:
        #: The held activity was rebuilt.
        self.rebuilt = False
        #: The attempt reached the dispatch adapter.
        self.dispatched = False
        #: The failure reason code and last error, when the attempt failed.
        self.failure: tuple[str, str] | None = None
        #: The failure is a ``VultronProtocolViolationError``: never retried.
        self.permanent = False
        #: The fault ``DispatchNode`` asked for: the event and failure class.
        self.fault: tuple[VultronEvent, str] | None = None

    def begin(self) -> None:
        """Forget the previous attempt."""
        self.rebuilt = False
        self.dispatched = False
        self.failure = None
        self.permanent = False
        self.fault = None

    def record_raise(self, reason: str, error: Exception) -> None:
        """Record that the attempt raised *error* at the *reason* stage."""
        self.failure = (reason, str(error))
        self.permanent = isinstance(error, VultronProtocolViolationError)

    def settle_rejection(self, outcome: InboxOutcome) -> None:
        """Count a rejection before dispatch as a failure of the attempt.

        A pipeline node that catches its own exception, such as extraction,
        rejects the item with nothing recorded here.  The rebuild released
        the item's record, so a rejection after the rebuild and before
        dispatch is retried like a raise, or the item would be lost.  This
        includes a pending queue that expired while a replayed item's case
        is unknown again, which no protocol path reaches.  A handler's
        ``REFUSED`` verdict reached dispatch and is final.
        """
        if (
            self.failure is None
            and outcome.status is InboxOutcomeStatus.REJECTED
            and self.rebuilt
            and not self.dispatched
        ):
            self.failure = (
                "processing_error",
                outcome.failure_reason or "rejected before dispatch",
            )


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
        attempt: When given, the rebuild and any raise are recorded on it,
            so the queue drain can retry the item (IE-06-004).
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

        try:
            # ``None`` when nothing is held; the staging logs why.
            activity = self._staging.rehydrate_deferred(activity_id)
        except Exception as exc:
            # Recorded for the queue drain's retry decision, then re-raised:
            # ``ParsePayloadNode`` still rejects the attempt (IE-06-004).
            if self._attempt is not None:
                self._attempt.record_raise("rehydration_error", exc)
            raise
        if self._attempt is not None and activity is not None:
            self._attempt.rebuilt = True
        return activity

    def rehydrate(self, activity: as_Activity) -> as_Activity:
        """No-op: parse already returns the rehydrated activity."""
        return activity


class ReplayDispatchAdapter:
    """Dispatch adapter for a replay of a queued item the inbox may retry.

    Wraps the delivery's own dispatch adapter.  A raised dispatch is recorded
    on *attempt* and re-raised to ``DispatchNode``, which rejects the attempt
    and asks for the sender's internal-error fault.  The fault is held, not
    sent: an attempt that is re-queued may still succeed, and a fault sent
    before that success would be false (ASK-07-010, ASK-07-007).  The queue
    drain sends it only when the item is dead-lettered or dropped
    (:meth:`send_held_fault`).

    Args:
        inner: The dispatch adapter that dispatches and queues the fault.
        attempt: The drain's record of the current attempt.
    """

    def __init__(self, inner: DispatchAdapter, attempt: ReplayAttempt) -> None:
        self._inner = inner
        self._attempt = attempt

    def dispatch(self, event: VultronEvent) -> HandlerResult:
        """Dispatch, recording a raise before it reaches ``DispatchNode``."""
        self._attempt.dispatched = True
        try:
            return self._inner.dispatch(event)
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
        and none is held when the attempt failed before dispatch.  A fault
        that cannot be queued is logged, never raised: the item is already
        settled.
        """
        held = self._attempt.fault
        if held is None:
            return
        event, failure_class = held
        try:
            self._inner.emit_processing_fault(event, failure_class)
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


def _retry_or_dead_letter(
    item_id: str,
    actor_id: str,
    failure: tuple[str, str],
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
        failure: The failure reason code and the last error.
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
    reason, last_error = failure
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
            "Inbox item activity_id=%s exhausted %d processing attempts for"
            " actor_id=%s; moved to dead letter (IE-06-004).",
            item_id,
            total,
            actor_id,
        )
        return True
    retry.set_inbox_attempt_count(item_id, total)
    queue_dl.inbox_append(item_id)
    logger.error(
        "Error processing inbox item activity_id=%s for actor_id=%s"
        " (attempt %d/%d); re-queuing for retry (IE-06-004).",
        item_id,
        actor_id,
        total,
        max_attempts,
    )
    return False


def drain_inbox_queue(
    actor_dl: DataLayer,
    actor_id: str,
    dispatch: DispatchAdapter,
    queue: PendingCaseQueuePort,
    staging: InlineObjectStaging,
    actor_config: ActorConfig | None,
    max_attempts: int,
) -> None:
    """Replay every item queued in *actor_dl*'s inbox, with bounded retry.

    Each attempt is a whole run of :func:`process_payload`: a failed act
    keeps nothing, so a retry re-runs the act from the start (ADR-0151).  A
    re-queued item goes to the back of the queue and is attempted again in
    the same drain, so the retries are not spaced in time.  An attempt that
    fails is settled here (IE-06-004):

    - a ``VultronProtocolViolationError`` is a permanent failure: the item is
      dropped, and its sender answered with the fault ``DispatchNode`` asked
      for;
    - any other raise, or a rejection after the rebuild and before dispatch
      (:meth:`ReplayAttempt.settle_rejection`), re-queues the item,
      unanswered, until ``max_attempts`` is used up, then dead-letters it and
      answers its sender (ASK-07-010).

    Every other attempt settles the item, and clears its attempt count.

    Args:
        actor_dl: The receiving actor's DataLayer, which holds the queue.
        actor_id: Canonical URI of the receiving actor.
        dispatch: The delivery's dispatch adapter, wrapped for each replay.
        queue: The pending-case queue port.
        staging: The inbox run's staging, which holds each item for replay.
        actor_config: The receiving actor's configuration, or ``None``.
        max_attempts: ``AppConfig.max_inbox_retry_attempts``.
    """
    attempt = ReplayAttempt()
    ingress = StoredActivityIngressAdapter(
        dl=actor_dl, staging=staging, attempt=attempt
    )
    replay_dispatch = ReplayDispatchAdapter(dispatch, attempt)
    # SqliteDataLayer satisfies RetryStore structurally, as for the outbox.
    retry = cast(RetryStore, actor_dl)
    while actor_dl.inbox_list():
        item_id = actor_dl.inbox_pop()
        if item_id is None:
            break
        attempt.begin()
        outcome = process_payload(
            item_id,
            ingress,
            replay_dispatch,
            queue,
            actor_config=actor_config,
        )
        logger.debug(
            "run_inbox_pipeline: replayed status=%s context_id=%s",
            outcome.status,
            outcome.context_id,
        )
        warn_if_rejected(outcome, actor_id, replayed=True)
        attempt.settle_rejection(outcome)

        if attempt.failure is not None and not attempt.permanent:
            if _retry_or_dead_letter(
                item_id,
                actor_id,
                attempt.failure,
                actor_dl,
                retry,
                max_attempts,
                staging,
            ):
                replay_dispatch.send_held_fault()
            continue

        if attempt.failure is not None:
            logger.error(
                "Inbox item activity_id=%s for actor_id=%s raised a protocol"
                " violation; dropped as a permanent failure (IE-06-004).",
                item_id,
                actor_id,
            )
            replay_dispatch.send_held_fault()
        # Settled: a count an earlier attempt or run stored has no further use.
        retry.clear_inbox_attempt_count(item_id)
