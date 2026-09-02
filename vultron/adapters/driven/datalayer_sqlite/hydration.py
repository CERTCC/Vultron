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

"""Row ↔ domain-object conversion for the SQLite DataLayer.

One responsibility: turning a :class:`~.schema.VultronObjectRecord` into the
most precise domain object the registries can name, and back.  Nothing here
opens a session or issues SQL — the callers in :mod:`.crud` and :mod:`.queries`
own that, and hand rows in.

Split out of ``datalayer.py`` (CS-18-002): that module had grown to two
unrelated jobs, this pipeline and a thin delegating façade over the other
submodules.  The functions take the DataLayer as their first argument, the same
shape :mod:`.crud`, :mod:`.queries` and :mod:`.queues` already use, so
``SqliteDataLayer``'s methods stay one-line delegations and every existing
``dl._from_row(row)`` call site keeps working.
"""

import logging
from typing import TYPE_CHECKING, Any, cast, get_args

from pydantic import BaseModel, ValidationError

from vultron.adapters.driven.db_record import (
    Record,
    _AS_LIST_REF_FIELDS,
    _AS_OBJECT_REF_FIELDS,
    record_to_object,
)
from vultron.core.models import find_in_core_vocabulary
from vultron.core.models.protocols import PersistableModel
from vultron.errors import VultronValidationError
from vultron.semantic_registry import (
    find_matching_semantics,
    semantics_to_activity_class as _semantics_to_activity_class,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

from .schema import VultronObjectRecord

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for typing only
    # ``datalayer`` imports this module to build its own methods, so the name
    # can only be a forward reference here.
    from .datalayer import SqliteDataLayer

logger = logging.getLogger(__name__)


def field_admits_object(obj: Any, field_name: str) -> bool:
    """True when *field_name* on *obj* can legitimately hold a nested object.

    ``_AS_OBJECT_REF_FIELDS`` names fields that are *usually* references, but the
    same name can be declared as a plain URI on a particular model (for instance
    ``as_CaseProposal.target``, required by CP-01-005 to be the case-actor's URI).
    Expanding such a field yields a model that violates its own annotation —
    ``model_copy`` does not validate, so the breach surfaces later and elsewhere.

    Unknown fields are treated as expandable, preserving the previous behaviour
    for models that do not declare the field at all.
    """
    # ``PersistableModel`` is a Protocol, so ``model_fields`` is reached
    # defensively rather than assumed.
    model_fields = getattr(type(obj), "model_fields", None)
    field = model_fields.get(field_name) if model_fields else None
    if field is None:
        return True
    annotation = field.annotation
    if annotation is None:
        return True
    candidates = list(get_args(annotation)) or [annotation]
    for candidate in candidates:
        # Unwrap one more level for containers such as ``Ref[as_Foo]``.
        parts = list(get_args(candidate)) or [candidate]
        for part in parts:
            if isinstance(part, type) and issubclass(part, BaseModel):
                return True
    return False


def to_row(obj: PersistableModel) -> VultronObjectRecord:
    """Convert a domain object to a storage row.

    No ``actor_id`` column is written: the store *is* the actor's, so
    stamping ownership on each row would be redundant (ADR-0073).
    """
    rec = Record.from_obj(obj)
    return VultronObjectRecord(
        id_=rec.id_,
        type_=rec.type_,
        data=rec.data_,
    )


def from_row(
    dl: "SqliteDataLayer", row: VultronObjectRecord
) -> PersistableModel | None:
    """Convert a storage row back to a fully-typed domain object.

    Reconstruction is a three-step pipeline:

    1. Core-vocabulary lookup — if the stored ``type_`` has a registered
       core counterpart in ``CORE_VOCABULARY``, reconstruct via
       ``find_in_core_vocabulary(type_).model_validate(data)`` (DL-05-001,
       DL-05-002).  This ensures domain entities round-trip as core objects
       rather than wire vocabulary types.  For persisted AS2 Activity types
       (no core counterpart), falls back to the wire vocabulary path below.
    2. ``record_to_object`` — wire-vocabulary base-type reconstruction
       (fallback for AS2 Activities and any type not in ``CORE_VOCABULARY``).
    3. :func:`rehydrate_fields` — expand dehydrated ``object_`` / ``target`` /
       ``origin`` / ``result`` / ``instrument`` ID strings back to typed
       Pydantic objects by reading them from the DataLayer.
    4. :func:`coerce_to_semantic_class` — pattern-match the rehydrated object
       against ``SEMANTIC_REGISTRY`` and, when a more specific
       Python class is known (e.g. ``RmSubmitReportActivity`` for
       ``as_Offer``), coerce via ``model_validate`` so that callers always
       receive the most precise type without manual coercion.
    """
    wire_obj: PersistableModel | None
    try:
        core_cls = find_in_core_vocabulary(row.type_)
    except KeyError:
        # No core counterpart (AS2 Activity types) → wire vocabulary path.
        wire_obj = wire_object_from_row(row)
        if wire_obj is None:
            return None
        obj = wire_obj
    else:
        try:
            obj = cast(PersistableModel, core_cls.model_validate(row.data))
        except ValidationError as exc:
            # Stored data came from a wire object whose schema differs from
            # the core class (e.g. as_EmbargoEvent lacks context).  Return
            # the wire object un-projected: that is the long-standing
            # behaviour the KNOWN_WIRE_ESCAPES ratchet in
            # test/architecture/test_dl_read_returns_core_objects.py
            # measures, and projecting here would dehydrate inline nested
            # objects that callers of these rows still expect inline.
            logger.debug(
                "from_row: core_cls.model_validate failed for type %r"
                " (row %r): %s; using wire fallback",
                row.type_,
                row.id_,
                exc,
            )
            wire_obj = wire_object_from_row(row)
            if wire_obj is None:
                return None
            obj = wire_obj
        except VultronValidationError as exc:
            # A core type's own shape guard rejected the row — e.g.
            # CaseParticipant's wire-spelled-key guard (#2232).  It is not a
            # ValueError subclass, so without naming it here it would escape
            # this ladder entirely instead of falling back like every other
            # shape mismatch (DL-05-002).
            #
            # Unlike the ValidationError case above, the row *is* a
            # wire-spelled copy of a core type, so project it: handing back
            # a wire object makes every core-typed caller fail (resolve_case
            # raises "Expected VulnerabilityCase, got as_VulnerabilityCase").
            logger.debug(
                "from_row: VultronValidationError for type %r (row %r):"
                " %s; projecting wire row to core",
                row.type_,
                row.id_,
                exc,
            )
            wire_obj = wire_object_from_row(row)
            if wire_obj is None:
                return None
            obj = project_wire_row_to_core(row, wire_obj, exc)
    if obj is None:
        return None
    obj = rehydrate_fields(dl, obj)
    return coerce_to_semantic_class(obj)


def wire_object_from_row(
    row: VultronObjectRecord,
) -> PersistableModel | None:
    """Reconstruct *row* through the wire vocabulary, or ``None``."""
    rec = Record(id_=row.id_, type_=row.type_, data_=row.data)
    try:
        return cast(PersistableModel, record_to_object(rec))
    except (ValueError, ValidationError, VultronValidationError):
        return None


def project_wire_row_to_core(
    row: VultronObjectRecord,
    wire_obj: PersistableModel,
    core_exc: Exception,
) -> PersistableModel:
    """Project a wire-vocabulary fallback back to its core counterpart.

    :func:`from_row` reaches this only when the row's ``type_`` *has* a core
    counterpart but the stored data does not validate against it, so the
    wire class was used instead.  Handing that wire object to core callers
    is what DL-05-001/DL-05-002 forbid: a wire ``as_VulnerabilityCase``
    reaching ``resolve_case`` raises "Expected VulnerabilityCase, got
    as_VulnerabilityCase" rather than reading the case (issue #2232).

    ``to_core()`` is the same projection the write path applies in
    ``_normalize_to_core`` — the persistence-boundary half of ADR-0062,
    applied on the way out as well as on the way in.  Wire types are looser
    than core types, so a row that fails core validation directly can still
    project cleanly: ``to_core()`` maps flat wire spellings onto the nested
    core shape instead of dropping them.

    When the projection also fails, *wire_obj* is returned unchanged — that
    is the pre-#2232 behaviour for these rows, and degrading it to ``None``
    would turn a wrongly-typed read into a missing-object read.  Both
    outcomes are logged: a silent fallback here is what made this class of
    shape bug so hard to trace.
    """
    to_core = getattr(wire_obj, "to_core", None)
    if to_core is None:
        logger.warning(
            "Row %r (type %r) failed core validation (%s) and its wire"
            " fallback %s has no to_core() projection; returning the wire"
            " object (DL-05-002, issue #2232).",
            row.id_,
            row.type_,
            core_exc,
            type(wire_obj).__name__,
        )
        return wire_obj
    try:
        projected = cast(PersistableModel, to_core())
    except (
        ValidationError,
        VultronValidationError,
        ValueError,
        TypeError,
    ) as exc:
        logger.warning(
            "Row %r (type %r) failed core validation (%s) and projecting"
            " its wire fallback %s to core also failed (%s); returning the"
            " wire object (issue #2232).",
            row.id_,
            row.type_,
            core_exc,
            type(wire_obj).__name__,
            exc,
        )
        return wire_obj
    logger.debug(
        "Row %r (type %r) failed core validation (%s); recovered the core"
        " shape by projecting the wire fallback %s via to_core()"
        " (issue #2232).",
        row.id_,
        row.type_,
        core_exc,
        type(wire_obj).__name__,
    )
    return projected


def rehydrate_fields(
    dl: "SqliteDataLayer", obj: PersistableModel
) -> PersistableModel:
    """Expand dehydrated object-reference fields back to typed objects.

    Fields listed in ``_AS_OBJECT_REF_FIELDS`` (``object_``, ``target``,
    ``origin``, ``result``, ``instrument``) are dehydrated to ID strings
    by the storage layer.  This function resolves each string ID via
    ``dl.read()`` and replaces it with the full domain object.  If a
    referenced object is not found the string is kept and a DEBUG message
    is logged.

    When a field holds an inline ``PersistableModel`` (kept inline by
    ``_KEEP_INLINE_NESTED_TYPES`` rather than dehydrated to a bare ID),
    this function recurses into it so that the nested object's own reference
    fields are expanded too.  Without this recursion an inline Offer's
    ``target`` would remain a bare string URI and break semantic dispatch
    that relies on the resolved type (e.g. Organisation ≠ CaseParticipant
    for ``OfferCaseManagerRolePattern`` vs ``OfferCaseOwnershipTransfer``).

    Expansion respects the field's **declared type**.  ``_AS_OBJECT_REF_FIELDS``
    is a flat list applied to every object, but some models declare one of
    those names as a plain URI rather than a reference — ``as_CaseProposal
    .target`` is required by CP-01-005 to be the case-actor's URI, not an
    inline actor.  Expanding it produced a model whose ``target`` was a dict,
    which ``model_copy`` accepts silently (it does not validate) and which then
    failed the next ``model_validate`` far away, in outbound delivery: the
    proposal could not be re-hydrated, the recipient saw a dehydrated object,
    matched no semantics, and never sent its ``Accept``. Nothing raised at the
    point of damage.
    """
    updates: dict[str, object] = {}
    for field_name in _AS_OBJECT_REF_FIELDS:
        value = getattr(obj, field_name, None)
        if value is None:
            continue
        if isinstance(value, str):
            if not value:
                continue
            if not field_admits_object(obj, field_name):
                logger.debug(
                    "Field %r on %r is declared as a plain URI; leaving its"
                    " reference unexpanded.",
                    field_name,
                    type(obj).__name__,
                )
                continue
            nested = dl.read(value)
            if nested is None:
                logger.debug(
                    "Could not rehydrate field %r with id %r on %r;"
                    " keeping string reference.",
                    field_name,
                    value,
                    type(obj).__name__,
                )
                continue
            updates[field_name] = nested
        elif isinstance(value, BaseModel):
            rehydrated = rehydrate_fields(dl, cast(PersistableModel, value))
            if rehydrated is not value:
                updates[field_name] = rehydrated
    if updates:
        obj = obj.model_copy(update=updates)
    return obj


def hydrate(dl: "SqliteDataLayer", obj: PersistableModel) -> PersistableModel:
    """Deep-hydrate all reference fields in *obj*, including list fields.

    Extends :func:`rehydrate_fields` (which handles scalar object-ref
    fields such as ``object_``, ``target``, ``origin``) to also expand
    fields listed in ``_AS_LIST_REF_FIELDS`` (e.g. ``case_participants``),
    where each list item may be a bare ID string rather than a full domain
    object.

    Called by the outbox handler at delivery time so that bootstrap
    payloads (``Create``/``Announce`` activities whose ``object_`` is a
    ``VulnerabilityCase``) carry embedded participant objects that
    recipients can store in their own DataLayer.

    Args:
        dl: The DataLayer whose store the references are read from.
        obj: A fully-constructed domain object (Pydantic model) whose
             list reference fields may still contain bare ID strings.

    Returns:
        A new model instance with all resolvable ID strings replaced by
        the corresponding domain objects.  Unresolvable IDs are left as
        strings and logged at DEBUG level.
    """
    obj = rehydrate_fields(dl, obj)
    updates: dict[str, object] = {}
    for field_name in _AS_LIST_REF_FIELDS:
        items = getattr(obj, field_name, None)
        if not isinstance(items, list):
            continue
        expanded: list[Any] = []
        changed = False
        for item in items:
            if isinstance(item, str) and item:
                resolved = dl.read(item)
                if resolved is not None:
                    expanded.append(resolved)
                    changed = True
                else:
                    logger.warning(
                        "Could not hydrate list item %r in field %r"
                        " on %r; sending bare ID string to recipient"
                        " (participant may be missing from sender DataLayer).",
                        item,
                        field_name,
                        type(obj).__name__,
                    )
                    expanded.append(item)
            else:
                expanded.append(item)
        if changed:
            updates[field_name] = expanded
    if updates:
        obj = obj.model_copy(update=updates)
    return obj


def coerce_to_semantic_class(obj: PersistableModel) -> PersistableModel:
    """Coerce a base-vocabulary activity to its semantic subtype.

    After rehydration the object has correct field types but may still be
    typed as a base vocabulary class (e.g. ``as_Offer``).  This function
    uses :func:`find_matching_semantics` to identify the semantic intent
    and, when a more specific class is registered in the semantic registry,
    coerces via ``model_validate``.
    Coercion failures are logged as warnings and the original object is
    returned unchanged.
    """
    if not isinstance(obj, as_Activity):
        return obj

    from vultron.core.models.events import MessageSemantics

    semantics = find_matching_semantics(obj)
    if semantics == MessageSemantics.UNKNOWN:
        return obj

    activity_cls = _semantics_to_activity_class().get(semantics)
    if activity_cls is None or isinstance(obj, activity_cls):
        return obj

    try:
        return cast(
            PersistableModel,
            activity_cls.model_validate(
                obj.model_dump(by_alias=True, serialize_as_any=True)
            ),
        )
    except (ValidationError, VultronValidationError, TypeError) as exc:
        logger.warning(
            "Could not coerce %r to semantic class %r: %s",
            type(obj).__name__,
            activity_cls.__name__,
            exc,
        )
        return obj


def object_from_storage(
    stored_record: dict[str, Any],
) -> PersistableModel | None:
    """Reconstruct a domain object from a raw stored-record dict."""
    try:
        record = Record.model_validate(stored_record)
        return cast(PersistableModel, record_to_object(record))
    except (ValidationError, VultronValidationError, ValueError):
        pass

    raw_type = stored_record.get("type")
    if isinstance(raw_type, str):
        try:
            vocab_cls = find_in_vocabulary(raw_type)
            return cast(
                PersistableModel, vocab_cls.model_validate(stored_record)
            )
        except (KeyError, ValidationError, VultronValidationError):
            pass

    raw_type = stored_record.get("type_")
    raw_data = stored_record.get("data_")
    if isinstance(raw_type, str) and isinstance(raw_data, dict):
        try:
            vocab_cls = find_in_vocabulary(raw_type)
            return cast(PersistableModel, vocab_cls.model_validate(raw_data))
        except (KeyError, ValidationError, VultronValidationError):
            pass

    return None
