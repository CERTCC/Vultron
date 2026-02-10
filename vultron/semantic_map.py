from enum import StrEnum, auto
from typing import Optional, Union

from pydantic import BaseModel

from vultron.as_vocab.base.enums import (
    as_IntransitiveActivityType as IAtype,
    as_ObjectType as AOtype,
    as_TransitiveActivityType as TAtype,
)
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.enums import VultronObjectType as VOtype


class MessageSemantics(StrEnum):
    """Defines high-level semantics for certain activity patterns that may be relevant for behavior dispatching."""

    CREATE_REPORT = auto()
    SUBMIT_REPORT = auto()
    VALIDATE_REPORT = auto()
    INVALIDATE_REPORT = auto()
    ACK_REPORT = auto()
    CLOSE_REPORT = auto()

    CREATE_CASE = auto()
    ADD_REPORT_TO_CASE = auto()

    SUGGEST_ACTOR_TO_CASE = auto()
    ACCEPT_SUGGEST_ACTOR_TO_CASE = auto()
    REJECT_SUGGEST_ACTOR_TO_CASE = auto()
    OFFER_CASE_OWNERSHIP_TRANSFER = auto()
    ACCEPT_CASE_OWNERSHIP_TRANSFER = auto()
    REJECT_CASE_OWNERSHIP_TRANSFER = auto()

    INVITE_ACTOR_TO_CASE = auto()
    ACCEPT_INVITE_ACTOR_TO_CASE = auto()
    REJECT_INVITE_ACTOR_TO_CASE = auto()

    CREATE_EMBARGO_EVENT = auto()
    ADD_EMBARGO_EVENT_TO_CASE = auto()
    REMOVE_EMBARGO_EVENT_FROM_CASE = auto()
    ANNOUNCE_EMBARGO_EVENT_TO_CASE = auto()
    INVITE_TO_EMBARGO_ON_CASE = auto()
    ACCEPT_INVITE_TO_EMBARGO_ON_CASE = auto()
    REJECT_INVITE_TO_EMBARGO_ON_CASE = auto()

    CLOSE_CASE = auto()

    CREATE_CASE_PARTICIPANT = auto()
    ADD_CASE_PARTICIPANT_TO_CASE = auto()
    REMOVE_CASE_PARTICIPANT_FROM_CASE = auto()

    CREATE_NOTE = auto()
    ADD_NOTE_TO_CASE = auto()
    REMOVE_NOTE_FROM_CASE = auto()

    CREATE_CASE_STATUS = auto()
    ADD_CASE_STATUS_TO_CASE = auto()

    CREATE_PARTICIPANT_STATUS = auto()
    ADD_PARTICIPANT_STATUS_TO_PARTICIPANT = auto()


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
            if pattern_field is None:
                return True
            if isinstance(pattern_field, ActivityPattern):
                return pattern_field.match(activity_field)
            else:
                return pattern_field == activity_field.as_type

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
    description="Remove an embargo event from a vulnerability case. This is typically observed as a REMOVE activity where the object is an EVENT and the target is a VULNERABILITY_CASE.",
    activity_=TAtype.REMOVE,
    object_=AOtype.EVENT,
    target_=VOtype.VULNERABILITY_CASE,
)
AnnounceEmbargoEventToCase = ActivityPattern(
    description="Announce an embargo event to a vulnerability case. This is typically observed as an ANNOUNCE activity where the object is an EVENT and the target is a VULNERABILITY_CASE.",
    activity_=TAtype.ANNOUNCE,
    object_=AOtype.EVENT,
    target_=VOtype.VULNERABILITY_CASE,
)
InviteToEmbargoOnCase = ActivityPattern(
    description="Invite an actor to an embargo on a vulnerability case. "
    "If accepted, this should precede invitation to the case itself.",
    activity_=TAtype.INVITE,
    object_=AOtype.ACTOR,
    target_=AOtype.EVENT,
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
    object_=AOtype.ACTOR,
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
LOOKUP_SEMANTICS: dict[MessageSemantics, ActivityPattern] = {
    MessageSemantics.CREATE_REPORT: CreateReport,
    MessageSemantics.SUBMIT_REPORT: ReportSubmission,
    MessageSemantics.VALIDATE_REPORT: ValidateReport,
    MessageSemantics.INVALIDATE_REPORT: InvalidateReport,
    MessageSemantics.CLOSE_REPORT: CloseReport,
    MessageSemantics.CREATE_CASE: CreateCase,
    MessageSemantics.ADD_REPORT_TO_CASE: AddReportToCase,
    MessageSemantics.SUGGEST_ACTOR_TO_CASE: SuggestActorToCase,
    MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE: AcceptSuggestActorToCase,
    MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE: RejectSuggestActorToCase,
    MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER: OfferCaseOwnershipTransfer,
    MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER: AcceptCaseOwnershipTransfer,
    MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER: RejectCaseOwnershipTransfer,
    MessageSemantics.INVITE_ACTOR_TO_CASE: InviteActorToCase,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: AcceptInviteActorToCase,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: RejectInviteActorToCase,
    MessageSemantics.CREATE_EMBARGO_EVENT: CreateEmbargoEvent,
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE: AddEmbargoEventToCase,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: RemoveEmbargoEventFromCase,
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE: AnnounceEmbargoEventToCase,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: InviteToEmbargoOnCase,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: AcceptInviteToEmbargoOnCase,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: RejectInviteToEmbargoOnCase,
    MessageSemantics.CLOSE_CASE: CloseCase,
    MessageSemantics.CREATE_CASE_PARTICIPANT: CreateCaseParticipant,
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE: AddCaseParticipantToCase,
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE: RemoveCaseParticipantFromCase,
    MessageSemantics.CREATE_NOTE: CreateNote,
    MessageSemantics.ADD_NOTE_TO_CASE: AddNoteToCase,
    MessageSemantics.REMOVE_NOTE_FROM_CASE: RemoveNoteFromCase,
    MessageSemantics.CREATE_CASE_STATUS: CreateCaseStatus,
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: AddCaseStatusToCase,
    MessageSemantics.CREATE_PARTICIPANT_STATUS: CreateParticipantStatus,
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: AddParticipantStatusToParticipant,
}


def find_matching_semantics(
    activity: as_Activity,
) -> Optional[MessageSemantics]:
    """Finds the matching semantics for a given activity, if any."""
    for semantics, pattern in LOOKUP_SEMANTICS.items():
        if pattern.match(activity):
            return semantics
    return None


if __name__ == "__main__":
    from vultron.scripts import vocab_examples

    examples = [
        vocab_examples.create_report(),
        vocab_examples.submit_report(),
        vocab_examples.validate_report(verbose=True),
        vocab_examples.invalidate_report(verbose=True),
        vocab_examples.close_report(verbose=True),
    ]

    for activity in examples:
        try:
            semantics = find_matching_semantics(activity)
        except Exception as e:
            print(f"Error finding semantics for activity: {e}")
            print(
                f"Activity: {activity.model_dump_json(indent=2,exclude_none=True)}"
            )
            continue
        print(f"## {semantics}")
        print(
            f"Activity: {activity.model_dump_json(indent=2,exclude_none=True)}"
        )
