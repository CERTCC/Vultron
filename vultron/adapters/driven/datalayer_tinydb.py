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

"""
TinyDB-backed activity store (driven adapter).

Concrete implementation of the ``vultron.core.ports.activity_store.DataLayer``
port for persisting and fetching ActivityStreams objects.

The backward-compat re-export shim at
``vultron.api.v2.datalayer.tinydb_backend`` will be removed once all callers
are updated to import from this module directly.

Environment variables
---------------------
``VULTRON_DB_PATH``
    Path to the TinyDB JSON file used by ``get_datalayer()``.  Defaults to
    ``"mydb.json"`` (relative to the process working directory).  Set this in
    multi-container deployments to isolate each container's database under a
    persistent volume (e.g., ``/app/data/mydb.json``).
"""

import os
from typing import Any, TypeVar, cast

from pydantic import ValidationError
from tinydb import Query, TinyDB
from tinydb.queries import QueryInstance
from tinydb.storages import MemoryStorage
from tinydb.table import Table

from vultron.adapters.utils import _URN_UUID_PREFIX, _UUID_RE
from vultron.adapters.driven.db_record import (
    Record,
    object_to_record,
    record_to_object,
)
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

PersistableModelT = TypeVar("PersistableModelT", bound=PersistableModel)

#: Default TinyDB file path used by :func:`get_datalayer` when no explicit
#: ``db_path`` is provided.  Override via the ``VULTRON_DB_PATH`` environment
#: variable *before* the module is imported (e.g., set the env var in the
#: container startup script or in ``docker-compose.yml``).
_DEFAULT_DB_PATH: str = os.environ.get("VULTRON_DB_PATH", "mydb.json")


class TinyDbDataLayer(DataLayer):
    def __init__(
        self,
        db_path: str | None = "mydb.json",
        actor_id: str | None = None,
    ) -> None:
        if db_path:
            open(db_path, "a").close()  # Ensure the file exists
            self._db_path: str | None = db_path
            self._db = TinyDB(db_path)
        else:
            self._db_path = None
            self._db = TinyDB(storage=MemoryStorage)
        self._actor_id = actor_id

    def close(self) -> None:
        """Close the underlying TinyDB instance, releasing any open file handles."""
        self._db.close()

    def _table(self, name: str) -> Table:
        if self._actor_id:
            return self._db.table(f"{self._actor_id}_{name}")
        return self._db.table(name)

    def _my_tables(self) -> list[Table]:
        """Return TinyDB Table handles scoped to this actor.

        For an actor-scoped DataLayer, only tables whose names start with the
        actor prefix are returned.  For the shared DataLayer (no actor_id),
        all tables are returned.  Uses raw ``_db.table(name)`` access so the
        prefix is never applied twice.
        """
        all_names = self._db.tables()
        if self._actor_id:
            prefix = f"{self._actor_id}_"
            names = [n for n in all_names if n.startswith(prefix)]
        else:
            names = list(all_names)
        return [self._db.table(n) for n in names]

    def _id_query(self, id_: str) -> QueryInstance:
        """Returns a TinyDB Query object for matching the given id.

        Args:
            id_ (str): The id to match.
        """
        return cast(QueryInstance, Query()["id_"] == id_)

    def _object_from_storage(
        self, stored_record: dict[str, Any]
    ) -> PersistableModel | None:
        try:
            record = Record.model_validate(stored_record)
            return cast(PersistableModel, record_to_object(record))
        except (ValidationError, ValueError):
            pass

        raw_type = stored_record.get("type")
        if isinstance(raw_type, str):
            vocab_cls = find_in_vocabulary(raw_type)
            if vocab_cls is not None:
                return cast(
                    PersistableModel, vocab_cls.model_validate(stored_record)
                )

        raw_type = stored_record.get("type_")
        raw_data = stored_record.get("data_")
        if isinstance(raw_type, str) and isinstance(raw_data, dict):
            vocab_cls = find_in_vocabulary(raw_type)
            if vocab_cls is not None:
                return cast(
                    PersistableModel, vocab_cls.model_validate(raw_data)
                )

        return None

    def create(self, record: StorableRecord | PersistableModel) -> None:
        """
        Inserts a record into the specified table.

        Accepts a ``StorableRecord`` (or its ``Record`` subclass) or any
        other Pydantic ``BaseModel``.  A plain ``StorableRecord`` is converted
        to a full ``Record`` using its ``id_``/``type_``/``data_`` fields; a
        non-``StorableRecord`` ``BaseModel`` is converted via
        ``object_to_record``.

        Args:
            record (StorableRecord | BaseModel): The record or model to insert.
        Raises:
            ValueError: If a record with the same ``id_`` already exists.
        """

        if isinstance(record, StorableRecord):
            rec = Record(
                id_=record.id_, type_=record.type_, data_=record.data_
            )
        else:
            rec = object_to_record(record)

        table = rec.type_
        id_ = rec.id_

        if id_ is None:
            raise ValueError("record must include id_")

        tbl = self._table(table)

        if tbl.contains(self._id_query(id_)):
            raise ValueError(
                f"record with id_={id_} already exists in {table}"
            )

        tbl.insert(rec.model_dump())

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None:
        """
        Reads an object by id across all tables and returns the reconstituted
        Pydantic object (as_Base subclass) or None if not found. If
        `raise_on_missing` is True, raises a KeyError when the object is not found.

        Compatibility shim: when *object_id* is a bare UUID the lookup is
        retried with the ``urn:uuid:`` prefix so that callers using the legacy
        bare-UUID pattern still work while IDs are being migrated to URI form.
        """
        candidates = [object_id]
        if _UUID_RE.match(object_id):
            candidates.append(f"{_URN_UUID_PREFIX}{object_id}")

        for candidate in candidates:
            for tbl in self._my_tables():
                rec = tbl.get(self._id_query(candidate))
                if rec:
                    obj = self._object_from_storage(cast(dict[str, Any], rec))
                    if obj is not None:
                        return obj
        if raise_on_missing:
            raise KeyError(
                f"Object with id '{object_id}' not found in datalayer"
            )
        return None

    def get(
        self, table: str | None = None, id_: str | None = None
    ) -> PersistableModel | dict[str, Any] | None:
        """
        Retrieves a record by id from the specified table, or if called with
        only `id_` (keyword) will search across all tables and return a
        reconstituted Pydantic object when possible.

        Usage:
            get(table, id_)
            get(id_=id_)
        """
        # If caller passed as get(id_=...)
        if table is None and id_ is not None:
            for tbl in self._my_tables():
                rec = tbl.get(self._id_query(id_))
                if rec:
                    obj = self._object_from_storage(cast(dict[str, Any], rec))
                    if obj is not None:
                        return obj
                    return cast(dict[str, Any], rec)
            return None

        # otherwise expect both table and id_ to be provided
        if table is None or id_ is None:
            raise ValueError(
                "get requires either table and id_ or id_ as keyword"
            )

        tbl = self._table(table)
        result = tbl.get(self._id_query(id_))
        return cast(dict[str, Any], result) if result is not None else None

    def get_all(self, table: str) -> list[dict[str, Any]]:
        tbl = self._table(table)
        return [cast(dict[str, Any], record) for record in tbl.all()]

    def update(self, id_: str, record: StorableRecord) -> bool:
        """
        Updates a record by id in the specified table.

        Accepts a ``StorableRecord`` (or its ``Record`` subclass) with
        ``id_``, ``type_``, and ``data_`` fields.

        Args:
            id_ (str): The id of the record to update.
            record (StorableRecord): The new record data.
        Returns:
            bool: True if a record was updated, False if not found.
        """
        rec = Record(id_=record.id_, type_=record.type_, data_=record.data_)
        tbl = self._table(rec.type_)
        updated = tbl.update(rec.model_dump(), self._id_query(id_))
        return len(updated) > 0

    def save(self, obj: PersistableModel) -> None:
        """Persist a domain object to the DataLayer, overwriting any existing record.

        Unlike ``create()``, ``save()`` does not raise if the object already exists.
        Use this for update operations where the caller owns the ID.

        Args:
            obj: Any Pydantic BaseModel with ``id_`` and ``type_`` fields.
        """
        rec = object_to_record(obj)
        tbl = self._table(rec.type_)
        if tbl.contains(self._id_query(rec.id_)):
            tbl.update(rec.model_dump(), self._id_query(rec.id_))
        else:
            tbl.insert(rec.model_dump())

    def delete(self, table: str, id_: str) -> bool:
        """
        Deletes a record by id from the specified table.
        Args:
            table (str): The name of the table.
            id_ (str): The id of the record to delete.

        Returns:
            bool: True if a record was deleted, False if not found.
        """
        tbl = self._table(table)
        removed = tbl.remove(self._id_query(id_))
        return len(removed) > 0

    def all(
        self, table: str | None = None
    ) -> list[StorableRecord] | dict[str, PersistableModel]:
        """
        If `table` is provided: returns a list of `Record` objects for that table.
        If `table` is None: returns a dict mapping object id -> reconstituted
        Pydantic object for all objects across all tables.
        """
        if table is not None:
            tbl = self._table(table)
            records = tbl.all()
            return [Record.model_validate(rec) for rec in records]

        # no table provided: return a dictionary of all objects across tables
        results: dict[str, PersistableModel] = {}
        for tbl in self._my_tables():
            for rec in tbl.all():
                stored_record = dict(rec)
                obj = self._object_from_storage(stored_record)
                if obj is None:
                    continue
                results[obj.id_] = obj
        return results

    def count_all(self) -> dict[str, int]:
        db = self._db
        counts = {"_default": len(db)}
        for name in db.tables():
            counts[name] = len(db.table(name))
        return counts

    def by_type(self, type_: str) -> dict[str, dict[str, Any]]:
        """
        Returns a dict mapping object id -> object's data dict for all records of
        the given type (table name).
        """
        tbl = self._table(type_)
        if tbl.name not in self._db.tables():
            return {}

        results: dict[str, dict[str, Any]] = {}
        for rec in tbl.all():
            try:
                record = Record.model_validate(dict(rec))
                results[record.id_] = record.data_
            except ValidationError:
                stored_record = dict(rec)
                raw_id = stored_record.get("id_")
                if isinstance(raw_id, str):
                    raw_data = stored_record.get("data_")
                    if isinstance(raw_data, dict):
                        results[raw_id] = raw_data
                    else:
                        results[raw_id] = stored_record
        return results

    def clear_table(self, table: str) -> None:
        """
        Removes all records from the specified table.

        Args:
            table (str): The name of the table to clear.
        """
        tbl = self._table(table)
        tbl.truncate()

    def clear_all(self) -> None:
        """
        Removes all tables and their records from the database.
        """
        self._db.drop_tables()

    def ping(self) -> bool:
        """
        Probe the DataLayer to confirm storage is accessible.

        Performs a lightweight read of the database table list.  Returns
        ``True`` if the storage backend responds normally; raises or returns
        ``False`` if the backend is unavailable.
        """
        list(self._db.tables())
        return True

    def exists(self, table: str, id_: str) -> bool:
        """
        Checks if a record with the given id exists in the specified table.

        Args:
            table (str): The name of the table.
            id_ (str): The id of the record to check.

        Returns:
            bool: True if a record with the given id exists, False otherwise.
        """
        tbl = self._table(table)
        return tbl.contains(self._id_query(id_))

    def find_actor_by_short_id(self, short_id: str) -> PersistableModel | None:
        """
        Find an actor by matching the short ID (last part of URI) against stored actor IDs.

        Searches across Actor, Person, Organization, Service, Application, and Group tables.
        Returns the first actor whose id_ ends with the given short_id.

        Args:
            short_id: The short identifier to search for (e.g., "vendorco")

        Returns:
            BaseModel | None: The reconstituted Actor object if found, None otherwise
        """
        actor_types = [
            "Actor",
            "Person",
            "Organization",
            "Service",
            "Application",
            "Group",
        ]

        for actor_type in actor_types:
            tbl = self._table(actor_type)
            if tbl.name not in self._db.tables():
                continue

            for rec in tbl.all():
                try:
                    record = Record.model_validate(dict(rec))
                    # Check if the id_ ends with /short_id or is exactly short_id
                    if (
                        record.id_.endswith(f"/{short_id}")
                        or record.id_ == short_id
                    ):
                        return cast(PersistableModel, record_to_object(record))
                except ValidationError:
                    continue

        return None

    def find_case_by_report_id(
        self, report_id: str
    ) -> PersistableModel | None:
        """Find a VulnerabilityCase whose ``vulnerability_reports`` references
        the given report ID.

        Each entry in ``vulnerability_reports`` may be stored as either a plain
        string ID or as a serialised inline object dict (with an ``id_`` key).
        Both forms are checked.

        Args:
            report_id: Full URI of the VulnerabilityReport to search for.

        Returns:
            The reconstituted VulnerabilityCase, or None if not found.
        """
        tbl = self._table("VulnerabilityCase")
        if tbl.name not in self._db.tables():
            return None

        for rec in tbl.all():
            try:
                record = Record.model_validate(dict(rec))
                reports = record.data_.get("vulnerability_reports", [])
                for entry in reports:
                    if entry == report_id:
                        return cast(PersistableModel, record_to_object(record))
                    if (
                        isinstance(entry, dict)
                        and entry.get("id_") == report_id
                    ):
                        return cast(PersistableModel, record_to_object(record))
            except (ValidationError, ValueError):
                continue

        return None

    # ------------------------------------------------------------------
    # Inbox / Outbox queue helpers
    # ------------------------------------------------------------------

    def inbox_append(self, activity_id: str) -> None:
        """Append an activity ID to this actor's inbox queue."""
        tbl = self._table("inbox")
        tbl.insert({"activity_id": activity_id})

    def inbox_list(self) -> list[str]:
        """Return all activity IDs currently in this actor's inbox, in insertion order."""
        tbl = self._table("inbox")
        return [
            activity_id
            for rec in tbl.all()
            if isinstance(activity_id := rec.get("activity_id"), str)
        ]

    def inbox_pop(self) -> str | None:
        """Remove and return the oldest activity ID from this actor's inbox queue.

        Returns ``None`` if the inbox is empty.
        """
        tbl = self._table("inbox")
        all_recs = tbl.all()
        if not all_recs:
            return None
        first = all_recs[0]
        tbl.remove(doc_ids=[first.doc_id])
        activity_id = first.get("activity_id")
        return activity_id if isinstance(activity_id, str) else None

    def outbox_append(self, activity_id: str) -> None:
        """Append an activity ID to this actor's outbox queue."""
        tbl = self._table("outbox")
        tbl.insert({"activity_id": activity_id})

    def outbox_list(self) -> list[str]:
        """Return all activity IDs currently in this actor's outbox, in insertion order."""
        tbl = self._table("outbox")
        return [
            activity_id
            for rec in tbl.all()
            if isinstance(activity_id := rec.get("activity_id"), str)
        ]

    def outbox_pop(self) -> str | None:
        """Remove and return the oldest activity ID from this actor's outbox queue.

        Returns ``None`` if the outbox is empty.
        """
        tbl = self._table("outbox")
        all_recs = tbl.all()
        if not all_recs:
            return None
        first = all_recs[0]
        tbl.remove(doc_ids=[first.doc_id])
        activity_id = first.get("activity_id")
        return activity_id if isinstance(activity_id, str) else None

    def record_outbox_item(self, actor_id: str, activity_id: str) -> None:
        """Queue an outbox item for *actor_id* regardless of this DL's scope.

        Uses the same ``{actor_id}_outbox`` table name that the actor-scoped
        DataLayer writes to, so that :func:`outbox_handler` can drain the
        queue whether the enqueuing happened from the shared DL (trigger
        use-cases, BT nodes) or the actor-scoped DL (``POST /outbox``).

        Args:
            actor_id: The actor whose outbox queue to append to.
            activity_id: The activity ID to enqueue.
        """
        tbl = self._db.table(f"{actor_id}_outbox")
        tbl.insert({"activity_id": activity_id})


_datalayer_instance: TinyDbDataLayer | None = None
_datalayer_instances: dict[str, TinyDbDataLayer] = {}


def get_datalayer(
    actor_id: str | None = None, db_path: str | None = _DEFAULT_DB_PATH
) -> TinyDbDataLayer:
    """Factory function to get or create a TinyDbDataLayer instance.

    When ``actor_id`` is provided, returns (or creates) an actor-scoped
    instance whose tables are prefixed with the actor ID (Option B — TinyDB
    namespace prefix per ADR-0012). Different actors get fully isolated
    DataLayer instances backed by the same TinyDB file.

    When ``actor_id`` is ``None``, returns (or creates) a shared/admin
    instance with no namespace prefix. Admin endpoints and health checks
    use this form.

    In tests, dependency injection should be used to override this.

    Args:
        actor_id: The actor whose scoped DataLayer to return. ``None`` for
            the shared/admin DataLayer.
        db_path: The path to the backing TinyDB file.  Defaults to
            ``_DEFAULT_DB_PATH`` (the value of ``VULTRON_DB_PATH`` at module
            import time, or ``"mydb.json"``).  Pass ``None`` explicitly to
            use in-memory storage (useful for testing).

    Returns:
        TinyDbDataLayer: An actor-scoped (or shared) instance.
    """
    global _datalayer_instance
    if actor_id is None:
        if _datalayer_instance is None:
            _datalayer_instance = TinyDbDataLayer(db_path=db_path)
        return _datalayer_instance
    if actor_id not in _datalayer_instances:
        _datalayer_instances[actor_id] = TinyDbDataLayer(
            db_path=db_path, actor_id=actor_id
        )
    return _datalayer_instances[actor_id]


def reset_datalayer(actor_id: str | None = None) -> None:
    """Reset one or all cached DataLayer instances. Used primarily for testing.

    Args:
        actor_id: If provided, resets only the instance for that actor.
            If ``None``, resets all instances (shared + all per-actor).
    """
    global _datalayer_instance, _datalayer_instances
    if actor_id is None:
        if _datalayer_instance is not None:
            _datalayer_instance.close()
        _datalayer_instance = None
        for instance in _datalayer_instances.values():
            instance.close()
        _datalayer_instances = {}
    else:
        if actor_id in _datalayer_instances:
            instance = _datalayer_instances.pop(actor_id)
            instance.close()
