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
from vultron.api.v2.datalayer.db_record import Record

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

    def create(self, record: Record) -> None:
        """
        Inserts a record into the specified table.

        Args:
            record (Record): The record to insert.
        Raises:
            ValueError: If a record with the same `_id` already exists.
        """

        table = record.type_
        id_ = record.id_

        if id_ is None:
            raise ValueError("record must include id_")

        tbl = self._table(table)

        if tbl.contains(self._id_query(id_)):
            raise ValueError(
                f"record with id_={id_} already exists in {table}"
            )

        tbl.insert(record.model_dump())

    def get(self, table: str, id_: str) -> dict | None:
        """
        Retrieves a record by id from the specified table.

        Args:
            table (str): The name of the table.
            id_ (str): The id of the record to retrieve.

        Returns:
            dict | None: The retrieved record, or None if not found.
        """
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
        updated = tbl.update(record, self._id_query(id_))
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

    def all(self, table: str) -> list[Record]:
        """
        Retrieves all records from the specified table.

        Args:
            table (str): The name of the table.
        Returns:
            list[Record]: A list of all records in the table.
        """
        tbl = self._table(table)
        records = tbl.all()
        return [Record.model_validate(rec) for rec in records]

    def count_all(self) -> dict[str, int]:
        db = self._db
        counts = {"_default": len(db)}
        for name in db.tables():
            counts[name] = len(db.table(name))
        return counts

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


def get_datalayer(db_path: str | None = "mydb.json") -> TinyDbDataLayer:
    """Factory function to create a TinyDbDataLayer instance.

    Args:
        db_path (str | None): The path to the database file. If None, uses in-memory storage.

    Returns:
        TinyDbDataLayer: An instance of TinyDbDataLayer.
    """
    return TinyDbDataLayer(db_path=db_path)


def main():
    pass


if __name__ == "__main__":
    main()
