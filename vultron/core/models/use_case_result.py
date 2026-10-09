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

"""Use-case result envelope: ``UseCaseResult`` and both of its halves.

``UseCaseResult`` is the common parent of every use-case return value
(UCORG-05-001, UCORG-05-008). This module defines it together with the
received-side subtype, ``HandlerResult``, and the ``HandlerDisposition``
vocabulary that subtype carries (ADR-0095), and with the trigger-side
hierarchy rooted at ``TriggerResult`` (ADR-0110)::

    TriggerResult          (no fields)
      ActivityResult       activity, emitting_actor_id
        NoteResult         + note
        CaseResult         + case_id
      StatusResult         activity_id, status_id
      OfferResult          offer
      RoleOfferResult      activity_id, activity

Each trigger subtype declares exactly the keys its verb's HTTP response body
carries (UCORG-05-005); the body is the subtype's ``model_dump()``, so a
``None``-valued key is still emitted (TRIG-12-002). ``activity``, ``offer``
and ``note`` are ``dict[NonEmptyString, Any]``: the JSON object a trigger BT captured on
its blackboard. Core cannot type them as wire activities without importing
the wire layer (ARCH-01-001); the demo layer's ``WireActivityResult`` is the
typed view of the same body (UCORG-05-014).

The envelope lives in ``core/models/`` rather than ``core/ports/`` because it
is a Pydantic model, and ports avoid exposing ``BaseModel`` as their own API
shape (``vultron/core/ports/AGENTS.md``). Defining it here lets the ``UseCase``
Protocol name it without defining a model of its own.

``HandlerDisposition`` is the handler's own vocabulary. The inbox pipeline maps
it many-to-one onto its own outcome statuses, and that mapping belongs to the
pipeline, not to this module or to any handler (HP-01-004).
"""

from enum import StrEnum
from typing import Any, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.primitives import NonEmptyString


class UseCaseResult(BaseModel):
    """Base type of every use-case ``execute()`` return value (UCORG-05-008).

    Carries no fields of its own: it exists so the ``UseCase`` Protocol and
    the UCORG-05-004 ratchet have one type to name. Subtypes MAY add
    domain-specific fields but MUST NOT carry raw ``dict`` payloads
    (UCORG-05-005).

    ``validate_assignment`` is set here so every subtype inherits it
    (ARCH-21, ADR-0064): a result mutated after construction is revalidated
    rather than silently accepted. ``extra="forbid"`` likewise applies to every
    subtype, as it does to every core-branch type (ARCH-12-003); a subtype that
    must tolerate unknown keys overrides it explicitly.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")


class HandlerDisposition(StrEnum):
    """What a received-side handler did with its inbound activity (UCORG-05-009).

    - ``APPLIED`` — local state changed to reflect the inbound assertion.
    - ``SKIPPED`` — a correct no-op: a duplicate, an already-present record,
      or an otherwise idempotent re-delivery of a message this actor was
      entitled to act on.
    - ``DEFERRED`` — the item was parked for later replay (for example a ledger
      entry buffered pending its predecessor), neither acted on nor declined.
    - ``REFUSED`` — the handler rejected the inbound assertion. This includes
      a message the receiver holds no role to act on — a CASE_MANAGER-addressed
      message at an actor that is not the case's CASE_MANAGER, or a copy that
      names the receiver in neither ``to`` nor ``cc`` (HP-01-005).

    A benign skip or a deferral MUST NOT be reported as ``REFUSED`` (HP-01-003),
    and "not mine to act on" is not a benign skip: the disposition is the
    receiver's own record of a misaddressed message.
    """

    APPLIED = "applied"
    SKIPPED = "skipped"
    DEFERRED = "deferred"
    REFUSED = "refused"


class HandlerResult(UseCaseResult):
    """Typed result of a received-side use case (UCORG-05-002, UCORG-05-005).

    ``reason`` rules, enforced at construction:

    - ``REFUSED`` requires a ``reason``: it becomes the outcome's
      ``failure_reason``, and a refusal nobody can explain is not triageable.
    - ``APPLIED`` rejects a ``reason``: applied work has nothing to explain,
      and a stray reason would read as a hidden failure.
    - ``SKIPPED`` and ``DEFERRED`` permit one. ADR-0095 constrains neither, and
      both benefit from it: *why* a no-op was correct (``"duplicate"``), and
      *what* a parked item is waiting for (the awaited predecessor).

    ``REFUSED`` is a protocol outcome only — the handler decided the assertion
    must not be applied. A programming error is not a refusal; it propagates as
    an exception, as it does today, so the two stay distinguishable the way
    ``BTExecutionResult.internal_error`` separates them on the BT side.

    The model is frozen: a verdict is not revised after the handler returns
    it. Prefer the ``applied()`` / ``skipped()`` / ``deferred()`` /
    ``refused()`` constructors over spelling out the ``disposition``.
    """

    model_config = ConfigDict(frozen=True)

    disposition: HandlerDisposition
    reason: NonEmptyString | None = None

    @model_validator(mode="after")
    def _check_reason_against_disposition(self) -> Self:
        if (
            self.disposition is HandlerDisposition.REFUSED
            and self.reason is None
        ):
            raise ValueError("a REFUSED HandlerResult requires a reason")
        if (
            self.disposition is HandlerDisposition.APPLIED
            and self.reason is not None
        ):
            raise ValueError(
                "an APPLIED HandlerResult must not carry a reason"
            )
        return self

    @property
    def took_effect(self) -> bool:
        """True when the assertion holds locally: ``APPLIED`` or ``SKIPPED``.

        A skip is a correct no-op, typically because the effect is already
        present. Callers that act on a completed effect — replaying items held
        for a case bootstrap, for example — gate on this rather than on the
        dispatch merely not raising.
        """
        return self.disposition in (
            HandlerDisposition.APPLIED,
            HandlerDisposition.SKIPPED,
        )

    @classmethod
    def applied(cls) -> Self:
        """The handler changed local state to reflect the inbound assertion."""
        return cls(disposition=HandlerDisposition.APPLIED)

    @classmethod
    def skipped(cls, reason: str | None = None) -> Self:
        """The handler correctly did nothing (duplicate, already present, ...)."""
        return cls(disposition=HandlerDisposition.SKIPPED, reason=reason)

    @classmethod
    def deferred(cls, reason: str | None = None) -> Self:
        """The handler parked the item for later replay."""
        return cls(disposition=HandlerDisposition.DEFERRED, reason=reason)

    @classmethod
    def refused(cls, reason: str) -> Self:
        """The handler rejected the inbound assertion, for ``reason``."""
        return cls(disposition=HandlerDisposition.REFUSED, reason=reason)


class TriggerResult(UseCaseResult):
    """Fieldless root of the trigger-side result hierarchy (UCORG-05-005).

    A trigger use case returns the subtype whose fields are exactly its
    verb's response-body keys; nothing returns the root itself. It exists so
    ``TriggerRequest[ResultT_co]`` has a bound, the UCORG-05-004 ratchet has
    a type to name, and every subtype inherits ``extra="forbid"`` — a use
    case whose return grows a key fails at construction instead of the key
    being silently dropped from the body (UCORG-05-007, UCORG-05-008).

    Frozen like :class:`HandlerResult`: a result is not revised after the
    use case returns it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class ActivityResult(TriggerResult):
    """Result of a BT-backed trigger that emits one activity.

    ``activity`` is the emitted activity's JSON object as the BT captured
    it, or ``None`` when the tree completed without capturing one (an
    idempotent no-op path); the key is emitted either way.
    ``emitting_actor_id`` names the actor whose outbox holds the activity — on
    a delegated emit that is the CASE_MANAGER, not the requesting actor
    (CM-24-001), and the router drains that actor's outbox.
    """

    activity: dict[NonEmptyString, Any] | None = None
    emitting_actor_id: NonEmptyString


class NoteResult(ActivityResult):
    """``add-note-to-case``: the activity plus the freshly minted note."""

    note: dict[NonEmptyString, Any] | None = None


class CaseResult(ActivityResult):
    """``create-case``: the activity plus the id of the case it created."""

    case_id: NonEmptyString | None = None


class StatusResult(TriggerResult):
    """``add-participant-status`` and the on-behalf variant.

    Carries the ids of the ``Add(ParticipantStatus)`` activity and of the
    stored status record; neither the activity body nor an emitting actor is
    part of this verb's response.
    """

    activity_id: NonEmptyString | None = None
    status_id: NonEmptyString | None = None


class OfferResult(TriggerResult):
    """``submit-report``: the ``Offer(VulnerabilityReport)`` JSON object."""

    offer: dict[NonEmptyString, Any] | None = None


class RoleOfferResult(TriggerResult):
    """``offer-case-participant-role``: activity id and activity, no emitter.

    The only trigger verb not backed by ``SvcBTTriggerBase`` (ADR-0110), so
    its body carries no ``emitting_actor_id``.
    """

    activity_id: NonEmptyString
    activity: dict[NonEmptyString, Any]


class SyncLogEntryResult(TriggerResult):
    """``sync-log-entry``: the committed ledger entry's id, hash and index.

    The demo-only verb that mints a canonical ``CaseLedgerEntry`` and fans it
    out.  ``emitting_actor_id`` names the case's CASE_MANAGER, as whom the
    commit tree ran and whose outbox holds the ``Announce(CaseLedgerEntry)``
    fan-out (CLP-09, BT-05-005); the router drains that outbox, exactly as it
    does for a delegated :class:`ActivityResult`.
    """

    log_entry_id: NonEmptyString
    entry_hash: NonEmptyString
    log_index: int
    emitting_actor_id: NonEmptyString


@runtime_checkable
class EmittingResult(Protocol):
    """A trigger result that names the actor whose outbox it wrote to.

    :class:`ActivityResult` and :class:`SyncLogEntryResult` satisfy it.  The
    router's shared body checks a result against this Protocol to pick the
    outbox it drains — the emitting actor's, which on a delegated emit is the
    CASE_MANAGER's rather than the requesting actor's (CM-24-001).
    """

    emitting_actor_id: str


__all__ = [
    "ActivityResult",
    "CaseResult",
    "EmittingResult",
    "HandlerDisposition",
    "HandlerResult",
    "NoteResult",
    "OfferResult",
    "RoleOfferResult",
    "StatusResult",
    "SyncLogEntryResult",
    "TriggerResult",
    "UseCaseResult",
]
