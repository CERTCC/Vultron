#!/usr/bin/env python
"""file: cvss_31_states
author: adh
created_at: 3/14/23 9:57 AM

This file contains the CVSS 3.1 vector enums.

"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

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
    O = CVSS_31_REMEDIATION_LEVEL_OFFICIAL_FIX
    T = CVSS_31_REMEDIATION_LEVEL_TEMPORARY_FIX
    W = CVSS_31_REMEDIATION_LEVEL_WORKAROUND
    U = CVSS_31_REMEDIATION_LEVEL_UNAVAILABLE


CVSS_31_RL = RemediationLevel
