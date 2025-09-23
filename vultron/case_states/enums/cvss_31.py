#!/usr/bin/env python

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from enum import IntEnum as Enum, auto


# todo: add enums for other CVSS classes
# AttackVector (AV)
# AttackComplexity (AC)
# PrivilegesRequired (PR)
# UserInteraction (UI)
# Scope (S)
# Confidentiality (C)
# Integrity (I)
# Availability (A)
# ReportConfidence (RC)
# ConfidentialityRequirement (CR)
# IntegrityRequirement (IR)
# AvailabilityRequirement (AR)
# ModifiedAttackVector (MAV)
# ModifiedAttackComplexity (MAC)
# ModifiedPrivilegesRequired (MPR)
# ModifiedUserInteraction (MUI)
# ModifiedScope (MS)
# ModifiedConfidentiality (MC)
# ModifiedIntegrity (MI)
# ModifiedAvailability (MA)

# todo: move the enum classes to a separate file


class ExploitCodeMaturity(Enum):
    """Exploit Code Maturity (E)"""

    CVSS_31_EXPLOIT_CODE_MATURITY_NOT_DEFINED = auto()
    CVSS_31_EXPLOIT_CODE_MATURITY_HIGH = auto()
    CVSS_31_EXPLOIT_CODE_MATURITY_FUNCTIONAL = auto()
    CVSS_31_EXPLOIT_CODE_MATURITY_PROOF_OF_CONCEPT = auto()
    CVSS_31_EXPLOIT_CODE_MATURITY_UNPROVEN = auto()

    # convenience aliases
    HIGH = CVSS_31_EXPLOIT_CODE_MATURITY_HIGH
    FUNCTIONAL = CVSS_31_EXPLOIT_CODE_MATURITY_FUNCTIONAL
    POC = CVSS_31_EXPLOIT_CODE_MATURITY_PROOF_OF_CONCEPT
    PROOF_OF_CONCEPT = CVSS_31_EXPLOIT_CODE_MATURITY_PROOF_OF_CONCEPT
    UNPROVEN = CVSS_31_EXPLOIT_CODE_MATURITY_UNPROVEN
    NOT_DEFINED = CVSS_31_EXPLOIT_CODE_MATURITY_NOT_DEFINED

    X = CVSS_31_EXPLOIT_CODE_MATURITY_NOT_DEFINED
    H = CVSS_31_EXPLOIT_CODE_MATURITY_HIGH
    F = CVSS_31_EXPLOIT_CODE_MATURITY_FUNCTIONAL
    P = CVSS_31_EXPLOIT_CODE_MATURITY_PROOF_OF_CONCEPT
    U = CVSS_31_EXPLOIT_CODE_MATURITY_UNPROVEN


CVSS_31_E = ExploitCodeMaturity


class RemediationLevel(Enum):
    """
    Remediation Level (RL)
    """

    CVSS_31_REMEDIATION_LEVEL_NOT_DEFINED = auto()
    CVSS_31_REMEDIATION_LEVEL_OFFICIAL_FIX = auto()
    CVSS_31_REMEDIATION_LEVEL_TEMPORARY_FIX = auto()
    CVSS_31_REMEDIATION_LEVEL_WORKAROUND = auto()
    CVSS_31_REMEDIATION_LEVEL_UNAVAILABLE = auto()

    # convenience aliases
    OFFICIAL_FIX = CVSS_31_REMEDIATION_LEVEL_OFFICIAL_FIX
    TEMPORARY_FIX = CVSS_31_REMEDIATION_LEVEL_TEMPORARY_FIX
    WORKAROUND = CVSS_31_REMEDIATION_LEVEL_WORKAROUND
    UNAVAILABLE = CVSS_31_REMEDIATION_LEVEL_UNAVAILABLE
    NOT_DEFINED = CVSS_31_REMEDIATION_LEVEL_NOT_DEFINED

    X = CVSS_31_REMEDIATION_LEVEL_NOT_DEFINED
    O = CVSS_31_REMEDIATION_LEVEL_OFFICIAL_FIX  # noqa: E741
    T = CVSS_31_REMEDIATION_LEVEL_TEMPORARY_FIX
    W = CVSS_31_REMEDIATION_LEVEL_WORKAROUND
    U = CVSS_31_REMEDIATION_LEVEL_UNAVAILABLE


CVSS_31_RL = RemediationLevel
