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

"""One received message, one staged record (ADR-0154).

Every received activity this actor holds is one
:class:`ReceivedActivityRecord`, under one id the **receiver** derives from
the sender's activity id (:meth:`build_id`), so the row never sits under an
id the sender chose: a sender that names its activity after a record the
receiver derives (a pending-case marker, an offer record, a report-case link)
cannot squat that id ahead of the receiver's own write.  The sender's id is
kept in :attr:`activity_id` for the reverse lookup.

The record holds the activity as the body that arrived, exactly as the parser
sealed it (:attr:`received_body`, VM-08-002), and nothing derived from it
(CLP-10-017, ADR-0149): no stored summary can drift from what was received.
A reader loads the body: core through the ``ReceivedActivityLoader`` port,
which parses and extracts it into a read-only view, and a reply through the
wire seam that parses it and embeds it as received (DL-06-004).

Lookup in both directions:

- their key -> ours: ``dl.read(ReceivedActivityRecord.build_id(their_id))``;
- ours -> theirs: ``record.activity_id``.

Two facts, two fields
---------------------

This one record replaced two (``DeferredInboxActivity`` retired with it), so
it carries the two facts those rows carried separately, and they are
genuinely independent:

- :attr:`stage` -- how far the message has got.  ``HELD`` is a message the
  receiver has not archived; ``ARCHIVED`` is one intake archived
  (CLP-10-017).
- :attr:`replay_owed` -- whether a replay is still owed from this record's
  body, because the delivery that carried it ended without routing it: it
  waits on its case (IO-03-009), on a ledger gap (SYNC-14-001), on an object
  fetch (AKM-05-007), or on a retry.

Both combinations of the two are reachable, which is why one enum cannot
carry them.  ``ARCHIVED`` with a replay owed is a buffered
``Announce(CaseLedgerEntry)``: intake archived it and the handler then held
it for the gap to fill.  ``HELD`` always owes a replay -- a record the
receiver neither archived nor will replay would be unreachable rubbish -- and
:meth:`_stage_and_replay_agree` refuses one at construction.

:attr:`replay_owed` is also what decides whether a routed copy carries
received evidence, which is why it is a field and not a lookup:

- a replay of this record routes the held body **with** its evidence, because
  the copy routed *is* the delivery held (VM-08-008);
- a *new* delivery answered by this record while a replay is owed routes the
  held copy **without** evidence, because the copy routed is not this
  delivery, and the held one will carry the evidence when it is replayed
  (VM-08-010);
- a new delivery answered by an archived record with no replay owed routes
  the archived body **with** its evidence, because that body is the first
  delivery's, sealed at its parse (VM-08-009).

Where this is going
-------------------

Intake still archives every arrival, so ``ARCHIVED`` here means "intake kept
it", not "the receiver applied it".  Once the doors run before the archive,
``ARCHIVED`` becomes the applied outcome, a refused message leaves a receipt
stub with no body, and ``replay_owed`` becomes a waiting stage of its own
(#5046, #5047 follow this record; the stub and the outcome stage are #5045's
second part).  Nothing outside this module reads the two fields together, so
that change lands here.
"""

import urllib.parse
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from vultron.core.models._helpers import now_utc, timestamp_serializer
from vultron.core.models.base import (
    CoreRecord,
    NonEmptyString,
    UriString,
    with_record_id,
)
from vultron.core.models.received_body import require_json_object_text


class ReceivedStage(StrEnum):
    """How far a received message has got (ADR-0154).

    - ``HELD`` -- the receiver holds the body but has not archived it.  The
      delivery that carried it ended without routing it, so a replay is
      always owed for a record in this stage.
    - ``ARCHIVED`` -- intake archived the body as received (CLP-10-017).  A
      replay may still be owed from it, when a handler held it after intake.
    """

    HELD = "held"
    ARCHIVED = "archived"


class ReceivedActivityRecord(CoreRecord):
    """One received activity, staged under a key the receiver derives.

    Attributes:
        activity_id: The sender's id for the activity -- their key.  The
            record's own ``id_`` is derived from it by :meth:`build_id`.
        received_body: The JSON body that arrived, as the parser sealed it
            (VM-08-002): the text of one JSON object.
        stage: How far this message has got; see :class:`ReceivedStage`.
        replay_owed: Whether a replay is still owed from
            :attr:`received_body`.
        awaiting_case_id: The case this record waits on before it can be
            routed, when that is what it waits for (IO-03-009).  ``None``
            when it waits on something else, or on nothing.
        received_at: When this receiver first held the message.  Orders the
            replay of several messages waiting on one case, so the order
            they arrived in is the order they are routed in.
        replay_rows_json: The storage rows staged from the activity's inline
            objects, which the replay stages again for routing (IO-03-009).
            Rows (``id_``, ``type_``, ``data_``), not domain objects, so no
            read by an object's own id ever reaches them, and held as one
            JSON string because storage normalises the keys of a nested
            mapping (``id_`` to ``id``).
    """

    type_: Literal["ReceivedActivityRecord"] = Field(  # type: ignore[assignment]
        default="ReceivedActivityRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    # Only the sealed body is held, never a core summary of the activity
    # (ADR-0149): nothing derived from what arrived is stored beside it.
    activity_id: NonEmptyString = Field(
        ..., description="The sender's id for the archived activity"
    )
    received_body: NonEmptyString = Field(
        ...,
        description=(
            "The received JSON body as the parser sealed it (VM-08-002)"
        ),
    )
    stage: ReceivedStage = Field(
        default=ReceivedStage.ARCHIVED,
        description="How far this received message has got (ADR-0154)",
    )
    replay_owed: bool = Field(
        default=False,
        description=(
            "Whether a replay is still owed from the held body (IO-03-009)"
        ),
    )
    awaiting_case_id: UriString | None = Field(
        default=None,
        description=(
            "The case this record waits on before it can be routed, when"
            " that is what it waits for (IO-03-009)"
        ),
    )
    received_at: datetime = Field(
        default_factory=now_utc,
        description="When this receiver first held the message",
    )
    _serialize_received_at = timestamp_serializer("received_at")
    replay_rows_json: NonEmptyString = Field(
        default="[]",
        description=(
            "JSON array of the storage rows (id_, type_, data_) staged from"
            " the activity's inline objects"
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

    @model_validator(mode="after")
    def _stage_and_replay_agree(self) -> Self:
        """Refuse a record whose stage and replay flag contradict each other.

        A ``HELD`` record the receiver will never replay is unreachable: it
        is neither the archive a reader loads nor a body any replay routes,
        so nothing would ever read it again.  Likewise a record that names
        the case it waits on owes the replay that waiting is for.  Both are
        wiring mistakes, refused here rather than left to be discovered as a
        lost message (ARCH-10-001).
        """
        if self.stage is ReceivedStage.HELD and not self.replay_owed:
            raise ValueError(
                f"received activity '{self.activity_id}' is HELD with no"
                " replay owed, so nothing would ever read it again: hold a"
                " body only for a replay, or archive it (ADR-0154)"
            )
        if self.awaiting_case_id is not None and not self.replay_owed:
            raise ValueError(
                f"received activity '{self.activity_id}' waits on case"
                f" '{self.awaiting_case_id}' with no replay owed, so the"
                " wait could never end (IO-03-009)"
            )
        return self


__all__ = ["ReceivedActivityRecord", "ReceivedStage"]
