#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""ID-to-object materialisation of a model's object-only slots.

**This module owns ID-to-object materialisation** (VM-06-007, ARCH-25-009;
ADR-0099).  See :func:`materialise_object_slots` for the rule and for why the
fabricated-stub behaviour it replaces is not reproduced.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar, get_args, get_origin

from pydantic import BaseModel

from vultron.core.models._helpers import strip_annotated
from vultron.core.models.base import CoreObject
from vultron.core.models.wire_keys import input_keys
from vultron.errors import VultronReferenceResolutionError
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.collections import as_Collection

if TYPE_CHECKING:
    from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


_M = TypeVar("_M", bound=BaseModel)


def _annotation_branches(annotation: Any) -> list[Any]:
    """Flatten an annotation into the leaf types a value may take.

    ``list[as_Activity]`` yields ``[as_Activity]``; ``as_Foo | as_Link | str``
    yields all three; ``list[as_Foo | str]`` yields both.  Used only to decide
    whether a slot can hold a bare URI, so containers are transparent — and so
    is the ``Annotated`` wrapper of ``NonEmptyString``, the IRI branch of every
    reference union (CS-08-001): it is stripped to ``str`` rather than
    recursed into, or its validator metadata would be reported as a branch.
    """
    annotation = strip_annotated(annotation)
    args = get_args(annotation)
    if not args:
        return [annotation]
    branches: list[Any] = []
    for arg in args:
        if arg is type(None):
            continue
        branches.extend(_annotation_branches(arg))
    return branches


def _slot_requires_object(annotation: Any) -> bool:
    """True when *annotation* can hold a model but cannot hold a bare URI.

    This is the test ARCH-25-009 (ADR-0099) turns on.  A slot declared
    ``ActivityStreamRef[as_Foo]`` expands to ``as_Foo | as_Link | NonEmptyString``
    (a ``str`` branch once its ``Annotated`` wrapper is stripped), so a
    URI is a legal value there and an unresolvable reference is *deferred* —
    left as the string, warned about, and carried on (VM-06-004).  A slot
    declared ``as_Foo`` or ``list[as_Foo]`` admits no ``str`` branch at all, so
    a bare URI is not a value it can legally hold: the reference must either be
    materialised or *refused*.

    ``as_Collection`` slots are excluded.  An AS2 actor's ``inbox`` and
    ``outbox`` are declared as collections but are *endpoints* — ActivityPub
    publishes them as URIs, they usually belong to a remote actor, and they
    are not rows in anybody's data layer.  ``as_Actor`` already declares how a
    URI becomes the object there: a ``mode="before"`` validator constructs the
    collection around it.  Materialising would pre-empt a coercion the class has already
    specified, and would send a ``dl.read()`` after a remote URL that can only
    come back empty.

    Slots that are **not** on the wire branch are excluded too, and that
    exclusion is load-bearing rather than defensive.  A core dimension field is
    annotated ``EmDimension`` — a ``BaseModel`` that is not an ``as_Object`` and
    admits no ``str`` branch — so the rule above would classify it as an
    ID-reference slot.  Since ARCH-25-005 (ADR-0099) a dimension *serializes to a bare
    state value*, so ``materialise_object_slots(CaseStatus, core_cs.model_dump(),
    dl)`` would read ``"NONE"`` as a reference and try to resolve it.  Only
    ``as_Object`` slots can hold a materialised AS2 object, so only they are in
    scope.
    """
    branches = _annotation_branches(annotation)
    if not branches:
        return False
    model_branches = [
        branch
        for branch in branches
        if isinstance(branch, type) and issubclass(branch, BaseModel)
    ]
    if not model_branches:
        return False
    # A promoted core class is a materialisable AS2 object too.  Requiring
    # ``as_Object`` alone excluded every class ARCH-25-003 (ADR-0099) collapsed —
    # ``participant_statuses: list[ParticipantStatus]`` stopped being an eligible
    # slot, so an unresolvable reference in it was left bare instead of refused,
    # silently dropping VM-06-009's refusal guarantee.
    #
    # ``CoreObject`` is the right addition rather than ``BaseModel``: the point of
    # this gate is to keep a *dimension* out, since ARCH-25-005 makes it serialize
    # to a bare state value that would otherwise be read as a reference. Dimensions
    # derive from ``_ScalarDimension``, not ``CoreObject``, so they stay excluded.
    if not all(
        issubclass(branch, (as_Object, CoreObject))
        for branch in model_branches
    ):
        return False
    if all(issubclass(branch, as_Collection) for branch in model_branches):
        return False
    return not any(branch is str for branch in branches)


def _is_list_slot(annotation: Any) -> bool:
    """True when *annotation* is a (possibly optional) list container."""
    if get_origin(annotation) is list:
        return True
    return any(
        get_origin(arg) is list
        for arg in get_args(annotation)
        if arg is not type(None)
    )


def _materialise_one(
    obj_id: str, dl: DataLayer, field_name: str, cls_name: str
) -> Any:
    """Resolve a single bare URI held in an object-only slot, or refuse.

    Both failure modes refuse rather than degrade, which is the whole point of
    this module owning the behaviour — see :func:`materialise_object_slots`.

    The second guard is not hypothetical.  ``dl.read()`` returns **core** objects
    for every ``CORE_VOCABULARY`` type (DL-05-004, ADR-0034); AS2 activities are
    the exemption that still comes back wire-shaped.  So a slot typed
    ``as_CaseStatus`` or ``list[as_ParticipantStatus]`` gets a core object back
    today, which cannot go into a wire slot.  Refusing here names the cause;
    substituting it would surface as an opaque Pydantic ``ValidationError`` three
    frames away.  Those two slots become materialisable when ARCH-25-003 (ADR-0099)
    deletes the paired classes and the slots name the core types directly.

    Raises:
        VultronReferenceResolutionError: If *obj_id* resolves to nothing, or to
            something that is not an AS2 object.
    """
    resolved = dl.read(obj_id)
    if resolved is None:
        raise VultronReferenceResolutionError(
            f"{cls_name}.{field_name}: reference '{obj_id}' could not be "
            "resolved in the data layer, and the slot is declared to hold an "
            "object rather than a URI. Refusing rather than fabricating a "
            "placeholder (VM-06-010)."
        )
    # A promoted core class is placeable: ARCH-25-003 has now retargeted these
    # slots at the core class, which is what the previous version of this message said
    # it was waiting for.  ``dl.read()`` returns core objects for paired types
    # (DL-05-004), so requiring ``as_Object`` alone refused every read of a
    # collapsed type — the refusal fired on the normal path instead of the
    # malformed one.
    if not isinstance(resolved, (as_Object, CoreObject)):
        raise VultronReferenceResolutionError(
            f"{cls_name}.{field_name}: reference '{obj_id}' resolved to "
            f"{type(resolved).__name__}, which is neither an AS2 object nor a "
            "core domain object, so it cannot be placed in this slot. Refusing "
            "rather than substituting a shape the slot cannot hold (VM-06-012)."
        )
    logger.debug(
        "Materialised %s.%s reference '%s' as %s.",
        cls_name,
        field_name,
        obj_id,
        type(resolved).__name__,
    )
    return resolved


def materialise_object_slots(
    model_cls: type[BaseModel], data: dict[str, Any], dl: DataLayer
) -> dict[str, Any]:
    """Fill *model_cls*'s object-only slots in *data* with resolved objects.

    ARCH-25-009 (ADR-0099) says an object slot holds the whole object, not an
    ID, that reading resolves an IRI reference to the referenced object, with
    an unresolvable reference deferred or refused, and that this module owns
    that resolution.  **This function is where it happens** (VM-06-007).

    The rule is read off the declared field types, which ADR-0099 makes the
    single source of truth:

    * A slot that admits ``str`` (every ``ActivityStreamRef[T]`` union) is left
      alone.  A URI is a legal value there, so an unresolvable reference is
      *deferred* — that is VM-06-004's behaviour and it already exists.
    * A slot that admits a model but **not** ``str`` — ``as_Activity``,
      ``list[as_Activity]`` — cannot legally hold a URI.  A bare string found
      there is resolved through *dl*, and an unresolvable one is **refused**
      with a :exc:`~vultron.errors.VultronReferenceResolutionError`.

    Operating on the pre-validation ``dict`` rather than a constructed model is
    forced, not stylistic: Pydantic rejects a bare string in a
    ``list[as_Activity]`` slot outright, so by the time an instance exists the
    reference can no longer be there to materialise.

    **The synthesized actor is deliberately not reproduced (AC-2 of #3486).**
    The behaviour being replaced is ``as_VulnerabilityCase.from_core``::

        data["case_activity"] = [
            as_Activity(id_=activity_id,
                        actor=core_obj.attributed_to or core_obj.id_)
            if isinstance(activity_id, str) else activity_id
            for activity_id in data.get("case_activity", [])
        ]

    That is a workaround for a reference that was not resolved, not a
    behaviour worth keeping.  ``as_Activity.actor`` is required and has no
    default, so a stub built from a bare ID must supply *something*, and
    ``from_core`` has no data layer to ask — so it invented the case's owner,
    or, failing that, the case's own URI.  Neither is the activity's actor.
    ``VulnerabilityCase.record_activity`` records activity by *any*
    participant, so in a multiparty case the stub misattributes every activity
    the case owner did not perform; the ``or core_obj.id_`` fallback
    attributes an activity to a case, which is not an actor at all.  A stub
    whose required field is invented is worse than an explicit failure,
    because it launders a missing object into a plausible-looking wrong one —
    and a wrong ``actor`` is what semantic dispatch and the AKM-03-003 outbox
    gate both key on.  The resolved object carries its true actor; where it
    cannot be resolved, this function refuses.

    Args:
        model_cls: The class *data* is about to be validated against.
        data: Field data, keyed by python field name **or** by the field's AS2
            alias — both are looked for, via :func:`input_keys`, because callers
            legitimately hand over either spelling and a slot silently skipped
            for being spelled ``caseActivity`` fails later and further away.
            Not mutated.
        dl: DataLayer used to resolve references.

    Returns:
        *data* unchanged when nothing needed materialising, otherwise a shallow
        copy with the resolved objects substituted under the key they arrived on.

    Raises:
        VultronReferenceResolutionError: If a reference in an object-only slot
            cannot be resolved, or resolves to a non-AS2 object.
    """
    model_fields = getattr(model_cls, "model_fields", None)
    if not model_fields:
        return data
    updates: dict[str, Any] = {}
    for field_name, field in model_fields.items():
        annotation = field.annotation
        if annotation is None or not _slot_requires_object(annotation):
            continue
        key = next(
            (k for k in input_keys(model_cls, field_name) if k in data), None
        )
        if key is None:
            continue
        value = data[key]
        if _is_list_slot(annotation):
            if not isinstance(value, list):
                continue
            if not any(isinstance(item, str) and item for item in value):
                continue
            updates[key] = [
                (
                    _materialise_one(item, dl, field_name, model_cls.__name__)
                    if isinstance(item, str) and item
                    else item
                )
                for item in value
            ]
        elif isinstance(value, str) and value:
            updates[key] = _materialise_one(
                value, dl, field_name, model_cls.__name__
            )
    if not updates:
        return data
    return {**data, **updates}


def materialise(
    model_cls: type[_M], data: dict[str, Any], dl: DataLayer
) -> _M:
    """Validate *data* into *model_cls*, materialising object slots first.

    The single-call form of :func:`materialise_object_slots` for callers that
    build an object from loose field data rather than from another object.
    That is the shape the per-class ``from_core`` overrides have, so this is
    what replaces them when they are deleted (#3487, #3488)::

        materialise(as_VulnerabilityCase, core_case.model_dump(mode="json"), dl)

    Raises:
        VultronReferenceResolutionError: If a reference in an object-only slot
            cannot be resolved, or resolves to a non-AS2 object.
        ValidationError: If Pydantic validation of the result fails.
    """
    return model_cls.model_validate(
        materialise_object_slots(model_cls, data, dl)
    )
