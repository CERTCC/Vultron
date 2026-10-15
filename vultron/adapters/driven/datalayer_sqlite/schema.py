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

"""SQLModel table definitions for the SQLite data layer."""

from typing import Any

from sqlalchemy import Column, Engine, Index, text
from sqlalchemy.dialects.sqlite import JSON
from sqlmodel import Field, SQLModel

from vultron.adapters.utils import strip_id_prefix
from vultron.errors import VultronStaleStoreError


class VultronObjectRecord(SQLModel, table=True):
    """Persistent storage row for a single domain object.

    There is no ``actor_id`` column: under ADR-0073 each actor has its own
    store, so every row in this table belongs to that store's actor by
    construction.  The column used to exist as a *filter*, which partitioned
    reads but not writes — one actor's ``save()`` could overwrite another's row
    because ``id_`` is globally unique within a file (issue #2238).
    """

    __tablename__ = "vultron_objects"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id_: str = Field(primary_key=True)
    type_: str = Field(index=True)
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))


OUTBOX_PENDING_PREDICATE = "queue = 'outbox'"
"""Rows the outbox no-duplicate index covers (OX-06-002).

An ``ON CONFLICT`` target against a partial index must repeat its ``WHERE``
clause, so the index and :mod:`.queues` share this one string.
"""

OUTBOX_PENDING_INDEX = "uq_vultron_queue_outbox_pending"
"""Name of the partial UNIQUE index on ``vultron_queue`` (OX-06-002)."""


class QueueEntry(SQLModel, table=True):
    """A single inbox or outbox entry.

    Like :class:`VultronObjectRecord`, this carries no ``actor_id``: the queue
    lives in its owning actor's store.  Dropping the column also removes the
    class of bug where a queue was written under one actor-id spelling and read
    under another (BUG-2026040901; see ``notes/datalayer-design.md``
    § "One Actor Id Is One Database").

    A partial UNIQUE index over ``(queue, activity_id)`` for outbox rows
    (:data:`OUTBOX_PENDING_INDEX`) makes the store itself enforce OX-06-002: an
    activity id cannot be pending in the outbox twice.  Popping or withdrawing
    an entry deletes its row, so the table holds only pending rows and a
    delivered id can be queued again.  The index is scoped to the outbox: the
    inbox has no no-duplicate rule, and its re-queue paths append plainly.

    ``create_all`` never alters an existing table, so a store created before
    the index was added would run without it.  Such a store is refused when it
    is opened (:func:`require_outbox_pending_index`); it must be reset.
    """

    __tablename__ = "vultron_queue"  # type: ignore[assignment]
    __table_args__ = (
        Index(
            OUTBOX_PENDING_INDEX,
            "queue",
            "activity_id",
            unique=True,
            sqlite_where=text(OUTBOX_PENDING_PREDICATE),
        ),
        {"extend_existing": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    queue: str = Field(index=True)  # "inbox" or "outbox"
    activity_id: str


def require_outbox_pending_index(engine: Engine) -> None:
    """Refuse a store whose ``vultron_queue`` table lacks the outbox index.

    ``create_all`` creates a missing table with its indexes but never adds an
    index to a table that already exists, so a store written before the
    OX-06-002 index would otherwise open without it, and every
    ``outbox_append`` would then fail on its ``ON CONFLICT`` target.  The store
    is refused at open instead, naming the reset; there is no migration.

    Raises:
        VultronStaleStoreError: If the index is absent.
    """
    with engine.connect() as conn:
        found = conn.execute(
            text(
                "SELECT 1 FROM sqlite_master"
                " WHERE type = 'index' AND tbl_name = 'vultron_queue'"
                " AND name = :name"
            ),
            {"name": OUTBOX_PENDING_INDEX},
        ).first()
    if found is None:
        raise VultronStaleStoreError(
            f"Store at {engine.url} predates the outbox no-duplicate index"
            f" ({OUTBOX_PENDING_INDEX}, OX-06-002); no migration is made, so"
            " the store must be reset (for the container demo,"
            " `docker compose down -v`)"
        )


class QueueAttemptEntry(SQLModel, table=True):
    """Shared persisted attempt counter for inbox and outbox retry tracking.

    Covers both inbox and outbox queues via a ``queue`` discriminator,
    satisfying the DRY requirement in IE-06-004 and #4168.

    The primary key is ``(queue, activity_id)`` so a single activity_id may
    appear at most once per queue name within one actor's store, with no
    cross-queue interference.

    Like the other queue tables, this table carries no ``actor_id``: the counter
    lives in the store of the actor whose queue is being drained (ADR-0073).

    ``queue`` values: ``"inbox"`` (IE-06-004) and ``"outbox"`` (OX-13-001).
    """

    __tablename__ = "vultron_queue_attempts"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    queue: str = Field(primary_key=True)  # "inbox" | "outbox"
    activity_id: str = Field(primary_key=True)
    attempt_count: int = Field(default=0)


def matches_short_id(full_id: str, short_id: str) -> bool:
    """Return True when *short_id* resolves to *full_id*.

    Surrogate keys are derived from canonical IDs by taking the final segment:
    ``https://host/api/v2/cases/abc`` -> ``abc``, ``urn:uuid:abc`` -> ``abc``.
    """
    if full_id == short_id:
        return True
    if full_id.endswith(f"/{short_id}"):
        return True
    return strip_id_prefix(full_id) == short_id


def _dimension_state(status: dict[str, Any], dimension: str) -> Any:
    """Return a status dict's state for *dimension* in any persisted shape.

    Three shapes are live and all three must be read:

    * the **bare state value** a dimension serializes to since ARCH-25-005 (ADR-0099)
      / SDO-01-004 — ``{"rm": "RECEIVED"}``;
    * the **one-key mapping** of ADR-0036 — ``{"rm": {"state": "RECEIVED"}}``,
      still accepted on input and still present in rows written before that
      change;
    * the **flat legacy wire spelling** — ``{"rm_state": "RECEIVED"}``,
      optionally camelCased.

    Reading only a subset makes this summary report ``rm=None`` for every row it
    misses, removing the observability that exists precisely to make shape
    migrations diagnosable (issues #2232, #2262).  That is why a new
    serialization shape has to be added here in the same change that introduces
    it, not afterwards.
    """
    nested = status.get(dimension)
    if isinstance(nested, dict):
        state = nested.get("state")
        if state is not None:
            return state
    elif isinstance(nested, str) and nested:
        return nested
    return status.get(f"{dimension}_state") or status.get(f"{dimension}State")


def participant_status_summary(data: Any) -> str:
    """Return a short debug summary of a CaseParticipant row's status list.

    Used by adapter logging on read/save to make read-after-write
    visibility issues directly diagnosable from container logs without
    dumping full JSON. Returns ``""`` (empty string) for non-participant
    rows or malformed data so callers can branch cheaply.
    """
    if not isinstance(data, dict):
        return ""
    # Fall through on a *missing* key, not on a falsy one: an empty ladder is a
    # participant row worth reporting as ``n_statuses=0`` (the state a re-seeded
    # status list is about to be silently created from), and ``or`` made that
    # branch unreachable by treating ``[]`` as "not a participant row".
    statuses = data.get("participant_statuses")
    if statuses is None:
        statuses = data.get("participantStatuses")
    if not isinstance(statuses, list):
        return ""
    if not statuses:
        return "n_statuses=0"
    entries = []
    for i, s in enumerate(statuses):
        if isinstance(s, dict):
            vfd = _dimension_state(s, "vfd")
            rm = _dimension_state(s, "rm")
            pub = s.get("published")
            upd = s.get("updated")
            entries.append(
                f"[{i}]vfd={vfd!r},rm={rm!r},pub={pub!r},upd={upd!r}"
            )
        else:
            entries.append(f"[{i}]<{type(s).__name__}>")
    return f"n_statuses={len(statuses)} " + " ".join(entries)
