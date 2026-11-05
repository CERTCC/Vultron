#!/usr/bin/env python
"""Pre-bootstrap pending case inbox queue management.

Handles queuing, expiry, and replay of inbox activities that arrive
before the local case replica exists (CBT-03-001, CBT-03-003, CBT-03-006).
A dropped activity is not asked for again here: the CASE_MANAGER recovers an
Invite its addressee never answered (ADR-0163).

**Which activities wait is read from the activities, not from a list.**  Each
waiting message names the case it waits on, on its own
``ReceivedActivityRecord`` (``awaiting_case_id``, ADR-0154), so the queue is
a read over those records in arrival order
(``received_holding.records_awaiting_case``).  The retired
``VultronPendingCaseInbox.activity_ids`` list held the same thing a second
time, and a queued id whose body had been lost was a message lost silently.

``VultronPendingCaseInbox`` stays for what is *not* per-message: the stub
Invite's trust anchor, and ``queued_at``, the one clock per case that opens
the CBT-03-001 window.  Keeping that clock per case preserves today's
behaviour, including its restart when a record that held only an anchor
takes its first waiting message, so an invitee's thinking time is not
charged against the queue.
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
from datetime import UTC
from typing import cast

from vultron.config import get_config
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import VultronEvent, resolve_case_context_id
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.received_holding import (
    discard_holding,
    records_awaiting_case,
    stop_awaiting_case,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


def _store(dl: DataLayer) -> CasePersistence:
    """*dl* as the narrow core port the holding services take.

    The full ``DataLayer`` satisfies ``CasePersistence`` structurally but is
    not assignable to it, because ``clone_for_actor`` returns the wider type.
    """
    return cast(CasePersistence, dl)


def _activity_context_id(
    activity: as_Activity, event: VultronEvent
) -> str | None:
    """Return the case context ID carried by an activity, if any.

    Thin wrapper over the core resolver so that the adapter layer and the
    core inbox BT pipeline agree on which case an activity belongs to.
    """
    return resolve_case_context_id(
        event, wire_context=getattr(activity, "context", None)
    )


def _case_window_is_open(queue_dl: DataLayer, case_id: str) -> bool:
    """Whether anything already waits on *case_id*, so its window is running.

    Read this **before** holding the activity being queued: the hold is what
    makes it one of the waiting (ADR-0154), so a reading taken afterwards
    cannot tell a first arrival from a redelivery of the only waiter.
    """
    return bool(records_awaiting_case(_store(queue_dl), case_id))


def _queue_pending_case_activity(
    queue_dl: DataLayer,
    case_id: str,
    case_actor_id: str | None = None,
    *,
    window_already_open: bool,
) -> None:
    """Open, or keep open, the expiry window for *case_id*'s waiting messages.

    The activity being queued is not named here, because nothing per-message
    is kept on this record: the activity already names the case it waits on,
    the caller having held it first (``hold_for_replay``, DL-06-006), which
    is what records the wait.  This only maintains the per-case record.

    Records *case_actor_id*, the sender of the first activity queued, on the
    first write.  It admits no sender: only a stub Invite anchors trust in
    the same record (``invite_anchored``, PCR-03-004).

    The expiry window opens with the first activity queued and runs from
    there (CBT-03-001, CBT-03-003).  *window_already_open* says whether
    anything was waiting on *case_id* **before** the caller held this
    activity, which is the only thing that decides it:

    - nothing was waiting, so this activity opens the window and
      ``queued_at`` restarts.  A record with only a stub Invite's trust
      anchor behind it is this case, so the time an invitee took to answer
      its Invite is not charged to the queue;
    - something was waiting, so the window is already running and is left
      alone.  A *redelivery* of an activity that is itself the only one
      waiting is this case too: it must not restart the clock, or a sender
      redelivering inside the window would hold the queue open for ever
      (CBT-03-003).

    The caller must read this before holding the activity, because the hold
    is what makes it one of the waiting (ADR-0154).
    """
    pending_id = VultronPendingCaseInbox.build_id(case_id)
    pending = queue_dl.read(pending_id)
    if isinstance(pending, VultronPendingCaseInbox):
        if window_already_open:
            return
        queue_dl.save(
            VultronPendingCaseInbox.model_validate(
                {**pending.model_dump(), "queued_at": now_utc()}
            )
        )
        return

    queue_dl.save(
        VultronPendingCaseInbox(
            case_id=case_id,
            case_actor_id=case_actor_id,
        )
    )


def _expire_pending_case_activities(
    case_id: str,
    queue_dl: DataLayer,
    timeout_seconds: int | None = None,
) -> bool:
    """Drop an expired pre-bootstrap queue (CBT-03-003).

    Checks whether the ``VultronPendingCaseInbox`` for *case_id* has
    held queued activities for longer than *timeout_seconds* (defaults to
    ``AppConfig.pre_bootstrap_queue_timeout_seconds``).  A record holding no
    activity — a stub Invite's trust anchor alone — has nothing to expire.
    When expired:

    1. Logs a WARNING for each dropped activity ID (CBT-03-006).
    2. Deletes the record holding each activity for its replay, and the
       queue record — unless a stub Invite anchored it (``invite_anchored``,
       PCR-03-004 path b), in which case only its queue is emptied: the
       anchor is what admits the case's later ``Announce``.

    It sends nothing.  A dropped Invite is the CASE_MANAGER's to resend, once
    the receiver states its ledger position after its replica is seeded
    (ADR-0163).

    Args:
        case_id: URI of the case whose pending queue should be checked.
        queue_dl: Actor-scoped DataLayer used to read and delete the queue.
        timeout_seconds: Expiry window in seconds.  ``None`` reads from
            ``get_config().pre_bootstrap_queue_timeout_seconds``.

    Returns:
        ``True`` if the queue was expired and dropped; ``False`` if the
        queue is still within the window or does not exist.

    Trigger: this check is called on inbox receipt so that any inbound
    activity for a pending case triggers expiry cleanup.  Cold
    queues (no subsequent traffic) are reclaimed when bootstrap or a
    new activity arrives.
    """
    if timeout_seconds is None:
        timeout_seconds = get_config().pre_bootstrap_queue_timeout_seconds

    pending_id = VultronPendingCaseInbox.build_id(case_id)
    pending = queue_dl.read(pending_id)
    if not isinstance(pending, VultronPendingCaseInbox):
        return False
    waiting = records_awaiting_case(_store(queue_dl), case_id)
    if not waiting:
        return False

    now = now_utc()
    queued_at = pending.queued_at
    if queued_at.tzinfo is None:
        queued_at = queued_at.replace(tzinfo=UTC)
    age_seconds = (now - queued_at).total_seconds()
    if age_seconds < timeout_seconds:
        return False

    for record in waiting:
        logger.warning(
            "Dropping expired pre-bootstrap activity '%s' for case '%s' "
            "(age %.0fs > timeout %ds) — resend required after bootstrap "
            "(CBT-03-006)",
            record.activity_id,
            case_id,
            age_seconds,
            timeout_seconds,
        )
        # The replay it was held for is given up (#3763, #4871).  An archive
        # intake wrote stays; a body held for nothing else goes (CLP-10-018).
        discard_holding(_store(queue_dl), record.activity_id)
    if not pending.invite_anchored:
        queue_dl.delete("PendingCaseInbox", pending_id)
    # An anchored record stays as it is: the stub Invite's trust anchor is
    # what admits the case's later Announce, and nothing per-message is left
    # on it to clear.
    logger.warning(
        "Pre-bootstrap queue for case '%s' expired after %.0fs; "
        "%d activity ID(s) dropped",
        case_id,
        age_seconds,
        len(waiting),
    )

    return True


def _replay_pending_case_activities(
    case_id: str,
    dl: DataLayer,
    queue_dl: DataLayer,
) -> None:
    """Move deferred activities for *case_id* back onto the live inbox queue.

    Before replaying, checks whether the pending queue has expired.  If
    it has, the queue and its record are dropped instead of replayed
    (CBT-03-003), a stub Invite's anchor included.  This
    handles the case where bootstrap arrives after the expiry window —
    the bootstrap itself is accepted, but the stale queued items are
    discarded.

    Args:
        case_id: URI of the case whose pending queue should be drained.
        dl: Shared DataLayer used for case lookup.
        queue_dl: Actor-scoped DataLayer for queue management.
    """
    if not isinstance(dl.read(case_id), VulnerabilityCase):
        return

    pending_id = VultronPendingCaseInbox.build_id(case_id)
    pending = queue_dl.read(pending_id)
    if not isinstance(pending, VultronPendingCaseInbox):
        return

    waiting_before = len(records_awaiting_case(_store(queue_dl), case_id))
    if _expire_pending_case_activities(case_id=case_id, queue_dl=queue_dl):
        logger.warning(
            "Bootstrap arrived for case '%s' but pre-bootstrap queue had "
            "already expired; dropped %d activity ID(s) — a fresh "
            "re-delivery is required",
            case_id,
            waiting_before,
        )
        # Expiry keeps a stub Invite's anchor, but the case is held now and
        # names its CASE_MANAGER itself, so the record has no use left.
        queue_dl.delete("PendingCaseInbox", pending_id)
        return

    waiting = records_awaiting_case(_store(queue_dl), case_id)
    for record in waiting:
        queue_dl.inbox_append(record.activity_id)
        # Queued, so no longer waiting on the case: the body stays held
        # until the drain replays it, and a second bootstrap for this case
        # does not queue it again.
        stop_awaiting_case(_store(queue_dl), record.activity_id)
    queue_dl.delete("PendingCaseInbox", pending_id)
    logger.info(
        "Queued %d deferred inbox activities for case '%s' after replica sync",
        len(waiting),
        case_id,
    )
