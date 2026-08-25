"""Outbox dead-letter model and adapter-level retry-store protocol.

The dead-letter concern is a delivery infrastructure artifact, not a domain
concern.  ``OutboxDeadLetterEntry`` records an HTTP-transport failure that
exhausted its retry budget; ``OutboxRetryStore`` is the adapter-level protocol
that ``outbox_handler`` uses to track cumulative attempt counts and record
exhausted activities.

These types live in the adapter layer (not ``vultron/core/``) because:
- The trigger is HTTP delivery failure — a transport-level event.
- The data captured (retry counts, failed recipients) is delivery bookkeeping.
- Core should be delivery-mechanism agnostic (hexagonal architecture).

``SqliteDataLayer`` satisfies ``OutboxRetryStore`` structurally.

See ``specs/outbox.yaml`` OX-13-001 through OX-13-004.
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

from vultron.core.models.base import NonEmptyString, VultronBase


class OutboxDeadLetterEntry(VultronBase):
    """Record of an outbox activity that exhausted its total delivery budget.

    Attributes:
        type_: Fixed literal ``"OutboxDeadLetterEntry"`` for DataLayer type lookup.
        activity_id: The ID of the activity that could not be delivered.
        actor_id: The canonical ID of the actor whose outbox this came from.
        reason: Short machine-readable reason code (e.g. ``"max_attempts_exhausted"``).
        total_attempts: Cumulative delivery attempt count at time of exhaustion.
        failed_recipients: Actor IDs that could not be reached.
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
    ) -> None: ...

    def dead_letter_list(self) -> list[OutboxDeadLetterEntry]: ...
