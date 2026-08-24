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

from sqlalchemy import Column
from sqlalchemy.dialects.sqlite import JSON
from sqlmodel import Field, SQLModel

from vultron.adapters.utils import strip_id_prefix


class VultronObjectRecord(SQLModel, table=True):
    """Persistent storage row for a single domain object.

    There is no ``actor_id`` column: under ADR-0072 each actor has its own
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


class QueueEntry(SQLModel, table=True):
    """A single inbox or outbox entry.

    Like :class:`VultronObjectRecord`, this carries no ``actor_id``: the queue
    lives in its owning actor's store.  Dropping the column also removes the
    class of bug where a queue was written under one actor-id spelling and read
    under another (BUG-2026040901, and the ``outbox_list()`` /
    ``clone_for_actor`` pitfall in ``notes/datalayer-design.md``).
    """

    __tablename__ = "vultron_queue"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    queue: str = Field(index=True)  # "inbox" or "outbox"
    activity_id: str


class OutboxAttemptEntry(SQLModel, table=True):
    """Persisted per-activity delivery attempt count for the outbox handler.

    Keyed by ``activity_id`` alone so counts survive drain-pass resets
    (OX-13-001).  Cleared when an activity is dead-lettered (OX-13-002).

    Like :class:`VultronObjectRecord` and :class:`QueueEntry`, this carries no
    ``actor_id``: the counter lives in the store of the actor whose outbox is
    being drained (ADR-0072).  ``activity_id`` is the primary key rather than a
    surrogate integer, which makes the counter structurally single-valued —
    there is no layout in which one activity accumulates two rival counts for
    one actor, so the upsert in
    :func:`~vultron.adapters.driven.datalayer_sqlite.queues.set_outbox_attempt_count`
    cannot silently start counting in parallel.
    """

    __tablename__ = "vultron_outbox_attempts"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

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
    """Return a status dict's state for *dimension* in either persisted shape.

    The canonical core shape nests the state (``{"rm": {"state": "RECEIVED"}}``,
    ADR-0036); the wire shape carries it flat (``{"rm_state": "RECEIVED"}``),
    optionally camelCased.  Reading only the flat spellings made this summary
    report ``rm=None`` for every canonical row — removing the observability
    that exists precisely to make shape migrations diagnosable (issue #2232).
    """
    nested = status.get(dimension)
    if isinstance(nested, dict):
        state = nested.get("state")
        if state is not None:
            return state
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
