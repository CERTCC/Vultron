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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# Copyright

"""
Provides TODO writeme
"""
from typing import TypeVar

from pydantic import BaseModel
from tinydb import TinyDB, Query
from tinydb.queries import QueryInstance
from tinydb.storages import MemoryStorage
from tinydb.table import Table

from vultron.api.v2.datalayer.abc import DataLayer
from vultron.api.v2.datalayer.db_record import (
    Record,
    object_to_record,
    record_to_object,
)

BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


class TinyDbDataLayer(DataLayer):
    def __init__(self, db_path: str | None = "mydb.json") -> None:
        if db_path:
            open(db_path, "a").close()  # Ensure the file exists
            self._db_path = db_path
            self._db = TinyDB(db_path)
        else:
            self._db_path = None
            self._db = TinyDB(storage=MemoryStorage)

    def _table(self, name: str) -> Table:
        return self._db.table(name)

    def _id_query(self, id_: str) -> QueryInstance:
        """Returns a TinyDB Query object for matching the given id.

        Args:
            id_ (str): The id to match.
        """
        return Query()["id_"] == id_

    def create(self, record: Record | BaseModel) -> None:
        """
        Inserts a record into the specified table.

        Accepts either a pre-built `Record` or a Pydantic `BaseModel` which will
        be converted to a `Record` using `object_to_record`.

        Args:
            record (Record | BaseModel): The record or model to insert.
        Raises:
            ValueError: If a record with the same `_id` already exists.
        """

        # allow callers to pass either a Record wrapper or a BaseModel
        if isinstance(record, Record):
            rec = record
        elif isinstance(record, BaseModel):
            rec = object_to_record(record)
        else:
            raise ValueError("record must be a Record or Pydantic BaseModel")

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
    ) -> BaseModel | None:
        """
        Reads an object by id across all tables and returns the reconstituted
        Pydantic object (as_Base subclass) or None if not found. If
        `raise_on_missing` is True, raises a KeyError when the object is not found.
        """
        for name in self._db.tables():
            tbl = self._table(name)
            rec = tbl.get(self._id_query(object_id))
            if rec:
                # rec is a dict representing Record
                try:
                    record = Record.model_validate(rec)
                    return record_to_object(record)
                except Exception:
                    # fallback: if stored data is already the object dict, return it
                    return rec
        if raise_on_missing:
            raise KeyError(
                f"Object with id '{object_id}' not found in datalayer"
            )
        return None

    def get(
        self, table: str | None = None, id_: str | None = None
    ) -> dict | None:
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
            # search across all tables for this id and return the rehydrated object
            for name in self._db.tables():
                tbl = self._table(name)
                rec = tbl.get(self._id_query(id_))
                if rec:
                    try:
                        record = Record.model_validate(rec)
                        return record_to_object(record)
                    except Exception:
                        return rec
            return None

        # otherwise expect both table and id_ to be provided
        if table is None or id_ is None:
            raise ValueError(
                "get requires either table and id_ or id_ as keyword"
            )

        tbl = self._table(table)
        result = tbl.get(self._id_query(id_))
        return result

    def get_all(self, table: str) -> list[dict]:
        tbl = self._table(table)
        records = tbl.all()
        return records

    def update(self, id_: str, record: Record) -> bool:
        """
        Updates a record by id in the specified table.

        Args:
            table (str): The name of the table.
            id_ (str): The id of the record to update.
            record (dict): The new record data.
        Returns:
            bool: True if a record was updated, False if not found.
        """
        tbl = self._table(record.type_)
        updated = tbl.update(record.model_dump(), self._id_query(id_))
        return len(updated) > 0

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
    ) -> list[Record] | dict[str, BaseModel]:
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
        results: dict[str, BaseModel] = {}
        for name in self._db.tables():
            tbl = self._table(name)
            for rec in tbl.all():
                try:
                    record = Record.model_validate(rec)
                    obj = record_to_object(record)
                    results[record.id_] = obj
                except Exception:
                    # store raw dict if validation fails
                    results[rec.get("id_")] = rec
        return results

    def count_all(self) -> dict[str, int]:
        db = self._db
        counts = {"_default": len(db)}
        for name in db.tables():
            counts[name] = len(db.table(name))
        return counts

    def by_type(self, as_type: str) -> dict[str, dict]:
        """
        Returns a dict mapping object id -> object's data dict for all records of
        the given type (table name).
        """
        if as_type not in self._db.tables():
            return {}

        tbl = self._table(as_type)
        results: dict[str, dict] = {}
        for rec in tbl.all():
            try:
                record = Record.model_validate(rec)
                results[record.id_] = record.data_
            except Exception:
                # fallback: try to return stored dict directly
                if isinstance(rec, dict) and "id_" in rec:
                    results[rec["id_"]] = rec.get("data_") or rec
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

    def find_actor_by_short_id(self, short_id: str) -> BaseModel | None:
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
            if actor_type not in self._db.tables():
                continue

            tbl = self._table(actor_type)
            for rec in tbl.all():
                try:
                    record = Record.model_validate(rec)
                    # Check if the id_ ends with /short_id or is exactly short_id
                    if (
                        record.id_.endswith(f"/{short_id}")
                        or record.id_ == short_id
                    ):
                        return record_to_object(record)
                except Exception:
                    continue

        return None


_datalayer_instance: TinyDbDataLayer | None = None


def get_datalayer(db_path: str | None = "mydb.json") -> TinyDbDataLayer:
    """Factory function to get or create a TinyDbDataLayer instance.

    Uses a singleton pattern to ensure the same instance is reused.
    In tests, dependency injection should be used to override this.

    Args:
        db_path (str | None): The path to the database file. If None, uses in-memory storage.

    Returns:
        TinyDbDataLayer: An instance of TinyDbDataLayer.
    """
    global _datalayer_instance
    if _datalayer_instance is None:
        _datalayer_instance = TinyDbDataLayer(db_path=db_path)
    return _datalayer_instance


def reset_datalayer() -> None:
    """Reset the singleton datalayer instance. Used primarily for testing."""
    global _datalayer_instance
    _datalayer_instance = None


def main():
    pass


if __name__ == "__main__":
    main()
