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


from vultron.case_states.enums.utils import unique_enum_list
from vultron.case_states.enums.vep import VEP
from vultron.case_states.patterns.base import compile_patterns
from vultron.case_states.validations import (
    ensure_valid_state,
)

_VEP = {
    "V.....": (VEP.NOT_APPLICABLE,),
    "...P..": (VEP.NOT_APPLICABLE,),
    "....X.": (VEP.NOT_APPLICABLE,),
    "vfdpx.": (VEP.TENABLE,),
}

VEP_ = compile_patterns(_VEP)


@ensure_valid_state
def vep(state):
    information = []
    for _re, info in VEP_.items():
        if _re.match(state):
            information.extend(info)
    return unique_enum_list(information)
