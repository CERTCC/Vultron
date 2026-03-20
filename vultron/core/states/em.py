#!/usr/bin/env python
"""This module defines the Embargo Management states for the Vultron protocol."""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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


class EM(StrEnum):
    """Embargo Management States

    NO_EMBARGO: No embargo is in effect
    PROPOSED: Embargo is proposed but not yet active
    ACTIVE: Embargo is active
    REVISE: Embargo is active and a revision is proposed
    EXITED: Embargo had been active but has been exited
    """

    NONE = "NONE"
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    REVISE = "REVISE"
    EXITED = "EXITED"

    # convenience aliases
    EMBARGO_MANAGEMENT_NONE = NONE
    EMBARGO_MANAGEMENT_PROPOSED = PROPOSED
    EMBARGO_MANAGEMENT_ACTIVE = ACTIVE
    EMBARGO_MANAGEMENT_REVISE = REVISE
    EMBARGO_MANAGEMENT_EXITED = EXITED

    NO_EMBARGO = NONE

    N = NONE
    P = PROPOSED
    A = ACTIVE
    R = REVISE
    X = EXITED


class EM_Trigger(StrEnum):
    """
    Embargo Management State Machine Triggers
    """

    # auto() makes these lowercase when stringified
    PROPOSE = auto()
    REJECT = auto()
    ACCEPT = auto()
    TERMINATE = auto()


class EmTransition(TransitionBase):
    trigger: EM_Trigger
    source: EM
    dest: EM


_transitions = [
    EmTransition(
        trigger=EM_Trigger.PROPOSE, source=EM.NO_EMBARGO, dest=EM.PROPOSED
    ).model_dump(),
    EmTransition(
        trigger=EM_Trigger.PROPOSE, source=EM.PROPOSED, dest=EM.PROPOSED
    ).model_dump(),
    EmTransition(
        trigger=EM_Trigger.REJECT, source=EM.PROPOSED, dest=EM.NO_EMBARGO
    ).model_dump(),
    EmTransition(
        trigger=EM_Trigger.ACCEPT, source=EM.PROPOSED, dest=EM.ACTIVE
    ).model_dump(),
    EmTransition(
        trigger=EM_Trigger.PROPOSE, source=EM.ACTIVE, dest=EM.REVISE
    ).model_dump(),
    EmTransition(
        trigger=EM_Trigger.PROPOSE, source=EM.REVISE, dest=EM.REVISE
    ).model_dump(),
    EmTransition(
        trigger=EM_Trigger.REJECT, source=EM.REVISE, dest=EM.ACTIVE
    ).model_dump(),
    EmTransition(
        trigger=EM_Trigger.ACCEPT, source=EM.REVISE, dest=EM.ACTIVE
    ).model_dump(),
    EmTransition(
        trigger=EM_Trigger.TERMINATE, source=EM.ACTIVE, dest=EM.EXITED
    ).model_dump(),
    EmTransition(
        trigger=EM_Trigger.TERMINATE, source=EM.REVISE, dest=EM.EXITED
    ).model_dump(),
]


class EMAdapter:
    """Adapter that lets the EM transitions machine operate on a plain .state attribute.

    Seed with the current EM state, pass to ``machine.add_model(initial=...)``,
    trigger the desired transition, then read back ``.state``.
    """

    def __init__(self, initial: EM) -> None:
        self.state = initial


def is_valid_em_transition(source: EM, dest: EM) -> bool:
    """Return True if (source → dest) is a valid EM state transition."""
    return any(
        t["source"] == source and t["dest"] == dest for t in _transitions
    )


def create_em_machine() -> Machine:
    """
    Generates a new Embargo Management State Machine

    Returns:
        A transitions Machine object representing the Embargo Management state machine
    """
    return Machine(
        states=EM,
        transitions=_transitions,
        initial=EM.NONE,
        auto_transitions=False,
        name="EM FSM",
    )


if __name__ == "__main__":
    M = create_em_machine()
    print(mermaid_machine(M))
