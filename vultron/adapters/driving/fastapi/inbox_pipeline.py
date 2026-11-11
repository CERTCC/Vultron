#!/usr/bin/env python
"""Injectable inbox pipeline for unit-level routing and deferral tests."""

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
from datetime import datetime
from typing import cast

from vultron.adapters.driving.fastapi.inbox_handler import (
    dispatch,
    make_dispatcher,
    prepare_for_dispatch,
)
from vultron.adapters.driving.fastapi.inbox_pending_queue import (
    _activity_context_id,
    _case_window_is_open,
    _expire_pending_case_activities,
    _queue_pending_case_activity,
    _replay_pending_case_activities,
)
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.core.behaviors.bridge.act_instant import (
    act_instant_in_tree_run,
    open_received_act,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import (
    VultronEvent,
    is_case_bootstrap,
    is_deferral_exempt,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.core.services.received_activity import (
    held_received_record,
)
from vultron.core.services.received_holding import (
    held_for_replay,
    hold_for_replay as hold_body_for_replay,
)
from vultron.errors import (
    VultronProtocolViolationError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)

#: Re-queues one activity may consume before :class:`InboxPipeline` drops it.
#: A failure that persists past this many retries is treated as permanent, so
#: a message that always raises cannot loop through the inbox forever (#2901).
MAX_REQUEUE_ATTEMPTS: int = 3


def _scalar_actor_ref(value: object) -> str | None:
    """Return an actor ID string from a scalar ref-like value."""
    if isinstance(value, str) and value:
        return value
    actor_id = getattr(value, "id_", None)
    if isinstance(actor_id, str) and actor_id:
        return actor_id
    return None


def _receiving_actor_id(activity: as_Activity) -> str | None:
    """Extract the canonical receiving actor ID from ``activity.to``."""
    to_value = getattr(activity, "to", None)
    if isinstance(to_value, list):
        for item in to_value:
            actor_id = _scalar_actor_ref(item)
            if actor_id is not None:
                return actor_id
        return None
    return _scalar_actor_ref(to_value)


def _record_the_wait_for_the_replay(
    *,
    body_store: DataLayer,
    queue_dl: DataLayer,
    activity_id: str,
    case_id: str,
) -> None:
    """Make the wait on *case_id* findable from *queue_dl*.

    This harness keeps the held body on its own store and the per-case record
    on the receiving actor's.  The replay reads which activities wait from
    the same store as that record, so when the two differ the body is held
    there as well; the stores agree in the production path, where this is one
    read of one record (``FastAPIQueuePort``).
    """
    bodies = cast(CasePersistence, body_store)
    queue = cast(CasePersistence, queue_dl)
    if bodies.actor_id == queue.actor_id:
        return
    held = held_received_record(bodies, activity_id)
    if held is None or held.received_body is None:
        return
    hold_body_for_replay(
        queue,
        activity_id,
        held.received_body,
        received_at=held.received_at,
        replay_rows_json=held.replay_rows_json,
        awaiting_case_id=case_id,
        verified_proofs=held.verified_proofs,
    )


class InboxPipeline:
    """Process one inbox item through rehydrate → extract → defer/dispatch."""

    def __init__(self, dispatcher: ActivityDispatcher, dl: DataLayer) -> None:
        self._dispatcher = dispatcher
        self._dl = dl
        self._requeue_counts: dict[str, int] = {}

    def _requeue(
        self,
        activity_id: str,
        queue_dl: DataLayer | None,
        actor_id: str | None,
        staging: InlineObjectStaging,
        at: datetime,
    ) -> bool:
        """Re-queue *activity_id* unless its retry budget is spent.

        The rebuild released the record holding the activity, so a re-queued
        item is held again first, stamped *at*, its arrival, or the retry
        would find nothing.

        Returns ``True`` when the item was re-queued, ``False`` when it had
        already been re-queued :data:`MAX_REQUEUE_ATTEMPTS` times and is
        dropped instead (#2901).
        """
        attempts = self._requeue_counts.get(activity_id, 0) + 1
        if attempts > MAX_REQUEUE_ATTEMPTS:
            logger.error(
                "Inbox item '%s' for actor '%s' still failing after %d"
                " re-queues — dropping (retry limit reached)",
                activity_id,
                actor_id,
                MAX_REQUEUE_ATTEMPTS,
            )
            return False
        self._requeue_counts[activity_id] = attempts
        staging.hold_again(activity_id, received_at=at)
        (queue_dl if queue_dl is not None else self._dl).inbox_append(
            activity_id
        )
        logger.info(
            "Re-queued inbox item '%s' for actor '%s' for retry (%d of %d)",
            activity_id,
            actor_id,
            attempts,
            MAX_REQUEUE_ATTEMPTS,
        )
        return True

    def process(self, activity_id: str) -> VultronEvent | None:
        """Process one queued activity ID, as one act at its arrival stamp.

        The act's instant is the arrival stamp the item's held record
        carries, as in the production queue drain (ADR-0176).  With no
        record owing the item's replay there is nothing to rebuild, so
        ``None`` is returned.
        """
        held = held_for_replay(cast(CasePersistence, self._dl), activity_id)
        if held is None:
            logger.error(
                "Inbox item %s has no held record owing its replay",
                activity_id,
            )
            # Not re-queued, so a later failure starts with the full budget.
            self._requeue_counts.pop(activity_id, None)
            return None
        with (
            open_received_act(held.received_at) as at,
            act_instant_in_tree_run(at),
        ):
            return self._process(activity_id, at)

    def _process(self, activity_id: str, at: datetime) -> VultronEvent | None:
        """Process one queued activity ID within its act, at *at*.

        The activity is rebuilt from the record that holds it for the inbox
        replay (its own ``ReceivedActivityRecord``), never read under its own
        id: the receiver keeps no copy of a received activity there
        (DL-06-006).

        Returns the dispatched ``VultronEvent`` or ``None`` when processing is
        deferred or an error prevents dispatch.  A protocol violation is
        dropped at once; any other error re-queues the item, up to
        :data:`MAX_REQUEUE_ATTEMPTS` times per item.  The item's count is
        cleared on every exit that does not re-queue it, so a later failure
        starts with the full budget.
        """
        queue_dl: DataLayer | None = None
        receiving_actor_id: str | None = None
        requeued = False
        staging = InlineObjectStaging(self._dl)
        try:
            obj = staging.rehydrate_deferred(activity_id)
            if not isinstance(obj, as_Activity):
                logger.error(
                    "Inbox item %s holds no activity to rebuild",
                    activity_id,
                )
                return None

            receiving_actor_id = _receiving_actor_id(obj)
            if receiving_actor_id is None:
                logger.error(
                    "InboxPipeline could not resolve receiving actor for '%s'",
                    activity_id,
                )
                return None

            queue_dl = cast(
                DataLayer, self._dl.clone_for_actor(receiving_actor_id)
            )

            event = prepare_for_dispatch(activity=obj)
            event = event.model_copy(
                update={"receiving_actor_id": receiving_actor_id}
            )
            case_id = _activity_context_id(obj, event)

            if (
                case_id is not None
                and not is_deferral_exempt(event)
                and not isinstance(self._dl.read(case_id), VulnerabilityCase)
            ):
                if _expire_pending_case_activities(
                    case_id=case_id, queue_dl=queue_dl, at=at
                ):
                    return None
                # Read before the hold: the hold is what makes this activity
                # one of the waiting, so only a reading taken first tells a
                # first arrival from a redelivery of the only waiter
                # (CBT-03-003).
                window_already_open = _case_window_is_open(queue_dl, case_id)
                # Held before it is queued: the record is its only copy, and
                # the hold is what records the wait, so it must name the case
                # or nothing will ever replay it (IO-03-009, ADR-0154).
                staging.hold_for_replay(
                    event.activity_id,
                    received_at=at,
                    awaiting_case_id=case_id,
                )
                # This harness holds bodies on its own store and keeps the
                # per-case record on the receiving actor's, which the
                # production path does not split (``FastAPIQueuePort`` uses
                # one store for both).  The replay reads the waits from the
                # same store as that record, so the wait is recorded there
                # too; before ADR-0154 the queued id played this part.
                _record_the_wait_for_the_replay(
                    body_store=self._dl,
                    queue_dl=queue_dl,
                    activity_id=event.activity_id,
                    case_id=case_id,
                )
                _queue_pending_case_activity(
                    queue_dl=queue_dl,
                    case_id=case_id,
                    case_actor_id=event.actor_id,
                    window_already_open=window_already_open,
                    at=at,
                )
                return None

            result = dispatch(
                event=event, dl=self._dl, dispatcher=self._dispatcher
            )
            if (
                result.took_effect
                and is_case_bootstrap(event)
                and case_id is not None
            ):
                _replay_pending_case_activities(
                    case_id=case_id,
                    dl=self._dl,
                    queue_dl=queue_dl,
                    at=at,
                )
            return event
        except VultronProtocolViolationError:
            logger.exception(
                "Protocol violation in inbox item '%s'"
                " — not re-queuing (permanent failure)",
                activity_id,
            )
            return None
        except VultronValidationError:
            logger.warning(
                "Validation error processing inbox item '%s'",
                activity_id,
                exc_info=True,
            )
            requeued = self._requeue(
                activity_id, queue_dl, receiving_actor_id, staging, at
            )
            return None
        except Exception:
            logger.exception(
                "Error processing inbox item '%s' in InboxPipeline",
                activity_id,
            )
            requeued = self._requeue(
                activity_id, queue_dl, receiving_actor_id, staging, at
            )
            return None
        finally:
            if not requeued:
                self._requeue_counts.pop(activity_id, None)


def build_test_pipeline(dl: DataLayer) -> InboxPipeline:
    """Build a test pipeline with production dispatcher wiring."""
    return InboxPipeline(dispatcher=make_dispatcher(), dl=dl)
