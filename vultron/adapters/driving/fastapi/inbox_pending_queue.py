#!/usr/bin/env python
"""Pre-bootstrap pending case inbox queue management.

Handles queuing, expiry, and replay of inbox activities that arrive
before the local case replica exists (CBT-03-003, CBT-03-004).
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
from datetime import timezone

from vultron.config import get_config
from vultron.core.models.events import VultronEvent
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.datalayer import ActorScopedDataLayer, DataLayer
from vultron.wire.as2.factories.case import bootstrap_replay_question_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


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
    queue_dl: ActorScopedDataLayer,
    case_id: str,
    activity_id: str,
    case_actor_id: str | None = None,
) -> None:
    """Persist *activity_id* in the deferred queue for *case_id*.

    Records *case_actor_id* on the first write so that the expiry
    handler knows where to send a replay ``Question`` (CBT-03-004).
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

    Checks whether the ``VultronPendingCaseInbox`` for *case_id* has
    been held for longer than *timeout_seconds* (defaults to
    ``AppConfig.pre_bootstrap_queue_timeout_seconds``).  When expired:

    1. Logs a WARNING for each dropped activity ID (CBT-03-003).
    2. Deletes the queue record.
    3. Emits a ``Question`` to the recorded ``case_actor_id`` asking
       for the bootstrap ``Create(VulnerabilityCase)`` to be resent
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
    queues (no subsequent traffic) are reclaimed when bootstrap or a
    new activity arrives.
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

    Before replaying, checks whether the pending queue has expired.  If
    it has, the queue is dropped instead of replayed (CBT-03-003).  This
    handles the case where bootstrap arrives after the expiry window —
    the bootstrap itself is accepted, but the stale queued items are
    discarded.

    Args:
        case_id: URI of the case whose pending queue should be drained.
        dl: Shared DataLayer used for case lookup and Question
            persistence.
        queue_dl: Actor-scoped DataLayer for queue management.
        actor_id: Canonical URI of the receiving actor, used when
            building a replay Question on expiry.  Defaults to ``""``
            when not provided (best-effort; expiry Warning is still
            logged).
    """
    if not isinstance(dl.read(case_id), VulnerabilityCase):
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
