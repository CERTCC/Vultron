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

from typing import Any

from pydantic import BaseModel, ValidationError

from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

# ActivityStreams fields typed as ``as_ObjectRef`` (accept URI string
# references).  Only these fields are candidates for dehydration.  Fields
# typed as concrete sub-objects (e.g. ``inbox``/``outbox`` on actors,
# ``participant_statuses`` on participants) must remain as inline dicts so
# that round-trip reconstruction via ``model_validate`` continues to work.
_AS_OBJECT_REF_FIELDS: frozenset[str] = frozenset(
    {
        "object_",  # as_TransitiveActivity.object_
        "target",  # optional target on activities
        "origin",  # optional origin on activities
        "result",  # optional result
        "instrument",  # optional instrument
    }
)

# Fields that hold a *list* of object references (ID strings or inline
# objects).  Used by ``DataLayer.hydrate()`` to expand bare ID strings to
# full domain objects — the list analogue of ``_AS_OBJECT_REF_FIELDS``.
_AS_LIST_REF_FIELDS: frozenset[str] = frozenset(
    {
        "case_participants",  # list[CaseParticipantRef] on VulnerabilityCase
    }
)


def _dehydrate_data(data: dict[str, Any]) -> dict[str, Any]:
    """Replace ``as_ObjectRef``-typed fields with their ID string.

    Only fields whose names are in ``_AS_OBJECT_REF_FIELDS`` are
    candidates.  A field value is collapsed to its ID string when it is a
    dict with a non-empty ``id_`` key.  All other fields (including lists)
    are passed through unchanged.

    This ensures that transitive activities (Offer, Create, …) store a URI
    reference to the nested object instead of an inline copy, eliminating
    redundant storage.

    Args:
        data: Serialised (``model_dump(mode="json")``) field dict of a
              domain object.

    Returns:
        A shallow copy of *data* with qualifying nested object dicts
        replaced by ID strings.
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in _AS_OBJECT_REF_FIELDS and isinstance(value, dict):
            # SYNC-13-002/SYNC-02-004: a CaseLedgerEntry is never stored as an
            # independent DataLayer record by ingress, so collapsing it to a
            # bare ID here would lose it (the referent is not resolvable on
            # read/replay).  SYNC-02-004 also requires the full inline entry to
            # travel inside the Announce envelope.  Keep it inline so a
            # replayed Announce(CaseLedgerEntry) still routes and applies its
            # effects.
            if value.get("type_") == "CaseLedgerEntry":
                result[key] = value
                continue
            nested_id = value.get("id_")
            if isinstance(nested_id, str) and nested_id:
                result[key] = nested_id
            else:
                result[key] = value
        else:
            result[key] = value
    return result


def _retype_inline_ref(obj: "BaseModel", field_name: str, raw: object) -> Any:
    """Return a specific-typed instance for one inline ref field, or ``None``.

    Returns ``None`` when *raw* is not an inline typed dict, the type is a base
    ``as_`` type, the vocabulary lookup fails, the field is already typed, or
    re-validation fails — i.e. when no re-typing should occur.
    """
    if not isinstance(raw, dict):
        return None
    type_str = raw.get("type_") or raw.get("type")
    if not isinstance(type_str, str) or type_str.startswith("as_"):
        return None
    try:
        specific_cls = find_in_vocabulary(type_str)
    except KeyError:
        return None
    if isinstance(getattr(obj, field_name, None), specific_cls):
        return None
    try:
        return specific_cls.model_validate(raw)
    except ValidationError:
        return None


def _retype_inline_object_refs(
    obj: "BaseModel", data: dict[str, Any]
) -> "BaseModel":
    """Re-type inline object-reference fields to their specific vocab class.

    Base-vocabulary reconstruction (``find_in_vocabulary(type_).model_validate``)
    validates an inline ``object_``/``target``/… against the base ``as_Object``
    union, which silently drops domain-specific fields (``case_id``,
    ``event_type``, …) because ``as_Object`` ignores extras.  Those fields are
    still present in the raw stored ``data`` dict, so this helper re-parses each
    inline reference with its specific vocabulary class and writes the typed
    object back onto *obj*.

    This keeps inline nested objects (e.g. the ``CaseLedgerEntry`` inside a
    stored ``Announce`` — SYNC-13-002 keeps it inline rather than as a separate
    record) fully typed on read/replay, so semantic routing and effect
    application work without re-reading a separate record.  Generic: it applies
    to any inline typed reference, not just ``CaseLedgerEntry``.
    """
    updates: dict[str, Any] = {}
    for field_name in _AS_OBJECT_REF_FIELDS:
        typed = _retype_inline_ref(obj, field_name, data.get(field_name))
        if typed is not None:
            updates[field_name] = typed
    if not updates:
        return obj
    try:
        return obj.model_copy(update=updates)
    except (ValidationError, TypeError):
        return obj


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
            # serialize_as_any=True serializes each nested object by its runtime
            # type, preserving subtype fields (e.g. a CaseLedgerEntry inline in
            # an Announce keeps case_id/event_type/…).  Without it, an inline
            # object_ typed only as the base union on the parent model would be
            # serialized against the base schema and lose its domain fields —
            # breaking read/replay reconstruction (SYNC-13-004).
            data_=_dehydrate_data(
                obj.model_dump(mode="json", serialize_as_any=True)
            ),
        )
        return record

    def to_obj(self) -> BaseModel:
        """Converts the Record back to a Pydantic BaseModel object.

        Returns:
            BaseModel: The converted object.
        """
        try:
            cls = find_in_vocabulary(self.type_)
        except KeyError:
            raise ValueError(
                f"Type '{self.type_}' not found in vocabulary for Record conversion"
            )
        obj = cls.model_validate(self.data_)
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
