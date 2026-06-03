"""Shared ``SemanticEntry`` dataclass used by all domain sub-modules."""

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

from dataclasses import dataclass, field

from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.wire.as2.extractor import ActivityPattern
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity


@dataclass(frozen=True)
class SemanticEntry:
    """All dispatch components for a single ``MessageSemantics`` value.

    Attributes:
        semantics: The semantic intent this entry describes.
        pattern: Wire-layer pattern for matching the incoming activity.
            ``None`` for the ``UNKNOWN`` fallback entry.
        event_class: Domain event class to construct from the matched activity.
        use_case_class: Use-case class to execute for this semantic type.
        wire_activity_class: Specific wire ``as_Activity`` subclass for
            DataLayer coercion. ``None`` when no specific wire class exists.
        include_activity: When ``True``, ``extract_intent()`` populates
            ``VultronEvent.activity`` for this semantic type.
    """

    semantics: MessageSemantics
    pattern: ActivityPattern | None
    event_class: type[VultronEvent]
    use_case_class: type
    wire_activity_class: type[as_Activity] | None = field(default=None)
    include_activity: bool = field(default=False)
