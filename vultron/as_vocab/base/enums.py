"""Provides enumerations for vocabulary categories and types."""

from enum import StrEnum


class as_ObjectType(StrEnum):
    ACTIVITY = "Activity"
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
