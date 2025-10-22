#!/usr/bin/env python
"""This module provides case state patterns mapped to embargo viability enums"""
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


import re

from vultron.case_states.enums.embargo import EmbargoViability
from vultron.case_states.enums.utils import unique_enum_list
from vultron.case_states.patterns.base import compile_patterns
from vultron.case_states.type_hints import EnumTuple
from vultron.case_states.validations import ensure_valid_state

_EMBARGO_VIABILITY = {
    "..dpxa": (
        EmbargoViability.START_OK,
        EmbargoViability.VIABLE,
    ),
    "...pxa": (EmbargoViability.VIABLE,),
    # if you're in P, the embargo is moot.
    "...P..": (EmbargoViability.NOT_VIABLE, EmbargoViability.NO_START),
    "....X.": (EmbargoViability.NOT_VIABLE, EmbargoViability.NO_START),
    ".....A": (EmbargoViability.NOT_VIABLE, EmbargoViability.NO_START),
    # in pX and pA, the embargo is about to fail, but it's not yet failed, take caution
    "...pX.": (
        EmbargoViability.NOT_VIABLE,
        EmbargoViability.CAUTION,
        EmbargoViability.NO_START,
    ),
    "...p.A": (
        EmbargoViability.NOT_VIABLE,
        EmbargoViability.CAUTION,
        EmbargoViability.NO_START,
    ),
    # in Fdpxa, it's not clear why you would start an embargo unless there is a good reason
    # but an existing embargo is still viable
    ".Fdpxa": (
        EmbargoViability.START_OK,
        EmbargoViability.VIABLE,
        EmbargoViability.CAUTION,
    ),
    # You shouldn't start an embargo in Dpxa, but an existing embargo can continue
    "..Dpxa": (EmbargoViability.VIABLE, EmbargoViability.NO_START),
}

EMBARGO_VIABILITY = compile_patterns(_EMBARGO_VIABILITY)


@ensure_valid_state
def embargo_viability(state: str) -> list[EmbargoViability]:
    """What is the viability of an embargo?

    Args:
        state: the state to check

    Returns:
        the viability of an embargo
    """
    results: list[EnumTuple] = []
    for pattern, viability in EMBARGO_VIABILITY.items():
        if re.match(pattern, state):
            results.extend(viability)
    return unique_enum_list(results)


@ensure_valid_state
def can_start_embargo(state: str) -> bool:
    """Can an embargo be started?

    Args:
        state: the state to check

    Returns:
        True if an embargo can be started, False otherwise
    """
    return EmbargoViability.START_OK in embargo_viability(state)


@ensure_valid_state
def embargo_viable(state: str) -> bool:
    """Is an embargo viable?

    Args:
        state: the state to check

    Returns:
        True if an embargo is viable, False otherwise
    """
    return EmbargoViability.VIABLE in embargo_viability(state)
