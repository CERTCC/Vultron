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

"""Provides a Record model for document database storage."""

from pydantic import BaseModel

from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary


class Record(StorableRecord):
    """Record wrapper stored in TinyDB.

    Extends ``StorableRecord`` (from ``core/ports/``) with adapter-layer
    helpers for converting to/from domain objects via the wire vocabulary.
    Internally fields are ``id_``, ``type_``, and ``data_``.
    ``type_`` selects both the table name and the class used to reconstitute
    the object when reading.  ``data_`` holds the object's serialised data.
    """

    @classmethod
    def from_obj(cls, obj: PersistableModel) -> "Record":
        """Creates a Record from a Pydantic BaseModel object.

        Args:
            obj: The object to convert.
        Returns:
            Record: The created Record.
        """
        if obj.type_.startswith("as_"):
            raise ValueError(
                "Object 'type_' attribute cannot start with 'as_' for Record conversion"
            )

        record = Record(
            id_=obj.id_,
            type_=obj.type_,
            data_=obj.model_dump(mode="json"),
        )
        return record

    def to_obj(self) -> BaseModel:
        """Converts the Record back to a Pydantic BaseModel object.

        Returns:
            BaseModel: The converted object.
        """
        cls = find_in_vocabulary(self.type_)
        if cls is None:
            raise ValueError(
                f"Type '{self.type_}' not found in vocabulary for Record conversion"
            )
        return cls.model_validate(self.data_)


def object_to_record(obj: PersistableModel) -> Record:
    """Converts a Pydantic BaseModel object to a Record for storage.

    Args:
        obj: The object to convert.
    Returns:
        Record: The converted Record.
    """
    return Record.from_obj(obj)


def record_to_object(record: Record) -> BaseModel:
    """Converts a Record back to a Pydantic BaseModel object.

    Args:
        record (Record): The Record to convert.
        registry (Vocabulary): The vocabulary registry to use for class lookup.
    Returns:
        BaseModel: The converted object.
    """
    return record.to_obj()


def main():
    pass


if __name__ == "__main__":
    main()
