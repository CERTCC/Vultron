#!/usr/bin/env python
"""file: info
author: adh
created_at: 1/21/21 11:11 AM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from vultron.cvd_states.enums.info import Info
from vultron.cvd_states.enums.utils import enum2title, unique_enum_list
from vultron.cvd_states.patterns.base import compile_patterns
from vultron.cvd_states.patterns.cvss31 import cvss_31 as cvss
from vultron.cvd_states.patterns.embargo import embargo_viability
from vultron.cvd_states.patterns.explanations import explain
from vultron.cvd_states.patterns.ssvc import ssvc
from vultron.cvd_states.patterns.vep import vep
from vultron.cvd_states.validations import ensure_valid_pattern

_INFO = {
    "vF....": (Info.INVALID_STATE,),
    ".fD...": (Info.INVALID_STATE,),
    "..d...": (Info.ATTACK_SUCCESS_LIKELY,),
    "..D...": (Info.ATTACK_SUCCESS_UNLIKELY,),
    "v..P..": (Info.EXPECT_VENDOR_AWARENESS_IMMINENTLY,),
    "v..pX.": (
        Info.EXPECT_PUBLIC_AWARENESS_IMMINENTLY,
        Info.EXPECT_VENDOR_AWARENESS_IMMINENTLY,
    ),
    "V..pX.": (Info.EXPECT_PUBLIC_AWARENESS_IMMINENTLY,),
}

INFO = compile_patterns(_INFO)


@ensure_valid_pattern
def info(state, include_ssvc=True, include_cvss=True, include_vep=True):
    information = []
    for _re, inf in INFO.items():
        if _re.match(state):
            information.extend(inf)

    information.extend(embargo_viability(state))

    if include_ssvc:
        information.extend(ssvc(state))
    if include_cvss:
        information.extend(cvss(state))
    if include_vep:
        information.extend(vep(state))
    return unique_enum_list(information)


def main():
    from vultron.cvd_states.patterns.potential_actions import action
    from vultron.cvd_states.hypercube import CVDmodel

    model = CVDmodel()

    for state in model.states:
        print(f"# {state} #")

        print(f"### description ###")

        for explanation in explain(state):
            print(f"* {enum2title(explanation)}")

        print(f"### info ###")
        for _info in info(state):
            print(f"* {enum2title(_info)}")
        print(f"### actions ###")
        for act in action(state):
            print(f"* {enum2title(act)}")
        print()
        print()


if __name__ == "__main__":
    main()