#!/usr/bin/env python
"""Participant Embargo Consent (PEC) state machine.

Tracks each case participant's consent status with respect to an active or
proposed embargo.  The seven-state machine is independent of the shared case-
level EM machine: the shared EM machine describes the coordinator's view of
the embargo lifecycle; PEC describes each individual participant's position.

States
------
UNBOUND        – Initial.  This participant is not bound by any embargo terms.
INVITED        – Participant has been invited but has not yet responded.
SIGNATORY      – Participant has accepted the current embargo terms.
LAPSED         – Was SIGNATORY; the owner activated longer terms this
                 participant has not accepted (ADR-0093).
DECLINED       – Participant explicitly refused (a Reject of the Invite, or a
                 consent withdrawal).
EXPIRED        – Participant was invited and the RSVP deadline passed with no
                 answer (ADR-0118).  Not a refusal.
UNBOUND_EXITED – Terminal.  The embargo terminated (EM EXITED); nothing leaves
                 this state (ADR-0118).

Transitions
-----------
INVITE  : UNBOUND | LAPSED | DECLINED | EXPIRED → INVITED
ACCEPT  : UNBOUND | INVITED | LAPSED | EXPIRED → SIGNATORY
DECLINE : UNBOUND | INVITED | LAPSED | SIGNATORY | EXPIRED → DECLINED
REVISE  : SIGNATORY → LAPSED
EXPIRE  : INVITED → EXPIRED  (RSVP deadline passed, CM-28-014)
EXIT    : every state except UNBOUND_EXITED → UNBOUND_EXITED
          (embargo terminated, MSM-07-006)

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
    EXPIRED = "EXPIRED"
    UNBOUND_EXITED = "UNBOUND_EXITED"


class PEC_Trigger(StrEnum):
    """Triggers for the Participant Embargo Consent state machine."""

    # auto() produces lowercase names when stringified, matching transitions lib convention.
    INVITE = auto()
    ACCEPT = auto()
    DECLINE = auto()
    REVISE = auto()
    EXPIRE = auto()
    EXIT = auto()


class PECTransition(TransitionBase):
    trigger: PEC_Trigger
    source: PEC
    dest: PEC


#: The one terminal state: no transition leaves it (ADR-0118).
PEC_TERMINAL_STATES: frozenset[PEC] = frozenset({PEC.UNBOUND_EXITED})


def _pec(trigger: PEC_Trigger, source: PEC, dest: PEC) -> dict:
    return PECTransition(
        trigger=trigger, source=source, dest=dest
    ).model_dump()


_transitions: list[dict] = [
    # INVITE transitions; EXPIRED is re-invitable like DECLINED (EMB-17-003)
    *(
        _pec(PEC_Trigger.INVITE, source, PEC.INVITED)
        for source in (PEC.UNBOUND, PEC.LAPSED, PEC.DECLINED, PEC.EXPIRED)
    ),
    # ACCEPT transitions (ADR-0048: UNBOUND is absence-of-embargo, not
    # pre-consent; ADR-0118: a late Accept the CASE_MANAGER honours moves an
    # EXPIRED participant straight to SIGNATORY, EMB-17-002)
    *(
        _pec(PEC_Trigger.ACCEPT, source, PEC.SIGNATORY)
        for source in (PEC.UNBOUND, PEC.INVITED, PEC.LAPSED, PEC.EXPIRED)
    ),
    # DECLINE transitions (ADR-0048: symmetric with ACCEPT from UNBOUND;
    # ADR-0093: SIGNATORY → DECLINED is consent withdrawal, not a lapse;
    # ADR-0118: a late explicit Reject records DECLINED over EXPIRED)
    *(
        _pec(PEC_Trigger.DECLINE, source, PEC.DECLINED)
        for source in (
            PEC.UNBOUND,
            PEC.INVITED,
            PEC.LAPSED,
            PEC.SIGNATORY,
            PEC.EXPIRED,
        )
    ),
    # REVISE: an active signatory lapses when the owner activates longer terms
    _pec(PEC_Trigger.REVISE, PEC.SIGNATORY, PEC.LAPSED),
    # EXPIRE: the RSVP deadline passed with no answer — not a refusal
    # (ADR-0118, CM-28-014).  DECLINE is never the timer path.
    _pec(PEC_Trigger.EXPIRE, PEC.INVITED, PEC.EXPIRED),
    # EXIT: the embargo terminated (EM EXITED) — every non-terminal state
    # moves to the terminal UNBOUND_EXITED, and nothing leaves it (ADR-0118)
    *(
        _pec(PEC_Trigger.EXIT, source, PEC.UNBOUND_EXITED)
        for source in PEC
        if source not in PEC_TERMINAL_STATES
    ),
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
