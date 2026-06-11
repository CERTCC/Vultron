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

"""Inbox and outbox queue operations for the SQLite data layer."""

import logging
from typing import Any

from sqlmodel import Session, col, select

from .schema import QueueEntry

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
