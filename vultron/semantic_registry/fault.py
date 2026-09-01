"""ProcessingFault semantic registry entries.

Covers the Create(ProcessingFault) NACK flow (ADR-0080, ASK-07-001).
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
from vultron.core.models.events.fault import CreateProcessingFaultReceivedEvent
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor._instances import CreateProcessingFaultPattern

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.CREATE_PROCESSING_FAULT,
        pattern=CreateProcessingFaultPattern,
        event_class=CreateProcessingFaultReceivedEvent,
        use_case_class=CreateProcessingFaultReceivedUseCase,
        phrase="{actor} reported a processing fault",
        wire_activity_class=None,
        include_activity=True,
    ),
]
