#!/usr/bin/env python

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

"""Inbox/outbox queues, delivery attempt counters and the dead-letter store.

Each of these lives in its owning actor's store (ADR-0073), so none of these
functions takes or filters on an ``actor_id``.  That removes a whole class of
defect in which a queue was written under one spelling of an actor id and read
under another — the cause of BUG-2026040901 and of the ``outbox_list()``
requires-``clone_for_actor`` pitfall.

``record_outbox_item(actor_id, ...)`` and ``outbox_list_for_actor(actor_id)``
used to exist so that an unscoped DataLayer could name the actor explicitly.
Every one of their call sites passed the *executing* actor's own id, so with a
mandatory actor scope they are exactly :func:`outbox_append` and
:func:`outbox_list` and have been folded into them.

The attempt counters and dead-letter store (OX-13-001–004) arrived after the
per-actor split and are scoped the same way: delivery bookkeeping about an
actor's own outbox is that actor's own data, so it is keyed on ``activity_id``
alone within the actor's store rather than on ``(actor_id, activity_id)``
within a shared one.
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlmodel import Session, col, select

from vultron.adapters.outbox_dead_letter import OutboxDeadLetterEntry

from .schema import OutboxAttemptEntry, QueueEntry

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for typing only
    # ``datalayer`` imports this module to build its own methods, so the name
    # can only be a forward reference here.  It was ``Any``, which said nothing
    # about the ``_engine`` attribute every function below reaches for
    # (CS-11-001 forbids an unjustified ``Any``).
    from .datalayer import SqliteDataLayer

logger = logging.getLogger(__name__)


def _queue_list(dl: "SqliteDataLayer", queue: str) -> list[str]:
    """Return every activity ID in *queue*, in insertion order."""
    with Session(dl._engine) as session:
        stmt = (
            select(QueueEntry)
            .where(QueueEntry.queue == queue)
            .order_by(col(QueueEntry.id))
        )
        rows = session.exec(stmt).all()
    return [row.activity_id for row in rows]


def _queue_pop(dl: "SqliteDataLayer", queue: str) -> str | None:
    """Remove and return the oldest activity ID in *queue*."""
    with Session(dl._engine) as session:
        stmt = (
            select(QueueEntry)
            .where(QueueEntry.queue == queue)
            .order_by(col(QueueEntry.id))
            .limit(1)
        )
        row = session.exec(stmt).first()
        if row is None:
            return None
        activity_id = row.activity_id
        session.delete(row)
        session.commit()
    return activity_id


def _queue_append(dl: "SqliteDataLayer", queue: str, activity_id: str) -> None:
    """Append *activity_id* to *queue*."""
    with Session(dl._engine) as session:
        session.add(QueueEntry(queue=queue, activity_id=activity_id))
        session.commit()


def inbox_append(
    dl: "SqliteDataLayer",
    activity_id: str,
) -> None:
    """Append an activity ID to this actor's inbox queue.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the activity to enqueue.
    """
    _queue_append(dl, "inbox", activity_id)


def inbox_list(dl: "SqliteDataLayer") -> list[str]:
    """Return all activity IDs in this actor's inbox, in insertion order.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        List of activity ID strings in insertion order.
    """
    return _queue_list(dl, "inbox")


def inbox_pop(dl: "SqliteDataLayer") -> str | None:
    """Remove and return the oldest activity ID from the inbox.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        The oldest activity ID string, or ``None`` if empty.
    """
    return _queue_pop(dl, "inbox")


def outbox_append(
    dl: "SqliteDataLayer",
    activity_id: str,
) -> None:
    """Append an activity ID to this actor's outbox queue.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the activity to enqueue.
    """
    _queue_append(dl, "outbox", activity_id)
    if dl._enqueue_callback is not None:
        try:
            dl._enqueue_callback(dl._actor_id)
        except Exception:  # noqa: BLE001
            logger.warning(
                "outbox_append: enqueue_callback raised for actor '%s'",
                dl._actor_id,
            )


def outbox_list(dl: "SqliteDataLayer") -> list[str]:
    """Return all activity IDs in this actor's outbox, in insertion order.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        List of activity ID strings in insertion order.
    """
    return _queue_list(dl, "outbox")


def outbox_pop(dl: "SqliteDataLayer") -> str | None:
    """Remove and return the oldest activity ID from the outbox.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        The oldest activity ID string, or ``None`` if empty.
    """
    return _queue_pop(dl, "outbox")


# ---------------------------------------------------------------------------
# Per-activity outbox attempt counter (OX-13-001)
# ---------------------------------------------------------------------------


def get_outbox_attempt_count(
    dl: "SqliteDataLayer",
    activity_id: str,
) -> int:
    """Return this actor's delivery attempt count for *activity_id* (0 if unseen).

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the outbox activity to query.

    Returns:
        Current attempt count, or ``0`` when no record exists.
    """
    with Session(dl._engine) as session:
        stmt = select(OutboxAttemptEntry).where(
            OutboxAttemptEntry.activity_id == activity_id
        )
        row = session.exec(stmt).first()
    return row.attempt_count if row is not None else 0


def set_outbox_attempt_count(
    dl: "SqliteDataLayer",
    activity_id: str,
    count: int,
) -> None:
    """Upsert this actor's delivery attempt count for *activity_id*.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the outbox activity.
        count: New attempt count to persist.
    """
    with Session(dl._engine) as session:
        stmt = select(OutboxAttemptEntry).where(
            OutboxAttemptEntry.activity_id == activity_id
        )
        row = session.exec(stmt).first()
        if row is None:
            session.add(
                OutboxAttemptEntry(
                    activity_id=activity_id,
                    attempt_count=count,
                )
            )
        else:
            row.attempt_count = count
            session.add(row)
        session.commit()


def clear_outbox_attempt_count(
    dl: "SqliteDataLayer",
    activity_id: str,
) -> None:
    """Remove this actor's attempt count entry for *activity_id*.

    Called after an activity is dead-lettered so the side-table does not
    accumulate stale rows (OX-13-002).

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the outbox activity whose counter to remove.
    """
    with Session(dl._engine) as session:
        stmt = select(OutboxAttemptEntry).where(
            OutboxAttemptEntry.activity_id == activity_id
        )
        row = session.exec(stmt).first()
        if row is not None:
            session.delete(row)
            session.commit()


# ---------------------------------------------------------------------------
# Dead-letter store (OX-13-002, OX-13-004)
# ---------------------------------------------------------------------------


def dead_letter_append(
    dl: "SqliteDataLayer",
    activity_id: str,
    reason: str,
    total_attempts: int,
    failed_recipients: list[str],
) -> None:
    """Write an exhausted outbox activity to this actor's dead-letter store.

    Constructs an :class:`OutboxDeadLetterEntry` and persists it via
    ``dl.save()`` so that operators can inspect it without log access
    (OX-13-002).

    ``entry.actor_id`` is taken from ``dl.actor_id`` rather than from a
    parameter.  The entry describes *this* actor's failed delivery attempt, and
    under ADR-0073 the store already fixes whose outbox that was — so there is
    no second identity to pass and none to get wrong.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the activity that exhausted its delivery budget.
        reason: Short machine-readable reason code.
        total_attempts: Total cumulative attempt count at exhaustion.
        failed_recipients: Actor IDs that could not be reached.
    """
    actor = dl.actor_id
    entry = OutboxDeadLetterEntry(
        activity_id=activity_id,
        actor_id=actor,
        reason=reason,
        total_attempts=total_attempts,
        failed_recipients=list(failed_recipients),
        recorded_at=datetime.now(UTC),
    )
    dl.save(entry)
    logger.debug(
        "dead_letter_append: stored OutboxDeadLetterEntry for activity '%s'"
        " (actor '%s', attempts=%d)",
        activity_id,
        actor,
        total_attempts,
    )


def dead_letter_list(
    dl: "SqliteDataLayer",
) -> list[OutboxDeadLetterEntry]:
    """Return this actor's dead-letter entries (OX-13-004).

    Reconstructs :class:`OutboxDeadLetterEntry` objects from the raw dicts
    stored in ``vultron_objects``.  Only this actor's entries are visible: a
    node-wide operator view must fan out over
    :func:`~vultron.adapters.driven.actor_hosts.hosted_actor_ids` and call this
    per actor.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        List of :class:`OutboxDeadLetterEntry` objects in no guaranteed order.
    """
    raw = dl.by_type("OutboxDeadLetterEntry")
    entries: list[OutboxDeadLetterEntry] = []
    for data in raw.values():
        try:
            entries.append(OutboxDeadLetterEntry.model_validate(data))
        except Exception:  # noqa: BLE001
            logger.warning(
                "dead_letter_list: could not reconstruct OutboxDeadLetterEntry"
                " from stored data: %r",
                data,
            )
    return entries
