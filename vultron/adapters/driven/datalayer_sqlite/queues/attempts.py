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

"""Per-queue delivery attempt counters (OX-13-001, IE-06-004).

Delivery bookkeeping about an actor's own queue is that actor's own data, so
it is keyed on ``activity_id`` alone within the actor's store.
"""

from typing import TYPE_CHECKING

from sqlmodel import select

from ..schema import QueueAttemptEntry

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for typing only
    # ``datalayer`` imports this module to build its own methods, so the name
    # can only be a forward reference here.  It was ``Any``, which said nothing
    # about the ``_engine`` attribute every function below reaches for
    # (CS-11-001 forbids an unjustified ``Any``).
    from ..datalayer import SqliteDataLayer


# ---------------------------------------------------------------------------
# Generic per-queue attempt counter (shared inbox/outbox mechanism, #4168)
# ---------------------------------------------------------------------------


def _get_queue_attempt_count(
    dl: SqliteDataLayer,
    queue: str,
    activity_id: str,
) -> int:
    """Return the attempt count for *activity_id* in *queue* (0 if unseen)."""
    with dl._session() as session:
        stmt = select(QueueAttemptEntry).where(
            QueueAttemptEntry.queue == queue,
            QueueAttemptEntry.activity_id == activity_id,
        )
        row = session.exec(stmt).first()
    return row.attempt_count if row is not None else 0


def _set_queue_attempt_count(
    dl: SqliteDataLayer,
    queue: str,
    activity_id: str,
    count: int,
) -> None:
    """Upsert the attempt count for *activity_id* in *queue*."""
    with dl._session() as session:
        stmt = select(QueueAttemptEntry).where(
            QueueAttemptEntry.queue == queue,
            QueueAttemptEntry.activity_id == activity_id,
        )
        row = session.exec(stmt).first()
        if row is None:
            session.add(
                QueueAttemptEntry(
                    queue=queue,
                    activity_id=activity_id,
                    attempt_count=count,
                )
            )
        else:
            row.attempt_count = count
            session.add(row)
        session.commit()


def _clear_queue_attempt_count(
    dl: SqliteDataLayer,
    queue: str,
    activity_id: str,
) -> None:
    """Remove the attempt count entry for *activity_id* in *queue*."""
    with dl._session() as session:
        stmt = select(QueueAttemptEntry).where(
            QueueAttemptEntry.queue == queue,
            QueueAttemptEntry.activity_id == activity_id,
        )
        row = session.exec(stmt).first()
        if row is not None:
            session.delete(row)
            session.commit()


# ---------------------------------------------------------------------------
# Per-activity outbox attempt counter (OX-13-001)
# ---------------------------------------------------------------------------


def get_outbox_attempt_count(
    dl: SqliteDataLayer,
    activity_id: str,
) -> int:
    """Return this actor's delivery attempt count for *activity_id* (0 if unseen).

    Delegates to the shared :func:`_get_queue_attempt_count` with
    ``queue="outbox"`` so inbox and outbox counters use the same backing table
    (``vultron_queue_attempts``) while keeping backward-compatible method names
    on the DataLayer.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the outbox activity to query.

    Returns:
        Current attempt count, or ``0`` when no record exists.
    """
    return _get_queue_attempt_count(dl, "outbox", activity_id)


def set_outbox_attempt_count(
    dl: SqliteDataLayer,
    activity_id: str,
    count: int,
) -> None:
    """Upsert this actor's delivery attempt count for *activity_id*.

    Delegates to the shared :func:`_set_queue_attempt_count` with
    ``queue="outbox"``.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the outbox activity.
        count: New attempt count to persist.
    """
    _set_queue_attempt_count(dl, "outbox", activity_id, count)


def clear_outbox_attempt_count(
    dl: SqliteDataLayer,
    activity_id: str,
) -> None:
    """Remove this actor's attempt count entry for *activity_id*.

    Called after an activity is dead-lettered so the side-table does not
    accumulate stale rows (OX-13-002).  Delegates to the shared
    :func:`_clear_queue_attempt_count` with ``queue="outbox"``.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the outbox activity whose counter to remove.
    """
    _clear_queue_attempt_count(dl, "outbox", activity_id)


# ---------------------------------------------------------------------------
# Per-activity inbox attempt counter (IE-06-004)
# ---------------------------------------------------------------------------


def get_inbox_attempt_count(
    dl: SqliteDataLayer,
    activity_id: str,
) -> int:
    """Return this actor's processing attempt count for inbox *activity_id*.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the inbox activity to query.

    Returns:
        Current attempt count, or ``0`` when no record exists.
    """
    return _get_queue_attempt_count(dl, "inbox", activity_id)


def set_inbox_attempt_count(
    dl: SqliteDataLayer,
    activity_id: str,
    count: int,
) -> None:
    """Upsert this actor's processing attempt count for inbox *activity_id*.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the inbox activity.
        count: New attempt count to persist.
    """
    _set_queue_attempt_count(dl, "inbox", activity_id, count)


def clear_inbox_attempt_count(
    dl: SqliteDataLayer,
    activity_id: str,
) -> None:
    """Remove this actor's attempt count entry for inbox *activity_id*.

    Called after an inbox item is dead-lettered so the side-table does not
    accumulate stale rows (IE-06-004).

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the inbox activity whose counter to remove.
    """
    _clear_queue_attempt_count(dl, "inbox", activity_id)
