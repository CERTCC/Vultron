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

"""Inbox and outbox queue operations for the SQLite data layer.

Each queue lives in its owning actor's store (ADR-0066), so none of these
functions takes or filters on an ``actor_id``.  That removes a whole class of
defect in which a queue was written under one spelling of an actor id and read
under another — the cause of BUG-2026040901 and of the ``outbox_list()``
requires-``clone_for_actor`` pitfall.

``record_outbox_item(actor_id, ...)`` and ``outbox_list_for_actor(actor_id)``
used to exist so that an unscoped DataLayer could name the actor explicitly.
Every one of their call sites passed the *executing* actor's own id, so with a
mandatory actor scope they are exactly :func:`outbox_append` and
:func:`outbox_list` and have been folded into them.
"""

import logging
from typing import Any

from sqlmodel import Session, col, select

from .schema import QueueEntry

logger = logging.getLogger(__name__)


def _queue_list(dl: "Any", queue: str) -> list[str]:
    """Return every activity ID in *queue*, in insertion order."""
    with Session(dl._engine) as session:
        stmt = (
            select(QueueEntry)
            .where(QueueEntry.queue == queue)
            .order_by(col(QueueEntry.id))
        )
        rows = session.exec(stmt).all()
    return [row.activity_id for row in rows]


def _queue_pop(dl: "Any", queue: str) -> str | None:
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


def _queue_append(dl: "Any", queue: str, activity_id: str) -> None:
    """Append *activity_id* to *queue*."""
    with Session(dl._engine) as session:
        session.add(QueueEntry(queue=queue, activity_id=activity_id))
        session.commit()


def inbox_append(
    dl: "Any",  # SqliteDataLayer
    activity_id: str,
) -> None:
    """Append an activity ID to this actor's inbox queue.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the activity to enqueue.
    """
    _queue_append(dl, "inbox", activity_id)


def inbox_list(dl: "Any") -> list[str]:  # SqliteDataLayer
    """Return all activity IDs in this actor's inbox, in insertion order.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        List of activity ID strings in insertion order.
    """
    return _queue_list(dl, "inbox")


def inbox_pop(dl: "Any") -> str | None:  # SqliteDataLayer
    """Remove and return the oldest activity ID from the inbox.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        The oldest activity ID string, or ``None`` if empty.
    """
    return _queue_pop(dl, "inbox")


def outbox_append(
    dl: "Any",  # SqliteDataLayer
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


def outbox_list(dl: "Any") -> list[str]:  # SqliteDataLayer
    """Return all activity IDs in this actor's outbox, in insertion order.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        List of activity ID strings in insertion order.
    """
    return _queue_list(dl, "outbox")


def outbox_pop(dl: "Any") -> str | None:  # SqliteDataLayer
    """Remove and return the oldest activity ID from the outbox.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        The oldest activity ID string, or ``None`` if empty.
    """
    return _queue_pop(dl, "outbox")
