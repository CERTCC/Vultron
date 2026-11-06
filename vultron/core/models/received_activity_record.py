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

While the record holds the message, it holds the activity as the body that
arrived, exactly as the parser sealed it (:attr:`received_body`, VM-08-002),
and nothing derived from it (CLP-10-017, ADR-0149): no stored summary can
drift from what was received.
A reader loads the body: core through the ``ReceivedActivityLoader`` port,
which parses and extracts it into a read-only view, and a reply through the
wire seam that parses it and embeds it as received (DL-06-004).

Why four fields are optional, against the fail-fast rule
--------------------------------------------------------

ARCH-10-001 asks that a required field validate at construction and that a
subtype-required field not be ``X | None``.  Four fields here are
``X | None`` even though each is required in one stage and forbidden in
another: :attr:`received_body` (every stage but a receipt stub), and
:attr:`sender_id`, :attr:`refusal_reason` and :attr:`body_hash` (a receipt
stub only).  The alternative was a discriminated union, or a second
``ReceiptStub`` class; both were refused because the seen-before door must
be **one read of one row** (ADR-0154), and a union or a sibling class makes
it two.

So the fields sit against that rule, and the cost is paid back by making the
invariant **checked at construction** rather than conventional:
:meth:`_a_stub_keeps_no_body` refuses a body-bearing stage with no body and
refuses a stub missing any of its three, in both directions.  A wiring
mistake is a ``ValidationError`` at the write, not a lost body discovered
later.  ``validate_assignment`` is on for every ``CoreRecord``, so an
assignment is refused the same way.

Lookup in both directions:

- their key -> ours: ``dl.read(ReceivedActivityRecord.build_id(their_id))``;
- ours -> theirs: ``record.activity_id``.

Two facts, two fields
---------------------

This one record replaced two (``DeferredInboxActivity`` retired with it), so
it carries the two facts those rows carried separately, and they are
genuinely independent:

- :attr:`stage` -- how far the message has got.  ``HELD`` is a message in
  holding: waiting, being handled, or left by a run that ended with no
  verdict (CLP-10-074); ``HANDLED`` is one a later run is handling again
  from that body; ``ARCHIVED`` is one the receiver applied, which the
  outcome stage archives (CLP-10-073); ``REFUSED`` is a receipt stub, all
  that is left of a message the receiver refused (CLP-10-018).
- :attr:`replay_owed` -- whether a replay is still owed from this record's
  body, because the delivery that carried it ended without routing it: it
  waits on its case (IO-03-009), on a ledger gap (SYNC-14-001), on an object
  fetch (AKM-05-007), or on a retry.

Both values of :attr:`replay_owed` are reachable in holding, which is why
one enum cannot carry them.  ``HELD`` with a replay owed is a message waiting
(for its case, a ledger gap, a fetch, a retry); ``HELD`` with none is one the
doors admitted and intake recorded, whose run is in progress or ended with no
verdict, so a later delivery runs it again (ADR-0154, CLP-10-074).  An
``ARCHIVED`` record never owes a replay: the archive holds only applied
messages, and a message still owed one has not reached its outcome.
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

What reads the stage
--------------------

The seen-before door of every received tree answers a resend from this one
record before intake runs (ADR-0154): a receipt stub is refused again with
its reason, an archived message is skipped, and a message waiting for a
replay is skipped with nothing re-run.  A ``HELD`` or ``HANDLED`` record that
owes no replay lets the delivery through, because inbox runs are serialized
per actor: a resend never meets a run in progress, only one that ended with
no verdict.

What tells a stage after intake that its run is a re-run is the record's
stage, ``HANDLED``, and nothing an earlier stage left in memory (ADR-0154):
intake moves a ``HELD`` record a run left to ``HANDLED`` before any later
stage reads it, so a crash anywhere after intake leaves a record the next
run reads as a re-run.  A stage before intake asks whether a record owed no
replay is already in holding (:func:`began_in_an_earlier_run`).
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
from vultron.primitives import NormalisedActorId


class ReceivedStage(StrEnum):
    """How far a received message has got (ADR-0154).

    - ``HELD`` -- the receiver holds the body in holding: waiting for a
      replay (:attr:`ReceivedActivityRecord.replay_owed`), or recorded by
      intake on the run that first handles it, and not yet at its outcome
      (CLP-10-017).
    - ``HANDLED`` -- handling began on the message in an earlier run, which
      ended with no verdict (CLP-10-074), and a later run handles it again
      from the held body.  Intake writes it when it meets the ``HELD``
      record, owed no replay, that the earlier run left, so every stage after
      intake tells a re-run from a first run by reading the record, not by
      reading what the door saw (ADR-0154).  It never owes a replay.  It is
      not the "handled" step of ADR-0154's lifecycle sketch: a first run's
      record stays ``HELD`` while it is handled, and only a re-run's is
      ``HANDLED``.
    - ``ARCHIVED`` -- the receiver applied the message, and the outcome stage
      kept its sealed body as the archive (CLP-10-073).  It never owes a
      replay.
    - ``REFUSED`` -- the receiver refused the message, so all that is left is
      a receipt stub: who sent it, which message, when it arrived, why it was
      refused and the digest of the body, which is not kept (CLP-10-018).

    ``HELD`` and ``HANDLED`` are the stages in holding
    (:data:`HOLDING_STAGES`).  ``HELD``, ``HANDLED`` and ``ARCHIVED`` are the
    body-bearing stages (:data:`BODY_BEARING_STAGES`); ``REFUSED`` is the one
    that is not.
    """

    HELD = "held"
    HANDLED = "handled"
    ARCHIVED = "archived"
    REFUSED = "refused"


#: The stages whose record holds the sealed received body.  ``REFUSED`` is
#: the only stage that does not, and a reader that needs a body asks this
#: rather than naming the stages itself.
BODY_BEARING_STAGES: frozenset[ReceivedStage] = frozenset(
    {ReceivedStage.HELD, ReceivedStage.HANDLED, ReceivedStage.ARCHIVED}
)

#: The stages of a message in holding, not yet at its final outcome
#: (ADR-0154): the outcome stage settles a record in either, a wait that ends
#: discards one, and a reader asking "is this message still held" asks this
#: rather than naming ``HELD`` alone.
HOLDING_STAGES: frozenset[ReceivedStage] = frozenset(
    {ReceivedStage.HELD, ReceivedStage.HANDLED}
)


class ReceivedActivityRecord(CoreRecord):
    """One received activity, staged under a key the receiver derives.

    Attributes:
        activity_id: The sender's id for the activity -- their key.  The
            record's own ``id_`` is derived from it by :meth:`build_id`.
        received_body: The JSON body that arrived, as the parser sealed it
            (VM-08-002): the text of one JSON object.  ``None`` only on a
            receipt stub, which gave the body up (CLP-10-018).
        sender_id: Who sent the message.  Kept **only** on a receipt stub,
            which has no body left to read it from; on a body-bearing record
            the body is the one account of what arrived, and a field beside
            it could drift from it (CLP-10-017, ADR-0149).
        refusal_reason: Why the receiver refused the message.  Receipt stub
            only.
        body_hash: The digest of the body the stub gave up
            (:func:`~vultron.core.models.received_body.received_body_digest`),
            so a reused id can still be told from a resend of the same body
            without keeping it (IE-10-002).  Receipt stub only.
        stage: How far this message has got; see :class:`ReceivedStage`.
        replay_owed: Whether a replay is still owed from
            :attr:`received_body`.
        awaiting_case_id: The case this record waits on before it can be
            routed, when that is what it waits for (IO-03-009).  ``None``
            when it waits on something else, or on nothing.
        received_at: When this receiver first held the message.  Orders the
            replay of several messages waiting on one case, so the order
            they arrived in is the order they are routed in, and on a receipt
            stub it is the time of receipt the stub records (CLP-10-018).
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
    received_body: NonEmptyString | None = Field(
        default=None,
        description=(
            "The received JSON body as the parser sealed it (VM-08-002);"
            " None only on a receipt stub (CLP-10-018)"
        ),
    )
    # The sender as the event carried it, so the stub records the id the
    # delivery was judged under, not another spelling of it (OID-01-006).
    sender_id: NormalisedActorId | None = Field(
        default=None,
        description=(
            "Who sent the refused message; a receipt stub only (CLP-10-018)"
        ),
    )
    refusal_reason: NonEmptyString | None = Field(
        default=None,
        description=(
            "Why the message was refused; a receipt stub only (CLP-10-018)"
        ),
    )
    body_hash: NonEmptyString | None = Field(
        default=None,
        description=(
            "The digest of the body a receipt stub gave up (IE-10-002)"
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
    def _is_a_json_object(cls, value: str | None) -> str | None:
        """Refuse a body that is not the text of one JSON object (VM-08-002).

        A receipt stub has no body at all; whether that is allowed is the
        stage's question, answered by :meth:`_a_stub_keeps_no_body`.
        """
        if value is None:
            return None
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

        An ``ARCHIVED`` record is an applied message, so a replay owed from
        it would apply it again; a message still owed one has not reached
        its outcome and stays ``HELD`` (ADR-0154).  A ``HANDLED`` record is a
        message a run is handling again from its body, so a replay owed from
        it would route it a second time beside that run.  Likewise a record that
        names the case it waits on owes the replay that waiting is for.  Both
        are wiring mistakes, refused here rather than left to be discovered
        as a message applied twice or lost (ARCH-10-001).
        """
        if self.stage is ReceivedStage.ARCHIVED and self.replay_owed:
            raise ValueError(
                f"received activity '{self.activity_id}' is ARCHIVED and owes"
                " a replay, but the archive holds only applied messages:"
                " keep a message owed a replay HELD (ADR-0154)"
            )
        if self.stage is ReceivedStage.HANDLED and self.replay_owed:
            raise ValueError(
                f"received activity '{self.activity_id}' is HANDLED and owes"
                " a replay, but HANDLED is a message a run is handling again"
                " from its body, not one waiting: keep a message owed a"
                " replay HELD (ADR-0154)"
            )
        if self.awaiting_case_id is not None and not self.replay_owed:
            raise ValueError(
                f"received activity '{self.activity_id}' waits on case"
                f" '{self.awaiting_case_id}' with no replay owed, so the"
                " wait could never end (IO-03-009)"
            )
        return self

    @property
    def is_receipt_stub(self) -> bool:
        """Whether this record is a receipt stub, holding no body."""
        return self.stage is ReceivedStage.REFUSED

    @model_validator(mode="after")
    def _a_stub_keeps_no_body(self) -> Self:
        """Refuse a record whose stage and its body/stub fields disagree.

        Pinned in both directions, because either way round loses something
        that cannot be recovered:

        - a body-bearing stage (:data:`BODY_BEARING_STAGES`) with no body is
          a record nothing can read as the message, and the body is gone;
        - a body-bearing record carrying a stub's fields stores something
          derived from what arrived beside the body it was derived from,
          which is the drift CLP-10-017 forbids;
        - a receipt stub that kept the body did not give it up, so the
          refusal did not take effect (CLP-10-018);
        - a receipt stub missing its sender, reason or digest records a
          refusal nobody can read: who sent what, when, why, and enough to
          tell a resend from a reused id (IE-10-002);
        - a receipt stub that still owes a replay would have the replay read
          a body that is no longer there.

        Validates only; nothing is assigned to ``self`` (ARCH-21-004).
        """
        if self.stage in BODY_BEARING_STAGES:
            return self._a_body_bearing_record_is_whole()
        return self._a_receipt_stub_is_whole()

    def _a_body_bearing_record_is_whole(self) -> Self:
        """The ``HELD``/``ARCHIVED`` half of :meth:`_a_stub_keeps_no_body`."""
        if self.received_body is None:
            raise ValueError(
                f"received activity '{self.activity_id}' is {self.stage} with"
                " no received body, so nothing can read it as the message:"
                " hold the sealed body, or record a receipt stub"
                " (VM-08-002, CLP-10-018)"
            )
        carried = sorted(
            field
            for field in ("sender_id", "refusal_reason", "body_hash")
            if getattr(self, field) is not None
        )
        if carried:
            raise ValueError(
                f"received activity '{self.activity_id}' is {self.stage} and"
                f" carries {', '.join(carried)}, which only a receipt stub"
                " keeps: a record holding the body stores nothing derived"
                " from it (CLP-10-017, ADR-0149)"
            )
        return self

    def _a_receipt_stub_is_whole(self) -> Self:
        """The ``REFUSED`` half of :meth:`_a_stub_keeps_no_body`."""
        if self.received_body is not None:
            raise ValueError(
                f"refused activity '{self.activity_id}' still holds its"
                " received body: a refusal keeps the receipt, not the"
                " message (CLP-10-018)"
            )
        missing = sorted(
            field
            for field in ("sender_id", "refusal_reason", "body_hash")
            if getattr(self, field) is None
        )
        if missing:
            raise ValueError(
                f"the receipt stub for activity '{self.activity_id}' is"
                f" missing {', '.join(missing)}: a stub records who sent"
                " what, when, why it was refused and the digest of the body"
                " it gave up (CLP-10-018, IE-10-002)"
            )
        if self.replay_owed:
            raise ValueError(
                f"the receipt stub for activity '{self.activity_id}' owes a"
                " replay, but the body it would replay is not kept"
                " (CLP-10-018, IO-03-009)"
            )
        return self


__all__ = [
    "BODY_BEARING_STAGES",
    "HOLDING_STAGES",
    "ReceivedActivityRecord",
    "ReceivedStage",
]
