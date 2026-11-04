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


"""Convert between CS state strings and the CS enums."""

from enum import StrEnum

from vultron.core.case_states.validations import ensure_valid_state
from vultron.core.states.cs.dimensions import (
    AttackObservation,
    ExploitPublication,
    FixDeployment,
    FixReadiness,
    PublicAwareness,
    VendorAwareness,
)
from vultron.core.states.cs.states import (
    CS,
    CS_d,
    CS_pxa,
    CS_vf,
)


def _last3(s):
    return s[-3:]


def _first3(s):
    return s[:3]


@ensure_valid_state
def vfd(state):
    vf, d, _pxa = state_string_to_enums(state)
    return (vf, d)


@ensure_valid_state
def pxa(state):
    _vf, _d, pxa = state_string_to_enums(state)
    value = pxa.value
    return value


@ensure_valid_state
def state_string_to_enums(s: str) -> tuple[CS_vf, CS_d, CS_pxa]:
    """
    Convert a state string to a tuple of enums that define the state `(CS_vf, CS_d, CS_pxa)`

    Args:
        s: the state string

    Returns:
        a tuple of enums

    """
    s1, s2, s3 = s[:2], s[2:3], s[3:]
    vf = CS_vf[s1]
    d = CS_d[s2]
    pxa = CS_pxa[s3]
    return (vf, d, pxa)


@ensure_valid_state
def state_string_to_enum2(
    s: str,
) -> tuple[StrEnum, ...]:
    """
    Convert a state string to a list of enums that define the state

    Example:
        ```python
        state_string_to_enum2('vfdpxa')
        ```
        returns
        ```python
        ( VendorAwareness.VENDOR_UNAWARE,
          FixReadiness.FIX_NOT_READY,
          FixDeployment.FIX_NOT_DEPLOYED,
          PublicAwareness.PUBLIC_UNAWARE,
          ExploitPublication.NO_PUBLIC_EXPLOIT,
          AttackObservation.NO_ATTACKS_OBSERVED)
        ```

    Args:
        s: the state string

    Returns:
        a list of Enums
    """
    enums = [
        VendorAwareness,
        FixReadiness,
        FixDeployment,
        PublicAwareness,
        ExploitPublication,
        AttackObservation,
    ]

    resolved_enums = []
    for value, enum in zip(s, enums, strict=False):
        resolved_enums.append(enum[value])

    return tuple(resolved_enums)


all_states = list(CS)
