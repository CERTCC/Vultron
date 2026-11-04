#!/usr/bin/env python
#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""CS-internal validity, transition, and history invariants.

This module expresses the Case State (CS) validity rules of the MPCVD
state-based model against the current enum models in
`vultron.core.states.cs` — `CS`, `CS_vf`, `CS_d`, `CS_pxa`, and the
per-dimension transition tables.

Three rule families live here:

Compound state validity
    The 32 members of `CS` *are* the valid compound states.  The two
    impossible-combination rules of the formal model (`vF` — a fix ready
    while the vendor is unaware; `fD` — a fix deployed that was never ready)
    are enforced structurally by `CompoundState` only containing the 32
    valid combinations, so no runtime predicate is needed.
    `test_cs_invariants.py` ratchets the enum against an independent
    derivation of the rule.

Transition validity (`is_valid_cs_transition`)
    A CS transition changes exactly one of the six dimensions, always from
    the not-yet-happened to the happened value, and must respect the two
    *ephemeral state* rules below.

Ephemeral states (`is_ephemeral_cs_state`, `required_next_cs_events`)
    Two compound states are transient in the formal model and constrain the
    very next event rather than being forbidden outright:

    - ``vP`` (public aware, vendor unaware) — the next event MUST be ``V``.
    - ``pX`` (exploit public, public unaware) — the next event MUST be ``P``.

History validity (`is_valid_cs_history`, `is_valid_cs_history_prefix`)
    A *history* is the order in which the six events occurred.  History
    validity is a **causal** property of a whole sequence, not a
    point-in-time or wall-clock one: it is what lets a consumer reject a
    reported case trajectory that no real case could have produced.

The complete-history ordering rules

- ``V ≺ F ≺ D``
- ``P ≺ X`` or ``P`` immediately follows ``X``
- ``V ≺ P`` or ``V`` immediately follows ``P``

are provably equivalent to replaying the sequence through
`is_valid_cs_transition` from `CS.vfdpxa`; both admit exactly the same 70
histories.  `test_cs_invariants.py` asserts that equivalence directly, so
the two formulations cannot drift apart.

Reference: Householder, A. D., and Spring, J.
*A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure
(MPCVD)*, CMU/SEI-2021-SR-021. <https://doi.org/10.1184/R1/16416771>

Spec: `specs/cs-behavior.yaml` CSB-17.  Decision: ADR-0060.

Grouped by concern (CS-18-005):

- ``events`` — the six CS events and the compound-state dimensions
- ``transitions`` — transition validity and the ephemeral-state rules
- ``history`` — event application and causal history validity
"""

from vultron.core.states.cs_invariants.events import (
    CS_EVENT_TO_PXA_TRIGGER,
    CS_EVENTS,
    PXA_EVENTS,
    VFD_EVENTS,
    CSEvent,
    cs_dimensions,
    cs_from_dimensions,
)
from vultron.core.states.cs_invariants.history import (
    apply_cs_event,
    ensure_valid_cs_history,
    is_valid_cs_history,
    is_valid_cs_history_prefix,
    replay_cs_history,
    valid_cs_histories,
)
from vultron.core.states.cs_invariants.transitions import (
    cs_transition_event,
    ensure_valid_cs_transition,
    is_ephemeral_cs_state,
    is_valid_cs_transition,
    next_cs_states,
    required_next_cs_events,
)

__all__ = [
    "CSEvent",
    "CS_EVENTS",
    "CS_EVENT_TO_PXA_TRIGGER",
    "PXA_EVENTS",
    "VFD_EVENTS",
    "apply_cs_event",
    "cs_dimensions",
    "cs_from_dimensions",
    "cs_transition_event",
    "ensure_valid_cs_history",
    "ensure_valid_cs_transition",
    "is_ephemeral_cs_state",
    "is_valid_cs_history",
    "is_valid_cs_history_prefix",
    "is_valid_cs_transition",
    "next_cs_states",
    "replay_cs_history",
    "required_next_cs_events",
    "valid_cs_histories",
]
