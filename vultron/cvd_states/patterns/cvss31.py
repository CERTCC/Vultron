#!/usr/bin/env python
"""file: cvss
author: adh
created_at: 3/13/23 2:59 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from enum import Enum
from typing import List

from vultron.cvd_states.enums.cvss_31 import CVSS_31_E, CVSS_31_RL
from vultron.cvd_states.patterns.base import compile_patterns
from vultron.cvd_states.validations import (
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
