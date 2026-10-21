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
"""A deferred inbox activity, held whole for its replay (DL-06-006, IO-03-004).

An activity the inbox defers until its case is known
(``VultronPendingCaseInbox``) is replayed later, by id, after the delivery that
carried it has ended.  The receiver keeps no copy of it under the id its
sender chose (DL-06-006): its type tables hold only what it authored, so a
received copy there would be read as one of its own.  This record holds the
activity instead, under a key the receiver derives from the activity id, and
is the only place the inbox holds it until the replay deletes it, or the
queue's expiry does.

It holds two things, and nothing derived from them (ADR-0149):

- the activity itself.  A delivery is held as the received body the parser
  sealed (VM-08-002, ADR-0149), so its replay parses those bytes and carries
  the same evidence as the first delivery.  An activity handed to the inbox
  in process with no sealed body is held as its storage row instead, and its
  replay carries no evidence (VM-08-002);
- the storage rows staged from its inline objects (IO-03-004), which the
  replay stages again for routing.  They are rows (``id_``, ``type_``,
  ``data_``), not domain objects, so no read by an object's own id ever
  reaches them, and they are held as one JSON string because storage
  normalises the keys of a nested mapping (``id_`` to ``id``).

A core reader that asks for a received activity still waiting on its case
loads it from this record as it loads an archived one
(the ``ReceivedActivityLoader`` port): the held body is parsed again,
not read from a stored summary of it.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from pydantic import Field, field_validator, model_validator

from vultron.core.models.base import (
    NonEmptyString,
    UriString,
    with_record_id,
)
from vultron.core.models.received_body import require_json_object_text
from vultron.core.models.retired_stored_fields import (
    RetiredFieldsRecord,
    RetiredStoredField,
)


class DeferredInboxActivity(RetiredFieldsRecord):
    """One deferred inbox activity, held under the receiver's key.

    Exactly one of :attr:`received_body` and :attr:`activity_row_json` is
    set: the sealed body when the delivery carried one, else the row.
    """

    type_: Literal["DeferredInboxActivity"] = Field(  # type: ignore[assignment]
        default="DeferredInboxActivity",
        validation_alias="type",
        serialization_alias="type",
    )
    # The event's core summary of the activity, retired for the body itself
    # (ADR-0149): nothing derived from what arrived is stored beside it.
    retired_stored_fields: ClassVar[Mapping[str, RetiredStoredField]] = {
        "activity": RetiredStoredField(None, "#4943"),
    }
    activity_id: UriString = Field(
        ..., description="The sender's id for the deferred activity"
    )
    received_body: NonEmptyString | None = Field(
        default=None,
        description=(
            "The received JSON body as the parser sealed it (VM-08-002)"
        ),
    )
    activity_row_json: NonEmptyString | None = Field(
        default=None,
        description=(
            "JSON storage row (id_, type_, data_) of an activity that arrived"
            " with no sealed body"
        ),
    )
    rows_json: NonEmptyString = Field(
        default="[]",
        description=(
            "JSON array of the storage rows (id_, type_, data_) staged from"
            " the activity's inline objects"
        ),
    )

    @classmethod
    def build_id(cls, activity_id: str) -> str:
        """Return the receiver's stable DataLayer id for *activity_id*."""
        slug = urllib.parse.quote(activity_id, safe="")
        return f"deferred-inbox-activity/{slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``activity_id``."""
        if isinstance(data, dict):
            activity_id = data.get("activity_id")
            if activity_id is not None:
                data = with_record_id(data, cls.build_id(activity_id))
        return data

    @field_validator("received_body")
    @classmethod
    def _body_is_a_json_object(cls, value: str | None) -> str | None:
        """Refuse a held body that is not the text of one JSON object."""
        if value is None:
            return value
        return require_json_object_text(value, "received_body")

    @model_validator(mode="after")
    def _holds_the_activity_once(self) -> DeferredInboxActivity:
        """Refuse a record that holds the activity twice, or not at all."""
        if (self.received_body is None) == (self.activity_row_json is None):
            raise ValueError(
                "DeferredInboxActivity holds the activity as exactly one of"
                " received_body and activity_row_json"
            )
        return self


__all__ = ["DeferredInboxActivity"]
