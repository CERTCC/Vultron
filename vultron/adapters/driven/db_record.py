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

from typing import Any, cast

from pydantic import BaseModel, ValidationError

from vultron.core.models.protocols import PersistableModel
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.core.ports.datalayer import StorableRecord
from vultron.errors import VultronValidationError
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

_WIRE_MODULE_PREFIX = "vultron.wire.as2"

# Wire vocabulary ``type_`` values are *bare* names ("CaseParticipant"), not
# ``as_``-prefixed, so the ``as_`` guard in ``Record.from_obj`` never fires for
# them.  Fifteen wire classes therefore shadow a ``CORE_VOCABULARY`` entry and
# can be written into a core-typed row, producing a row whose field shape does
# not match the class that reads it back (issue #2232).
#
# Types listed here are normalised to their core counterpart via ``to_core()``
# before serialisation, so the persisted row always carries the canonical core
# shape.  The set may only GROW as the remaining shadowing types are migrated;
# it is the write-side analogue of ``KNOWN_WIRE_ESCAPES`` in
# ``test/architecture/test_dl_read_returns_core_objects.py`` (DL-05-004).
#
# ``ParticipantStatus`` and ``CaseParticipant`` are normalised because their
# two shapes are structurally incompatible: core nests ``rm: RmDimension``
# while wire uses a flat ``rm_state``, so a wire-shaped row silently yields
# ``None`` for ``status.rm.state``.  The other thirteen shadowing types
# (``VulnerabilityCase``, ``VulnerabilityReport``, the actor types, …) differ
# only by key spelling today and are not yet normalised — tracked in #2268.
_NORMALIZE_WIRE_TO_CORE: frozenset[str] = frozenset(
    {
        "CaseParticipant",
        "ParticipantStatus",
    }
)

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

# AS2 Activity ``type_`` strings (transitive + intransitive) plus
# ``CaseLedgerEntry``.  When a nested ``_AS_OBJECT_REF_FIELDS`` value has one
# of these types it MUST be kept inline rather than collapsed to a bare ID
# string: Activities may not have independent DataLayer records (e.g. a
# reconstituted Offer in the validate-report path, a CaseLedgerEntry inside an
# Announce envelope), so dehydrating them would make rehydration impossible on
# read-back and cause MV-09-001 outbox-gate failures.
_KEEP_INLINE_NESTED_TYPES: frozenset[str] = frozenset(
    {
        # as_TransitiveActivityType values
        "Accept",
        "Add",
        "Announce",
        "Block",
        "Create",
        "Delete",
        "Dislike",
        "Flag",
        "Follow",
        "Ignore",
        "Invite",
        "Join",
        "Leave",
        "Like",
        "Listen",
        "Move",
        "Offer",
        "Read",
        "Reject",
        "Remove",
        "TentativeAccept",
        "TentativeReject",
        "Undo",
        "Update",
        "View",
        # as_IntransitiveActivityType values
        "Arrive",
        "Question",
        "Travel",
        # Vultron-specific type kept inline for the same reason
        "CaseLedgerEntry",
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
            # Keep Activity-type and CaseLedgerEntry nested objects inline.
            # These may not have independent DataLayer records (e.g. a
            # reconstituted Offer in validate-report, or a CaseLedgerEntry
            # inside an Announce envelope), so collapsing them to a bare ID
            # would make rehydration impossible on outbox read-back, causing
            # MV-09-001 gate failures.  See _KEEP_INLINE_NESTED_TYPES.
            if value.get("type_") in _KEEP_INLINE_NESTED_TYPES:
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
        raw_sub = data.get(field_name)
        typed = _retype_inline_ref(obj, field_name, raw_sub)
        if typed is not None:
            if isinstance(raw_sub, dict):
                typed = _retype_inline_object_refs(typed, raw_sub)
            updates[field_name] = typed
    if not updates:
        return obj
    try:
        return obj.model_copy(update=updates)
    except (ValidationError, TypeError):
        return obj


def _project_shadowing_wire_obj(obj: "BaseModel") -> "BaseModel":
    """Project one object to its core counterpart when it shadows a core type.

    Returns *obj* unchanged unless it is a wire class whose bare ``type_``
    shadows a :data:`_NORMALIZE_WIRE_TO_CORE` entry.

    Raises:
        VultronValidationError: when the wire object cannot be projected to its
            core counterpart.  Core types are stricter than wire types, so a
            projection failure means the object was never valid domain data;
            surfacing it beats persisting a row nothing can read (ARCH-15-002).
            A dedicated error type — not a bare ``ValueError`` — because
            ``crud.create`` raises ``ValueError`` for an already-existing row
            and callers legitimately swallow *that*; the two must stay
            distinguishable.
    """
    if not type(obj).__module__.startswith(_WIRE_MODULE_PREFIX):
        return obj
    type_ = getattr(obj, "type_", None)
    if not isinstance(type_, str):
        return obj
    if type_ not in _NORMALIZE_WIRE_TO_CORE or type_ not in CORE_VOCABULARY:
        return obj
    to_core = getattr(obj, "to_core", None)
    if to_core is None:
        raise VultronValidationError(
            f"Wire class {type(obj).__name__} shadows core type '{type_}' but"
            " has no to_core() projection, so it cannot be persisted in the"
            " canonical core shape (issue #2232)."
        )
    _PROJECTION_ERRORS = (
        ValidationError,
        VultronValidationError,
        ValueError,
        TypeError,
    )
    try:
        return cast("BaseModel", to_core())
    except _PROJECTION_ERRORS as exc:
        raise VultronValidationError(
            f"Cannot persist {type(obj).__name__}"
            f" '{getattr(obj, 'id_', '<no id>')}': projecting it to core type"
            f" '{type_}' failed ({exc}). A wire-shaped '{type_}' row must not"
            " be stored — normalise at the wire→core boundary instead"
            " (issue #2232)."
        ) from exc


def _normalize_to_core(obj: PersistableModel) -> PersistableModel:
    """Return the core-shaped equivalent of *obj*, or *obj* unchanged.

    A wire vocabulary class whose bare ``type_`` shadows a ``CORE_VOCABULARY``
    entry would otherwise be written into a core-typed row in the wire field
    shape, so whichever class reads the row back decides what the data means
    (issue #2232).  For the types in :data:`_NORMALIZE_WIRE_TO_CORE` the
    difference is structural — core ``ParticipantStatus`` nests
    ``rm: RmDimension`` where the wire shape carries a flat ``rm_state`` — so
    the row is normalised here, at the persistence boundary, and no
    wire-shaped row is ever stored.

    Both the object itself **and its direct children** are projected.  Only
    checking the top level left the invariant unmet in the case that motivated
    it: a ``VulnerabilityCase`` row stores its ``case_participants`` inline, so
    a wire-shaped participant nested inside a core-shaped case still persisted a
    flat ``rm_state``.  One level of child projection is sufficient because
    ``to_core()`` recurses — projecting an ``as_CaseParticipant`` also projects
    its ``as_ParticipantStatus`` children.

    Raises:
        VultronValidationError: when a wire object (at either level) cannot be
            projected to its core counterpart.
    """
    if not isinstance(obj, BaseModel):
        return obj
    model = _project_shadowing_wire_obj(obj)
    updates: dict[str, Any] = {}
    for field_name in type(model).model_fields:
        value = getattr(model, field_name, None)
        if isinstance(value, BaseModel):
            projected = _project_shadowing_wire_obj(value)
            if projected is not value:
                updates[field_name] = projected
        elif isinstance(value, list) and value:
            items = [
                (
                    _project_shadowing_wire_obj(item)
                    if isinstance(item, BaseModel)
                    else item
                )
                for item in value
            ]
            if any(new is not old for new, old in zip(items, value)):
                updates[field_name] = items
    if not updates:
        return cast(PersistableModel, model)
    # ``model_copy`` rather than re-validation: the parent's field is declared
    # with the *wire* child type, so validating a core child against it would
    # fail.  ``model_dump(serialize_as_any=True)`` in ``from_obj`` serialises
    # each child by its runtime type, so the core shape is what reaches the row.
    return cast(PersistableModel, model.model_copy(update=updates))


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

        # Wire ``type_`` values are bare, so the guard above cannot catch a
        # wire class shadowing a core type.  Normalise those to the canonical
        # core shape before serialising (issue #2232).
        obj = _normalize_to_core(obj)

        record = Record(
            id_=obj.id_,
            type_=obj_type,
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
