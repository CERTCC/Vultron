#!/usr/bin/env python
"""file: explanations
author: adh
created_at: 3/16/23 1:39 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from enum import IntEnum, auto


class Explanation(IntEnum):
    VENDOR_IS_UNAWARE_OF_VULNERABILITY = auto()
    VENDOR_IS_AWARE_OF_VULNERABILITY = auto()
    FIX_IS_NOT_READY = auto()
    FIX_IS_READY = auto()
    FIX_HAS_NOT_BEEN_DEPLOYED = auto()
    FIX_HAS_BEEN_DEPLOYED = auto()
    PUBLIC_IS_UNAWARE_OF_VULNERABILITY = auto()
    PUBLIC_IS_AWARE_OF_VULNERABILITY = auto()
    NO_EXPLOITS_HAVE_BEEN_MADE_PUBLIC = auto()
    EXPLOITS_HAVE_BEEN_MADE_PUBLIC = auto()
    NO_ATTACKS_HAVE_BEEN_OBSERVED = auto()
    ATTACKS_HAVE_BEEN_OBSERVED = auto()
