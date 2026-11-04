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

"""The actor's inbox and outbox FIFO queues.

Each queue lives in its owning actor's store (ADR-0073), so no function here
takes or filters on an ``actor_id``.  :func:`outbox_append` refuses a second
pending copy of an activity already queued.
"""

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import col, select

from ..schema import OUTBOX_PENDING_PREDICATE, QueueEntry
from ..transaction import run_after_commit

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for typing only
    # ``datalayer`` imports this module to build its own methods, so the name
    # can only be a forward reference here.  It was ``Any``, which said nothing
    # about the ``_engine`` attribute every function below reaches for
    # (CS-11-001 forbids an unjustified ``Any``).
    from ..datalayer import SqliteDataLayer


logger = logging.getLogger(__name__)


def _queue_list(dl: "SqliteDataLayer", queue: str) -> list[str]:
    """Return every activity ID in *queue*, in insertion order."""
    with dl._session() as session:
        stmt = (
            select(QueueEntry)
            .where(QueueEntry.queue == queue)
            .order_by(col(QueueEntry.id))
        )
        rows = session.exec(stmt).all()
    return [row.activity_id for row in rows]


def _queue_pop(dl: "SqliteDataLayer", queue: str) -> str | None:
    """Remove and return the oldest activity ID in *queue*."""
    with dl._session() as session:
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
    with dl._session() as session:
        session.add(QueueEntry(queue=queue, activity_id=activity_id))
        session.commit()


def _outbox_append_unless_pending(
    dl: "SqliteDataLayer", activity_id: str
) -> bool:
    """Append *activity_id* to the outbox unless it is already pending there.

    One ``INSERT ... ON CONFLICT DO NOTHING`` statement against the partial
    UNIQUE index on outbox rows (:data:`~.schema.OUTBOX_PENDING_INDEX`): the
    store itself refuses the duplicate, and SQLite runs the statement
    atomically, so two writers cannot both queue the id — on a file-backed
    store too, where sessions are not serialized (OX-06-002).  The conflict
    target repeats the index's ``WHERE`` clause, as SQLite requires for a
    partial index, so only the outbox can use this function.

    Returns:
        ``True`` when the id was queued, ``False`` when it was already pending.
    """
    stmt = (
        sqlite_insert(QueueEntry)
        .values(queue="outbox", activity_id=activity_id)
        .on_conflict_do_nothing(
            index_elements=["queue", "activity_id"],
            index_where=text(OUTBOX_PENDING_PREDICATE),
        )
        .returning(col(QueueEntry.id))
    )
    with dl._session() as session:
        queued_row = session.execute(stmt).scalar_one_or_none()
        session.commit()
    return queued_row is not None


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
) -> bool:
    """Append an activity ID to this actor's outbox queue unless it is pending.

    The outbox-id idempotency check (OX-06-002, ADR-0119): an id already
    waiting in this outbox is not queued a second time, so it is delivered
    once per queueing.  An id no longer pending is queued again; delivery
    popped it, and the receiver deduplicates a redelivery by id (ID-02-001).
    The enqueue callback runs only when a row was added.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the activity to enqueue.

    Returns:
        ``True`` when the id was queued, ``False`` when it was already pending.
    """
    if not _outbox_append_unless_pending(dl, activity_id):
        logger.debug(
            "outbox_append: activity '%s' already pending for actor '%s'"
            " — not queued again (OX-06-002)",
            activity_id,
            dl._actor_id,
        )
        return False
    callback = dl._enqueue_callback
    if callback is not None:

        def _notify() -> None:
            try:
                callback(dl._actor_id)
            except Exception:  # noqa: BLE001  # ruff-baseline #3326
                logger.warning(
                    "outbox_append: enqueue_callback raised for actor '%s'",
                    dl._actor_id,
                )

        # Inside a transaction the row is not visible to the drain until the
        # transaction commits, and is gone if it rolls back.
        run_after_commit(dl._engine, _notify)
    return True


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
