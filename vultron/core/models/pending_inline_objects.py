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
"""The inline objects of a deferred inbox activity, held for its replay (#3763).

Ingress keeps no record of an inline object before its handler judges it
(CLP-10-017): the objects are staged for routing in a throwaway store and
dropped.  An activity the inbox defers until its case is known
(``VultronPendingCaseInbox``) is replayed later, by id, and by then the
delivery's staging store is gone.  This record holds the staged rows for that
replay, under a key the receiver derives from the activity id.

The rows are opaque to everything but the inbox replay: they are storage rows
(``id_``, ``type_``, ``data_``), not domain objects, so no read by an object's
own id ever reaches them.  They are held as one JSON string because storage
normalises the keys of a nested mapping (``id_`` to ``id``), which would
change the rows it holds.  The replay stages them again and deletes this
record; a handler writes any core record they give rise to, after its guards.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import (
    CoreRecord,
    NonEmptyString,
    UriString,
    with_record_id,
)


class PendingInlineObjects(CoreRecord):
    """Staged inline-object rows for one deferred inbox activity."""

    type_: Literal["PendingInlineObjects"] = Field(  # type: ignore[assignment]
        default="PendingInlineObjects",
        validation_alias="type",
        serialization_alias="type",
    )
    activity_id: UriString = Field(
        ..., description="The sender's id for the deferred activity"
    )
    rows_json: NonEmptyString = Field(
        ...,
        description=(
            "JSON array of the storage rows (id_, type_, data_) staged from"
            " the activity's inline objects"
        ),
    )

    @classmethod
    def build_id(cls, activity_id: str) -> str:
        """Return the stable DataLayer ID for *activity_id*."""
        slug = urllib.parse.quote(activity_id, safe="")
        return f"pending-inline-objects/{slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``activity_id``."""
        if isinstance(data, dict):
            activity_id = data.get("activity_id")
            if activity_id is not None:
                data = with_record_id(data, cls.build_id(activity_id))
        return data
