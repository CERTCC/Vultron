#!/usr/bin/env python
"""file: embargo
author: adh
created_at: 3/16/23 1:39 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from enum import IntEnum, auto


class EmbargoViability(IntEnum):
    """The viability of an embargo"""

    EMBARGO_VIABILITY_START_OK = auto()
    EMBARGO_VIABILITY_NO_START = auto()
    EMBARGO_VIABILITY_VIABLE = auto()
    EMBARGO_VIABILITY_NOT_VIABLE = auto()
    EMBARGO_VIABILITY_CAUTION = auto()

    # convenience aliases
    START_OK = EMBARGO_VIABILITY_START_OK
    NO_START = EMBARGO_VIABILITY_NO_START
    VIABLE = EMBARGO_VIABILITY_VIABLE
    NOT_VIABLE = EMBARGO_VIABILITY_NOT_VIABLE
    CAUTION = EMBARGO_VIABILITY_CAUTION
