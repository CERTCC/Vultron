"""Dead-letter record model for outbox activities that exhausted delivery attempts.

When an outbound activity's total delivery attempts reach ``max_total_attempts``,
it is moved from the outbox queue to a ``OutboxDeadLetterEntry`` in the DataLayer
rather than being re-queued indefinitely.  Entries are stored for operator review
without requiring log access.

See ``specs/outbox.yaml`` OX-13-002, OX-13-003, OX-13-004.
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
from typing import Literal

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
