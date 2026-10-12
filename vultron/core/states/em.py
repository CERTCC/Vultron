#!/usr/bin/env python
"""This module defines the Embargo Management states for the Vultron protocol.

A case's EM state is never set directly: it is derived from its embargo
register (ADR-0122, :func:`vultron.core.states.embargo_register.derive_em`).
The EM state machine still governs it: every register step names an EM
trigger, and must move EM along one of that trigger's transitions in
:data:`EM_TRANSITIONS` (ADR-0130, EMB-18-005, EMB-18-006).  The table adds a
rule the derivation must obey, not a second way to set EM.
"""

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

from collections.abc import Mapping
from enum import StrEnum, auto
from types import MappingProxyType

from transitions import Machine


class EM(StrEnum):
    """Embargo Management States

    NONE: No embargo is in effect
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

    N = NONE
    P = PROPOSED
    A = ACTIVE
    R = REVISE
    X = EXITED


class EM_Trigger(StrEnum):
    """Embargo Management state machine triggers (ADR-0130)."""

    # auto() makes these lowercase when stringified
    PROPOSE = auto()
    ACCEPT = auto()
    REJECT = auto()
    TERMINATE = auto()


#: The EM transition table (ADR-0130, EMB-18-005): ``trigger → {(source,
#: destination)}``.  With several proposals open, EM leaves ``PROPOSED`` or
#: ``REVISE`` only when the last open proposal is off the table, so ``reject``
#: and ``accept`` each have a move that stays put.  Normative: every embargo
#: register step is checked against it (EMB-18-006).
EM_TRANSITIONS: Mapping[EM_Trigger, frozenset[tuple[EM, EM]]] = (
    MappingProxyType(
        {
            EM_Trigger.PROPOSE: frozenset(
                {
                    (EM.NONE, EM.PROPOSED),
                    (EM.PROPOSED, EM.PROPOSED),
                    (EM.ACTIVE, EM.REVISE),
                    (EM.REVISE, EM.REVISE),
                }
            ),
            EM_Trigger.REJECT: frozenset(
                {
                    (EM.PROPOSED, EM.NONE),
                    (EM.PROPOSED, EM.PROPOSED),
                    (EM.REVISE, EM.ACTIVE),
                    (EM.REVISE, EM.REVISE),
                }
            ),
            EM_Trigger.ACCEPT: frozenset(
                {
                    (EM.PROPOSED, EM.ACTIVE),
                    (EM.PROPOSED, EM.REVISE),
                    (EM.REVISE, EM.ACTIVE),
                    (EM.REVISE, EM.REVISE),
                }
            ),
            EM_Trigger.TERMINATE: frozenset(
                {(EM.ACTIVE, EM.EXITED), (EM.REVISE, EM.EXITED)}
            ),
        }
    )
)


def is_em_transition(trigger: EM_Trigger, source: EM, dest: EM) -> bool:
    """True when *trigger* may move EM from *source* to *dest* (ADR-0130).

    Reads :data:`EM_TRANSITIONS` when called, so the register step and every
    other caller check against the one table.
    """
    return (source, dest) in EM_TRANSITIONS.get(trigger, frozenset())


def em_transition_rows() -> list[dict[str, str]]:
    """:data:`EM_TRANSITIONS` as ``{trigger, source, dest}`` rows.

    In table order, then by source and destination as the :class:`EM`
    enum orders them, so an export (the demo state export, #4427) is
    deterministic.  The rows are the ``transitions`` form
    :func:`create_em_machine` builds from.
    """
    order = list(EM)
    return [
        {"trigger": str(trigger), "source": str(src), "dest": str(dst)}
        for trigger, moves in EM_TRANSITIONS.items()
        for src, dst in sorted(
            moves, key=lambda m: (order.index(m[0]), order.index(m[1]))
        )
    ]


def create_em_machine() -> Machine:
    """The EM state machine, built from :data:`EM_TRANSITIONS`.

    For tools that draw or export the machine (``mermaid_machine``, the demo
    state export).  A case's EM is never moved by this machine: it is derived
    from the embargo register (ADR-0122), under this table (ADR-0130).
    """
    return Machine(
        states=[str(state) for state in EM],
        transitions=em_transition_rows(),
        initial=str(EM.NONE),
        auto_transitions=False,
        name="EM FSM",
    )


def is_em_assertion_acceptable(current: EM, asserted: EM) -> bool:
    """Return True if a received CaseStatus's EM may be accepted.

    The EM acceptance rule for a received ``CaseStatus`` (RSH-05-023): EM is
    derived from the case's embargo register (ADR-0122), so a status can
    only carry the EM the receiver already derives — it never moves EM.  The
    CASE_MANAGER's ``FilterCsEmDimensionNode`` and the replica's
    ``ApplyCaseStatusFromLedgerNode`` both apply it, so the two sides of the
    ledger cannot adjudicate EM differently.
    """
    return asserted == current


# Named EM state subsets (SM-07-001 style convenience constants)
# Example: EM_NEGOTIATING groups states where embargo negotiation is ongoing
EM_NEGOTIATING = (EM.PROPOSED, EM.REVISE)

# States where an embargo is currently in force.
# Once an entry is ACTIVE the register never returns EM to NONE/PROPOSED.
EM_EMBARGO_ACTIVE = (EM.ACTIVE, EM.REVISE)


def is_em_embargo_active(state: EM) -> bool:
    """Return True if an embargo is currently in force (ACTIVE or REVISE).

    The REVISE state retains the active embargo while a revision is negotiated;
    the embargo remains in force until EXITED.

    Examples::

        is_em_embargo_active(EM.ACTIVE)   # True
        is_em_embargo_active(EM.REVISE)   # True
        is_em_embargo_active(EM.PROPOSED) # False
        is_em_embargo_active(EM.EXITED)   # False
    """
    return state in EM_EMBARGO_ACTIVE


def is_em_exited(state: EM) -> bool:
    """Return True if the embargo has been exited (terminated).

    Examples::

        is_em_exited(EM.EXITED)   # True
        is_em_exited(EM.ACTIVE)   # False
        is_em_exited(EM.PROPOSED) # False
    """
    return state == EM.EXITED
