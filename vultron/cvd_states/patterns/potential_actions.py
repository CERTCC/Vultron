#!/usr/bin/env python
"""file: potential_actions.py
author: adh
created_at: 5/13/21 1:24 PM

This module contains the logic for determining the potential actions that can be taken
based on the current state of the CVD case.

The logic is based on the CVD state model, which is a 6-character string that represents
the current state of the CVD case. The characters in the string represent the following
states:
v,V - Vendor Awareness
f,F - Fix Availability
d,D - Fix Deployment
p,P - Public Awareness
x,X - Exploit Public
a,A - Attacks Observed

"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from vultron.cvd_states.enums.potential_actions import Actions
from vultron.cvd_states.enums.utils import unique_enum_list
from vultron.cvd_states.patterns.base import compile_patterns

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
    from vultron.cvd_states.hypercube import CVDmodel
    from vultron.cvd_states.enums.utils import enum2title

    model = CVDmodel()
    for state in model.states:
        print(f"# State: {state}")
        print(f"## Potential Actions")
        for a in action(state):
            print(f"- {enum2title(a)}")

        print()


if __name__ == "__main__":
    main()
