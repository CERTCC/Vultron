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

"""The core record root, :class:`CoreRecord`, and the validated-assignment mixin.

ARCH-25-004 (ADR-0099) gives core two roots; this is the one for stored
records that are not AS2 objects.
"""

import inspect
import types as _types
import typing as _typing
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vultron.core.models._helpers import new_object_id
from vultron.core.models.registry import CORE_TYPE_MAP
from vultron.primitives import NonEmptyString


def concrete_type_annotation(cls: type) -> Any | None:
    """Return the resolved ``type_`` annotation of *cls*, or ``None``.

    For a class that declares its own ``type_``.  The annotation is resolved
    through ``typing.get_type_hints`` so the check holds under ``from
    __future__ import annotations`` (PEP 563), where raw annotations are
    strings.  ``None`` means *cls* is not registered: its forward references
    cannot be resolved yet (``NameError``) or an annotation is not a valid
    type (``TypeError``) — a half-constructed entry is worse than a missing
    one, which surfaces immediately at lookup time (CS-23-001) — or ``type_``
    is a union, which marks an intermediate abstract base.  Shared by
    :class:`CoreRecord` and ``CoreObject``, so the two registration hooks
    cannot catch different errors.
    """
    try:
        hints = _typing.get_type_hints(cls)
    except (NameError, TypeError):
        return None
    annotation = hints.get("type_")
    if isinstance(annotation, _types.UnionType):
        return None
    if _typing.get_origin(annotation) is _typing.Union:
        return None
    return annotation


class ValidatedAssignmentMixin(BaseModel):
    """Mixin that enables Pydantic post-construction field validation on core models.

    Applied by :class:`CoreRecord`, so every core root and everything below it
    validates assignment to the same standard as construction (ARCH-21-001).
    Also composed directly onto the core ``BaseModel`` subclasses that are not
    records — dimensions, the hash-chain ledger record, dispatch events.
    Pydantic v2 merges ``model_config`` across the MRO, so the flag composes
    with each class's own configuration.
    """

    model_config = ConfigDict(validate_assignment=True)


class CoreRecord(ValidatedAssignmentMixin):
    """Minimal core root: a stored record that is not an AS2 object.

    ARCH-25-004 (ADR-0099) gives core two roots.  This one carries only the
    identity every stored record needs — ``id_``, ``type_``, ``name`` — for
    records that never go on the wire in their own right: dead letters,
    offer bookkeeping, replication state.  It has no ``@context``, no alias
    generator and no AS2 object fields, so it has no AS2 spelling, which is
    why the rendering port refuses it (ARCH-20-003).

    The AS2-shaped root is :class:`CoreObject`, which extends this one.

    Every concrete subclass that declares a ``Literal`` ``type_`` registers in
    :data:`CORE_TYPE_MAP` so a stored row can be reconstructed by its type
    string (ARCH-12-010).  Wire classes do not inherit this root, so nothing
    here has to guard against them (#2416).
    """

    # A stored record refuses any key it does not declare: a row written before
    # a field rename fails loudly at read time instead of silently losing the
    # renamed field (#4186, ARCH-12-003).  ``id`` and ``type`` are the stored
    # spelling (``_rekey_wire_identity``); ``id_`` and ``type_`` the Python one.
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id_: NonEmptyString = Field(
        default_factory=new_object_id,
        validation_alias="id",
        serialization_alias="id",
    )
    type_: NonEmptyString | None = Field(
        default=None,
        validation_alias="type",
        serialization_alias="type",
    )
    name: NonEmptyString | None = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore[arg-type]
        # Register every concrete core subclass in CORE_TYPE_MAP so that
        # find_in_vocabulary(..., include_core=True) can locate it without
        # placing it in the wire VOCABULARY dict. Only subclasses that declare
        # their own concrete type_ annotation are registered; abstract bases that inherit or omit
        # type_ are skipped (same guard as CoreObject).
        if "type_" not in inspect.get_annotations(cls):
            return
        annotation = concrete_type_annotation(cls)
        if annotation is None:
            return
        # Register by class name (covers classes where _set_type_from_class_name
        # sets type_ = cls.__name__, e.g. CoreActor stored as "CoreActor").
        CORE_TYPE_MAP[cls.__name__] = cls
        # Also register by the Literal value itself when it differs from the
        # class name (e.g. VultronOfferRecord → "OfferRecord"). Extract from
        # the annotation directly; model_fields is not yet populated at
        # __init_subclass__ time.
        literal_args = _typing.get_args(annotation)
        if (
            literal_args
            and len(literal_args) == 1
            and isinstance(literal_args[0], str)
        ):
            CORE_TYPE_MAP[literal_args[0]] = cls


def with_record_id(data: dict[str, Any], record_id: str) -> dict[str, Any]:
    """Return a copy of *data* whose record id is *record_id*.

    For a record that derives its id from its other fields.  The id is stated
    under the one spelling *data* already uses: ``id_`` for a dump or an
    assignment check (which validates by field name), ``id`` otherwise.  Stating
    the other spelling beside it would leave one of the two an unrecognised key,
    which ``extra="forbid"`` refuses.
    """
    out = dict(data)
    if "id_" in out and "id" not in out:
        out["id_"] = record_id
    else:
        out.pop("id_", None)
        out["id"] = record_id
    return out
