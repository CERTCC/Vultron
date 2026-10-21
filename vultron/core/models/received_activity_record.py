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

"""The receiver's archive of one received activity (ADR-0111, ADR-0149).

Intake writes one :class:`ReceivedActivityRecord` per received activity.  The
record's id is the **receiver's** key, derived by :meth:`build_id` from the
sender's activity id, so the archive never occupies a row under an id the
sender chose: a sender who names its activity after a record the receiver
derives (a pending-case-inbox marker, an offer record, a report-case link)
cannot squat that id ahead of the receiver's own write.  The sender's id is
kept in :attr:`activity_id` for the reverse lookup.

The record holds the activity as the body that arrived, exactly as the parser
sealed it (:attr:`received_body`, VM-08-002), and nothing derived from it
(CLP-10-017, ADR-0149): no stored summary can drift from what was received.
A reader loads the body: core through
the ``ReceivedActivityLoader`` port, which parses and extracts it into
a read-only view, and a reply through the wire seam that parses it and embeds
it as received (DL-06-004).

Lookup in both directions:

- their key → ours: ``dl.read(ReceivedActivityRecord.build_id(their_id))``;
- ours → theirs: ``record.activity_id``.
"""

import urllib.parse
from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from pydantic import Field, field_validator, model_validator

from vultron.core.models.base import NonEmptyString, with_record_id
from vultron.core.models.received_body import require_json_object_text
from vultron.core.models.retired_stored_fields import (
    RetiredFieldsRecord,
    RetiredStoredField,
)


class ReceivedActivityRecord(RetiredFieldsRecord):
    """One received activity, archived under a key the receiver derives.

    Attributes:
        activity_id: The sender's id for the activity — their key.  The
            record's own ``id_`` is derived from it by :meth:`build_id`.
        received_body: The JSON body that arrived, as the parser sealed it
            (VM-08-002): the text of one JSON object.
    """

    type_: Literal["ReceivedActivityRecord"] = Field(  # type: ignore[assignment]
        default="ReceivedActivityRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    # The event's core summary of the activity, retired for the body itself
    # (ADR-0149): nothing derived from what arrived is stored beside it.
    retired_stored_fields: ClassVar[Mapping[str, RetiredStoredField]] = {
        "activity": RetiredStoredField(None, "#4943"),
    }
    activity_id: NonEmptyString = Field(
        ..., description="The sender's id for the archived activity"
    )
    received_body: NonEmptyString = Field(
        ...,
        description=(
            "The received JSON body as the parser sealed it (VM-08-002)"
        ),
    )

    @classmethod
    def build_id(cls, activity_id: str) -> str:
        """The receiver's stable DataLayer id for the activity *activity_id*."""
        slug = urllib.parse.quote(activity_id, safe="")
        return f"received-activity/{slug}"

    @field_validator("received_body")
    @classmethod
    def _is_a_json_object(cls, value: str) -> str:
        """Refuse a body that is not the text of one JSON object (VM-08-002)."""
        return require_json_object_text(value, "received_body")

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``activity_id``."""
        if isinstance(data, dict):
            activity_id = data.get("activity_id")
            if activity_id is not None:
                data = with_record_id(data, cls.build_id(activity_id))
        return data


__all__ = ["ReceivedActivityRecord"]
