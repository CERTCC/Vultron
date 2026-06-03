"""Unknown and unresolvable-object fallback registry entries.

These MUST be last in ``SEMANTIC_REGISTRY`` — they are the catch-all
sentinels used when no other pattern matches.
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

from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.unknown import (
    UnknownReceivedEvent,
    UnresolvableObjectReceivedEvent,
)
from vultron.core.use_cases.received.unknown import (
    UnknownUseCase,
    UnresolvableObjectUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry

# ``UNKNOWN_UNRESOLVABLE_OBJECT`` must come before ``UNKNOWN``.
# Both entries have ``pattern=None`` — they are matched via special-case
# logic in ``find_matching_semantics()``, not by pattern iteration.
ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
        pattern=None,
        event_class=UnresolvableObjectReceivedEvent,
        use_case_class=UnresolvableObjectUseCase,
        wire_activity_class=None,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.UNKNOWN,
        pattern=None,
        event_class=UnknownReceivedEvent,
        use_case_class=UnknownUseCase,
        wire_activity_class=None,
    ),
]
