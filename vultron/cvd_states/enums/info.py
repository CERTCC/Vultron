#!/usr/bin/env python
"""file: info
author: adh
created_at: 3/16/23 1:40 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from enum import IntEnum, auto


class Info(IntEnum):
    INVALID_STATE = auto()
    ATTACK_SUCCESS_LIKELY = auto()
    ATTACK_SUCCESS_UNLIKELY = auto()
    EXPECT_VENDOR_AWARENESS_IMMINENTLY = auto()
    EXPECT_PUBLIC_AWARENESS_IMMINENTLY = auto()
