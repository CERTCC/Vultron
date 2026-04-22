"""Dead-letter record model for unresolvable-object_ inbox activities.

When an inbound activity's ``object_`` URI cannot be resolved after
rehydration, the activity is stored as a ``DeadLetterRecord`` rather than
raising an error.  Records are stored in the DataLayer for administrative
review and retry.

See ``specs/semantic-extraction.md`` SE-04-003.
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
from typing import Any, Literal

from pydantic import Field

from vultron.core.models.base import NonEmptyString, VultronBase


class DeadLetterRecord(VultronBase):
    """Record of an inbox activity whose ``object_`` URI could not be resolved.

    Attributes:
        type_: Fixed literal ``"DeadLetterRecord"`` for DataLayer type lookup.
        unresolvable_uri: The bare string URI that could not be resolved.
        actor_id: The canonical ID of the actor in whose inbox this arrived.
        activity_id: The ID of the unresolvable activity.
        activity_type: The AS2 type of the activity (e.g. ``"Accept"``).
        activity_summary: Serialized snapshot of the activity's key fields.
        received_at: UTC timestamp when the dead-letter was recorded.
    """

    type_: Literal["DeadLetterRecord"] = Field(  # type: ignore[assignment]
        default="DeadLetterRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    unresolvable_uri: NonEmptyString
    actor_id: NonEmptyString
    activity_id: NonEmptyString
    activity_type: NonEmptyString | None = None
    activity_summary: dict[str, Any] | None = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
