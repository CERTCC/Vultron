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

"""Base class for Vultron Protocol core domain object models."""

import types as _types
import typing as _typing
from datetime import datetime, timedelta
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_serializer,
    model_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel

from vultron.core.models._helpers import _new_urn, now_utc
from vultron.core.models.registry import CORE_TYPE_MAP, CORE_VOCABULARY
from vultron.primitives import NonEmptyString, UriString  # noqa: F401

#: The Vultron JSON-LD ``@context``.  VM-10-001 (MUST) requires it on every
#: Vultron-specific object on the wire; the ActivityStreams namespace alone "is
#: not sufficient" for types AS2 does not define.
#:
#: It lives in core rather than beside ``ACTIVITY_STREAMS_NS`` in the wire layer
#: because under ADR-0099 the core classes *are* the objects that carry it, and
#: core MUST NOT import wire (ARCH-01-001 — the one boundary rule ADR-0099 leaves
#: fully in force).  Wire imports it from here, which detail 6 permits.
VULTRON_CONTEXT_URI = "https://certcc.github.io/Vultron/ns/context.jsonld"


class ValidatedAssignmentMixin(BaseModel):
    """Mixin that enables Pydantic post-construction field validation on core models.

    Apply to core-branch roots only (ARCH-21-001). ``VultronBase`` is permanently
    excluded because it is the shared base of both branches and ``as_Base``
    inherits it (ARCH-12-001, ARCH-12-002). Composes correctly with
    ``VultronBase.model_config`` (``populate_by_name=True``) across the MRO:
    Pydantic v2 merges ``model_config`` from all BaseModel ancestors, so the
    result carries both ``validate_assignment=True`` and ``populate_by_name=True``.
    """

    model_config = ConfigDict(validate_assignment=True)


class VultronBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id_: NonEmptyString = Field(
        default_factory=_new_urn,
        validation_alias="id",
        serialization_alias="id",
    )
    type_: NonEmptyString | None = Field(
        default=None,
        validation_alias="type",
        serialization_alias="type",
    )
    name: NonEmptyString | None = None
    preview: NonEmptyString | None = None
    media_type: NonEmptyString | None = None


class VultronObject(ValidatedAssignmentMixin, VultronBase):
    """Base class for core domain object models.

    Captures the common ``id_``, ``type_``, and ``name`` fields shared by
    all domain object types, mirroring the ``as_Base``/``as_Object`` class
    hierarchy in the wire layer.  Concrete domain object classes inherit from
    this base rather than directly from ``BaseModel``.
    """

    # Sentinel: True on the core branch (default), overridden to False on
    # as_Object so wire-branch types never self-register in CORE_TYPE_MAP
    # (issue #2416).  CoreObject subclasses inherit True and are guarded by
    # CoreObject.__init_subclass__ instead.
    _is_core_branch: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore[arg-type]
        # Wire-branch types inherit _is_core_branch=False from as_Object and
        # must not self-register in CORE_TYPE_MAP (issue #2416).
        if not cls._is_core_branch:
            return
        # Register every concrete VultronObject subclass in CORE_TYPE_MAP so
        # that find_in_vocabulary() can locate them without placing them in the
        # wire VOCABULARY dict (ARCH-12-003). Only subclasses that declare
        # their own concrete type_ annotation are registered; abstract bases
        # that inherit or omit type_ are skipped (same guard as CoreObject).
        own_annotations = cls.__dict__.get("__annotations__", {})
        if "type_" not in own_annotations:
            return
        try:
            hints = _typing.get_type_hints(cls)
        except (NameError, TypeError):
            # Forward references cannot be resolved yet (NameError) or an
            # annotation is not a valid type (TypeError) — do not register.
            # A half-constructed entry is worse than a missing one, which
            # surfaces immediately at lookup time (CS-23-001).
            return
        annotation = hints.get("type_")
        if isinstance(annotation, _types.UnionType):
            return
        if _typing.get_origin(annotation) is _typing.Union:
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

    replies: Any | None = None
    url: NonEmptyString | None = None
    generator: Any | None = None
    context: Any | None = None
    tag: Any | None = None
    in_reply_to: Any | None = Field(
        default=None,
        validation_alias="inReplyTo",
        serialization_alias="inReplyTo",
    )

    duration: timedelta | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    published: datetime | None = Field(default_factory=now_utc)
    updated: datetime | None = Field(default_factory=now_utc)

    # content
    content: Any | None = None
    summary: NonEmptyString | None = None
    icon: Any | None = None
    image: Any | None = None
    attachment: Any | None = None
    location: Any | None = None
    to: Any | None = None
    cc: Any | None = None
    bto: Any | None = None
    bcc: Any | None = None
    audience: Any | None = None
    attributed_to: NonEmptyString | None = None


class CoreObject(VultronObject):
    """Base class for the migrated Vultron core domain object hierarchy.

    Mirrors ``as_Base`` / ``as_Object`` in the wire layer and carries the
    minimal AS2-derived fields a domain object needs to participate in
    federated coordination: ``id_``, ``type_``, ``name`` (inherited from
    :class:`VultronBase`), ``attributed_to``, ``published``, ``updated``
    (inherited from :class:`VultronObject`), and ``context_`` (added here
    as the JSON-LD ``@context`` field).

    Subclasses that override ``type_`` with a concrete (non-union)
    annotation — e.g. ``type_: Literal["VulnerabilityCase"] = ...`` —
    register themselves in :data:`CORE_VOCABULARY` via
    ``__init_subclass__``.  Subclasses that leave ``type_`` abstract
    (omitted, or annotated as a union) are intentionally not registered.

    ``context_`` defaults to ``None`` and is ``exclude=True``, so it never
    reaches a stored row: ADR-0099 detail 1 keeps persistence on Python field
    names with no ``@context``.  It is emitted only on the AS2 path — see
    :meth:`_serialize_with_jsonld_context`.

    See ``docs/adr/0017-domain-wire-object-separation.md`` for the
    rationale, and ``notes/domain-model-separation.md`` for the broader
    architectural direction (tracked by issue #699).
    """

    # The AS2 spelling of every field, derived rather than hand-maintained.
    #
    # ADR-0099 detail 2 puts the AS2 spelling on the core class, because under one
    # object model there is no second class left to hold it.  `to_camel` derives
    # it correctly for all but three fields — `id_`, `type_` and `context_`, whose
    # trailing underscores exist to dodge Python keyword/shadowing collisions and
    # which therefore carry explicit aliases (`id`, `type`, `@context`).  `@context`
    # could not come from a generator at all.
    #
    # Deriving beats enumerating here: a hand-written alias per field silently
    # omits the ones nobody remembered, which is precisely how `attributedTo`
    # became `attributed_to` on the wire for four object types.  What keeps the
    # derivation honest is a closed-world test on the projected key set
    # (test_core_object_projection_keys), not the declaration site.
    #
    # ARCH-20-001 forbids this, on a rationale that predates ADR-0099: it reads
    # "keeps every fact about wire spelling ... behind the adapter-side translator
    # that owns projection (ARCH-12-005)", and ADR-0099 removed that translator.
    # The part of the rule that still binds — one rendering seam — is unaffected:
    # the port remains the only caller that passes `by_alias=True`.
    model_config = ConfigDict(alias_generator=to_camel)

    context_: NonEmptyString | None = Field(
        default=None,
        validation_alias="@context",
        serialization_alias="@context",
        exclude=True,
    )

    @field_serializer(
        "start_time", "end_time", "published", "updated", when_used="json"
    )
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        """Write timestamps with an explicit offset, as the wire classes did.

        Pydantic's default JSON form for an aware UTC datetime is ``...Z``;
        ``isoformat()`` gives ``...+00:00``.  Both denote the same instant and
        both are valid ISO-8601, which is why swapping them is invisible in
        review — but they are different *bytes*, and
        ``CaseLedgerEntry.payloadSnapshot`` is compared across replicas, so two
        actors on different spellings disagree about the canonical snapshot of an
        identical event.

        Every one of the 226 timestamps in ``docs/reference/examples`` uses the
        offset form, so that is the published contract.  Promoting a core class
        onto the wire must not quietly renegotiate it.
        """
        if value is None:
            return None
        return value.isoformat()

    @model_serializer(mode="wrap")
    def _serialize_with_jsonld_context(
        self,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> Any:
        """Add the JSON-LD ``@context`` on the AS2 path, and only there.

        ADR-0099 detail 1 gives one class two serializations, chosen by where the
        object is going:

        ==========================  ==========================================
        inter-actor delivery        ``model_dump_json(by_alias=True)`` — AS2:
                                    camelCase **plus** ``@context``
        persistence                 ``model_dump(mode="json")`` — Python field
                                    names, no ``@context``
        ==========================  ==========================================

        ``by_alias`` is exactly that fork, so it is what selects the behaviour
        here rather than a flag a caller has to remember to pass.

        VM-10-001 (MUST) requires the Vultron context on Vultron-specific objects;
        the ActivityStreams namespace alone "is not sufficient".  Before ADR-0099
        the paired ``as_*`` class supplied it from ``as_Base``; deleting those
        classes removed it from every promoted type, including nested ones such as
        ``caseParticipants[]``, which is not a change any peer asked for.

        An explicitly-supplied ``context_`` wins, so a document parsed from the
        wire round-trips with the context it arrived with instead of being
        silently relabelled.
        """
        data = handler(self)
        if not isinstance(data, dict) or not info.by_alias:
            return data
        data["@context"] = self.context_ or VULTRON_CONTEXT_URI
        return data

    # Re-narrow published/updated: the core branch guarantees these are always
    # populated (default_factory ensures it).  VultronObject uses datetime|None
    # (per ARCH-12-002: shared base must be lenient for the wire branch).
    published: datetime = Field(default_factory=now_utc)
    updated: datetime = Field(default_factory=now_utc)

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore[arg-type]
        # Register only subclasses that override ``type_`` with a concrete
        # (non-union) annotation — e.g. ``type_: Literal["FooBar"] = "FooBar"``.
        # We inspect the subclass's *own* ``__annotations__`` so an inheriting
        # class that does not redeclare ``type_`` (e.g. a behavioral mixin)
        # is not registered. We then resolve the annotation through
        # ``typing.get_type_hints`` so the check is robust under
        # ``from __future__ import annotations`` (PEP 563), where raw
        # annotations are stringified and ``isinstance(..., UnionType)``
        # would silently fall through and register abstract bases.
        own_annotations = cls.__dict__.get("__annotations__", {})
        if "type_" not in own_annotations:
            # No explicit type_ annotation: _set_type_from_class_name will set
            # type_ = cls.__name__ at construction time, so register by class
            # name so that find_in_vocabulary can reconstruct from DB storage.
            # This fires for abstract intermediate subclasses too — any
            # CoreObject subclass that never overrides type_ registers here,
            # making find_in_vocabulary('ClassName') succeed even for abstract
            # bases.  Intentional: _set_type_from_class_name runs on all such
            # subclasses, so every registered name is a valid stored type_.
            CORE_TYPE_MAP[cls.__name__] = cls
            return  # Skip CORE_VOCABULARY — not a concrete vocab entry
        try:
            hints = _typing.get_type_hints(cls)
        except (NameError, TypeError):
            # Forward references cannot be resolved yet (NameError) or an
            # annotation is not a valid type (TypeError) — do not register.
            # Silent registration of a half-constructed class is worse than a
            # missing entry, which surfaces immediately at lookup time.  Kept
            # symmetric with VultronObject.__init_subclass__, which runs the
            # same get_type_hints(cls) call for every CoreObject subclass; a
            # divergent catch here would let one handler swallow what the other
            # crashes on (CS-23-001).
            return
        annotation = hints.get("type_")
        # Skip union annotations (e.g. ``str | None``) — these mark
        # intermediate abstract bases, not concrete vocabulary entries.
        if isinstance(annotation, _types.UnionType):
            return
        if _typing.get_origin(annotation) is _typing.Union:
            return
        CORE_VOCABULARY[cls.__name__] = cls

    @model_validator(mode="before")
    @classmethod
    def _set_type_from_class_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("type") and not data.get("type_"):
                field_info = cls.model_fields.get("type_")
                if field_info is not None and field_info.default is None:
                    data = dict(data)
                    data["type"] = cls.__name__
        return data
