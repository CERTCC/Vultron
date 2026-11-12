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

"""
The `vultron.core.states.cs` module implements the CVD Case State Model enums.

It also provides functions for converting between state strings and enums.

Grouped by concern (CS-18-005):

- ``dimensions`` — the six per-event dimension enums
- ``states`` — the compound enums ``CS_vf``, ``CS_d``, ``CS_pxa`` and ``CS``
- ``parsing`` — state-string conversion
- ``predicates`` — milestone groups and predicates
- ``transitions`` — triggers, transition tables and transition checks
- ``machine`` — the PXA state machine and the listing script
"""

from vultron.core.states.cs.dimensions import (
    AttackObservation,
    ExploitPublication,
    FixDeployment,
    FixReadiness,
    PublicAwareness,
    VendorAwareness,
)
from vultron.core.states.cs.machine import (
    create_pxa_machine,
    main,
)
from vultron.core.states.cs.parsing import (
    all_states,
    cs_state,
    pxa,
    state_string_to_enum2,
    state_string_to_enums,
    vfd,
)
from vultron.core.states.cs.predicates import (
    D_FIX_DEPLOYED,
    PXA_ATTACKS_OBSERVED,
    PXA_EXPLOIT_PUBLIC,
    PXA_PUBLIC_AWARE,
    VF_FIX_READY,
    VF_VENDOR_AWARE,
    is_d_fix_deployed,
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
    is_vf_fix_ready,
    is_vf_vendor_aware,
)
from vultron.core.states.cs.states import (
    CS,
    CompoundState,
    CS_d,
    CS_pxa,
    CS_vf,
    DState,
    PxaState,
    State,
    VfState,
)
from vultron.core.states.cs.transitions import (
    D_Trigger,
    DTransition,
    PXA_Trigger,
    PxaTransition,
    VF_Trigger,
    VfTransition,
    is_monotonic_d_forward,
    is_monotonic_pxa_forward,
    is_monotonic_vf_forward,
    is_pxa_assertion_acceptable,
    is_valid_d_transition,
    is_valid_pxa_transition,
    is_valid_vf_transition,
)

__all__ = [
    "AttackObservation",
    "CS",
    "CS_d",
    "CS_pxa",
    "CS_vf",
    "CompoundState",
    "DState",
    "DTransition",
    "D_FIX_DEPLOYED",
    "D_Trigger",
    "ExploitPublication",
    "FixDeployment",
    "FixReadiness",
    "PXA_ATTACKS_OBSERVED",
    "PXA_EXPLOIT_PUBLIC",
    "PXA_PUBLIC_AWARE",
    "PXA_Trigger",
    "PublicAwareness",
    "PxaState",
    "PxaTransition",
    "State",
    "VF_FIX_READY",
    "VF_Trigger",
    "VF_VENDOR_AWARE",
    "VendorAwareness",
    "VfState",
    "VfTransition",
    "all_states",
    "cs_state",
    "create_pxa_machine",
    "is_d_fix_deployed",
    "is_monotonic_d_forward",
    "is_monotonic_pxa_forward",
    "is_monotonic_vf_forward",
    "is_pxa_assertion_acceptable",
    "is_pxa_attacks_observed",
    "is_pxa_exploit_public",
    "is_pxa_public_aware",
    "is_valid_d_transition",
    "is_valid_pxa_transition",
    "is_valid_vf_transition",
    "is_vf_fix_ready",
    "is_vf_vendor_aware",
    "main",
    "pxa",
    "state_string_to_enum2",
    "state_string_to_enums",
    "vfd",
]
