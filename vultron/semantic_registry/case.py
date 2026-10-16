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

from vultron.core.behaviors.sender_entitlement import AddresseeSide
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CreateCaseReceivedEvent,
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
)
from vultron.core.models.events.case_proposal import (
    AcceptCaseProposalReceivedEvent,
    CreateCaseProposalReceivedEvent,
    RejectCaseProposalReceivedEvent,
)
from vultron.core.use_cases.received.case import (
    AddReportToCaseReceivedUseCase,
    CreateCaseReceivedUseCase,
    DeferCaseReceivedUseCase,
    EngageCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case_proposal import (
    AcceptCaseProposalReceivedUseCase,
    CreateCaseProposalReceivedUseCase,
    RejectCaseProposalReceivedUseCase,
)
from vultron.enums.object_types import VultronObjectType as VOtype
from vultron.enums.roles import CVDRole
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    Occasion,
    ProtocolShorthand,
)
from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype
from vultron.wire.as2.extractor import (
    AcceptCaseProposalPattern,
    ActivityPattern,
    AddReportToCaseActivityPattern,
    CreateCaseActivityPattern,
    CreateCaseProposalPattern,
    DeferCasePattern,
    EngageCasePattern,
    RejectCaseProposalPattern,
)
from vultron.wire.as2.vocab.activities.case import (
    _AddReportToCaseActivity,
    _CreateCaseActivity,
    _RmDeferCaseActivity,
    _RmEngageCaseActivity,
)

ENTRIES: list[SemanticEntry] = [
    # CaseProposal entries (CP-03-001 through CP-03-004): must appear before
    # any more-general Create/Accept/Reject patterns that share the same
    # activity_ type (SE-03-002).
    SemanticEntry(
        semantics=MessageSemantics.CREATE_CASE_PROPOSAL,
        pattern=CreateCaseProposalPattern,
        event_class=CreateCaseProposalReceivedEvent,
        use_case_class=CreateCaseProposalReceivedUseCase,
        phrase="{actor} proposed a new case",
        wire_activity_class=None,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a report receiver asks a Case Actor Service to open a "
                    "case for a report"
                ),
                anchor="create-case-proposal",
                addressee=AddresseeSide.OUTSIDE_CASE,
                heading="Create case proposal",
                description=(
                    "Submits a case proposal for the attached report to the "
                    "service's inbox. No case exists yet."
                ),
                example="create_case_proposal",
                usual_senders=(
                    CVDRole.VENDOR,
                    CVDRole.COORDINATOR,
                ),
            ),
        ),
        page=MessagePage.CASE_PROPOSAL,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_CASE_PROPOSAL,
        pattern=AcceptCaseProposalPattern,
        event_class=AcceptCaseProposalReceivedEvent,
        use_case_class=AcceptCaseProposalReceivedUseCase,
        phrase="{actor} accepted the case proposal",
        wire_activity_class=None,
        include_activity=True,
        occasions=(
            Occasion(
                when="a Case Actor Service agrees to open the proposed case",
                anchor="accept-case-proposal",
                addressee=AddresseeSide.OUTSIDE_CASE,
                heading="Accept case proposal",
                description=(
                    "Accepts the case proposal and tells the proposing actor "
                    "that a case will be opened for its report."
                ),
                example="accept_case_proposal",
            ),
        ),
        page=MessagePage.CASE_PROPOSAL,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_CASE_PROPOSAL,
        pattern=RejectCaseProposalPattern,
        event_class=RejectCaseProposalReceivedEvent,
        use_case_class=RejectCaseProposalReceivedUseCase,
        phrase="{actor} declined the case proposal",
        wire_activity_class=None,
        include_activity=True,
        occasions=(
            Occasion(
                when="a Case Actor Service declines to open the proposed case",
                anchor="reject-case-proposal",
                addressee=AddresseeSide.OUTSIDE_CASE,
                heading="Reject case proposal",
                description="Rejects the case proposal. No case is opened.",
                example="reject_case_proposal",
            ),
        ),
        page=MessagePage.CASE_PROPOSAL,
    ),
    SemanticEntry(
        semantics=MessageSemantics.CREATE_CASE,
        pattern=CreateCaseActivityPattern,
        event_class=CreateCaseReceivedEvent,
        use_case_class=CreateCaseReceivedUseCase,
        phrase="{actor} created the case",
        wire_activity_class=_CreateCaseActivity,
        include_activity=True,
        # The bootstrap answers the request that asked for the case: a
        # vendor's CaseProposal, or a reporter's report Offer (CBT-01-005).
        answers=(
            VOtype.CASE_PROPOSAL,
            ActivityPattern(
                activity_=TAtype.OFFER, object_=VOtype.VULNERABILITY_REPORT
            ),
        ),
        occasions=(
            Occasion(
                when=(
                    "the Case Manager has opened a case for a submitted report"
                ),
                anchor="create-case",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Create case",
                description=(
                    "Mints the vulnerability case, seats its initial "
                    "participants and links the report."
                ),
                example="create_case",
                howto=HowToGuide.INITIALIZE_CASE,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ENGAGE_CASE,
        pattern=EngageCasePattern,
        event_class=EngageCaseReceivedEvent,
        use_case_class=EngageCaseReceivedUseCase,
        phrase="{actor} engaged the case",
        wire_activity_class=_RmEngageCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="a Participant accepts the case for further action",
                anchor="report-accepted",
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Joins the case, moving the sender's RM state to Accepted."
                    " Engaging is a case-participation decision, so the verb "
                    "names the case rather than the report."
                ),
                example="engage_case",
                howto=HowToGuide.MANAGE_CASE,
                shorthand=ProtocolShorthand.RA,
            ),
        ),
        page=MessagePage.RM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.DEFER_CASE,
        pattern=DeferCasePattern,
        event_class=DeferCaseReceivedEvent,
        use_case_class=DeferCaseReceivedUseCase,
        phrase="{actor} deferred the case",
        wire_activity_class=_RmDeferCaseActivity,
        # Matches its ENGAGE_CASE sibling above.  Without it the event carries
        # no activity, so the ledger snapshot is dumped from the VultronEvent —
        # which has neither `type` nor `published` — and the commit aborts at
        # the canonical-signature check.  A received Ignore(VulnerabilityCase)
        # therefore never reached the ledger, and when the receiving actor held
        # CASE_MANAGER the abort also skipped the RM→DEFERRED transition.
        include_activity=True,
        occasions=(
            Occasion(
                when="a Participant defers further action on the case",
                anchor="report-deferred",
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Ignores the case, moving the sender's RM state to "
                    "Deferred. Deferring is a case-participation decision, so "
                    "the verb names the case rather than the report."
                ),
                example="defer_case",
                howto=HowToGuide.MANAGE_CASE,
                shorthand=ProtocolShorthand.RD,
            ),
        ),
        page=MessagePage.RM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_REPORT_TO_CASE,
        pattern=AddReportToCaseActivityPattern,
        event_class=AddReportToCaseReceivedEvent,
        use_case_class=AddReportToCaseReceivedUseCase,
        phrase="{actor} added the report to the case",
        wire_activity_class=_AddReportToCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Owner links a further report to an existing case"
                ),
                anchor="add-report-to-case",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Add report to case",
                description=(
                    "Adds a vulnerability report to the case named by the "
                    "target."
                ),
                example="add_report_to_case",
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
]
