"""Case-lifecycle semantic registry entries.

Covers case creation, state transitions, and report attachment.
Case closure is in ``sync`` (follows embargo entries in dispatch order).
Case participant management is in ``case_participant``.
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
from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CreateCaseReceivedEvent,
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
    UpdateCaseReceivedEvent,
)
from vultron.core.use_cases.received.case import (
    AddReportToCaseReceivedUseCase,
    CreateCaseReceivedUseCase,
    DeferCaseReceivedUseCase,
    EngageCaseReceivedUseCase,
    UpdateCaseReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor import (
    AddReportToCaseActivityPattern,
    CreateCaseActivityPattern,
    DeferCasePattern,
    EngageCasePattern,
    UpdateCaseActivityPattern,
)
from vultron.wire.as2.vocab.activities.case import (
    _AddReportToCaseActivity,
    _CreateCaseActivity,
    _RmDeferCaseActivity,
    _RmEngageCaseActivity,
    _UpdateCaseActivity,
)

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.CREATE_CASE,
        pattern=CreateCaseActivityPattern,
        event_class=CreateCaseReceivedEvent,
        use_case_class=CreateCaseReceivedUseCase,
        wire_activity_class=_CreateCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.UPDATE_CASE,
        pattern=UpdateCaseActivityPattern,
        event_class=UpdateCaseReceivedEvent,
        use_case_class=UpdateCaseReceivedUseCase,
        wire_activity_class=_UpdateCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ENGAGE_CASE,
        pattern=EngageCasePattern,
        event_class=EngageCaseReceivedEvent,
        use_case_class=EngageCaseReceivedUseCase,
        wire_activity_class=_RmEngageCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.DEFER_CASE,
        pattern=DeferCasePattern,
        event_class=DeferCaseReceivedEvent,
        use_case_class=DeferCaseReceivedUseCase,
        wire_activity_class=_RmDeferCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_REPORT_TO_CASE,
        pattern=AddReportToCaseActivityPattern,
        event_class=AddReportToCaseReceivedEvent,
        use_case_class=AddReportToCaseReceivedUseCase,
        wire_activity_class=_AddReportToCaseActivity,
    ),
]
