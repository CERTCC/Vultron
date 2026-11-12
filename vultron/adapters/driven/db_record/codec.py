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

"""The stored-row codec: dehydrate a model's data on write, retype on read.

:func:`_dehydrate_data` collapses nested references to ids for storage;
:func:`_retype_inline_object_refs` re-validates the inline snapshots a row
keeps into their declared classes when it is read back.
"""

from typing import Any

from pydantic import BaseModel, ValidationError

from vultron.adapters.driven.db_record.ref_fields import (
    _KEEP_INLINE_NESTED_TYPES,
    _activity_object_ref_properties,
    _inline_required_refs,
    _inline_typed_fields,
    object_ref_fields,
)
from vultron.core.models._helpers import STORED_CONTEXT_KEY
from vultron.core.models.base.core_object import (
    CoreObject,
    unmodelled_object_fields,
)
from vultron.core.models.protocols import PersistableModel
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseReference,
    is_case_reference_shape,
)

STORED_ROW_CONTEXT: dict[str, bool] = {STORED_CONTEXT_KEY: True}
"""Validation context for reading a stored row back (``STORED_CONTEXT_KEY``)."""


# Trailing-underscore Python field names whose wire-facing names differ and
# must be used in persisted rows (ARCH-23-005).  Only the three identity
# fields have this property; every other field is either identical to its
# wire name (snake_case → snake_case) or a camelCase alias that this path
# MUST NOT apply (ARCH-20-001).
_PYTHON_TO_WIRE_IDENTITY_KEYS: dict[str, str] = {
    "id_": "id",
    "type_": "type",
    "context_": "@context",
}


def _rekey_wire_identity(data: dict[str, Any]) -> dict[str, Any]:
    """Rename Python trailing-underscore identity keys to their wire-facing names.

    Renames ``id_`` → ``id``, ``type_`` → ``type``, and ``context_`` →
    ``@context`` recursively through all dict values and list-of-dict items,
    per ARCH-23-005.  Only those three keys are renamed; all others pass
    through unchanged, so no camelCase is introduced (contrast: blanket
    ``by_alias=True`` would apply the ``alias_generator=to_camel`` and make
    every field camelCase).

    Applied to the result of :func:`_dehydrate_data` before the dict is
    stored in :attr:`Record.data_`.  Read-back tolerates both spellings via
    ``populate_by_name=True`` / ``validate_by_name=True`` on all model roots,
    so existing rows keyed ``id_``/``type_`` continue to round-trip correctly
    (AC-3).
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        wire_key = _PYTHON_TO_WIRE_IDENTITY_KEYS.get(key, key)
        if isinstance(value, dict):
            result[wire_key] = _rekey_wire_identity(value)
        elif isinstance(value, list):
            result[wire_key] = [
                _rekey_wire_identity(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[wire_key] = value
    return result


def _dehydrate_data(
    data: dict[str, Any], obj: PersistableModel | BaseModel | None = None
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

    Three things are never collapsed:

    - a nested value whose ``type_`` is in ``_KEEP_INLINE_NESTED_TYPES``;
    - a field named in *obj*'s ``inline_required_refs`` (or its semantic
      class's, see :func:`_inline_required_refs`), for models whose protocol
      contract is to carry the object rather than reference it;
    - a typed case reference (:class:`as_VulnerabilityCaseReference`), which
      names a case and has no record of its own: collapsed to its id, it
      would be read back as a bare id, and routing could no longer tell its
      type when the store does not hold the case (ADR-0165).

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
        inline_required = _inline_required_refs(obj)

    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in inline_required:
            # The model declares this ref is carried, not referenced. Collapsing
            # it would store a URI that nothing can resolve.
            result[key] = value
            continue
        if isinstance(getattr(obj, key, None), as_VulnerabilityCaseReference):
            # A reference is already the smallest form, and the case it names
            # need not be held here (ADR-0165).
            result[key] = value
            continue
        if key in ref_fields and isinstance(value, dict):
            # Keep Activity-type and CaseLedgerEntry nested objects inline.
            # These may not have independent DataLayer records (e.g. a
            # reconstituted Offer in validate-report, or a CaseLedgerEntry
            # inside an Announce envelope), so collapsing them to a bare ID
            # would make rehydration impossible on outbox read-back, causing
            # AKM-03-003 gate failures.  See _KEEP_INLINE_NESTED_TYPES.
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


def _retype_inline_ref(obj: BaseModel, field_name: str, raw: object) -> Any:
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
    reference: dict[str, Any] = {
        _PYTHON_TO_WIRE_IDENTITY_KEYS.get(str(k), str(k)): v
        for k, v in raw.items()
        if v is not None
    }
    if is_case_reference_shape(reference):
        # A stored case reference reads back as one, never as a sparse case
        # that fails the case's validation (ADR-0165).
        if isinstance(
            getattr(obj, field_name, None), as_VulnerabilityCaseReference
        ):
            return None
        return as_VulnerabilityCaseReference.model_validate(reference)
    try:
        # Both-branch: a stored inline ref may be any persisted type, core
        # records included, so this read path opts into the core fallback
        # (VM-06-014).
        specific_cls = find_in_vocabulary(type_str, include_core=True)
    except KeyError:
        return None
    if isinstance(getattr(obj, field_name, None), specific_cls):
        return None
    try:
        return specific_cls.model_validate(raw, context=STORED_ROW_CONTEXT)
    except ValidationError:
        return None


def _retype_inline_object_refs(
    obj: BaseModel, data: dict[str, Any]
) -> BaseModel:
    """Re-type inline object-reference fields to their specific vocab class.

    Base-vocabulary reconstruction (``find_in_vocabulary(type_).model_validate``)
    validates an inline ``object_``/``target``/… against the base ``as_Object``
    union, which silently drops domain-specific fields (``case_id``,
    ``semantic_type``, …) because ``as_Object`` ignores extras.  Those fields are
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
    except ValidationError, TypeError:
        return obj


def _build_unmodelled_item(item: object) -> object:
    """Build one stored slot value as its own wire class, when core lacks it."""
    if not isinstance(item, dict):
        return item
    type_str = item.get("type") or item.get("type_")
    if not isinstance(type_str, str):
        return item
    try:
        # Both-branch, as for every stored read (VM-06-014).
        specific_cls = find_in_vocabulary(type_str, include_core=True)
    except KeyError:
        return item
    if issubclass(specific_cls, CoreObject):
        return item
    try:
        return specific_cls.model_validate(item, context=STORED_ROW_CONTEXT)
    except ValidationError:
        # Left as stored: the row's own validation then names the fault.
        return item


def _build_unmodelled_inline(
    cls: type[BaseModel], data: dict[str, Any]
) -> dict[str, Any]:
    """Build each stored object core does not model before *cls* reads *data*.

    A core object's AS2 reference slot may hold a wire object, such as a Link
    or a Mention, as the parse edge built it.  Stored, it is a mapping that is
    not a ``CoreObject``, and the slot admits only a built model in its place,
    so the row would not read back.  Each such mapping is built as the class
    its ``type`` names first.
    """
    if not issubclass(cls, CoreObject):
        return data
    fields = unmodelled_object_fields(cls)
    updates: dict[str, Any] = {}
    for name in fields & data.keys():
        raw = data[name]
        if isinstance(raw, list):
            built: object = [_build_unmodelled_item(item) for item in raw]
        else:
            built = _build_unmodelled_item(raw)
        if built is not raw:
            updates[name] = built
    return {**data, **updates} if updates else data
