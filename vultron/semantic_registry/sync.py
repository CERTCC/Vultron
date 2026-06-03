"""Case closure, sync and case-log semantic registry entries.

``CLOSE_CASE`` appears here because it follows the embargo entries in the
original dispatch order and precedes the case-log sync entries.
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
from vultron.core.models.events.case import CloseCaseReceivedEvent
from vultron.core.models.events.sync import (
    AnnounceLogEntryReceivedEvent,
    RejectLogEntryReceivedEvent,
)
from vultron.core.use_cases.received.case import CloseCaseReceivedUseCase
from vultron.core.use_cases.received.sync import (
    AnnounceLogEntryReceivedUseCase,
    RejectLogEntryReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor import (
    AnnounceLogEntryPattern,
    CloseCasePattern,
    RejectLogEntryPattern,
)
from vultron.wire.as2.vocab.activities.case import _RmCloseCaseActivity
from vultron.wire.as2.vocab.activities.sync import (
    _AnnounceLogEntryActivity,
    _RejectLogEntryActivity,
)

ENTRIES: list[SemanticEntry] = [
    # CLOSE_CASE precedes the sync entries in the original dispatch order
    # (after all embargo entries, before case-participant management).
    SemanticEntry(
        semantics=MessageSemantics.CLOSE_CASE,
        pattern=CloseCasePattern,
        event_class=CloseCaseReceivedEvent,
        use_case_class=CloseCaseReceivedUseCase,
        wire_activity_class=_RmCloseCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ANNOUNCE_CASE_LOG_ENTRY,
        pattern=AnnounceLogEntryPattern,
        event_class=AnnounceLogEntryReceivedEvent,
        use_case_class=AnnounceLogEntryReceivedUseCase,
        wire_activity_class=_AnnounceLogEntryActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_CASE_LOG_ENTRY,
        pattern=RejectLogEntryPattern,
        event_class=RejectLogEntryReceivedEvent,
        use_case_class=RejectLogEntryReceivedUseCase,
        wire_activity_class=_RejectLogEntryActivity,
    ),
]
