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

"""The :class:`Record` model and its object conversions."""

from pydantic import BaseModel

from vultron.adapters.driven.db_record.codec import (
    STORED_ROW_CONTEXT,
    _build_unmodelled_inline,
    _dehydrate_data,
    _rekey_wire_identity,
    _retype_inline_object_refs,
)
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
    def from_obj(cls, obj: PersistableModel) -> Record:
        """Creates a Record from a Pydantic BaseModel object.

        Args:
            obj: The object to convert.
        Returns:
            Record: The created Record.
        """
        obj_type = obj.type_
        # Two distinct faults, reported distinctly.  They were previously raised
        # with one message naming only the ``as_`` case, which sent a reader
        # hunting for a wire class when the object simply had no ``type_`` —
        # ``type_`` selects the table, so neither can be stored.
        if obj_type is None:
            raise ValueError(
                f"Object of class {type(obj).__name__!r} (id={obj.id_!r}) has no"
                " 'type_' attribute, which is what selects the storage table;"
                " it cannot be converted to a Record"
            )
        if obj_type.startswith("as_"):
            raise ValueError(
                f"Object 'type_' attribute {obj_type!r} cannot start with 'as_'"
                " for Record conversion"
            )

        record = Record(
            id_=obj.id_,
            type_=obj_type,
            # serialize_as_any=True serializes each nested object by its runtime
            # type, preserving subtype fields (e.g. a CaseLedgerEntry inline in
            # an Announce keeps case_id/semantic_type/…).  Without it, an inline
            # object_ typed only as the base union on the parent model would be
            # serialized against the base schema and lose its domain fields —
            # breaking read/replay reconstruction (SYNC-13-004).
            # ``obj`` is passed so its ``inline_required_refs`` are honoured.
            # _rekey_wire_identity renames id_/type_ to id/type at every nesting
            # level so stored rows carry wire-facing keys (ARCH-23-005).
            data_=_rekey_wire_identity(
                _dehydrate_data(
                    obj.model_dump(mode="json", serialize_as_any=True), obj
                )
            ),
        )
        return record

    def to_obj(self) -> BaseModel:
        """Converts the Record back to a Pydantic BaseModel object.

        Returns:
            BaseModel: The converted object.
        """
        try:
            # Both-branch: a record holds whatever was stored, including core
            # records keyed only in CORE_TYPE_MAP (VM-06-014).
            cls = find_in_vocabulary(self.type_, include_core=True)
        except KeyError:
            raise ValueError(  # noqa: B904  # ruff-baseline #3353
                f"Type '{self.type_}' not found in vocabulary for Record conversion"
            )
        # A stored row: a validator that defaults an omitted field refuses
        # the omission instead (STORED_CONTEXT_KEY).
        obj = cls.model_validate(
            _build_unmodelled_inline(cls, self.data_),
            context=STORED_ROW_CONTEXT,
        )
        return _retype_inline_object_refs(obj, self.data_)


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
