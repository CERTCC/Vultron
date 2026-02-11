"""Enumeration definitions for the Vultron Protocol."""

from enum import auto, StrEnum


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


class OfferStatusEnum(StrEnum):
    """Enumeration of Offer Statuses"""

    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    TENTATIVELY_REJECTED = "TENTATIVELY_REJECTED"
    REJECTED = "REJECTED"


class VultronObjectType(StrEnum):
    """Enumeration of Vultron Object Types for Activity Streams."""

    VULNERABILITY_CASE = "VulnerabilityCase"
    VULNERABILITY_REPORT = "VulnerabilityReport"
    CASE_PARTICIPANT = "CaseParticipant"
    CASE_STATUS = "CaseStatus"
    PARTICIPANT_STATUS = "ParticipantStatus"


class as_ObjectType(StrEnum):
    # generics
    ACTIVITY = "Activity"
    ACTOR = "Actor"
    LINK = "Link"
    # specific types
    DOCUMENT = "Document"
    IMAGE = "Image"
    VIDEO = "Video"
    AUDIO = "Audio"
    PAGE = "Page"
    ARTICLE = "Article"
    NOTE = "Note"
    EVENT = "Event"
    PROFILE = "Profile"
    TOMBSTONE = "Tombstone"
    RELATIONSHIP = "Relationship"
    PLACE = "Place"


class as_ActorType(StrEnum):
    PERSON = "Person"
    GROUP = "Group"
    ORGANIZATION = "Organization"
    APPLICATION = "Application"
    SERVICE = "Service"


class as_IntransitiveActivityType(StrEnum):
    TRAVEL = "Travel"
    ARRIVE = "Arrive"
    QUESTION = "Question"


class as_TransitiveActivityType(StrEnum):
    LIKE = "Like"
    IGNORE = "Ignore"
    BLOCK = "Block"
    OFFER = "Offer"
    INVITE = "Invite"
    FLAG = "Flag"
    REMOVE = "Remove"
    UNDO = "Undo"
    CREATE = "Create"
    DELETE = "Delete"
    MOVE = "Move"
    ADD = "Add"
    JOIN = "Join"
    UPDATE = "Update"
    LISTEN = "Listen"
    LEAVE = "Leave"
    ANNOUNCE = "Announce"
    FOLLOW = "Follow"
    ACCEPT = "Accept"
    TENTATIVE_ACCEPT = "TentativeAccept"
    VIEW = "View"
    DISLIKE = "Dislike"
    REJECT = "Reject"
    TENTATIVE_REJECT = "TentativeReject"
    READ = "Read"


def merge_enums(name, enums: list[StrEnum]) -> StrEnum:
    """Merge multiple StrEnum classes into a single StrEnum."""

    values = {member.name: member.value for e in enums for member in e}
    # sort the values by name
    values = dict(sorted(values.items()))
    return StrEnum(name, values)


as_ActivityType = merge_enums(
    "as_ActivityType", [as_IntransitiveActivityType, as_TransitiveActivityType]
)
as_AllObjectTypes = merge_enums(
    "as_AllObjectTypes", [as_ObjectType, as_ActorType, as_ActivityType]
)
