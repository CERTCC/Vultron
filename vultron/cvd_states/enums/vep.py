#!/usr/bin/env python
"""file: vep
author: adh
created_at: 3/16/23 1:40 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from enum import IntEnum, auto


class VEP(IntEnum):
    VEP_TENABLE = auto()
    VEP_NOT_APPLICABLE = auto()

    # convenience aliases
    TENABLE = VEP_TENABLE
    NOT_APPLICABLE = VEP_NOT_APPLICABLE
