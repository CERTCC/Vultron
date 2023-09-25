#!/usr/bin/env python
"""file: vep
author: adh
created_at: 3/13/23 3:01 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from vultron.cvd_states.enums.utils import unique_enum_list
from vultron.cvd_states.enums.vep import VEP
from vultron.cvd_states.patterns.base import compile_patterns
from vultron.cvd_states.validations import (
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
