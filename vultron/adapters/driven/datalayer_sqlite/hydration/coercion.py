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

"""Domain-object hydration and semantic coercion after a row is read.

Expands stored references into the objects they name
(:func:`rehydrate_fields`, :func:`hydrate`), collapses by-reference fields and
coerces a generic activity onto its semantic class
(:func:`coerce_to_semantic_class`), and rebuilds an object from storage
(:func:`object_from_storage`).
"""

import logging
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ValidationError

from vultron.adapters.driven.datalayer_sqlite.hydration.fields import (
    _declared_model_class,
    class_field_admits_object,
    field_admits_object,
)
from vultron.adapters.driven.db_record import (
    STORED_ROW_CONTEXT,
    Record,
    object_ref_fields,
    record_to_object,
)
from vultron.adapters.driven.db_record.ref_fields import _AS_LIST_REF_FIELDS
from vultron.core.models.events import MessageSemantics
from vultron.core.models.protocols import PersistableModel
from vultron.errors import VultronValidationError
from vultron.semantic_registry import (
    find_matching_semantics,
    semantics_to_activity_class as _semantics_to_activity_class,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.registry import (
    find_in_vocabulary,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for typing only
    # ``datalayer`` imports this module to build its own methods, so the name
    # can only be a forward reference here.
    from ..datalayer import SqliteDataLayer


logger = logging.getLogger(__name__)


def rehydrate_fields(
    dl: "SqliteDataLayer", obj: PersistableModel
) -> PersistableModel:
    """Expand dehydrated object-reference fields back to typed objects.

    The object's :func:`object_ref_fields` (``object_``, ``target``,
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

    Expansion respects the field's **declared type**.  :func:`object_ref_fields`
    keys on field *names*, but some models declare one of
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
    for field_name in object_ref_fields(type(obj)):
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


def _collapse_by_reference_fields(
    obj: BaseModel, model_cls: type
) -> BaseModel:
    """Return *obj* with each field *model_cls* takes by reference as an id.

    :func:`rehydrate_fields` expands a reference by the *stored* class's
    declared type, and the pattern match needs that expansion to confirm the
    referent's type.  The semantic class may still declare the field a plain
    URI — ``_ReadLogEntryActivity.object_`` (SYNC-17-001),
    ``_RmInviteToFullCaseActivity.target`` (AKM-02-003) — so the expanded
    object goes back to its id before validation (#5513).

    A field *model_cls* declares as one model class is walked into with that
    class, so an embedded activity is collapsed too: the full-case Invite
    inside ``_RmAcceptFullCaseInviteActivity.object_`` hands over its
    ``target`` as the case id.  A referent with no string id is left as it
    is, and validation reports it as before.
    """
    updates: dict[str, object] = {}
    for field_name in object_ref_fields(type(obj)):
        value = getattr(obj, field_name, None)
        if not isinstance(value, BaseModel):
            continue
        if not class_field_admits_object(model_cls, field_name):
            ref_id = getattr(value, "id_", None)
            if isinstance(ref_id, str) and ref_id:
                updates[field_name] = ref_id
            continue
        nested_cls = _declared_model_class(model_cls, field_name)
        if nested_cls is None or isinstance(value, nested_cls):
            continue
        collapsed = _collapse_by_reference_fields(value, nested_cls)
        if collapsed is not value:
            updates[field_name] = collapsed
    return obj.model_copy(update=updates) if updates else obj


def coerce_to_semantic_class(obj: PersistableModel) -> PersistableModel:
    """Coerce a base-vocabulary activity to its semantic subtype.

    After rehydration the object has correct field types but may still be
    typed as a base vocabulary class (e.g. ``as_Offer``).  This function
    uses :func:`find_matching_semantics` to identify the semantic intent
    and, when a more specific class is registered in the semantic registry,
    coerces via ``model_validate``.  A field the semantic class takes by
    reference is handed over as its id, however rehydration expanded it
    (:func:`_collapse_by_reference_fields`).  An activity whose ``object_``
    stayed a bare id matches no pattern (SE-01-006), so it keeps its base
    class.
    Coercion failures are logged as warnings and the original object is
    returned unchanged.
    """
    if not isinstance(obj, as_Activity):
        return obj

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
                _collapse_by_reference_fields(obj, activity_cls).model_dump(
                    by_alias=True, serialize_as_any=True
                )
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
    """Reconstruct a domain object from a raw stored-record dict.

    Returns ``None`` when no reconstruction path accepts the row.  That is a
    row which *exists* but cannot be read back as a clean object — e.g. a
    object whose stored computed-field value contradicts the state it is
    derived from (ARCH-23-005) — so the failure is logged at WARNING with the
    record id and every path's reason rather than being indistinguishable from
    "not found".
    """
    failures: list[str] = []
    try:
        record = Record.model_validate(stored_record)
        return cast(PersistableModel, record_to_object(record))
    except (ValidationError, VultronValidationError, ValueError) as exc:
        failures.append(f"record: {exc}")

    # Both-branch lookups below: a stored record may hold any persisted type,
    # core records included, so they opt into the core fallback (VM-06-014).
    raw_type = stored_record.get("type")
    if isinstance(raw_type, str):
        try:
            vocab_cls = find_in_vocabulary(raw_type, include_core=True)
            return cast(
                PersistableModel,
                vocab_cls.model_validate(
                    stored_record, context=STORED_ROW_CONTEXT
                ),
            )
        except (KeyError, ValidationError, VultronValidationError) as exc:
            failures.append(f"type={raw_type!r}: {exc}")

    raw_type = stored_record.get("type_")
    raw_data = stored_record.get("data_")
    if isinstance(raw_type, str) and isinstance(raw_data, dict):
        try:
            vocab_cls = find_in_vocabulary(raw_type, include_core=True)
            return cast(
                PersistableModel,
                vocab_cls.model_validate(raw_data, context=STORED_ROW_CONTEXT),
            )
        except (KeyError, ValidationError, VultronValidationError) as exc:
            failures.append(f"type_={raw_type!r}: {exc}")

    logger.warning(
        "Stored record %r could not be reconstructed as a domain object;"
        " returning None. Reasons: %s",
        stored_record.get("id_") or stored_record.get("id"),
        " | ".join(failures) or "no reconstruction path applies",
    )
    return None
