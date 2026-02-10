"""Provides enumerations for vocabulary categories and types."""

from enum import StrEnum


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


# activity type is the union of intransitive and transitive activity types
as_ActivityType = merge_enums(
    "as_ActivityType", [as_IntransitiveActivityType, as_TransitiveActivityType]
)

as_AllObjectTypes = merge_enums(
    "as_AllObjectTypes", [as_ObjectType, as_ActorType, as_ActivityType]
)

if __name__ == "__main__":

    for types in [
        as_ObjectType,
        as_ActorType,
        as_TransitiveActivityType,
        as_IntransitiveActivityType,
        as_ActivityType,
        as_AllObjectTypes,
    ]:
        print(f"{types.__name__}:")
        for member in types:
            print(f"  {member.name} = {member.value}")
