#!/usr/bin/env python
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
"""
Enumerated state explanations
"""

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
