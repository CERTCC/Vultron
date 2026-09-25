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
from typing import cast

from vultron.adapters.driving.fastapi.inbox_handler import (
    dispatch,
    make_dispatcher,
    prepare_for_dispatch,
)
from vultron.adapters.driving.fastapi.inbox_pending_queue import (
    _activity_context_id,
    _expire_pending_case_activities,
    _queue_pending_case_activity,
    _replay_pending_case_activities,
)
from vultron.core.models.events import VultronEvent, is_case_bootstrap
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.errors import (
    VultronProtocolViolationError,
    VultronValidationError,
)
from vultron.wire.as2.rehydration import rehydrate
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


class InboxPipeline:
    """Process one inbox item through rehydrate → extract → defer/dispatch."""

    def __init__(self, dispatcher: ActivityDispatcher, dl: DataLayer) -> None:
        self._dispatcher = dispatcher
        self._dl = dl
        self._requeue_counts: dict[str, int] = {}

    def _requeue(self, activity_id: str, queue_dl: DataLayer | None) -> bool:
        """Re-queue *activity_id* unless its retry budget is spent.

        Returns ``True`` when the item was re-queued, ``False`` when it had
        already been re-queued :data:`MAX_REQUEUE_ATTEMPTS` times and is
        dropped instead (#2901).
        """
        attempts = self._requeue_counts.get(activity_id, 0) + 1
        if attempts > MAX_REQUEUE_ATTEMPTS:
            self._requeue_counts.pop(activity_id, None)
            logger.error(
                "Inbox item '%s' still failing after %d re-queues"
                " — dropping (retry limit reached)",
                activity_id,
                MAX_REQUEUE_ATTEMPTS,
            )
            return False
        self._requeue_counts[activity_id] = attempts
        (queue_dl if queue_dl is not None else self._dl).inbox_append(
            activity_id
        )
        logger.info(
            "Re-queued inbox item '%s' for retry (%d of %d)",
            activity_id,
            attempts,
            MAX_REQUEUE_ATTEMPTS,
        )
        return True

    def process(self, activity_id: str) -> VultronEvent | None:
        """Process one queued activity ID.

        Returns the dispatched ``VultronEvent`` or ``None`` when processing is
        deferred or an error prevents dispatch.  A protocol violation is
        dropped at once; any other error re-queues the item, up to
        :data:`MAX_REQUEUE_ATTEMPTS` times per item.
        """
        queue_dl: DataLayer | None = None
        try:
            obj = rehydrate(activity_id, dl=self._dl)
            if not isinstance(obj, as_Activity):
                logger.error(
                    "Rehydrated inbox item %s is not an Activity: %s",
                    activity_id,
                    type(obj).__name__,
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
                and not is_case_bootstrap(event)
                and not isinstance(self._dl.read(case_id), VulnerabilityCase)
            ):
                if _expire_pending_case_activities(
                    case_id=case_id,
                    actor_id=receiving_actor_id,
                    dl=self._dl,
                    queue_dl=queue_dl,
                ):
                    return None
                _queue_pending_case_activity(
                    queue_dl=queue_dl,
                    case_id=case_id,
                    activity_id=event.activity_id,
                    case_actor_id=event.actor_id,
                )
                return None

            dispatch(event=event, dl=self._dl, dispatcher=self._dispatcher)
            self._requeue_counts.pop(activity_id, None)
            if is_case_bootstrap(event) and case_id is not None:
                _replay_pending_case_activities(
                    case_id=case_id,
                    dl=self._dl,
                    queue_dl=queue_dl,
                    actor_id=receiving_actor_id,
                )
            return event
        except VultronProtocolViolationError:
            logger.error(
                "Protocol violation in inbox item '%s'"
                " — not re-queuing (permanent failure)",
                activity_id,
                exc_info=True,
            )
            return None
        except VultronValidationError:
            logger.warning(
                "Validation error processing inbox item '%s'",
                activity_id,
                exc_info=True,
            )
            self._requeue(activity_id, queue_dl)
            return None
        except Exception:
            logger.error(
                "Error processing inbox item '%s' in InboxPipeline",
                activity_id,
                exc_info=True,
            )
            self._requeue(activity_id, queue_dl)
            return None


def build_test_pipeline(dl: DataLayer) -> InboxPipeline:
    """Build a test pipeline with production dispatcher wiring."""
    return InboxPipeline(dispatcher=make_dispatcher(), dl=dl)
