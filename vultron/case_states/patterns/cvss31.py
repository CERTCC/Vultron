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
"""
Case State Patterns for CVSS 3.1
"""
from enum import Enum
from typing import List

from vultron.case_states.enums.cvss_31 import CVSS_31_E, CVSS_31_RL
from vultron.case_states.patterns.base import compile_patterns
from vultron.case_states.validations import (
    ensure_valid_state,
)

_CVSS_E_patterns = {
    ".....A": (CVSS_31_E.HIGH, CVSS_31_E.FUNCTIONAL),
    "....Xa": (CVSS_31_E.HIGH, CVSS_31_E.FUNCTIONAL, CVSS_31_E.POC),
    "....xa": (CVSS_31_E.UNPROVEN, CVSS_31_E.NOT_DEFINED),
}

CVSS_31_E_ = compile_patterns(_CVSS_E_patterns)

_CVSS_RL_patterns = {
    "Vf....": (
        CVSS_31_RL.NOT_DEFINED,
        CVSS_31_RL.UNAVAILABLE,
        CVSS_31_RL.WORKAROUND,
        CVSS_31_RL.TEMPORARY_FIX,
    ),
    "VF....": (CVSS_31_RL.OFFICIAL_FIX, CVSS_31_RL.TEMPORARY_FIX),
}

CVSS_31_RL_ = compile_patterns(_CVSS_RL_patterns)


@ensure_valid_state
def cvss_31_e(state: str) -> List[Enum]:
    """Given a Vultron Case State (vfdpxa...VFDPXA) return the CVSS 3.1 Expliotation information

    Args:
        state: Vultron Case State string

    Returns:
        List of CVSS 3.1 Exploitation information
    """
    information = []
    for pat, info in CVSS_31_E_.items():
        if pat.match(state):
            information.extend(info)
    return sorted(list(set(information)))


@ensure_valid_state
def cvss_31_rl(state: str) -> List[Enum]:
    """Given a Vultron Case State (vfdpxa...VFDPXA) return the CVSS 3.1 Remediation Level information

    Args:
        state: Vultron Case State string

    Returns:
        List of CVSS 3.1 Remediation Level information
    """
    information = []
    for pat, info in CVSS_31_RL_.items():
        if pat.match(state):
            information.extend(info)
    return sorted(list(set(information)))


@ensure_valid_state
def cvss_31(state: str) -> List[Enum]:
    """Given a Vultron Case State (vfdpxa...VFDPXA) return the CVSS 3.1 information

    Args:
        state: Vultron Case State string

    Returns:
        List of CVSS 3.1 information
    """
    _e = cvss_31_e(state)
    _rl = cvss_31_rl(state)
    combined = _e + _rl
    return sorted(list(set(combined)))
