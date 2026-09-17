#!/usr/bin/env python
"""Participant Embargo Consent (PEC) state machine.

Tracks each case participant's consent status with respect to an active or
proposed embargo.  The five-state machine is independent of the shared case-
level EM machine: the shared EM machine describes the coordinator's view of
the embargo lifecycle; PEC describes each individual participant's position.

States
------
UNBOUND     – This participant is not bound by any embargo terms.
INVITED     – Participant has been invited but has not yet responded.
SIGNATORY   – Participant has accepted the current embargo terms.
LAPSED      – Embargo terms changed (REVISE); participant's prior consent no
              longer covers the revision.
DECLINED    – Participant explicitly declined (current invite or lapsed terms).

Transitions
-----------
INVITE  : UNBOUND | LAPSED | DECLINED → INVITED
ACCEPT  : UNBOUND | INVITED | LAPSED → SIGNATORY
DECLINE : UNBOUND | INVITED | LAPSED | SIGNATORY → DECLINED
REVISE  : SIGNATORY → LAPSED
RESET   : * → UNBOUND  (embargo terminated or removed)

``UNBOUND`` means *not bound by any embargo terms* (ADR-0048, ADR-0091).
``ACCEPT`` and ``DECLINE`` are therefore valid directly from ``UNBOUND``
for self-determined embargoes and implicit-consent cases (CM-14-005).
"""

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

from enum import StrEnum, auto

from transitions import Machine

from vultron.core.states.common import TransitionBase, mermaid_machine


class PEC(StrEnum):
    """Participant Embargo Consent states."""

    UNBOUND = "UNBOUND"
    INVITED = "INVITED"
    SIGNATORY = "SIGNATORY"
    DECLINED = "DECLINED"
    LAPSED = "LAPSED"


class PEC_Trigger(StrEnum):
    """Triggers for the Participant Embargo Consent state machine."""

    # auto() produces lowercase names when stringified, matching transitions lib convention.
    INVITE = auto()
    ACCEPT = auto()
    DECLINE = auto()
    REVISE = auto()
    RESET = auto()


class PECTransition(TransitionBase):
    trigger: PEC_Trigger
    # source accepts PEC enum members or the wildcard string "*"
    source: PEC | str
    dest: PEC


_transitions: list[dict] = [
    # INVITE transitions
    PECTransition(
        trigger=PEC_Trigger.INVITE, source=PEC.UNBOUND, dest=PEC.INVITED
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.INVITE, source=PEC.LAPSED, dest=PEC.INVITED
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.INVITE, source=PEC.DECLINED, dest=PEC.INVITED
    ).model_dump(),
    # ACCEPT transitions (ADR-0048: UNBOUND is absence-of-embargo, not pre-consent)
    PECTransition(
        trigger=PEC_Trigger.ACCEPT, source=PEC.UNBOUND, dest=PEC.SIGNATORY
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.ACCEPT, source=PEC.INVITED, dest=PEC.SIGNATORY
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.ACCEPT, source=PEC.LAPSED, dest=PEC.SIGNATORY
    ).model_dump(),
    # DECLINE transitions (ADR-0048: symmetric with ACCEPT from UNBOUND;
    # ADR-0093: SIGNATORY → DECLINED is consent withdrawal, not a lapse)
    PECTransition(
        trigger=PEC_Trigger.DECLINE, source=PEC.UNBOUND, dest=PEC.DECLINED
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.DECLINE, source=PEC.INVITED, dest=PEC.DECLINED
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.DECLINE, source=PEC.LAPSED, dest=PEC.DECLINED
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.DECLINE, source=PEC.SIGNATORY, dest=PEC.DECLINED
    ).model_dump(),
    # REVISE: an active signatory lapses when embargo terms change
    PECTransition(
        trigger=PEC_Trigger.REVISE, source=PEC.SIGNATORY, dest=PEC.LAPSED
    ).model_dump(),
    # RESET: embargo terminated or removed — all participants revert to UNBOUND
    PECTransition(
        trigger=PEC_Trigger.RESET, source="*", dest=PEC.UNBOUND
    ).model_dump(),
]


def create_pec_machine() -> Machine:
    """Create a new Participant Embargo Consent state machine instance."""
    return Machine(
        states=PEC,
        transitions=_transitions,
        initial=PEC.UNBOUND,
        auto_transitions=False,
        name="PEC FSM",
    )


if __name__ == "__main__":
    M = create_pec_machine()
    print(mermaid_machine(M))
