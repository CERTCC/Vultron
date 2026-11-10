#!/usr/bin/env python
"""InboxOutcome model and adapter/port protocol interfaces.

Defines the typed return model and Protocol interfaces used by
:func:`~vultron.core.behaviors.inbox.process_payload`.

Per specs/inbox-orchestration.yaml:
- IO-01-001 through IO-01-008: InboxOutcome model
- IO-03-001, IO-03-005: IngressPayloadAdapter and DispatchAdapter protocols
- IO-03-002: PendingCaseQueuePort protocol
"""

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

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, Self, runtime_checkable

from pydantic import BaseModel, model_validator

from vultron.core.models.events import VultronEvent
from vultron.core.models.use_case_result import HandlerResult
from vultron.primitives import NonEmptyString


class InboxOutcomeStatus(StrEnum):
    """What the inbox pipeline did with one payload (IO-01-002).

    - ``PROCESSED`` — dispatched, and the handler applied or correctly skipped it.
    - ``DEFERRED`` — held for replay: by ``DeferCheckNode`` before dispatch
      (missing case context), or by the handler after it (IO-01-006).
    - ``REJECTED`` — refused, unparseable, undispatchable, or the dispatch
      raised.

    This vocabulary belongs to the pipeline. ``DispatchNode`` alone maps a
    handler's ``HandlerDisposition`` onto it (HP-01-004).
    """

    PROCESSED = "processed"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class InboxOutcome(BaseModel):
    """Result returned by every :func:`process_payload` call.

    Per specs/inbox-orchestration.yaml IO-01-001 through IO-01-008.
    """

    status: InboxOutcomeStatus
    context_id: str | None = None
    activity_id: NonEmptyString | None = None
    failure_reason: str | None = None
    #: The activity's semantic type is recognized, but no use case handles
    #: it ("no use case found", SE-05-005).  Only a ``rejected`` outcome is
    #: unhandled; the driving adapter logs it at INFO, not WARNING, because
    #: the message is not invalid (IO-01-005).
    unhandled: bool = False

    @model_validator(mode="after")
    def _only_a_rejection_is_unhandled(self) -> Self:
        if self.unhandled and self.status is not InboxOutcomeStatus.REJECTED:
            raise ValueError(
                f"an unhandled InboxOutcome is rejected, not {self.status}"
            )
        return self


@runtime_checkable
class IngressPayloadAdapter(Protocol):
    """Adapter: raw input → rehydrated as_Activity.

    Owns parse and rehydrate; isolates wire-format knowledge from the
    orchestration BT.  Per IO-03-001.
    """

    def parse(
        self,
        payload: dict[str, Any] | bytes | str | Any,
    ) -> Any | None:
        """Parse raw payload into a typed Activity.

        Returns ``None`` on parse failure; MUST NOT raise.
        """
        ...  # pragma: no cover

    def rehydrate(self, activity: Any) -> Any:
        """Resolve nested object references to their full representations."""
        ...  # pragma: no cover


@runtime_checkable
class DispatchAdapter(Protocol):
    """Adapter: VultronEvent → use-case execution.

    Wraps the existing ActivityDispatcher port.  Per IO-03-001, IO-03-005.
    """

    def dispatch(self, event: VultronEvent) -> HandlerResult:
        """Dispatch a domain event and return the handler's verdict.

        The ``HandlerResult`` is the only channel from the handler to
        ``InboxOutcome`` (UCORG-05-010).
        """
        ...  # pragma: no cover

    def emit_processing_fault(
        self, event: VultronEvent, failure_class: str
    ) -> None:
        """Queue ``Create(ProcessingFault)`` of *failure_class* to the sender.

        The receiving actor answers *event*'s sender, ``event.actor_id``,
        about the activity ``event.activity_id`` (ASK-07-001).  The fault id
        is derived from the failed activity and the failure class, so a
        second failure of the same activity builds no second fault
        (ASK-07-018, ID-04-004).
        """
        ...  # pragma: no cover


@runtime_checkable
class PendingCaseQueuePort(Protocol):
    """Port: pending-case inbox queue management.

    Provides defer and replay queue operations to :class:`DeferCheckNode`
    without requiring adapter-layer imports in core.  Per IO-03-002.
    """

    def is_case_known(self, case_id: str) -> bool:
        """Return ``True`` if the case replica is locally available."""
        ...  # pragma: no cover

    def queue(
        self,
        activity_id: str,
        case_id: str,
        case_actor_id: str | None = None,
        *,
        at: datetime,
    ) -> None:
        """Persist *activity_id* in the deferred queue for *case_id*.

        The adapter holds the activity's received body for the replay on the
        activity's own record, under a key the receiver derives (DL-06-006,
        IO-03-009); the hold is what records the wait, naming *case_id* on
        that record (ADR-0154), and a core reader loads the body from there
        before the outcome stage archives it.

        *at* is the act's instant, the activity's arrival stamp: the held
        record keeps it for the replay, and a first waiter opens the case's
        expiry window at it (CBT-03-001, ADR-0176).
        """
        ...  # pragma: no cover

    def check_and_expire(self, case_id: str, *, at: datetime) -> bool:
        """Drop *case_id*'s queue and return ``True`` if it expired by *at*.

        The queue has expired when the arrival stamp that opened its window
        plus the interval (CBT-03-005) is not after *at*, the instant of the
        act that asks (CBT-03-003, ADR-0176).
        """
        ...  # pragma: no cover

    def replay(self, case_id: str, *, at: datetime) -> None:
        """Move the activities waiting on *case_id* back to the live inbox.

        Which they are is read from the waiting records themselves, in the
        order they arrived (ADR-0154).  The queue is judged for expiry at
        *at*, the instant of the act that releases it, first: an expired
        queue is dropped, not replayed (CBT-03-003, ADR-0176).
        """
        ...  # pragma: no cover


@runtime_checkable
class ReceivedOutcomePort(Protocol):
    """Port: move a received record to its final outcome stage (ADR-0154).

    An applied or skipped message's record is archived with the sealed body
    it holds (:meth:`apply`), a refused one leaves a receipt stub
    (:meth:`refuse`), a deferred one stays in holding, and an internal error
    leaves the record untouched for the re-run (CLP-10-073, CLP-10-074).
    """

    def apply(self, activity_id: str) -> None:
        """Archive the ``HELD`` record of an applied or skipped *activity_id*.

        Nothing is written for a record already at its outcome, one still
        owed a replay, or no record at all (CLP-10-073, CLP-10-076).

        Raises:
            Exception: Whatever the store raises.  ``update()`` in the
                calling node is what catches it (BT-HELPER-01).
        """
        ...  # pragma: no cover

    def refuse(
        self,
        activity_id: str,
        *,
        sender_id: str,
        reason: str,
        received_body: str | None,
        received_at: datetime,
    ) -> None:
        """Give up *activity_id*'s body for a receipt stub.

        The stub records *sender_id*, the activity id, the time of receipt,
        *reason* and the digest of the body (CLP-10-018).  A delivery a door
        refused before intake ran has no record, so its stub is written from
        *received_body*, its own sealed body, stamped *received_at*, the
        delivery's arrival stamp (ADR-0176).  Idempotent: a second refusal
        of the same activity leaves the first reason standing.

        A body still owed to a replay is left as it is: the replay is the
        held message's own outcome (CLP-10-076).

        Raises:
            Exception: Whatever the store raises, and a wiring error when
                nothing is held for *activity_id* and no *received_body* is
                given.  ``update()`` in the calling node is what catches it
                (BT-HELPER-01).
        """
        ...  # pragma: no cover
