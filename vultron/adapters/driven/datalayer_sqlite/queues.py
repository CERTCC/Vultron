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

"""Inbox, outbox queue operations and outbox dead-letter store for the SQLite data layer."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from vultron.adapters.outbox_dead_letter import OutboxDeadLetterEntry

from .schema import OutboxAttemptEntry, QueueEntry

logger = logging.getLogger(__name__)


def inbox_append(
    dl: "Any",  # SqliteDataLayer
    activity_id: str,
) -> None:
    """Append an activity ID to this actor's inbox queue.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the activity to enqueue.
    """
    actor = dl._actor_id or ""
    with Session(dl._engine) as session:
        session.add(
            QueueEntry(actor_id=actor, queue="inbox", activity_id=activity_id)
        )
        session.commit()


def inbox_list(dl: "Any") -> list[str]:  # SqliteDataLayer
    """Return all activity IDs in this actor's inbox, in insertion order.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        List of activity ID strings in insertion order.
    """
    actor = dl._actor_id or ""
    with Session(dl._engine) as session:
        stmt = (
            select(QueueEntry)
            .where(
                QueueEntry.actor_id == actor,
                QueueEntry.queue == "inbox",
            )
            .order_by(col(QueueEntry.id))
        )
        rows = session.exec(stmt).all()
    return [row.activity_id for row in rows]


def inbox_pop(dl: "Any") -> str | None:  # SqliteDataLayer
    """Remove and return the oldest activity ID from the inbox.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        The oldest activity ID string, or ``None`` if empty.
    """
    actor = dl._actor_id or ""
    with Session(dl._engine) as session:
        stmt = (
            select(QueueEntry)
            .where(
                QueueEntry.actor_id == actor,
                QueueEntry.queue == "inbox",
            )
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


def outbox_append(
    dl: "Any",  # SqliteDataLayer
    activity_id: str,
) -> None:
    """Append an activity ID to this actor's outbox queue.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the activity to enqueue.
    """
    actor = dl._actor_id or ""
    with Session(dl._engine) as session:
        session.add(
            QueueEntry(actor_id=actor, queue="outbox", activity_id=activity_id)
        )
        session.commit()
    if dl._enqueue_callback is not None:
        try:
            dl._enqueue_callback(actor)
        except Exception:  # noqa: BLE001
            logger.warning(
                "outbox_append: enqueue_callback raised for actor '%s'",
                actor,
            )


def outbox_list(dl: "Any") -> list[str]:  # SqliteDataLayer
    """Return all activity IDs in this actor's outbox, in insertion order.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        List of activity ID strings in insertion order.
    """
    actor = dl._actor_id or ""
    with Session(dl._engine) as session:
        stmt = (
            select(QueueEntry)
            .where(
                QueueEntry.actor_id == actor,
                QueueEntry.queue == "outbox",
            )
            .order_by(col(QueueEntry.id))
        )
        rows = session.exec(stmt).all()
    return [row.activity_id for row in rows]


def outbox_list_for_actor(
    dl: "Any",  # SqliteDataLayer
    actor_id: str,
) -> list[str]:
    """Return all outbox activity IDs for *actor_id*, in insertion order.

    Unlike :func:`outbox_list`, this bypasses ``self._actor_id`` and
    reads the queue for the named actor directly — matching the write
    semantics of :func:`record_outbox_item`.

    Args:
        dl: The SqliteDataLayer instance.
        actor_id: Actor ID to query the outbox for.

    Returns:
        List of activity ID strings in insertion order.
    """
    with Session(dl._engine) as session:
        stmt = (
            select(QueueEntry)
            .where(
                QueueEntry.actor_id == actor_id,
                QueueEntry.queue == "outbox",
            )
            .order_by(col(QueueEntry.id))
        )
        rows = session.exec(stmt).all()
    return [row.activity_id for row in rows]


def outbox_pop(dl: "Any") -> str | None:  # SqliteDataLayer
    """Remove and return the oldest activity ID from the outbox.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        The oldest activity ID string, or ``None`` if empty.
    """
    actor = dl._actor_id or ""
    with Session(dl._engine) as session:
        stmt = (
            select(QueueEntry)
            .where(
                QueueEntry.actor_id == actor,
                QueueEntry.queue == "outbox",
            )
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


def record_outbox_item(
    dl: "Any",  # SqliteDataLayer
    actor_id: str,
    activity_id: str,
) -> None:
    """Queue an outbox item for *actor_id* regardless of this DL's scope.

    Bypasses ``self._actor_id`` to allow the shared or any actor-scoped
    DataLayer to write directly to a named actor's outbox queue.

    Args:
        dl: The SqliteDataLayer instance.
        actor_id: The actor whose outbox queue to append to.
        activity_id: The activity ID to enqueue.
    """
    with Session(dl._engine) as session:
        session.add(
            QueueEntry(
                actor_id=actor_id,
                queue="outbox",
                activity_id=activity_id,
            )
        )
        session.commit()
    if dl._enqueue_callback is not None:
        try:
            dl._enqueue_callback(actor_id)
        except Exception:  # noqa: BLE001
            logger.warning(
                "record_outbox_item: enqueue_callback raised"
                " for actor '%s'",
                actor_id,
            )


# ---------------------------------------------------------------------------
# Per-activity outbox attempt counter (OX-13-001)
# ---------------------------------------------------------------------------


def get_outbox_attempt_count(
    dl: "Any",  # SqliteDataLayer
    activity_id: str,
) -> int:
    """Return the cumulative delivery attempt count for *activity_id* (0 if unseen).

    Args:
        dl: The actor-scoped SqliteDataLayer instance.
        activity_id: ID of the outbox activity to query.

    Returns:
        Current attempt count, or ``0`` when no record exists.
    """
    actor = dl._actor_id or ""
    with Session(dl._engine) as session:
        stmt = select(OutboxAttemptEntry).where(
            OutboxAttemptEntry.actor_id == actor,
            OutboxAttemptEntry.activity_id == activity_id,
        )
        row = session.exec(stmt).first()
    return row.attempt_count if row is not None else 0


def set_outbox_attempt_count(
    dl: "Any",  # SqliteDataLayer
    activity_id: str,
    count: int,
) -> None:
    """Upsert the delivery attempt count for *activity_id*.

    Args:
        dl: The actor-scoped SqliteDataLayer instance.
        activity_id: ID of the outbox activity.
        count: New attempt count to persist.
    """
    actor = dl._actor_id or ""
    with Session(dl._engine) as session:
        stmt = select(OutboxAttemptEntry).where(
            OutboxAttemptEntry.actor_id == actor,
            OutboxAttemptEntry.activity_id == activity_id,
        )
        row = session.exec(stmt).first()
        if row is None:
            session.add(
                OutboxAttemptEntry(
                    actor_id=actor,
                    activity_id=activity_id,
                    attempt_count=count,
                )
            )
        else:
            row.attempt_count = count
            session.add(row)
        session.commit()


def clear_outbox_attempt_count(
    dl: "Any",  # SqliteDataLayer
    activity_id: str,
) -> None:
    """Remove the attempt count entry for *activity_id*.

    Called after an activity is dead-lettered so the side-table does not
    accumulate stale rows (OX-13-002).

    Args:
        dl: The actor-scoped SqliteDataLayer instance.
        activity_id: ID of the outbox activity whose counter to remove.
    """
    actor = dl._actor_id or ""
    with Session(dl._engine) as session:
        stmt = select(OutboxAttemptEntry).where(
            OutboxAttemptEntry.actor_id == actor,
            OutboxAttemptEntry.activity_id == activity_id,
        )
        row = session.exec(stmt).first()
        if row is not None:
            session.delete(row)
            session.commit()


# ---------------------------------------------------------------------------
# Dead-letter store (OX-13-002, OX-13-004)
# ---------------------------------------------------------------------------


def dead_letter_append(
    dl: "Any",  # SqliteDataLayer (actor-scoped)
    activity_id: str,
    reason: str,
    total_attempts: int,
    failed_recipients: list[str],
) -> None:
    """Write an exhausted outbox activity to the dead-letter store (OX-13-002).

    Constructs an :class:`OutboxDeadLetterEntry` and persists it via
    ``dl.save()`` so that operators can inspect it without log access.

    Args:
        dl: The actor-scoped SqliteDataLayer instance.
        activity_id: ID of the activity that exhausted its delivery budget.
        reason: Short machine-readable reason code.
        total_attempts: Total cumulative attempt count at exhaustion.
        failed_recipients: Actor IDs that could not be reached.
    """
    actor = dl._actor_id or ""
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
    dl: "Any",  # SqliteDataLayer
) -> list[OutboxDeadLetterEntry]:
    """Return all dead-letter entries readable from the DataLayer (OX-13-004).

    Reconstructs :class:`OutboxDeadLetterEntry` objects from the raw dicts
    stored in ``vultron_objects``.  Entries from all actors are included
    when called on the shared (unscoped) DataLayer.

    Args:
        dl: The SqliteDataLayer instance (shared or actor-scoped).

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
