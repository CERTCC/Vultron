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

import re
import types as _types
import typing as _typing
from datetime import datetime, timedelta
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from vultron.core.models._helpers import _new_urn, _now_utc
from vultron.core.models.registry import CORE_VOCABULARY


def _non_empty(v: str) -> str:
    if not v.strip():
        raise ValueError("must be a non-empty string")
    return v


NonEmptyString = Annotated[str, AfterValidator(_non_empty)]

_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:[^\s]")


def _valid_uri(v: str) -> str:
    if not _URI_SCHEME_RE.match(v):
        raise ValueError("must be a URI (e.g. urn:uuid:... or https://...)")
    return v


UriString = Annotated[NonEmptyString, AfterValidator(_valid_uri)]


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


class VultronObject(VultronBase):
    """Base class for core domain object models.

    Captures the common ``id_``, ``type_``, and ``name`` fields shared by
    all domain object types, mirroring the ``as_Base``/``as_Object`` class
    hierarchy in the wire layer.  Concrete domain object classes inherit from
    this base rather than directly from ``BaseModel``.
    """

    replies: Any | None = None
    url: NonEmptyString | None = None
    generator: Any | None = None
    context: NonEmptyString | None = None
    tag: Any | None = None
    in_reply_to: NonEmptyString | None = None

    duration: timedelta | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    published: datetime = Field(default_factory=_now_utc)
    updated: datetime = Field(default_factory=_now_utc)

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

    ``context_`` defaults to ``None``: the JSON-LD ``@context`` value is a
    wire-layer concern, and the wire projection layer is responsible for
    supplying the AS2 namespace at serialization time.

    See ``docs/adr/0017-domain-wire-object-separation.md`` for the
    rationale, and ``notes/domain-model-separation.md`` for the broader
    architectural direction (tracked by issue #699).
    """

    context_: NonEmptyString | None = Field(
        default=None,
        validation_alias="@context",
        serialization_alias="@context",
        exclude=True,
    )

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
            return  # No type_ override → abstract base, skip
        try:
            hints = _typing.get_type_hints(cls)
        except Exception:
            # If forward references cannot be resolved, do not register —
            # silent registration of a half-constructed class is worse than
            # a missing entry, which surfaces immediately at lookup time.
            return
        annotation = hints.get("type_")
        # Skip union annotations (e.g. ``str | None``) — these mark
        # intermediate abstract bases, not concrete vocabulary entries.
        if isinstance(annotation, _types.UnionType):
            return
        if _typing.get_origin(annotation) is _typing.Union:
            return
        CORE_VOCABULARY[cls.__name__] = cls

    @model_validator(mode="after")
    def _set_type_from_class_name(self) -> "CoreObject":
        if self.type_ is None:
            self.type_ = self.__class__.__name__
        return self
