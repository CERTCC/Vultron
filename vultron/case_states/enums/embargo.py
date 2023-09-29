#!/usr/bin/env python
"""file: embargo
author: adh
created_at: 3/16/23 1:39 PM
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
