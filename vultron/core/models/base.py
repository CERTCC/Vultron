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
from datetime import datetime, timedelta
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from vultron.core.models._helpers import _new_urn


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
    published: datetime | None = None
    updated: datetime | None = None

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
