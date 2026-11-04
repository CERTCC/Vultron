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


"""The CS PXA ``transitions`` state machine and the enum listing script."""

from transitions import Machine

from vultron.core.states.common import mermaid_machine
from vultron.core.states.cs.parsing import (
    all_states,
)
from vultron.core.states.cs.states import (
    CS,
    CS_pxa,
)
from vultron.core.states.cs.transitions import (
    _pxa_transitions,
)


def create_pxa_machine() -> Machine:
    """
    Generates a new Case State Public Exploit Attacks Machine object

    Returns:
        Machine: New Machine object
    """
    return Machine(
        states=CS_pxa,
        transitions=_pxa_transitions,
        initial=CS_pxa.pxa,
        auto_transitions=False,
        name="CS PXA State Machine",
    )


def main():
    print("Case State Enumerations")
    print()
    print("Public Case States")
    for state in CS_pxa:
        print(state, state.name, state.value)
    print()
    print("Case States")
    for state in CS:
        print(state, state.name, state.value)
    print()
    print("All Case States")
    for state in all_states:
        print(state, state.name, state.value)

    print("Mermaid Diagrams of State machines")
    print(mermaid_machine(create_pxa_machine()))
