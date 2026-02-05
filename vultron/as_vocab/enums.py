"""Provides enumerations for Vultron ActivityStreams Vocabulary categories and types."""

from enum import StrEnum


class VultronObjectType(StrEnum):
    VULNERABILITY_CASE = "VulnerabilityCase"
    VULNERABILITY_REPORT = "VulnerabilityReport"
    CASE_PARTICIPANT = "CaseParticipant"
    CASE_STATUS = "CaseStatus"
    PARTICIPANT_STATUS = "ParticipantStatus"
