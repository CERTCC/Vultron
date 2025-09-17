#!/usr/bin/env python
"""This module provides
# TODO replace me
"""
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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


from enum import IntEnum, auto


class ZeroDayType(IntEnum):
    """Enum for the type of Zero Day"""

    NOT_APPLICABLE = auto()

    ZERO_DAY_VULNERABILITY_TYPE_1 = auto()
    ZERO_DAY_VULNERABILITY_TYPE_2 = auto()
    ZERO_DAY_VULNERABILITY_TYPE_3 = auto()
    ZERO_DAY_EXPLOIT_TYPE_1 = auto()
    ZERO_DAY_EXPLOIT_TYPE_2 = auto()
    ZERO_DAY_EXPLOIT_TYPE_3 = auto()
    ZERO_DAY_ATTACK_TYPE_1 = auto()
    ZERO_DAY_ATTACK_TYPE_2 = auto()
    ZERO_DAY_ATTACK_TYPE_3 = auto()

    # convenience aliases
    NA = NOT_APPLICABLE
    VULNERABILITY_TYPE_1 = ZERO_DAY_VULNERABILITY_TYPE_1
    VULNERABILITY_TYPE_2 = ZERO_DAY_VULNERABILITY_TYPE_2
    VULNERABILITY_TYPE_3 = ZERO_DAY_VULNERABILITY_TYPE_3
    EXPLOIT_TYPE_1 = ZERO_DAY_EXPLOIT_TYPE_1
    EXPLOIT_TYPE_2 = ZERO_DAY_EXPLOIT_TYPE_2
    EXPLOIT_TYPE_3 = ZERO_DAY_EXPLOIT_TYPE_3
    ATTACK_TYPE_1 = ZERO_DAY_ATTACK_TYPE_1
    ATTACK_TYPE_2 = ZERO_DAY_ATTACK_TYPE_2
    ATTACK_TYPE_3 = ZERO_DAY_ATTACK_TYPE_3

    ZD_NA = NOT_APPLICABLE
    ZD_VUL_1 = ZERO_DAY_VULNERABILITY_TYPE_1
    ZD_VUL_2 = ZERO_DAY_VULNERABILITY_TYPE_2
    ZD_VUL_3 = ZERO_DAY_VULNERABILITY_TYPE_3
    ZD_EXP_1 = ZERO_DAY_EXPLOIT_TYPE_1
    ZD_EXP_2 = ZERO_DAY_EXPLOIT_TYPE_2
    ZD_EXP_3 = ZERO_DAY_EXPLOIT_TYPE_3
    ZD_ATK_1 = ZERO_DAY_ATTACK_TYPE_1
    ZD_ATK_2 = ZERO_DAY_ATTACK_TYPE_2
    ZD_ATK_3 = ZERO_DAY_ATTACK_TYPE_3
