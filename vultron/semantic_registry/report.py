"""Report-domain semantic registry entries."""

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
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
    SubmitReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.use_cases.received.report import (
    AckReportReceivedUseCase,
    CloseReportReceivedUseCase,
    CreateReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
    SubmitReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor import (
    AckReportPattern,
    CloseReportPattern,
    CreateReportPattern,
    InvalidateReportPattern,
    ReportSubmissionPattern,
    ValidateReportPattern,
)
from vultron.wire.as2.vocab.activities.report import (
    _RmCloseReportActivity,
    _RmCreateReportActivity,
    _RmInvalidateReportActivity,
    _RmReadReportActivity,
    _RmSubmitReportActivity,
    _RmValidateReportActivity,
)

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.CREATE_REPORT,
        pattern=CreateReportPattern,
        event_class=CreateReportReceivedEvent,
        use_case_class=CreateReportReceivedUseCase,
        wire_activity_class=_RmCreateReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.SUBMIT_REPORT,
        pattern=ReportSubmissionPattern,
        event_class=SubmitReportReceivedEvent,
        use_case_class=SubmitReportReceivedUseCase,
        wire_activity_class=_RmSubmitReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACK_REPORT,
        pattern=AckReportPattern,
        event_class=AckReportReceivedEvent,
        use_case_class=AckReportReceivedUseCase,
        wire_activity_class=_RmReadReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.VALIDATE_REPORT,
        pattern=ValidateReportPattern,
        event_class=ValidateReportReceivedEvent,
        use_case_class=ValidateReportReceivedUseCase,
        wire_activity_class=_RmValidateReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVALIDATE_REPORT,
        pattern=InvalidateReportPattern,
        event_class=InvalidateReportReceivedEvent,
        use_case_class=InvalidateReportReceivedUseCase,
        wire_activity_class=_RmInvalidateReportActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.CLOSE_REPORT,
        pattern=CloseReportPattern,
        event_class=CloseReportReceivedEvent,
        use_case_class=CloseReportReceivedUseCase,
        wire_activity_class=_RmCloseReportActivity,
        include_activity=True,
    ),
]
