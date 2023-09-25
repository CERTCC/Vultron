#!/usr/bin/env python
"""file: embargo
author: adh
created_at: 2/23/21 12:52 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

import re

from vultron.cvd_states.enums.embargo import EmbargoViability
from vultron.cvd_states.enums.utils import unique_enum_list
from vultron.cvd_states.patterns.base import compile_patterns
from vultron.cvd_states.validations import ensure_valid_state

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
def embargo_viability(state: str) -> EmbargoViability:
    """What is the viability of an embargo?

    Args:
        state: the state to check

    Returns:
        the viability of an embargo
    """
    results = []
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
