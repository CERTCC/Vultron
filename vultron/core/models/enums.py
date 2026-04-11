"""Core domain enumeration definitions for the Vultron Protocol."""

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

from enum import StrEnum


class VultronObjectType(StrEnum):
    """Enumeration of Vultron-specific domain object types."""

    VULNERABILITY_CASE = "VulnerabilityCase"
    VULNERABILITY_REPORT = "VulnerabilityReport"
    VULNERABILITY_RECORD = "VulnerabilityRecord"
    CASE_REFERENCE = "CaseReference"
    EMBARGO_POLICY = "EmbargoPolicy"
    CASE_PARTICIPANT = "CaseParticipant"
    CASE_STATUS = "CaseStatus"
    PARTICIPANT_STATUS = "ParticipantStatus"
    CASE_LOG_ENTRY = "CaseLogEntry"
