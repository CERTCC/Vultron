#!/usr/bin/env python
"""file: vep
author: adh
created_at: 3/16/23 1:40 PM
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


class VEP(IntEnum):
    VEP_TENABLE = auto()
    VEP_NOT_APPLICABLE = auto()

    # convenience aliases
    TENABLE = VEP_TENABLE
    NOT_APPLICABLE = VEP_NOT_APPLICABLE
