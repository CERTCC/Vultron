"""Enumeration definitions for the Vultron Protocol."""

from enum import StrEnum

# MessageSemantics lives in the domain layer; re-exported here for compatibility.
from vultron.core.models.events import MessageSemantics

__all__ = ["MessageSemantics"]


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
    VULNERABILITY_RECORD = "VulnerabilityRecord"
    CASE_REFERENCE = "CaseReference"
    EMBARGO_POLICY = "EmbargoPolicy"
    CASE_PARTICIPANT = "CaseParticipant"
    CASE_STATUS = "CaseStatus"
    PARTICIPANT_STATUS = "ParticipantStatus"
