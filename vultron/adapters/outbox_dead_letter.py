"""Retry-store protocol and dead-letter models for inbox and outbox delivery.

``DeadLetterEntry`` (outbox) and ``InboxDeadLetterEntry`` share the same
adapter-layer pattern: both extend ``CoreRecord`` so they are stored via
``dl.save()`` and recoverable by type string.  Neither is a domain object —
they record transport-layer delivery failures.

``RetryStore`` is the unified adapter-level protocol used by both the outbox
handler (OX-13) and inbox handler (IE-06-004) to persist attempt counts and
move exhausted activities to the dead-letter store.  ``SqliteDataLayer``
satisfies ``RetryStore`` structurally.

``OutboxDeadLetterEntry`` and ``OutboxRetryStore`` are kept for backward
compatibility with code written before #4168.  New code should use
``RetryStore`` and the generic queue-aware methods.

See ``specs/outbox.yaml`` OX-13-001 through OX-13-004, OX-14-001 through
OX-14-003, and ``specs/inbox-endpoint.yaml`` IE-06-004.
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

from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import Field

from vultron.core.models.base import CoreRecord, NonEmptyString


class OutboxDeadLetterEntry(CoreRecord):
    """Record of an outbox activity that exhausted its total delivery budget.

    Although it lives in the adapter layer, it extends ``CoreRecord`` and so
    registers in ``CORE_TYPE_MAP`` when this module is imported. That is
    deliberate: ARCH-12-010 requires every non-``CoreObject`` ``CoreRecord`` to
    be discoverable by type string, which is what lets ``dl.read`` reconstruct
    a stored entry typed rather than as a raw row. Because registration is an
    import side effect, ``CORE_TYPE_MAP`` holds this key only once the outbox
    adapters are loaded; nothing in core may rely on it being present.

    Attributes:
        type_: Fixed literal ``"OutboxDeadLetterEntry"`` for DataLayer type lookup.
        activity_id: The ID of the activity that could not be delivered.
        actor_id: The canonical ID of the actor whose outbox this came from.
        reason: Short machine-readable reason code (e.g. ``"max_attempts_exhausted"``).
        total_attempts: Cumulative delivery attempt count at time of exhaustion.
        failed_recipients: Actor IDs that could not be reached.
        ledger_entry_id: ID of the ``CaseLedgerEntry`` whose event this activity
            was replicating, or ``None`` when the activity is not an
            ``Announce(CaseLedgerEntry)`` (OX-14-001, OX-14-003).
        recorded_at: UTC timestamp when the dead-letter was recorded.
    """

    type_: Literal["OutboxDeadLetterEntry"] = Field(  # type: ignore[assignment]
        default="OutboxDeadLetterEntry",
        validation_alias="type",
        serialization_alias="type",
    )
    activity_id: NonEmptyString
    actor_id: NonEmptyString
    reason: NonEmptyString
    total_attempts: int
    failed_recipients: list[str] = Field(default_factory=list)
    ledger_entry_id: NonEmptyString | None = None
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InboxDeadLetterEntry(CoreRecord):
    """Record of an inbox activity that exhausted its retry budget (IE-06-004).

    Extends the same ``CoreRecord``-based pattern as ``OutboxDeadLetterEntry``
    so that both inbox and outbox dead letters are stored and retrieved via
    the same ``dl.save()`` / ``dl.by_type()`` mechanism.

    Attributes:
        type_: Fixed literal ``"InboxDeadLetterEntry"`` for DataLayer type lookup.
        activity_id: The ID of the activity that could not be processed.
        actor_id: The canonical ID of the actor whose inbox this came from.
        reason: Short machine-readable reason code.
        total_attempts: Cumulative processing attempt count at time of exhaustion.
        last_error: String representation of the last exception raised.
        recorded_at: UTC timestamp when the dead-letter was recorded.
    """

    type_: Literal["InboxDeadLetterEntry"] = Field(  # type: ignore[assignment]
        default="InboxDeadLetterEntry",
        validation_alias="type",
        serialization_alias="type",
    )
    activity_id: NonEmptyString
    actor_id: NonEmptyString
    reason: NonEmptyString
    total_attempts: int
    last_error: str = ""
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutboxRetryStore(Protocol):
    """Adapter-level port for outbox delivery retry tracking and dead-lettering.

    ``outbox_handler`` uses this protocol to persist cumulative attempt counts
    across drain passes and to move exhausted activities to the dead-letter
    store.  ``SqliteDataLayer`` satisfies this protocol structurally.

    This protocol is intentionally NOT part of the core ``DataLayer`` port — it
    expresses a delivery-infrastructure concern, not a domain contract.

    No method takes an ``actor_id``.  Under ADR-0073 the implementing store
    *is* one actor's, so the attempt counters and dead-letter entries it holds
    are that actor's own delivery bookkeeping.  A node-wide operator view fans
    out over hosted actors rather than querying across them.
    """

    def get_outbox_attempt_count(self, activity_id: str) -> int: ...

    def set_outbox_attempt_count(
        self, activity_id: str, count: int
    ) -> None: ...

    def clear_outbox_attempt_count(self, activity_id: str) -> None: ...

    def dead_letter_append(
        self,
        activity_id: str,
        reason: str,
        total_attempts: int,
        failed_recipients: list[str],
        ledger_entry_id: str | None = None,
    ) -> None: ...

    def dead_letter_list(self) -> list[OutboxDeadLetterEntry]: ...


class RetryStore(OutboxRetryStore, Protocol):
    """Unified retry-store protocol covering both inbox and outbox (IE-06-004).

    Extends ``OutboxRetryStore`` with inbox-specific retry tracking and
    dead-lettering.  ``SqliteDataLayer`` satisfies this protocol structurally.

    The outbox methods are inherited from ``OutboxRetryStore``; this protocol
    adds the inbox counterparts so a single cast from ``DataLayer`` suffices
    for code that needs to track either queue's retry budget.
    """

    def get_inbox_attempt_count(self, activity_id: str) -> int: ...

    def set_inbox_attempt_count(
        self, activity_id: str, count: int
    ) -> None: ...

    def clear_inbox_attempt_count(self, activity_id: str) -> None: ...

    def inbox_dead_letter_append(
        self,
        activity_id: str,
        reason: str,
        total_attempts: int,
        last_error: str = "",
    ) -> None: ...

    def inbox_dead_letter_list(self) -> list[InboxDeadLetterEntry]: ...
