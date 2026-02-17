#!/usr/bin/env python
"""This module provides case state patterns mapped to info enums"""

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


from vultron.case_states.enums.info import Info
from vultron.case_states.enums.utils import enum2title, unique_enum_list
from vultron.case_states.patterns.base import compile_patterns
from vultron.case_states.patterns.cvss31 import cvss_31 as cvss
from vultron.case_states.patterns.embargo import embargo_viability
from vultron.case_states.patterns.explanations import explain
from vultron.case_states.patterns.ssvc import ssvc
from vultron.case_states.patterns.vep import vep
from vultron.case_states.validations import ensure_valid_pattern

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
    from vultron.case_states.patterns.potential_actions import action
    from vultron.case_states.hypercube import CVDmodel

    model = CVDmodel()

    for state in model.states:
        print(f"# {state} #")

        print("### description ###")

        for explanation in explain(state):
            print(f"* {enum2title(explanation)}")

        print("### info ###")
        for _info in info(state):
            print(f"* {enum2title(_info)}")
        print("### actions ###")
        for act in action(state):
            print(f"* {enum2title(act)}")
        print()
        print()


if __name__ == "__main__":
    main()
