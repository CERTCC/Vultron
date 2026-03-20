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
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""
Provides an enumeration of Report Management states.
"""

import logging
from enum import StrEnum, auto

from transitions import Machine

from vultron.core.states.common import TransitionBase, mermaid_machine

logger = logging.getLogger(__name__)


class RM(StrEnum):
    """
    Report Management States

    START: Report has not yet been received
    RECEIVED: Report has been received but not yet validated
    INVALID: Report has been received but is invalid
    VALID: Report has been received and is valid
    DEFERRED: Report has been received and is valid but has been deferred
    ACCEPTED: Report has been received, is valid, and has been accepted
    CLOSED: Report has been closed
    """

    # convenience aliases
    START = "START"
    RECEIVED = "RECEIVED"
    INVALID = "INVALID"
    VALID = "VALID"
    DEFERRED = "DEFERRED"
    ACCEPTED = "ACCEPTED"
    CLOSED = "CLOSED"

    REPORT_MANAGEMENT_START = START
    REPORT_MANAGEMENT_RECEIVED = RECEIVED
    REPORT_MANAGEMENT_INVALID = INVALID
    REPORT_MANAGEMENT_VALID = VALID
    REPORT_MANAGEMENT_DEFERRED = DEFERRED
    REPORT_MANAGEMENT_ACCEPTED = ACCEPTED
    REPORT_MANAGEMENT_CLOSED = CLOSED

    S = START
    R = RECEIVED
    I = INVALID  # noqa: E741
    V = VALID
    D = DEFERRED
    A = ACCEPTED
    C = CLOSED


# Report Management States that can be closed
RM_CLOSABLE = (
    RM.INVALID,
    RM.DEFERRED,
    RM.ACCEPTED,
)

# Report Management States that are not closed
RM_UNCLOSED = (
    RM.START,
    RM.RECEIVED,
    RM.INVALID,
    RM.VALID,
    RM.DEFERRED,
    RM.ACCEPTED,
)

# Report Management States that are active
RM_ACTIVE = (
    RM.RECEIVED,
    RM.VALID,
    RM.ACCEPTED,
)


class RM_Trigger(StrEnum):
    """
    Enumerates Report Management State Triggers

    RECEIVE: when a report is received
    VALIDATE: when a report is validated
    INVALIDATE: when a report is invalidated
    ACCEPT: when a report is accepted
    DEFER: when a report is deferred (soft close, may be reopened)
    CLOSE: when a report is closed (hard close, no reopening)
    """

    # auto() makes these lowercase when stringified
    RECEIVE = auto()
    VALIDATE = auto()
    INVALIDATE = auto()
    ACCEPT = auto()
    DEFER = auto()
    CLOSE = auto()


class RmTransition(TransitionBase):
    trigger: RM_Trigger
    source: RM
    dest: RM


_transitions = [
    RmTransition(
        trigger=RM_Trigger.RECEIVE, source=RM.START, dest=RM.RECEIVED
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.VALIDATE, source=RM.RECEIVED, dest=RM.VALID
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.INVALIDATE, source=RM.RECEIVED, dest=RM.INVALID
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.VALIDATE, source=RM.INVALID, dest=RM.VALID
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.ACCEPT, source=RM.VALID, dest=RM.ACCEPTED
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.ACCEPT, source=RM.DEFERRED, dest=RM.ACCEPTED
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.DEFER, source=RM.VALID, dest=RM.DEFERRED
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.DEFER, source=RM.ACCEPTED, dest=RM.DEFERRED
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.CLOSE, source=RM.ACCEPTED, dest=RM.CLOSED
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.CLOSE, source=RM.INVALID, dest=RM.CLOSED
    ).model_dump(),
    RmTransition(
        trigger=RM_Trigger.CLOSE, source=RM.DEFERRED, dest=RM.CLOSED
    ).model_dump(),
]


def is_valid_rm_transition(source: RM, dest: RM) -> bool:
    """Return True if (source → dest) is a valid RM state transition."""
    return any(
        t["source"] == source and t["dest"] == dest for t in _transitions
    )


def create_rm_machine() -> Machine:
    """
    Generates a new Report Management State Machine object

    Returns:
        A transitions Machine object representing the Report Management state machine

    """
    return Machine(
        states=RM,
        transitions=_transitions,
        initial=RM.START,
        auto_transitions=False,
        name="RM FSM",
    )


if __name__ == "__main__":
    M = create_rm_machine()
    print(mermaid_machine(M))
