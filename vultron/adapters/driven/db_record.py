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

from functools import lru_cache
from typing import Any, get_args

from pydantic import BaseModel, ValidationError

from vultron.core.models.base import CoreObject
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord
from vultron.wire.as2.enums import (
    as_IntransitiveActivityType,
    as_TransitiveActivityType,
)
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary


def _is_generic_object_ref(annotation: Any) -> bool:
    """True when *annotation* is a reference to the *generic* ``as_Object``.

    The generic AS2 object-reference alias ``as_ObjectRef`` expands to
    ``as_Object | as_Link | str | None`` and its required form
    ``as_ObjectRequiredRef`` to ``as_Object | as_Link | str`` (no ``None``).
    Both are matched; a *narrowed* reference (``as_ActorRef`` →
    ``as_Actor | as_Link | str | None``) is not, because its ``T`` is a
    subclass of ``as_Object`` rather than ``as_Object`` itself.  This is the
    single property that separates the AS2 Activity object-reference fields
    from narrowed refs, JSON-LD ``context``/``in_reply_to`` (typed ``Any``),
    and unrelated types' refs (``as_Relationship.subject``, …).

    Under ADR-0099 detail 3 the aliases also admit ``CoreObject`` — a core
    object *is* its own wire object, so it may sit inline in an activity — and
    that widened form is matched too.  Missing it silently drops ``object_``,
    ``target``, ``origin`` and ``instrument`` from dehydration, so a stored
    activity's inline object reads back as a bare ``as_Object`` and semantic
    matching no longer recognises the activity.
    """
    args = set(get_args(annotation)) - {CoreObject}
    return args in (
        {as_Object, as_Link, str},
        {as_Object, as_Link, str, type(None)},
    )


@lru_cache(maxsize=1)
def _activity_object_ref_properties() -> frozenset[str]:
    """The generic object-reference field names of the AS2 Activity model.

    Derived from ``as_TransitiveActivity``'s own annotations — the single
    source of truth (ARCH-23-004).  ``object_`` is inherited by every
    transitive activity; ``target``/``origin``/``result``/``instrument`` come
    from ``as_Activity``.  This replaces the former hand-maintained frozenset
    restatement that could silently drift from the annotations it claimed to
    mirror (#2936).
    """
    return frozenset(
        name
        for name, field in as_TransitiveActivity.model_fields.items()
        if _is_generic_object_ref(field.annotation)
    )


@lru_cache(maxsize=None)
def object_ref_fields(cls: type[BaseModel]) -> frozenset[str]:
    """The generic AS2 object-reference fields *cls* actually declares.

    These fields hold either an inline object or a bare URI string, so they
    are the only ones eligible for dehydration to an ID on write and
    rehydration back to an object on read.  Fields typed as concrete
    sub-objects (``inbox``/``outbox`` on actors, ``participant_statuses`` on
    participants) are excluded and stay inline, so ``model_validate``
    round-trips.

    Computed as the intersection of the model's own fields with the
    Activity-model object-reference properties, cached per class.  A model that
    narrows one of these names to a plain URI (``as_CaseProposal.target``,
    CP-01-005) still lists it — the name is what the storage layer keys on;
    :func:`~vultron.adapters.driven.datalayer_sqlite.hydration.field_admits_object`
    is the runtime guard that then declines to expand it.
    """
    return _activity_object_ref_properties() & frozenset(cls.model_fields)


# AS2 Activity ``type_`` strings (transitive + intransitive) plus
# ``CaseLedgerEntry``.  When a nested object-reference value has one
# of these types it MUST be kept inline rather than collapsed to a bare ID
# string for two independent reasons:
#
# 1. Technical: Activities may not have independent DataLayer records (e.g. a
#    reconstituted Offer in the validate-report path, a CaseLedgerEntry inside
#    an Announce envelope), so dehydrating them would make rehydration
#    impossible on read-back and cause AKM-03-001 outbox-gate failures.
#
# 2. Semantic (more important): a received Activity is an artifact; its inline
#    sub-fields are a snapshot of state at receipt time.  An
#    Accept(Offer(VulnerabilityCase)) captures what was offered at the moment
#    of acceptance, not the current case state.  This must not be changed even
#    if Activities eventually gain independent DataLayer records.  See
#    notes/datalayer-design.md § "Received Activity Artifacts: Inline
#    Sub-Field Snapshots Are Intentional".
_KEEP_INLINE_NESTED_TYPES: frozenset[str] = frozenset(
    {e.value for e in as_TransitiveActivityType}
    | {e.value for e in as_IntransitiveActivityType}
    | {"CaseLedgerEntry"}
)


def _inline_typed_fields(cls: type[BaseModel]) -> frozenset[str]:
    """Fields of *cls* whose inline value must be re-typed on read-back.

    A superset of :func:`object_ref_fields`: re-typing is safe for any field
    that can hold an inline typed object, whereas *dehydration* is only safe
    for a field declared as a reference, so the two sets are deliberately
    distinct.

    ``context`` is here and not in :func:`object_ref_fields`.  It is never
    dehydrated, so it is always stored whole — but nothing re-typed it either,
    and ``as_Activity.context`` is loosely typed, so read-back left a raw
    ``dict``.  That is enough to break semantic matching:
    ``_OfferCaseParticipantRoleActivity`` is recognised by its ``context``
    being a ``VulnerabilityCase`` (ADR-0039), so a stored role offer came back
    classified UNKNOWN, was never coerced out of the base ``as_Offer``, and the
    receiver had no semantics to dispatch on.
    """
    return object_ref_fields(cls) | {"context"}


# Fields that hold a *list* of object references (ID strings or inline
# objects).  Used by ``DataLayer.hydrate()`` to expand bare ID strings to
# full domain objects — the list analogue of the object-reference fields.
_AS_LIST_REF_FIELDS: frozenset[str] = frozenset(
    {
        "case_participants",  # list[CaseParticipantRef] on VulnerabilityCase
    }
)


def _dehydrate_data(
    data: dict[str, Any], obj: "PersistableModel | BaseModel | None" = None
) -> dict[str, Any]:
    """Replace generic object-reference fields with their ID string.

    Only fields returned by :func:`object_ref_fields` are candidates (or, when
    *obj* is omitted, the Activity-model object-reference properties).  A field
    value is collapsed to its ID string when it is a dict with a non-empty
    ``id_`` key.  All other fields (including lists) are passed through
    unchanged.

    This ensures that transitive activities (Offer, Create, …) store a URI
    reference to the nested object instead of an inline copy, eliminating
    redundant storage.

    Two things are never collapsed:

    - a nested value whose ``type_`` is in ``_KEEP_INLINE_NESTED_TYPES``;
    - a field named in *obj*'s ``inline_required_refs``, for models whose
      protocol contract is to carry the object rather than reference it.

    Both exist for the same reason: dehydration is only reversible when the
    nested object has a record of its own to be read back from.  It often does
    not — ingress gives a record only to the *first* level of an inbound
    activity's nesting — and a collapse with no counterpart write is silent
    data loss that surfaces far away (#2482).

    Kept-inline values are stored whole, without further recursion into their
    own sub-fields, so their nested values are a snapshot of state at write
    time — intentional artifact semantics.  See ``_KEEP_INLINE_NESTED_TYPES``
    and ``notes/datalayer-design.md``
    § "Received Activity Artifacts: Inline Sub-Field Snapshots Are
    Intentional" for why this must not be changed to recursive dehydration.

    Args:
        data: Serialised (``model_dump(mode="json")``) field dict of a
              domain object.
        obj: The object *data* was serialised from, consulted for its
             ``inline_required_refs`` declaration.  Optional so that callers
             testing the dict transform alone need not construct a model;
             omitting it only forgoes the per-model exemption.

    Returns:
        A shallow copy of *data* with qualifying nested object dicts
        replaced by ID strings.
    """
    inline_required: frozenset[str] = frozenset()
    ref_fields = _activity_object_ref_properties()
    if obj is not None:
        ref_fields = object_ref_fields(type(obj))
        declared = getattr(type(obj), "inline_required_refs", None)
        if isinstance(declared, frozenset | set):
            inline_required = frozenset(declared)

    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in inline_required:
            # The model declares this ref is carried, not referenced. Collapsing
            # it would store a URI that nothing can resolve.
            result[key] = value
            continue
        if key in ref_fields and isinstance(value, dict):
            # Keep Activity-type and CaseLedgerEntry nested objects inline.
            # These may not have independent DataLayer records (e.g. a
            # reconstituted Offer in validate-report, or a CaseLedgerEntry
            # inside an Announce envelope), so collapsing them to a bare ID
            # would make rehydration impossible on outbox read-back, causing
            # AKM-03-001 gate failures.  See _KEEP_INLINE_NESTED_TYPES.
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

    Iterates :func:`_inline_typed_fields`, not :func:`object_ref_fields` —
    re-typing what is already stored inline is always safe, so its scope is
    wider than dehydration's.  See that helper for why ``context`` needs it.
    """
    updates: dict[str, Any] = {}
    for field_name in _inline_typed_fields(type(obj)):
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

        record = Record(
            id_=obj.id_,
            type_=obj_type,
            # serialize_as_any=True serializes each nested object by its runtime
            # type, preserving subtype fields (e.g. a CaseLedgerEntry inline in
            # an Announce keeps case_id/event_type/…).  Without it, an inline
            # object_ typed only as the base union on the parent model would be
            # serialized against the base schema and lose its domain fields —
            # breaking read/replay reconstruction (SYNC-13-004).
            # ``obj`` is passed so its ``inline_required_refs`` are honoured.
            data_=_dehydrate_data(
                obj.model_dump(mode="json", serialize_as_any=True), obj
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
