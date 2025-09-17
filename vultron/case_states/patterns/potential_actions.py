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


from vultron.case_states.enums.potential_actions import Actions
from vultron.case_states.enums.utils import unique_enum_list
from vultron.case_states.patterns.base import compile_patterns

# things you COULD do, not necessarily things you SHOULD do
_ACTIONS = {
    "...P..": (
        Actions.TERMINATE_ANY_EXISTING_EMBARGO,
        Actions.PUBLISH_VULNERABILITY,
    ),
    "....X.": (
        Actions.TERMINATE_ANY_EXISTING_EMBARGO,
        Actions.PUBLISH_VULNERABILITY,
        Actions.PUBLICIZE_PUBLISHED_EXPLOITS,
        Actions.MONITOR_FOR_EXPLOIT_REFINEMENT,
        Actions.PUBLISH_DETECTION_FOR_EXPLOITS,
    ),
    ".....A": (
        Actions.TERMINATE_ANY_EXISTING_EMBARGO,
        Actions.PUBLISH_VULNERABILITY,
        Actions.MONITOR_FOR_ADDITIONAL_ATTACKS,
        Actions.PUBLISH_DETECTION_FOR_ATTACKS,
    ),
    "VfdpX.": (Actions.INITIATE_EMBARGO_TERMINATION,),
    "Vfdp.A": (Actions.INITIATE_EMBARGO_TERMINATION,),
    "....x.": (Actions.MONITOR_FOR_EXPLOIT_PUBLICATION,),
    ".....a": (Actions.MONITOR_FOR_ATTACKS,),
    "vfdP..": (
        Actions.PAY_ATTENTION_TO_PUBLIC_REPORTS,
        Actions.ESCALATE_VENDOR_NOTIFICATION_PRIORITY,
    ),
    "...pxa": (
        Actions.MAINTAIN_VIGILANCE_FOR_EMBARGO_EXIT_CRITERIA,
        Actions.MAINTAIN_ANY_EXISTING_EMBARGO,
    ),
    "VfdP..": (
        Actions.ESCALATE_VIGILANCE_FOR_EXPLOITS,
        Actions.ESCALATE_VIGILANCE_FOR_ATTACKS,
        Actions.PUBLISH_MITIGATION,
        Actions.PUBLICIZE_MITIGATION,
        Actions.ESCALATE_FIX_PRIORITY,
    ),
    "V..p..": (Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    ".fdP..": (Actions.PUBLISH_MITIGATION,),
    "...pX.": (Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    "...PX.": (Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    "...p.A": (Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    "vfdp..": (Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    "Vfd...": (Actions.CREATE_FIX, Actions.ENCOURAGE_VENDOR_TO_CREATE_FIX),
    "VFd...": (Actions.DEPLOY_FIX,),
    ".fdPxA": (Actions.PUBLISH_EXPLOIT_CODE,),
    "VFdPxa": (Actions.PUBLISH_EXPLOIT_CODE,),
    "vfd...": (Actions.NOTIFY_VENDOR,),
    ".FdP..": (Actions.ESCALATE_DEPLOYMENT_PRIORITY,),
    ".f..X.": (Actions.ESCALATE_FIX_PRIORITY,),
    ".f...A": (Actions.ESCALATE_FIX_PRIORITY,),
    ".Fd.X.": (Actions.ESCALATE_DEPLOYMENT_PRIORITY,),
    ".Fd..A": (Actions.ESCALATE_DEPLOYMENT_PRIORITY,),
    "..dpxa": (Actions.NEGOTIATE_OR_ESTABLISH_DISCLOSURE_EMBARGO,),
    "Vfdp..": (
        Actions.MOTIVATE_VENDOR_TO_FIX,
        Actions.PUBLISH_VULNERABILITY,
    ),
    "VFdpxa": (Actions.SCRUTINIZE_APPROPRIATENESS_OF_EMBARGO_INITIATION,),
    "VFdp..": (
        Actions.ENCOURAGE_VENDOR_TO_DEPLOY_FIX,
        Actions.PUBLISH_VULNERABILITY,
        Actions.PUBLISH_FIX,
    ),
    "VFdP..": (Actions.PROMOTE_FIX_DEPLOYMENT,),
    "VFDp..": (Actions.PUBLISH_VULNERABILITY,),
    ".fd.xa": (Actions.DISCOURAGE_EXPLOIT_PUBLICATION,),
    "vfdpx.": (Actions.INITIATE_VEP_USGOV,),
    "VFDPXA": (Actions.CLOSE_CASE,),
    "VFDPxa": (Actions.CLOSE_CASE,),
    "VFDPXa": (Actions.CLOSE_CASE,),
    "VFDPxA": (Actions.CLOSE_CASE,),
}

ACTIONS = compile_patterns(_ACTIONS)


def action(state):
    actions = []
    for pat, info in ACTIONS.items():
        if pat.match(state):
            actions.extend(info)
    return unique_enum_list(actions)


def main():
    from vultron.case_states.hypercube import CVDmodel
    from vultron.case_states.enums.utils import enum2title

    model = CVDmodel()
    for state in model.states:
        print(f"# State: {state}")
        print(f"## Potential Actions")
        for a in action(state):
            print(f"- {enum2title(a)}")

        print()


if __name__ == "__main__":
    main()
