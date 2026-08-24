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

"""CRUD operations for the SQLite data layer."""

import logging
from typing import Any, cast

from sqlmodel import Session, select

from vultron.adapters.driven.db_record import (
    Record,
    _NORMALIZE_WIRE_TO_CORE,
    object_to_record,
)
from vultron.adapters.utils import _URN_UUID_PREFIX, _UUID_RE
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord

from .schema import VultronObjectRecord, QueueEntry, participant_status_summary

logger = logging.getLogger(__name__)


def _storable_to_record(record: StorableRecord) -> Record:
    """Normalise a StorableRecord through the full wire→core path.

    Only types in :data:`_NORMALIZE_WIRE_TO_CORE` require a round-trip
    (currently ``CaseParticipant`` and ``ParticipantStatus``).  For all other
    types the ``data_`` is preserved verbatim — the vocabulary round-trip
    would deserialise against the *base* wire class and silently lose
    subtype-specific fields (e.g. ``embargo_policy`` on ``VultronPerson``).
    """
    tmp = Record(id_=record.id_, type_=record.type_, data_=record.data_)
    if record.type_ not in _NORMALIZE_WIRE_TO_CORE:
        return tmp
    try:
        return Record.from_obj(cast(PersistableModel, tmp.to_obj()))
    except (ValueError, KeyError):
        logger.warning(
            "DataLayer _storable_to_record: normalisation failed for %s, persisting verbatim",
            record.type_,
        )
        return tmp


def create(
    dl: "Any",  # SqliteDataLayer
    record: "StorableRecord | PersistableModel",
) -> None:
    """Insert a new record; raises ``ValueError`` if it already exists.

    Args:
        dl: The SqliteDataLayer instance.
        record: A ``StorableRecord`` (or subclass) or any Pydantic model
            with ``id_`` and ``type_`` attributes.

    Raises:
        ValueError: If a record with the same ``id_`` already exists.
    """
    if isinstance(record, StorableRecord):
        rec = _storable_to_record(record)
    else:
        rec = object_to_record(record)

    with Session(dl._engine) as session:
        existing = session.get(VultronObjectRecord, rec.id_)
        if existing is not None:
            raise ValueError(
                f"record with id_={rec.id_!r} already exists "
                f"in {rec.type_!r}"
            )
        row = VultronObjectRecord(
            id_=rec.id_,
            type_=rec.type_,
            data=rec.data_,
        )
        session.add(row)
        session.commit()
    logger.debug("DataLayer stored %s '%s'", rec.type_, rec.id_)


def read(
    dl: "Any",  # SqliteDataLayer
    object_id: str,
    raise_on_missing: bool = False,
) -> PersistableModel | None:
    """Read an object by ID across all actor-scoped rows.

    Supports bare-UUID lookup compatibility (retries with the
    ``urn:uuid:`` prefix when a plain UUID is supplied).

    Args:
        dl: The SqliteDataLayer instance.
        object_id: Full or bare-UUID identifier of the object.
        raise_on_missing: If ``True`` raises ``KeyError`` when the
            object is not found.

    Returns:
        Reconstituted domain object or ``None``.
    """
    candidates = [object_id]
    if _UUID_RE.match(object_id):
        candidates.append(f"{_URN_UUID_PREFIX}{object_id}")

    with Session(dl._engine) as session:
        for candidate in candidates:
            stmt = select(VultronObjectRecord).where(
                VultronObjectRecord.id_ == candidate
            )
            row = session.exec(stmt).first()
            if row is not None:
                if row.type_ == "CaseParticipant":
                    summary = participant_status_summary(row.data)
                    logger.debug(
                        "DataLayer read CaseParticipant '%s' from "
                        "actor '%s' store: %s",
                        row.id_,
                        dl._actor_id,
                        summary,
                    )
                obj = dl._from_row(row)
                if obj is not None:
                    return cast(PersistableModel | None, obj)

    if raise_on_missing:
        raise KeyError(f"Object with id {object_id!r} not found in datalayer")
    return None


def save(
    dl: "Any",  # SqliteDataLayer
    obj: PersistableModel,
) -> None:
    """Persist a domain object, overwriting any existing record.

    Unlike ``create()``, ``save()`` does not raise if the object already
    exists.

    Args:
        dl: The SqliteDataLayer instance.
        obj: Any Pydantic model with ``id_`` and ``type_`` fields.
    """
    rec = object_to_record(obj)
    with Session(dl._engine) as session:
        row = session.get(VultronObjectRecord, rec.id_)
        if row is None:
            row = VultronObjectRecord(
                id_=rec.id_,
                type_=rec.type_,
                data=rec.data_,
            )
        else:
            row.type_ = rec.type_
            row.data = rec.data_
        session.add(row)
        session.commit()
    logger.debug("DataLayer saved %s '%s'", rec.type_, rec.id_)
    if rec.type_ == "CaseParticipant":
        logger.debug(
            "DataLayer saved CaseParticipant '%s' (dl_actor_id=%r): %s",
            rec.id_,
            dl._actor_id,
            participant_status_summary(rec.data_),
        )


def save_many(
    dl: "Any",  # SqliteDataLayer
    objs: list["PersistableModel"],
) -> None:
    """Persist multiple domain objects in a single atomic transaction.

    All objects are written in one ``Session`` block and committed together.
    If any object fails to serialise the entire transaction is rolled back
    — no partial write reaches storage (CM-21-004).

    Args:
        dl: The SqliteDataLayer instance.
        objs: Domain objects to persist.  Each is serialised via
            ``object_to_record``; existing rows are overwritten (upsert
            semantics matching :func:`save`).
    """
    rows = [object_to_record(obj) for obj in objs]
    with Session(dl._engine) as session:
        for rec in rows:
            row = session.get(VultronObjectRecord, rec.id_)
            if row is None:
                row = VultronObjectRecord(
                    id_=rec.id_,
                    type_=rec.type_,
                    data=rec.data_,
                )
            else:
                row.type_ = rec.type_
                row.data = rec.data_
            session.add(row)
        session.commit()
    for rec in rows:
        logger.debug("DataLayer saved %s '%s' (batch)", rec.type_, rec.id_)


def delete(
    dl: "Any",  # SqliteDataLayer
    table: str,
    id_: str,
) -> bool:
    """Delete a record by type and ID.

    Args:
        dl: The SqliteDataLayer instance.
        table: Object type (used as a filter).
        id_: Object identifier.

    Returns:
        ``True`` if deleted; ``False`` if not found.
    """
    with Session(dl._engine) as session:
        stmt = select(VultronObjectRecord).where(
            VultronObjectRecord.type_ == table,
            VultronObjectRecord.id_ == id_,
        )
        row = session.exec(stmt).first()
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True


def clear_table(
    dl: "Any",  # SqliteDataLayer
    table: str,
) -> None:
    """Remove all records of a given object type.

    Args:
        dl: The SqliteDataLayer instance.
        table: Object type to clear.
    """
    with Session(dl._engine) as session:
        stmt = select(VultronObjectRecord).where(
            VultronObjectRecord.type_ == table
        )
        rows = session.exec(stmt).all()
        for row in rows:
            session.delete(row)
        session.commit()


def clear_all(
    dl: "Any",  # SqliteDataLayer
) -> None:
    """Remove every object record and queue entry in this actor's store.

    The store belongs to exactly one actor (ADR-0071), so this clears that
    actor and cannot reach another's data.

    Args:
        dl: The SqliteDataLayer instance.
    """
    with Session(dl._engine) as session:
        for row in session.exec(select(VultronObjectRecord)).all():
            session.delete(row)
        for entry in session.exec(select(QueueEntry)).all():
            session.delete(entry)
        session.commit()


def update(
    dl: "Any",  # SqliteDataLayer
    id_: str,
    record: StorableRecord,
) -> bool:
    """Update an existing record by ID.

    Args:
        dl: The SqliteDataLayer instance.
        id_: Identifier of the record to update.
        record: New record data (``StorableRecord`` or subclass).

    Returns:
        ``True`` if the record was updated; ``False`` if not found.
    """
    normalized = _storable_to_record(record)
    with Session(dl._engine) as session:
        row = session.get(VultronObjectRecord, id_)
        if row is None:
            return False
        row.type_ = normalized.type_
        row.data = normalized.data_
        session.add(row)
        session.commit()
        logger.debug("DataLayer updated %s '%s'", normalized.type_, id_)
        return True


def get(
    dl: "Any",  # SqliteDataLayer
    table: str | None = None,
    id_: str | None = None,
) -> PersistableModel | dict[str, Any] | None:
    """Retrieve a record by type and/or ID.

    Usage::

        get(dl, table, id_)   # returns raw data dict for that type/id
        get(dl, id_=id_)      # searches all types, returns domain object

    Args:
        dl: The SqliteDataLayer instance.
        table: Object type (used as a filter on ``type_``).
        id_: Object identifier.

    Returns:
        Domain object, raw dict, or ``None``.
    """
    with Session(dl._engine) as session:
        if table is None and id_ is not None:
            stmt = select(VultronObjectRecord).where(
                VultronObjectRecord.id_ == id_
            )
            row = session.exec(stmt).first()
            if row is None:
                return None
            obj = dl._from_row(row)
            if obj is not None:
                return cast(PersistableModel | dict[str, Any] | None, obj)
            return {"id_": row.id_, "type_": row.type_, "data_": row.data}

        if table is None or id_ is None:
            raise ValueError(
                "get requires either table and id_ or id_ as keyword"
            )

        stmt = select(VultronObjectRecord).where(
            VultronObjectRecord.type_ == table,
            VultronObjectRecord.id_ == id_,
        )
        row = session.exec(stmt).first()
        if row is None:
            return None
        return {"id_": row.id_, "type_": row.type_, "data_": row.data}


def get_all(
    dl: "Any",  # SqliteDataLayer
    table: str,
) -> list[dict[str, Any]]:
    """Return all raw data dicts for a given object type.

    Args:
        dl: The SqliteDataLayer instance.
        table: Object type to query.

    Returns:
        List of dicts, each with ``id_``, ``type_``, and ``data_`` keys.
    """
    with Session(dl._engine) as session:
        stmt = select(VultronObjectRecord).where(
            VultronObjectRecord.type_ == table
        )
        rows = session.exec(stmt).all()
        return [
            {"id_": row.id_, "type_": row.type_, "data_": row.data}
            for row in rows
        ]
