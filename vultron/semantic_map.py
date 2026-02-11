"""
This module defines the mapping between MessageSemantics and ActivityPatterns
intended for use in the behavior dispatcher to determine the semantics of incoming activities
based on their structure and content.
It provides a function to find the matching semantics for a given activity.
"""

from vultron.activity_patterns import ActivityPattern
from vultron import activity_patterns as ap
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.enums import MessageSemantics

# The order of the patterns in this dictionary matters for matching,
# as the find_matching_semantics function will return the first match it finds.
SEMANTICS_ACTIVITY_PATTERNS: dict[MessageSemantics, ActivityPattern] = {
    MessageSemantics.CREATE_REPORT: ap.CreateReport,
    MessageSemantics.SUBMIT_REPORT: ap.ReportSubmission,
    MessageSemantics.ACK_REPORT: ap.AckReport,
    MessageSemantics.VALIDATE_REPORT: ap.ValidateReport,
    MessageSemantics.INVALIDATE_REPORT: ap.InvalidateReport,
    MessageSemantics.CLOSE_REPORT: ap.CloseReport,
    MessageSemantics.CREATE_CASE: ap.CreateCase,
    MessageSemantics.ADD_REPORT_TO_CASE: ap.AddReportToCase,
    MessageSemantics.SUGGEST_ACTOR_TO_CASE: ap.SuggestActorToCase,
    MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE: ap.AcceptSuggestActorToCase,
    MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE: ap.RejectSuggestActorToCase,
    MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER: ap.OfferCaseOwnershipTransfer,
    MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER: ap.AcceptCaseOwnershipTransfer,
    MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER: ap.RejectCaseOwnershipTransfer,
    MessageSemantics.INVITE_ACTOR_TO_CASE: ap.InviteActorToCase,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: ap.AcceptInviteActorToCase,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: ap.RejectInviteActorToCase,
    MessageSemantics.CREATE_EMBARGO_EVENT: ap.CreateEmbargoEvent,
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE: ap.AddEmbargoEventToCase,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: ap.RemoveEmbargoEventFromCase,
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE: ap.AnnounceEmbargoEventToCase,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: ap.InviteToEmbargoOnCase,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: ap.AcceptInviteToEmbargoOnCase,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: ap.RejectInviteToEmbargoOnCase,
    MessageSemantics.CLOSE_CASE: ap.CloseCase,
    MessageSemantics.CREATE_CASE_PARTICIPANT: ap.CreateCaseParticipant,
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE: ap.AddCaseParticipantToCase,
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE: ap.RemoveCaseParticipantFromCase,
    MessageSemantics.CREATE_NOTE: ap.CreateNote,
    MessageSemantics.ADD_NOTE_TO_CASE: ap.AddNoteToCase,
    MessageSemantics.REMOVE_NOTE_FROM_CASE: ap.RemoveNoteFromCase,
    MessageSemantics.CREATE_CASE_STATUS: ap.CreateCaseStatus,
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: ap.AddCaseStatusToCase,
    MessageSemantics.CREATE_PARTICIPANT_STATUS: ap.CreateParticipantStatus,
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: ap.AddParticipantStatusToParticipant,
}

# TODO test that there are no overlapping patterns in SEMANTICS_ACTIVITY_PATTERNS
#  that could cause ambiguity in matching


def find_matching_semantics(
    activity: as_Activity,
) -> MessageSemantics:
    """
    Finds the matching semantics for a given activity, if any.

    Note that this returns the first matching semantics it finds,
    so the order of the patterns in SEMANTICS_ACTIVITY_PATTERNS may affect
    the results if there are overlapping patterns.

    Args:
        activity: ap.The activity to find semantics for.
    Returns:
        The matching MessageSemantics StrEnum value,
        or MessageSemantics.UNKNOWN if no match is found.
    """
    # Implementation note:
    # Looping through all semantics in order is not optimized for performance,
    # but it is good enough to start with as long as
    # - the pattern count is relatively small and
    # - the patterns are not too complex.
    for semantics, pattern in SEMANTICS_ACTIVITY_PATTERNS.items():
        if pattern.match(activity):
            return semantics
    return MessageSemantics.UNKNOWN


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
