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
    PxaState,
)
from vultron.errors import StateValidationError


def cs_state(s: object) -> CS:
    """Return the ``CS`` member a state string names.

    The 32 members of ``CS`` are the valid compound states (CSB-17-001), so a
    string names a valid state exactly when it is one of their names; nothing
    else, a pattern with wildcards included, is a state.

    Args:
        s: the state string, such as ``"VFdpxa"``

    Returns:
        the ``CS`` member named *s*

    Raises:
        StateValidationError: if *s* is not the name of a ``CS`` member
    """
    if isinstance(s, str) and s in CS.__members__:
        return CS[s]
    raise StateValidationError(f"Invalid state [{s}]")


def _last3(s):
    return s[-3:]


def _first3(s):
    return s[:3]


def vfd(state: str) -> tuple[CS_vf, CS_d]:
    """Return the ``(CS_vf, CS_d)`` parts of the state *state* names.

    Raises:
        StateValidationError: if *state* does not name a valid CS state
    """
    vf, d, _pxa = state_string_to_enums(state)
    return (vf, d)


def pxa(state: str) -> PxaState:
    """Return the ``PxaState`` of the state *state* names.

    Raises:
        StateValidationError: if *state* does not name a valid CS state
    """
    _vf, _d, pxa = state_string_to_enums(state)
    value: PxaState = pxa.value
    return value


def state_string_to_enums(s: str) -> tuple[CS_vf, CS_d, CS_pxa]:
    """
    Convert a state string to a tuple of enums that define the state `(CS_vf, CS_d, CS_pxa)`

    Args:
        s: the state string

    Returns:
        a tuple of enums

    Raises:
        StateValidationError: if *s* does not name a valid CS state

    """
    vf_state, d_state, pxa_state = cs_state(s).value
    return (vf_state, d_state, pxa_state)


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

    Raises:
        StateValidationError: if *s* does not name a valid CS state
    """
    cs_state(s)
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
