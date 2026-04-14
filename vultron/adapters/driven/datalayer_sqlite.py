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

"""SQLite/SQLModel-backed activity store (driven adapter).

Concrete implementation of the ``vultron.core.ports.datalayer.DataLayer``
port for persisting and fetching ActivityStreams objects using SQLite via
SQLModel and SQLAlchemy.

Environment variables
---------------------
``VULTRON_DB_URL``
    SQLAlchemy connection URL used by ``get_datalayer()``.  Defaults to
    ``"sqlite:///mydb.sqlite"`` (relative to the process working directory).
    Set this in multi-container deployments to isolate each container's
    database under a persistent volume (e.g.,
    ``sqlite:////app/data/mydb.sqlite``).  Use ``"sqlite:///:memory:"`` for
    in-memory storage (useful for testing and development).
"""

import json
import logging
import os
from datetime import date, datetime
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import Column, Engine, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from vultron.adapters.driven.db_record import (
    Record,
    object_to_record,
    record_to_object,
)
from vultron.adapters.utils import _URN_UUID_PREFIX, _UUID_RE
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

logger = logging.getLogger(__name__)

#: Default SQLAlchemy DB URL used by :func:`get_datalayer` when no explicit
#: ``db_url`` is provided.  Override via the ``VULTRON_DB_URL`` environment
#: variable *before* the module is imported (e.g., set the env var in the
#: container startup script or in ``docker-compose.yml``).
_DEFAULT_DB_URL: str = os.environ.get(
    "VULTRON_DB_URL", "sqlite:///mydb.sqlite"
)

#: Actor types used by :meth:`SqliteDataLayer.find_actor_by_short_id`.
_ACTOR_TYPES: frozenset[str] = frozenset(
    {"Actor", "Person", "Organization", "Service", "Application", "Group"}
)


class VultronObjectRecord(SQLModel, table=True):
    """Persistent storage row for a single domain object."""

    __tablename__ = "vultron_objects"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id_: str = Field(primary_key=True)
    type_: str = Field(index=True)
    actor_id: str | None = Field(default=None, index=True)
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))


class QueueEntry(SQLModel, table=True):
    """A single inbox or outbox entry for an actor."""

    __tablename__ = "vultron_queue"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    actor_id: str = Field(index=True)
    queue: str = Field(index=True)  # "inbox" or "outbox"
    activity_id: str


def _json_default(obj: Any) -> Any:
    """JSON encoder fallback that serializes ``datetime`` / ``date`` objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(
        f"Object of type {type(obj).__name__} is not JSON serializable"
    )


def _json_serializer(value: Any) -> str:
    """Serialize *value* to a JSON string, handling datetime objects."""
    return json.dumps(value, default=_json_default)


def _make_engine(db_url: str) -> Engine:
    """Create a SQLAlchemy engine for the given URL.

    For in-memory databases uses ``StaticPool`` so every connection
    shares the same in-memory database instead of creating a fresh one.
    A custom ``json_serializer`` ensures that ``datetime`` values stored in
    JSON columns are serialised as ISO-8601 strings instead of raising
    ``TypeError``.

    Args:
        db_url: SQLAlchemy connection URL.

    Returns:
        Configured :class:`sqlalchemy.engine.Engine`.
    """
    kwargs: dict[str, Any] = {
        "connect_args": {"check_same_thread": False},
        "json_serializer": _json_serializer,
    }
    if db_url == "sqlite:///:memory:":
        kwargs["poolclass"] = StaticPool
    return create_engine(db_url, **kwargs)


class SqliteDataLayer:
    """SQLite-backed implementation of the :class:`DataLayer` protocol."""

    def __init__(
        self,
        db_url: str = "sqlite:///:memory:",
        actor_id: str | None = None,
    ) -> None:
        self._engine = _make_engine(db_url)
        self._actor_id = actor_id
        self._owns_engine: bool = True
        SQLModel.metadata.create_all(self._engine)

    def close(self) -> None:
        """Dispose the underlying SQLAlchemy engine, releasing connections."""
        if self._owns_engine:
            self._engine.dispose()

    def __enter__(self) -> "SqliteDataLayer":
        """Support ``with SqliteDataLayer(...) as dl:`` usage."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close the data layer when exiting the ``with`` block."""
        self.close()

    def __del__(self) -> None:
        """Dispose engine on garbage collection to avoid ResourceWarning.

        Only disposes if this instance created (owns) the engine.  Borrowed
        engines (``_owns_engine = False``) must be disposed by their owner.
        """
        if not getattr(self, "_owns_engine", True):
            return
        try:
            self._engine.dispose()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scoped(self, stmt: Any) -> Any:
        """Apply actor-scoping WHERE clause when this DL has an actor_id."""
        if self._actor_id:
            return stmt.where(VultronObjectRecord.actor_id == self._actor_id)
        return stmt

    def _to_row(self, obj: PersistableModel) -> VultronObjectRecord:
        """Convert a domain object to a storage row."""
        rec = Record.from_obj(obj)
        return VultronObjectRecord(
            id_=rec.id_,
            type_=rec.type_,
            actor_id=self._actor_id,
            data=rec.data_,
        )

    def _from_row(self, row: VultronObjectRecord) -> PersistableModel | None:
        """Convert a storage row back to a domain object."""
        rec = Record(id_=row.id_, type_=row.type_, data_=row.data)
        try:
            return cast(PersistableModel, record_to_object(rec))
        except (ValueError, ValidationError):
            return None

    def _object_from_storage(
        self, stored_record: dict[str, Any]
    ) -> PersistableModel | None:
        """Reconstruct a domain object from a raw stored-record dict."""
        try:
            record = Record.model_validate(stored_record)
            return cast(PersistableModel, record_to_object(record))
        except (ValidationError, ValueError):
            pass

        raw_type = stored_record.get("type")
        if isinstance(raw_type, str):
            try:
                vocab_cls = find_in_vocabulary(raw_type)
                return cast(
                    PersistableModel, vocab_cls.model_validate(stored_record)
                )
            except KeyError:
                pass

        raw_type = stored_record.get("type_")
        raw_data = stored_record.get("data_")
        if isinstance(raw_type, str) and isinstance(raw_data, dict):
            try:
                vocab_cls = find_in_vocabulary(raw_type)
                return cast(
                    PersistableModel, vocab_cls.model_validate(raw_data)
                )
            except KeyError:
                pass

        return None

    # ------------------------------------------------------------------
    # DataLayer Protocol implementation
    # ------------------------------------------------------------------

    def create(self, record: "StorableRecord | PersistableModel") -> None:
        """Insert a new record; raises ``ValueError`` if it already exists.

        Args:
            record: A ``StorableRecord`` (or subclass) or any Pydantic model
                with ``id_`` and ``type_`` attributes.

        Raises:
            ValueError: If a record with the same ``id_`` already exists.
        """
        if isinstance(record, StorableRecord):
            rec = Record(
                id_=record.id_, type_=record.type_, data_=record.data_
            )
        else:
            rec = object_to_record(record)

        with Session(self._engine) as session:
            existing = session.get(VultronObjectRecord, rec.id_)
            if existing is not None:
                raise ValueError(
                    f"record with id_={rec.id_!r} already exists "
                    f"in {rec.type_!r}"
                )
            row = VultronObjectRecord(
                id_=rec.id_,
                type_=rec.type_,
                actor_id=self._actor_id,
                data=rec.data_,
            )
            session.add(row)
            session.commit()

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None:
        """Read an object by ID across all actor-scoped rows.

        Supports bare-UUID lookup compatibility (retries with the
        ``urn:uuid:`` prefix when a plain UUID is supplied).

        Args:
            object_id: Full or bare-UUID identifier of the object.
            raise_on_missing: If ``True`` raises ``KeyError`` when the
                object is not found.

        Returns:
            Reconstituted domain object or ``None``.
        """
        candidates = [object_id]
        if _UUID_RE.match(object_id):
            candidates.append(f"{_URN_UUID_PREFIX}{object_id}")

        with Session(self._engine) as session:
            for candidate in candidates:
                stmt = self._scoped(
                    select(VultronObjectRecord).where(
                        VultronObjectRecord.id_ == candidate
                    )
                )
                row = session.exec(stmt).first()
                if row is not None:
                    obj = self._from_row(row)
                    if obj is not None:
                        return obj

        if raise_on_missing:
            raise KeyError(
                f"Object with id {object_id!r} not found in datalayer"
            )
        return None

    def get(
        self, table: str | None = None, id_: str | None = None
    ) -> PersistableModel | dict[str, Any] | None:
        """Retrieve a record by type and/or ID.

        Usage::

            get(table, id_)   # returns raw data dict for that type/id
            get(id_=id_)      # searches all types, returns domain object

        Args:
            table: Object type (used as a filter on ``type_``).
            id_: Object identifier.

        Returns:
            Domain object, raw dict, or ``None``.
        """
        with Session(self._engine) as session:
            if table is None and id_ is not None:
                stmt = self._scoped(
                    select(VultronObjectRecord).where(
                        VultronObjectRecord.id_ == id_
                    )
                )
                row = session.exec(stmt).first()
                if row is None:
                    return None
                obj = self._from_row(row)
                if obj is not None:
                    return obj
                return {"id_": row.id_, "type_": row.type_, "data_": row.data}

            if table is None or id_ is None:
                raise ValueError(
                    "get requires either table and id_ or id_ as keyword"
                )

            stmt = self._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.type_ == table,
                    VultronObjectRecord.id_ == id_,
                )
            )
            row = session.exec(stmt).first()
            if row is None:
                return None
            return {"id_": row.id_, "type_": row.type_, "data_": row.data}

    def get_all(self, table: str) -> list[dict[str, Any]]:
        """Return all raw data dicts for a given object type.

        Args:
            table: Object type to query.

        Returns:
            List of dicts, each with ``id_``, ``type_``, and ``data_`` keys.
        """
        with Session(self._engine) as session:
            stmt = self._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.type_ == table
                )
            )
            rows = session.exec(stmt).all()
            return [
                {"id_": row.id_, "type_": row.type_, "data_": row.data}
                for row in rows
            ]

    def update(self, id_: str, record: StorableRecord) -> bool:
        """Update an existing record by ID.

        Args:
            id_: Identifier of the record to update.
            record: New record data (``StorableRecord`` or subclass).

        Returns:
            ``True`` if the record was updated; ``False`` if not found.
        """
        with Session(self._engine) as session:
            row = session.get(VultronObjectRecord, id_)
            if row is None:
                return False
            row.type_ = record.type_
            row.data = record.data_
            session.add(row)
            session.commit()
            return True

    def save(self, obj: PersistableModel) -> None:
        """Persist a domain object, overwriting any existing record.

        Unlike ``create()``, ``save()`` does not raise if the object already
        exists.

        Args:
            obj: Any Pydantic model with ``id_`` and ``type_`` fields.
        """
        rec = object_to_record(obj)
        with Session(self._engine) as session:
            row = session.get(VultronObjectRecord, rec.id_)
            if row is None:
                row = VultronObjectRecord(
                    id_=rec.id_,
                    type_=rec.type_,
                    actor_id=self._actor_id,
                    data=rec.data_,
                )
            else:
                row.type_ = rec.type_
                row.data = rec.data_
            session.add(row)
            session.commit()

    def delete(self, table: str, id_: str) -> bool:
        """Delete a record by type and ID.

        Args:
            table: Object type (used as a filter).
            id_: Object identifier.

        Returns:
            ``True`` if deleted; ``False`` if not found.
        """
        with Session(self._engine) as session:
            stmt = self._scoped(
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

    def clear_table(self, table: str) -> None:
        """Remove all records of a given object type.

        Args:
            table: Object type to clear.
        """
        with Session(self._engine) as session:
            stmt = self._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.type_ == table
                )
            )
            rows = session.exec(stmt).all()
            for row in rows:
                session.delete(row)
            session.commit()

    def clear_all(self) -> None:
        """Remove all object records (and queue entries) for this actor scope."""
        with Session(self._engine) as session:
            if self._actor_id:
                for row in session.exec(
                    select(VultronObjectRecord).where(
                        VultronObjectRecord.actor_id == self._actor_id
                    )
                ).all():
                    session.delete(row)
                for entry in session.exec(
                    select(QueueEntry).where(
                        QueueEntry.actor_id == self._actor_id
                    )
                ).all():
                    session.delete(entry)
            else:
                for row in session.exec(select(VultronObjectRecord)).all():
                    session.delete(row)
                for entry in session.exec(select(QueueEntry)).all():
                    session.delete(entry)
            session.commit()

    def ping(self) -> bool:
        """Probe storage; returns ``True`` when the backend is accessible."""
        with Session(self._engine) as session:
            session.exec(select(VultronObjectRecord).limit(1)).all()
        return True

    def exists(self, table: str, id_: str) -> bool:
        """Check whether a record exists.

        Args:
            table: Object type.
            id_: Object identifier.

        Returns:
            ``True`` if found; ``False`` otherwise.
        """
        with Session(self._engine) as session:
            stmt = self._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.type_ == table,
                    VultronObjectRecord.id_ == id_,
                )
            )
            row = session.exec(stmt).first()
            return row is not None

    def all(
        self, table: str | None = None
    ) -> list[StorableRecord] | dict[str, PersistableModel]:
        """Return all records, optionally filtered by type.

        Args:
            table: When provided, returns a list of ``Record`` objects for
                that type.  When ``None``, returns a dict mapping object
                ``id_`` → reconstituted domain object across all types.

        Returns:
            List of ``StorableRecord`` (when *table* is given) or a dict of
            ``{id_: domain_object}``.
        """
        with Session(self._engine) as session:
            if table is not None:
                stmt = self._scoped(
                    select(VultronObjectRecord).where(
                        VultronObjectRecord.type_ == table
                    )
                )
                rows = session.exec(stmt).all()
                return [
                    Record(id_=row.id_, type_=row.type_, data_=row.data)
                    for row in rows
                ]

            stmt = self._scoped(select(VultronObjectRecord))
            rows = session.exec(stmt).all()
            results: dict[str, PersistableModel] = {}
            for row in rows:
                obj = self._from_row(row)
                if obj is not None:
                    results[obj.id_] = obj
            return results

    def count_all(self) -> dict[str, int]:
        """Return a dict mapping type → record count.

        Returns:
            Mapping of ``{type_name: count}``.  Includes a ``"_default"``
            key with value ``0`` (SQLite has no default table concept).
        """
        with Session(self._engine) as session:
            stmt = self._scoped(
                select(
                    VultronObjectRecord.type_,
                    func.count(),  # type: ignore[call-overload]
                ).group_by(VultronObjectRecord.type_)
            )
            rows = session.exec(stmt).all()
        counts: dict[str, int] = {"_default": 0}
        for type_name, count in rows:
            counts[type_name] = count
        return counts

    def by_type(self, type_: str) -> dict[str, dict[str, Any]]:
        """Return all records of a given type as a ``{id_: data_}`` dict.

        Args:
            type_: Object type to query.

        Returns:
            Mapping of ``{id_: data_dict}`` for every record of that type.
        """
        with Session(self._engine) as session:
            stmt = self._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.type_ == type_
                )
            )
            rows = session.exec(stmt).all()
        results: dict[str, dict[str, Any]] = {}
        for row in rows:
            results[row.id_] = row.data
        return results

    def find_actor_by_short_id(self, short_id: str) -> PersistableModel | None:
        """Find an actor by the last path segment of its URI.

        Searches across all actor-type rows (Actor, Person, Organization,
        Service, Application, Group) and returns the first actor whose
        ``id_`` ends with ``/{short_id}`` or equals ``short_id``.

        Args:
            short_id: Short identifier to search for (e.g., ``"vendorco"``).

        Returns:
            Reconstituted actor object, or ``None`` if not found.
        """
        with Session(self._engine) as session:
            stmt = select(VultronObjectRecord).where(
                VultronObjectRecord.type_.in_(list(_ACTOR_TYPES))  # type: ignore[attr-defined]
            )
            if self._actor_id:
                stmt = stmt.where(
                    VultronObjectRecord.actor_id == self._actor_id
                )
            rows = session.exec(stmt).all()

        for row in rows:
            if row.id_.endswith(f"/{short_id}") or row.id_ == short_id:
                obj = self._from_row(row)
                if obj is not None:
                    return obj
        return None

    def find_case_by_report_id(
        self, report_id: str
    ) -> PersistableModel | None:
        """Find a ``VulnerabilityCase`` referencing the given report ID.

        Each entry in ``vulnerability_reports`` may be stored as either a
        plain string ID or a serialised inline object dict (with an ``id_``
        key).  Both forms are checked.

        Args:
            report_id: Full URI of the ``VulnerabilityReport`` to search for.

        Returns:
            Reconstituted ``VulnerabilityCase``, or ``None`` if not found.
        """
        with Session(self._engine) as session:
            stmt = self._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.type_ == "VulnerabilityCase"
                )
            )
            rows = session.exec(stmt).all()

        for row in rows:
            reports = row.data.get("vulnerability_reports", [])
            for entry in reports:
                if entry == report_id:
                    return self._from_row(row)
                if isinstance(entry, dict) and entry.get("id_") == report_id:
                    return self._from_row(row)
        return None

    # ------------------------------------------------------------------
    # Inbox / Outbox queue helpers
    # ------------------------------------------------------------------

    def inbox_append(self, activity_id: str) -> None:
        """Append an activity ID to this actor's inbox queue.

        Args:
            activity_id: ID of the activity to enqueue.
        """
        actor = self._actor_id or ""
        with Session(self._engine) as session:
            session.add(
                QueueEntry(
                    actor_id=actor, queue="inbox", activity_id=activity_id
                )
            )
            session.commit()

    def inbox_list(self) -> list[str]:
        """Return all activity IDs in this actor's inbox, in insertion order."""
        actor = self._actor_id or ""
        with Session(self._engine) as session:
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

    def inbox_pop(self) -> str | None:
        """Remove and return the oldest activity ID from the inbox.

        Returns:
            The oldest activity ID string, or ``None`` if empty.
        """
        actor = self._actor_id or ""
        with Session(self._engine) as session:
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

    def outbox_append(self, activity_id: str) -> None:
        """Append an activity ID to this actor's outbox queue.

        Args:
            activity_id: ID of the activity to enqueue.
        """
        actor = self._actor_id or ""
        with Session(self._engine) as session:
            session.add(
                QueueEntry(
                    actor_id=actor, queue="outbox", activity_id=activity_id
                )
            )
            session.commit()

    def outbox_list(self) -> list[str]:
        """Return all activity IDs in this actor's outbox, in insertion order."""
        actor = self._actor_id or ""
        with Session(self._engine) as session:
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

    def outbox_pop(self) -> str | None:
        """Remove and return the oldest activity ID from the outbox.

        Returns:
            The oldest activity ID string, or ``None`` if empty.
        """
        actor = self._actor_id or ""
        with Session(self._engine) as session:
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

    def record_outbox_item(self, actor_id: str, activity_id: str) -> None:
        """Queue an outbox item for *actor_id* regardless of this DL's scope.

        Bypasses ``self._actor_id`` to allow the shared or any actor-scoped
        DataLayer to write directly to a named actor's outbox queue.

        Args:
            actor_id: The actor whose outbox queue to append to.
            activity_id: The activity ID to enqueue.
        """
        with Session(self._engine) as session:
            session.add(
                QueueEntry(
                    actor_id=actor_id,
                    queue="outbox",
                    activity_id=activity_id,
                )
            )
            session.commit()


# ---------------------------------------------------------------------------
# Module-level factory / singleton management
# ---------------------------------------------------------------------------

_shared_instance: SqliteDataLayer | None = None
_actor_instances: dict[str, SqliteDataLayer] = {}


def get_datalayer(
    actor_id: str | None = None, db_url: str | None = None
) -> SqliteDataLayer:
    """Factory that returns (or creates) a :class:`SqliteDataLayer` instance.

    When ``actor_id`` is provided, returns (or creates) an actor-scoped
    instance whose rows are filtered by ``actor_id``.  Different actors get
    fully isolated DataLayer views backed by the same SQLite file.

    When ``actor_id`` is ``None``, returns (or creates) a shared/admin
    instance with no actor filtering.  Admin endpoints and health checks use
    this form.

    In tests, use dependency injection to override this function, or set the
    ``VULTRON_DB_URL`` environment variable to ``"sqlite:///:memory:"`` before
    the module is imported.

    Args:
        actor_id: The actor whose scoped DataLayer to return.  ``None`` for
            the shared/admin DataLayer.
        db_url: SQLAlchemy connection URL.  Defaults to ``_DEFAULT_DB_URL``
            (the value of ``VULTRON_DB_URL`` at module import time, or
            ``"sqlite:///mydb.sqlite"``).

    Returns:
        :class:`SqliteDataLayer` — actor-scoped or shared instance.
    """
    global _shared_instance
    _url = (
        db_url
        if db_url is not None
        else os.environ.get("VULTRON_DB_URL", _DEFAULT_DB_URL)
    )
    if actor_id is None:
        if _shared_instance is None:
            _shared_instance = SqliteDataLayer(db_url=_url)
        return _shared_instance
    if actor_id not in _actor_instances:
        _actor_instances[actor_id] = SqliteDataLayer(
            db_url=_url, actor_id=actor_id
        )
    return _actor_instances[actor_id]


def get_all_actor_datalayers() -> dict[str, SqliteDataLayer]:
    """Return a snapshot of all registered actor-scoped DataLayer instances.

    Used by :class:`~vultron.adapters.driving.fastapi.outbox_monitor.OutboxMonitor`
    to iterate over all actors' outboxes without exposing the mutable
    module-level cache directly.

    Returns:
        A shallow copy of the ``actor_id → SqliteDataLayer`` mapping for
        every actor that has called :func:`get_datalayer` with an
        ``actor_id``.
    """
    return dict(_actor_instances)


def reset_datalayer(actor_id: str | None = None) -> None:
    """Reset one or all cached DataLayer instances.

    Disposes the underlying SQLAlchemy engine for each cached instance that
    is being cleared, then removes it from the module-level cache.  The next
    call to :func:`get_datalayer` will create a new instance with a fresh,
    empty in-memory database.

    Engines are disposed *before* their references are dropped so that
    ``sqlite3.Connection`` objects are closed explicitly.  Without this,
    Python's cyclic GC may finalise the connection objects in an order that
    emits ``ResourceWarning`` during a later, unrelated test.

    .. note::
        Callers that created a ``SqliteDataLayer`` instance *directly* (not via
        :func:`get_datalayer`) are responsible for calling :meth:`close` on
        those instances themselves; ``reset_datalayer`` cannot track them.

    Args:
        actor_id: If provided, resets only the instance for that actor.
            If ``None``, resets all instances (shared + all per-actor).
    """
    global _shared_instance, _actor_instances

    instances_to_close: list[SqliteDataLayer] = []

    if actor_id is None:
        if _shared_instance is not None:
            instances_to_close.append(_shared_instance)
        instances_to_close.extend(_actor_instances.values())
        _shared_instance = None
        _actor_instances = {}
    else:
        if actor_id in _actor_instances:
            instances_to_close.append(_actor_instances.pop(actor_id))

    for inst in instances_to_close:
        inst.close()
