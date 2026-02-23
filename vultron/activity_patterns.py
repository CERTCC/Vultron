"""
Defines patterns of Activity Streams Activity objects that have specific semantic meaning
in the context of the Vultron protocol. Also provides an ActivityPattern class to represent
and match these patterns.
"""

from typing import Optional, Union

from pydantic import BaseModel

from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.enums import (
    VultronObjectType as VOtype,
    as_IntransitiveActivityType as IAtype,
    as_ObjectType as AOtype,
    as_TransitiveActivityType as TAtype,
)


class ActivityPattern(BaseModel):
    """
    Represents a pattern to match against an activity for behavior dispatching.
    Supports nested patterns for wrapped objects.
    """

    description: Optional[str] = None
    activity_: TAtype | IAtype

    # Top-level object info (for leaf nodes)
    to_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    object_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    target_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    context_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    in_reply_to_: Optional["ActivityPattern"] = None

    def match(self, activity: as_Activity) -> bool:
        """Checks if the given activity matches this pattern."""
        if self.activity_ != activity.as_type:
            return False

        def match_field(pattern_field, activity_field) -> bool:
            """Helper to match a single field, supporting nested patterns."""
            if pattern_field is None:
                return True
            # If activity_field is a string (URI/ID reference), we can't match on type
            # In this case, we conservatively return True (can't determine match)
            if isinstance(activity_field, str):
                return True
            if isinstance(pattern_field, ActivityPattern):
                return pattern_field.match(activity_field)
            else:
                # Otherwise check if types match
                return pattern_field == getattr(
                    activity_field, "as_type", None
                )

        if not match_field(self.object_, getattr(activity, "as_object", None)):
            return False
        if not match_field(self.target_, getattr(activity, "target", None)):
            return False
        if not match_field(self.context_, getattr(activity, "context", None)):
            return False
        if not match_field(self.to_, getattr(activity, "to", None)):
            return False
        if not match_field(
            self.in_reply_to_, getattr(activity, "in_reply_to", None)
        ):
            return False

        return True


CreateEmbargoEvent = ActivityPattern(
    description="Create an embargo event. This is the initial step in the embargo management process, where a coordinator creates an embargo event to manage the embargo on a vulnerability case.",
    activity_=TAtype.CREATE,
    object_=AOtype.EVENT,
    context_=VOtype.VULNERABILITY_CASE,
)
AddEmbargoEventToCase = ActivityPattern(
    description="Add an embargo event to a vulnerability case. This is typically observed as an ADD activity where the object is an EVENT and the target is a VULNERABILITY_CASE.",
    activity_=TAtype.ADD,
    object_=AOtype.EVENT,
    target_=VOtype.VULNERABILITY_CASE,
)
RemoveEmbargoEventFromCase = ActivityPattern(
    description="Remove an embargo event from a vulnerability case. This is typically observed as a REMOVE activity where the object is an EVENT. The origin field of the activity contains the VulnerabilityCase from which the embargo is removed.",
    activity_=TAtype.REMOVE,
    object_=AOtype.EVENT,
)
AnnounceEmbargoEventToCase = ActivityPattern(
    description="Announce an embargo event to a vulnerability case. This is typically observed as an ANNOUNCE activity where the object is an EVENT and the context is a VULNERABILITY_CASE.",
    activity_=TAtype.ANNOUNCE,
    object_=AOtype.EVENT,
    context_=VOtype.VULNERABILITY_CASE,
)
InviteToEmbargoOnCase = ActivityPattern(
    description="Propose an embargo on a vulnerability case. "
    "This is observed as an INVITE activity where the object is an EmbargoEvent "
    "and the context is the VulnerabilityCase. Corresponds to EmProposeEmbargo.",
    activity_=TAtype.INVITE,
    object_=AOtype.EVENT,
    context_=VOtype.VULNERABILITY_CASE,
)
AcceptInviteToEmbargoOnCase = ActivityPattern(
    description="Accept an invitation to an embargo on a vulnerability case.",
    activity_=TAtype.ACCEPT,
    object_=InviteToEmbargoOnCase,
)
RejectInviteToEmbargoOnCase = ActivityPattern(
    description="Reject an invitation to an embargo on a vulnerability case.",
    activity_=TAtype.REJECT,
    object_=InviteToEmbargoOnCase,
)
CreateReport = ActivityPattern(
    description="Create a vulnerability report. This is the initial step in the vulnerability disclosure process, where a finder creates a report to disclose a vulnerability."
    " It may not always be observed directly, as it could be implicit in the OFFER of the report.",
    activity_=TAtype.CREATE,
    object_=VOtype.VULNERABILITY_REPORT,
)
ReportSubmission = ActivityPattern(
    description="Submit a vulnerability report for validation. This is typically observed as an OFFER of a VULNERABILITY_REPORT, which represents the submission of the report to a coordinator or vendor for validation.",
    activity_=TAtype.OFFER,
    object_=VOtype.VULNERABILITY_REPORT,
)
AckReport = ActivityPattern(activity_=TAtype.READ, object_=ReportSubmission)
ValidateReport = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=ReportSubmission
)
InvalidateReport = ActivityPattern(
    activity_=TAtype.TENTATIVE_REJECT, object_=ReportSubmission
)
CloseReport = ActivityPattern(
    activity_=TAtype.REJECT, object_=ReportSubmission
)
CreateCase = ActivityPattern(
    activity_=TAtype.CREATE, object_=VOtype.VULNERABILITY_CASE
)
EngageCase = ActivityPattern(
    description="Actor engages (joins) a VulnerabilityCase, transitioning their RM state to ACCEPTED.",
    activity_=TAtype.JOIN,
    object_=VOtype.VULNERABILITY_CASE,
)
DeferCase = ActivityPattern(
    description="Actor defers (ignores) a VulnerabilityCase, transitioning their RM state to DEFERRED.",
    activity_=TAtype.IGNORE,
    object_=VOtype.VULNERABILITY_CASE,
)
AddReportToCase = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.VULNERABILITY_REPORT,
    target_=VOtype.VULNERABILITY_CASE,
)
SuggestActorToCase = ActivityPattern(
    activity_=TAtype.OFFER,
    object_=AOtype.ACTOR,
    target_=VOtype.VULNERABILITY_CASE,
)
AcceptSuggestActorToCase = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=SuggestActorToCase
)
RejectSuggestActorToCase = ActivityPattern(
    activity_=TAtype.REJECT, object_=SuggestActorToCase
)
OfferCaseOwnershipTransfer = ActivityPattern(
    activity_=TAtype.OFFER, object_=VOtype.VULNERABILITY_CASE
)
AcceptCaseOwnershipTransfer = ActivityPattern(
    activity_=TAtype.ACCEPT, object_=OfferCaseOwnershipTransfer
)
RejectCaseOwnershipTransfer = ActivityPattern(
    activity_=TAtype.REJECT, object_=OfferCaseOwnershipTransfer
)
InviteActorToCase = ActivityPattern(
    activity_=TAtype.INVITE,
    target_=VOtype.VULNERABILITY_CASE,
)
AcceptInviteActorToCase = ActivityPattern(
    activity_=TAtype.ACCEPT,
    object_=InviteActorToCase,
)
RejectInviteActorToCase = ActivityPattern(
    activity_=TAtype.REJECT,
    object_=InviteActorToCase,
)
CloseCase = ActivityPattern(
    activity_=TAtype.LEAVE, object_=VOtype.VULNERABILITY_CASE
)
CreateNote = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=AOtype.NOTE,
)
AddNoteToCase = ActivityPattern(
    activity_=TAtype.ADD,
    object_=AOtype.NOTE,
    target_=VOtype.VULNERABILITY_CASE,
)
RemoveNoteFromCase = ActivityPattern(
    activity_=TAtype.REMOVE,
    object_=AOtype.NOTE,
    target_=VOtype.VULNERABILITY_CASE,
)
CreateCaseParticipant = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=VOtype.CASE_PARTICIPANT,
    context_=VOtype.VULNERABILITY_CASE,
)
AddCaseParticipantToCase = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.CASE_PARTICIPANT,
    target_=VOtype.VULNERABILITY_CASE,
)
RemoveCaseParticipantFromCase = ActivityPattern(
    activity_=TAtype.REMOVE,
    object_=VOtype.CASE_PARTICIPANT,
    target_=VOtype.VULNERABILITY_CASE,
)
CreateCaseStatus = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=VOtype.CASE_STATUS,
    context_=VOtype.VULNERABILITY_CASE,
)
AddCaseStatusToCase = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.CASE_STATUS,
    target_=VOtype.VULNERABILITY_CASE,
)
CreateParticipantStatus = ActivityPattern(
    activity_=TAtype.CREATE,
    object_=VOtype.PARTICIPANT_STATUS,
    context_=VOtype.VULNERABILITY_CASE,
)
AddParticipantStatusToParticipant = ActivityPattern(
    activity_=TAtype.ADD,
    object_=VOtype.PARTICIPANT_STATUS,
    target_=VOtype.CASE_PARTICIPANT,
    context_=VOtype.VULNERABILITY_CASE,
)
