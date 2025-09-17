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


from vultron.case_states.enums.explanations import Explanation
from vultron.case_states.enums.utils import unique_enum_list
from vultron.case_states.patterns.base import compile_patterns
from vultron.case_states.validations import ensure_valid_pattern

_EXPLANATION_PATTERNS = {
    "v.....": (Explanation.VENDOR_IS_UNAWARE_OF_VULNERABILITY,),
    "V.....": (Explanation.VENDOR_IS_AWARE_OF_VULNERABILITY,),
    ".f....": (Explanation.FIX_IS_NOT_READY,),
    ".F....": (Explanation.FIX_IS_READY,),
    "..d...": (Explanation.FIX_HAS_NOT_BEEN_DEPLOYED,),
    "..D...": (Explanation.FIX_HAS_BEEN_DEPLOYED,),
    "...p..": (Explanation.PUBLIC_IS_UNAWARE_OF_VULNERABILITY,),
    "...P..": (Explanation.PUBLIC_IS_AWARE_OF_VULNERABILITY,),
    "....x.": (Explanation.NO_EXPLOITS_HAVE_BEEN_MADE_PUBLIC,),
    "....X.": (Explanation.EXPLOITS_HAVE_BEEN_MADE_PUBLIC,),
    ".....a": (Explanation.NO_ATTACKS_HAVE_BEEN_OBSERVED,),
    ".....A": (Explanation.ATTACKS_HAVE_BEEN_OBSERVED,),
}

EXPLANATIONS = compile_patterns(_EXPLANATION_PATTERNS)


@ensure_valid_pattern
def explain(state):
    """Given the shorthand for a state, return a list of its explanations"""
    information = []
    for pat, info in EXPLANATIONS.items():
        if pat.match(state):
            information.extend(info)
    return unique_enum_list(information)


def main():
    for pat, explanation in EXPLANATIONS.items():
        e_str = ", ".join(
            [e.name.replace("_", " ").title() for e in explanation]
        )
        print(f"* {pat.pattern} => {e_str}")


if __name__ == "__main__":
    main()
