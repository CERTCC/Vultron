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
    object_to_record,
)
from vultron.adapters.utils import _URN_UUID_PREFIX, _UUID_RE
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord

from .schema import VultronObjectRecord, QueueEntry, participant_status_summary

logger = logging.getLogger(__name__)


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
        rec = Record(id_=record.id_, type_=record.type_, data_=record.data_)
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
            actor_id=dl._actor_id,
            data=rec.data_,
        )
        session.add(row)
        session.commit()
    logger.info("DataLayer stored %s '%s'", rec.type_, rec.id_)


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
            stmt = dl._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.id_ == candidate
                )
            )
            row = session.exec(stmt).first()
            if row is not None:
                if row.type_ == "CaseParticipant":
                    summary = participant_status_summary(row.data)
                    logger.debug(
                        "DataLayer read CaseParticipant '%s' (row "
                        "actor_id=%r dl_actor_id=%r): %s",
                        row.id_,
                        row.actor_id,
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
                actor_id=dl._actor_id,
                data=rec.data_,
            )
        else:
            row.type_ = rec.type_
            row.data = rec.data_
        session.add(row)
        session.commit()
    logger.info("DataLayer saved %s '%s'", rec.type_, rec.id_)
    if rec.type_ == "CaseParticipant":
        logger.debug(
            "DataLayer saved CaseParticipant '%s' (dl_actor_id=%r): %s",
            rec.id_,
            dl._actor_id,
            participant_status_summary(rec.data_),
        )


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
        stmt = dl._scoped(
            select(VultronObjectRecord).where(
                VultronObjectRecord.type_ == table,
                VultronObjectRecord.id_ == id_,
            )
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
        stmt = dl._scoped(
            select(VultronObjectRecord).where(
                VultronObjectRecord.type_ == table
            )
        )
        rows = session.exec(stmt).all()
        for row in rows:
            session.delete(row)
        session.commit()


def clear_all(
    dl: "Any",  # SqliteDataLayer
) -> None:
    """Remove all object records (and queue entries) for this actor scope.

    Args:
        dl: The SqliteDataLayer instance.
    """
    with Session(dl._engine) as session:
        if dl._actor_id:
            for row in session.exec(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.actor_id == dl._actor_id
                )
            ).all():
                session.delete(row)
            for entry in session.exec(
                select(QueueEntry).where(QueueEntry.actor_id == dl._actor_id)
            ).all():
                session.delete(entry)
        else:
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
    with Session(dl._engine) as session:
        row = session.get(VultronObjectRecord, id_)
        if row is None:
            return False
        row.type_ = record.type_
        row.data = record.data_
        session.add(row)
        session.commit()
        logger.info("DataLayer updated %s '%s'", record.type_, id_)
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
            stmt = dl._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.id_ == id_
                )
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

        stmt = dl._scoped(
            select(VultronObjectRecord).where(
                VultronObjectRecord.type_ == table,
                VultronObjectRecord.id_ == id_,
            )
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
        stmt = dl._scoped(
            select(VultronObjectRecord).where(
                VultronObjectRecord.type_ == table
            )
        )
        rows = session.exec(stmt).all()
        return [
            {"id_": row.id_, "type_": row.type_, "data_": row.data}
            for row in rows
        ]
