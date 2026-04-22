#!/usr/bin/env python
"""Participant Embargo Consent (PEC) state machine.

Tracks each case participant's consent status with respect to an active or
proposed embargo.  The five-state machine is independent of the shared case-
level EM machine: the shared EM machine describes the coordinator's view of
the embargo lifecycle; PEC describes each individual participant's position.

States
------
NO_EMBARGO  – No embargo is in scope for this participant.
INVITED     – Participant has been invited but has not yet responded.
SIGNATORY   – Participant has accepted the current embargo terms.
LAPSED      – Embargo terms changed (REVISE); participant's prior consent no
              longer covers the revision.
DECLINED    – Participant explicitly declined (current invite or lapsed terms).

Transitions
-----------
INVITE  : NO_EMBARGO | LAPSED | DECLINED → INVITED
ACCEPT  : INVITED | LAPSED → SIGNATORY
DECLINE : INVITED | LAPSED → DECLINED
REVISE  : SIGNATORY → LAPSED
RESET   : * → NO_EMBARGO  (embargo terminated or removed)
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

import logging
from enum import StrEnum, auto

from transitions import Machine, MachineError

from vultron.core.states.common import TransitionBase, mermaid_machine

logger = logging.getLogger(__name__)


class PEC(StrEnum):
    """Participant Embargo Consent states."""

    NO_EMBARGO = "NO_EMBARGO"
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
        trigger=PEC_Trigger.INVITE, source=PEC.NO_EMBARGO, dest=PEC.INVITED
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.INVITE, source=PEC.LAPSED, dest=PEC.INVITED
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.INVITE, source=PEC.DECLINED, dest=PEC.INVITED
    ).model_dump(),
    # ACCEPT transitions
    PECTransition(
        trigger=PEC_Trigger.ACCEPT, source=PEC.INVITED, dest=PEC.SIGNATORY
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.ACCEPT, source=PEC.LAPSED, dest=PEC.SIGNATORY
    ).model_dump(),
    # DECLINE transitions
    PECTransition(
        trigger=PEC_Trigger.DECLINE, source=PEC.INVITED, dest=PEC.DECLINED
    ).model_dump(),
    PECTransition(
        trigger=PEC_Trigger.DECLINE, source=PEC.LAPSED, dest=PEC.DECLINED
    ).model_dump(),
    # REVISE: an active signatory lapses when embargo terms change
    PECTransition(
        trigger=PEC_Trigger.REVISE, source=PEC.SIGNATORY, dest=PEC.LAPSED
    ).model_dump(),
    # RESET: embargo terminated or removed — all participants revert to NO_EMBARGO
    PECTransition(
        trigger=PEC_Trigger.RESET, source="*", dest=PEC.NO_EMBARGO
    ).model_dump(),
]


class PECAdapter:
    """Adapter for applying PEC transitions to a plain ``.state`` attribute."""

    def __init__(self, initial: PEC) -> None:
        self.state = initial


def create_pec_machine() -> Machine:
    """Create a new Participant Embargo Consent state machine instance."""
    return Machine(
        states=PEC,
        transitions=_transitions,
        initial=PEC.NO_EMBARGO,
        auto_transitions=False,
        name="PEC FSM",
    )


def apply_pec_trigger(current_state: PEC, trigger: PEC_Trigger) -> PEC:
    """Apply a PEC trigger to a state and return the resulting state.

    Returns the unchanged state when the transition is not valid (logs a
    warning instead of raising).
    """
    adapter = PECAdapter(current_state)
    machine = create_pec_machine()
    machine.add_model(adapter, initial=current_state)
    try:
        getattr(adapter, trigger)()
        return PEC(adapter.state)
    except MachineError:
        logger.warning(
            "Invalid PEC transition: state='%s' trigger='%s' — ignored",
            current_state,
            trigger,
        )
        return current_state


if __name__ == "__main__":
    M = create_pec_machine()
    print(mermaid_machine(M))
