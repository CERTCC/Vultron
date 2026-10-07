#!/usr/bin/env python
"""The embargo register's state machine and the EM state derived from it.

A case keeps one register entry for every embargo ever proposed on it
(ADR-0122).  Each entry has one of six statuses:

PROPOSED   – An open proposal, awaiting the case owner's decision.
ACTIVE     – In force.
REJECTED   – The case owner declined the proposal.
SUPERSEDED – Was in force; a revision replaced it.
CANCELLED  – Closed with no owner decision: the embargo question became moot.
TERMINATED – Was in force when the case's embargo ended.

Triggers (``None`` is "no entry yet")
-------------------------------------
PROPOSE   : None → PROPOSED
ACTIVATE  : PROPOSED → ACTIVE
REJECT    : PROPOSED → REJECTED
SUPERSEDE : ACTIVE → SUPERSEDED   (in the step that activates another entry)
TERMINATE : ACTIVE → TERMINATED   (with a :class:`TerminationReason`)
CANCEL    : PROPOSED → CANCELLED  (with a TERMINATE, or on a threat signal
                                   while no entry is ACTIVE)

``REJECTED``, ``SUPERSEDED``, ``CANCELLED`` and ``TERMINATED`` are final.
EM has no transition table of its own: it is :func:`derive_em` over the
register's statuses.  The step rules (which triggers may share a step, and
invariant 4) live with the step itself in
:mod:`vultron.core.models.embargo_register`; this module holds what can be
checked on one set of statuses.
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

from collections import Counter
from collections.abc import Iterable
from enum import StrEnum, auto

from vultron.core.states.em import EM
from vultron.errors import VultronInvalidStateTransitionError


class EmbargoRegisterStatus(StrEnum):
    """Status of one embargo in a case's embargo register."""

    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"
    TERMINATED = "TERMINATED"


class RegisterTrigger(StrEnum):
    """Triggers for one embargo register entry."""

    # auto() produces lowercase names when stringified.
    PROPOSE = auto()
    ACTIVATE = auto()
    REJECT = auto()
    SUPERSEDE = auto()
    TERMINATE = auto()
    CANCEL = auto()


class TerminationReason(StrEnum):
    """Why an ``ACTIVE`` entry was ``TERMINATED`` (ADR-0122)."""

    END_TIME_REACHED = "END_TIME_REACHED"
    EARLY = "EARLY"
    THREAT_SIGNAL = "THREAT_SIGNAL"


_S = EmbargoRegisterStatus
_T = RegisterTrigger

#: Statuses no trigger leaves.
FINAL_REGISTER_STATUSES: frozenset[EmbargoRegisterStatus] = frozenset(
    {_S.REJECTED, _S.SUPERSEDED, _S.CANCELLED, _S.TERMINATED}
)

#: ``trigger → {source → destination}``; a ``None`` source is "no entry yet".
_TRANSITIONS: dict[
    RegisterTrigger, dict[EmbargoRegisterStatus | None, EmbargoRegisterStatus]
] = {
    _T.PROPOSE: {None: _S.PROPOSED},
    _T.ACTIVATE: {_S.PROPOSED: _S.ACTIVE},
    _T.REJECT: {_S.PROPOSED: _S.REJECTED},
    _T.SUPERSEDE: {_S.ACTIVE: _S.SUPERSEDED},
    _T.TERMINATE: {_S.ACTIVE: _S.TERMINATED},
    _T.CANCEL: {_S.PROPOSED: _S.CANCELLED},
}


def register_trigger_is_legal(
    current: EmbargoRegisterStatus | None, trigger: RegisterTrigger
) -> bool:
    """True when *trigger* moves an entry at *current*."""
    return current in _TRANSITIONS[trigger]


def register_status_after(
    current: EmbargoRegisterStatus | None, trigger: RegisterTrigger
) -> EmbargoRegisterStatus:
    """The status *trigger* leaves an entry in, starting from *current*.

    Raises:
        VultronInvalidStateTransitionError: *trigger* is not legal from
            *current*.
    """
    try:
        return _TRANSITIONS[trigger][current]
    except KeyError:
        raise VultronInvalidStateTransitionError(
            f"Embargo register: an entry"
            f" {f'at {current}' if current else 'not yet in the register'}"
            f" does not accept trigger '{trigger}'."
        ) from None


def register_invariant_violations(
    statuses: Iterable[EmbargoRegisterStatus],
) -> list[str]:
    """Every register invariant (1–3 of ADR-0122) that *statuses* break.

    Invariant 4 — no change after a step has left an entry ``TERMINATED`` —
    is about a step, not a set of statuses, so the step checks it.  An empty
    list means the statuses are a legal register.
    """
    counts = Counter(statuses)
    active = counts[_S.ACTIVE]
    terminated = counts[_S.TERMINATED]
    violations: list[str] = []
    if active > 1:
        violations.append(f"{active} entries are ACTIVE (at most one)")
    if terminated > 1:
        violations.append(f"{terminated} entries are TERMINATED (at most one)")
    if active and terminated:
        violations.append("an entry is ACTIVE and another is TERMINATED")
    if counts[_S.SUPERSEDED] and active + terminated != 1:
        violations.append(
            "a SUPERSEDED entry exists without exactly one ACTIVE or"
            " TERMINATED entry"
        )
    if terminated and counts[_S.PROPOSED]:
        violations.append("an entry is PROPOSED while another is TERMINATED")
    return violations


def derive_em(statuses: Iterable[EmbargoRegisterStatus]) -> EM:
    """The case's EM state, read from its register entries' statuses.

    ======  ========  ==========  ========
    ACTIVE  PROPOSED  TERMINATED  EM
    ======  ========  ==========  ========
    0       0         0           NONE
    0       ≥1        0           PROPOSED
    1       0         0           ACTIVE
    1       ≥1        0           REVISE
    0       0         1           EXITED
    ======  ========  ==========  ========

    ``REJECTED``, ``SUPERSEDED`` and ``CANCELLED`` entries do not move EM.

    Raises:
        VultronInvalidStateTransitionError: *statuses* break a register
            invariant, so no row of the table applies.
    """
    statuses = list(statuses)
    violations = register_invariant_violations(statuses)
    if violations:
        raise VultronInvalidStateTransitionError(
            "Embargo register breaks its invariants: " + "; ".join(violations)
        )
    counts = Counter(statuses)
    if counts[_S.TERMINATED]:
        return EM.EXITED
    if counts[_S.ACTIVE]:
        return EM.REVISE if counts[_S.PROPOSED] else EM.ACTIVE
    return EM.PROPOSED if counts[_S.PROPOSED] else EM.NONE
