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

from vultron.core.behaviors.sender_entitlement import AddresseeSide
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
from vultron.enums.roles import CVDRole
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    Occasion,
    ProtocolShorthand,
)
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
        phrase="{actor} created a vulnerability report",
        wire_activity_class=_RmCreateReportActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a Reporter has written up a vulnerability and is about to"
                    " submit the report"
                ),
                anchor="create-report",
                addressee=AddresseeSide.OUTSIDE_CASE,
                heading="Create report",
                description=(
                    "Mints the vulnerability report object. It precedes the "
                    "Offer that submits the report."
                ),
                example="create_report",
                howto=HowToGuide.REPORT_VULNERABILITY,
                usual_senders=(CVDRole.REPORTER,),
            ),
        ),
        page=MessagePage.RM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.SUBMIT_REPORT,
        pattern=ReportSubmissionPattern,
        event_class=SubmitReportReceivedEvent,
        use_case_class=SubmitReportReceivedUseCase,
        phrase="{actor} submitted the report",
        wire_activity_class=_RmSubmitReportActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a Reporter submits a vulnerability report to a Vendor or "
                    "Coordinator"
                ),
                anchor="report-submission",
                addressee=AddresseeSide.OUTSIDE_CASE,
                description=(
                    "Offers the report to a new Participant. The Offer may "
                    "carry proposed embargo terms."
                ),
                example="submit_report",
                howto=HowToGuide.REPORT_VULNERABILITY,
                shorthand=ProtocolShorthand.RS,
                usual_senders=(CVDRole.REPORTER,),
            ),
        ),
        page=MessagePage.RM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACK_REPORT,
        pattern=AckReportPattern,
        event_class=AckReportReceivedEvent,
        use_case_class=AckReportReceivedUseCase,
        phrase="{actor} acknowledged the report",
        wire_activity_class=_RmReadReportActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="a report receiver has received a submitted report",
                anchor="report-acknowledgment",
                addressee=AddresseeSide.OUTSIDE_CASE,
                description=(
                    "Acknowledges receipt of the submitted report. Report "
                    "submission is not replicated through the case ledger, so "
                    "the acknowledgment is an explicit message."
                ),
                example="read_report",
                howto=HowToGuide.REPORT_VULNERABILITY,
                shorthand=ProtocolShorthand.RK,
                usual_senders=(
                    CVDRole.VENDOR,
                    CVDRole.COORDINATOR,
                ),
            ),
        ),
        page=MessagePage.RM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.VALIDATE_REPORT,
        pattern=ValidateReportPattern,
        event_class=ValidateReportReceivedEvent,
        use_case_class=ValidateReportReceivedUseCase,
        phrase="{actor} validated the report",
        wire_activity_class=_RmValidateReportActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="a report receiver judges the report valid",
                anchor="report-valid",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Validate report",
                description=(
                    "Designates the report as valid, moving the sender's RM "
                    "state to Valid."
                ),
                example="validate_report",
                howto=HowToGuide.REPORT_VULNERABILITY,
                shorthand=ProtocolShorthand.RV,
                usual_senders=(
                    CVDRole.VENDOR,
                    CVDRole.COORDINATOR,
                ),
            ),
        ),
        page=MessagePage.RM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVALIDATE_REPORT,
        pattern=InvalidateReportPattern,
        event_class=InvalidateReportReceivedEvent,
        use_case_class=InvalidateReportReceivedUseCase,
        phrase="{actor} invalidated the report",
        wire_activity_class=_RmInvalidateReportActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="a report receiver judges the report invalid",
                anchor="report-invalid",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Invalidate report",
                description=(
                    "Designates the report as invalid, moving the sender's RM "
                    "state to Invalid."
                ),
                example="invalidate_report",
                howto=HowToGuide.REPORT_VULNERABILITY,
                shorthand=ProtocolShorthand.RI,
                usual_senders=(
                    CVDRole.VENDOR,
                    CVDRole.COORDINATOR,
                ),
            ),
        ),
        page=MessagePage.RM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.CLOSE_REPORT,
        pattern=CloseReportPattern,
        event_class=CloseReportReceivedEvent,
        use_case_class=CloseReportReceivedUseCase,
        phrase="{actor} closed the report",
        wire_activity_class=_RmCloseReportActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="a report receiver closes a report no case holds",
                anchor="report-closed",
                addressee=AddresseeSide.OUTSIDE_CASE,
                heading="Close report",
                description=(
                    "Closes the report, moving the sender's RM state to "
                    "Closed. Once a case holds the report, its Case Owner "
                    "closes the case with Leave(VulnerabilityCase) instead, "
                    "and every receiver refuses a Close(Report) for it."
                ),
                example="close_report",
                howto=HowToGuide.REPORT_VULNERABILITY,
                shorthand=ProtocolShorthand.RC,
                usual_senders=(
                    CVDRole.VENDOR,
                    CVDRole.COORDINATOR,
                ),
            ),
        ),
        page=MessagePage.RM,
    ),
]
