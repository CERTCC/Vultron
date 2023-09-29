#!/usr/bin/env python
"""file: ssvc
author: adh
created_at: 3/13/23 3:53 PM
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


from vultron.case_states.enums.ssvc_2 import (
    SSVC_2_Exploitation,
    SSVC_2_Public_Value_Added,
    SSVC_2_Report_Public,
    SSVC_2_Supplier_Contacted,
)
from vultron.case_states.enums.utils import unique_enum_list
from vultron.case_states.patterns.base import compile_patterns
from vultron.case_states.validations import ensure_valid_state

_SSVC = {
    "....xa": (SSVC_2_Exploitation.NONE,),
    "....Xa": (SSVC_2_Exploitation.POC,),
    ".....A": (SSVC_2_Exploitation.ACTIVE,),
    "...p..": (
        SSVC_2_Report_Public.NO,
        SSVC_2_Public_Value_Added.PRECEDENCE,
        SSVC_2_Public_Value_Added.AMPLIATIVE,
    ),
    "...P..": (SSVC_2_Report_Public.YES,),
    "V.....": (SSVC_2_Supplier_Contacted.YES,),
    "v.....": (SSVC_2_Supplier_Contacted.NO,),
    "VFdp..": (SSVC_2_Public_Value_Added.AMPLIATIVE,),
    "..dP..": (
        SSVC_2_Public_Value_Added.AMPLIATIVE,
        SSVC_2_Public_Value_Added.LIMITED,
    ),
    "VF.P..": (SSVC_2_Public_Value_Added.LIMITED,),
    "..D...": (SSVC_2_Public_Value_Added.LIMITED,),
}

SSVC = compile_patterns(_SSVC)


# function to return a  list of unique enums given a list of different enum items
# the enum items can be from different enums


@ensure_valid_state
def ssvc(state):
    information = []
    for pat, info in SSVC.items():
        if pat.match(state):
            information.extend(info)
    return unique_enum_list(information)
