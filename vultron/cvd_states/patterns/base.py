#!/usr/bin/env python
"""file: base
author: adh
created_at: 3/13/23 4:01 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

import re

from vultron.cvd_states.validations import is_valid_pattern


def compile_patterns(dict_of_patterns):
    # check that all the patterns are valid
    for pattern in dict_of_patterns.keys():
        is_valid_pattern(pattern)

    return {re.compile(k): v for k, v in dict_of_patterns.items()}
