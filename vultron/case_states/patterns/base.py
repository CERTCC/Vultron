#!/usr/bin/env python
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

import re

from vultron.case_states.type_hints import EnumTuple
from vultron.case_states.validations import is_valid_pattern


def compile_patterns(
    dict_of_patterns: dict[str, EnumTuple],
) -> dict[re.Pattern, EnumTuple]:
    """Compile the patterns in the dictionary keys to regex patterns
    Args:
        dict_of_patterns: A dictionary with string patterns as keys and
            associated information as values
    Returns:
        A dictionary with compiled regex patterns as keys and associated
        information as values
    """
    # check that all the patterns are valid
    for pattern in dict_of_patterns.keys():
        is_valid_pattern(pattern)

    return {re.compile(k): v for k, v in dict_of_patterns.items()}
