#!/usr/bin/env python
"""file: explanations
author: adh
created_at: 1/21/21 11:09 AM
"""

#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from vultron.cvd_states.enums.explanations import Explanation
from vultron.cvd_states.enums.utils import unique_enum_list
from vultron.cvd_states.patterns.base import compile_patterns
from vultron.cvd_states.validations import ensure_valid_pattern

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
        e_str = ", ".join([e.name.replace("_", " ").title() for e in explanation])
        print(f"* {pat.pattern} => {e_str}")


if __name__ == "__main__":
    main()
