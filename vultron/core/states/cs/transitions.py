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


"""The CS sub-machine triggers, transition tables and transition checks."""

from enum import StrEnum

from vultron.core.states.common import TransitionBase
from vultron.core.states.cs.states import (
    CS_d,
    CS_pxa,
    CS_vf,
    DState,
    PxaState,
    VfState,
)


class VF_Trigger(StrEnum):
    V = "vendor_becomes_aware"
    F = "fix_is_ready"


class D_Trigger(StrEnum):
    D = "fix_is_deployed"


class PXA_Trigger(StrEnum):
    P = "public_becomes_aware"
    X = "exploit_made_public"
    A = "attacks_are_observed"


class VfTransition(TransitionBase):
    trigger: VF_Trigger
    source: CS_vf
    dest: CS_vf


class DTransition(TransitionBase):
    trigger: D_Trigger
    source: CS_d
    dest: CS_d


class PxaTransition(TransitionBase):
    trigger: PXA_Trigger
    source: CS_pxa
    dest: CS_pxa


_vf_transitions = [
    VfTransition(
        trigger=VF_Trigger.V, source=CS_vf.vf, dest=CS_vf.Vf
    ).model_dump(),
    VfTransition(
        trigger=VF_Trigger.F, source=CS_vf.Vf, dest=CS_vf.VF
    ).model_dump(),
]
_d_transitions = [
    DTransition(trigger=D_Trigger.D, source=CS_d.d, dest=CS_d.D).model_dump(),
]
_pxa_transitions = [
    PxaTransition(
        trigger=PXA_Trigger.P, source=CS_pxa.pxa, dest=CS_pxa.Pxa
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.P, source=CS_pxa.pxA, dest=CS_pxa.PxA
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.P, source=CS_pxa.pXa, dest=CS_pxa.PXa
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.P, source=CS_pxa.pXA, dest=CS_pxa.PXA
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.X, source=CS_pxa.pxa, dest=CS_pxa.pXa
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.X, source=CS_pxa.pxA, dest=CS_pxa.pXA
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.X, source=CS_pxa.Pxa, dest=CS_pxa.PXa
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.X, source=CS_pxa.PxA, dest=CS_pxa.PXA
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.A, source=CS_pxa.pxa, dest=CS_pxa.pxA
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.A, source=CS_pxa.Pxa, dest=CS_pxa.PxA
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.A, source=CS_pxa.pXa, dest=CS_pxa.pXA
    ).model_dump(),
    PxaTransition(
        trigger=PXA_Trigger.A, source=CS_pxa.PXa, dest=CS_pxa.PXA
    ).model_dump(),
]


def is_valid_vf_transition(source: CS_vf, dest: CS_vf) -> bool:
    """Return True if (source → dest) is a valid VF state transition."""
    return any(
        t["source"] == source and t["dest"] == dest for t in _vf_transitions
    )


def is_valid_d_transition(source: CS_d, dest: CS_d) -> bool:
    """Return True if (source → dest) is a valid D state transition."""
    return any(
        t["source"] == source and t["dest"] == dest for t in _d_transitions
    )


def is_valid_pxa_transition(source: CS_pxa, dest: CS_pxa) -> bool:
    """Return True if (source → dest) is a valid PXA state transition."""
    return any(
        t["source"] == source and t["dest"] == dest for t in _pxa_transitions
    )


def _is_component_regression(
    source_component: str, dest_component: str
) -> bool:
    """Return True if a single V/F/D or P/X/A component un-sets itself.

    Each component is a two-valued flag whose lowercase form means "has not
    happened yet" and whose uppercase form means "has happened" (e.g.
    ``VendorAwareness.VENDOR_UNAWARE = "v"`` vs ``VENDOR_AWARE = "V"``).
    Every one of these facts is a one-way latch: once a vendor is aware, a fix
    is ready, an exploit is public, or attacks are observed, that cannot become
    untrue.  A component therefore regresses exactly when it goes from
    uppercase to lowercase.
    """
    return str(source_component).isupper() and str(dest_component).islower()


def _is_monotonic_forward(
    source: VfState | DState | PxaState | str,
    dest: VfState | DState | PxaState | str,
) -> bool:
    """Return True if *dest* strictly advances *source* with no component
    regressing.

    ``source`` and ``dest`` are the ``NamedTuple`` values of a ``CS_vf``,
    ``CS_d``, or ``CS_pxa`` member; their components are compared position-wise.
    """
    if source == dest:
        return False
    return not any(
        _is_component_regression(s, d)
        for s, d in zip(source, dest, strict=False)
    )


def is_monotonic_vf_forward(source: CS_vf, dest: CS_vf) -> bool:
    """Return True if (source → dest) advances VF without regressing.

    Examples::

        is_monotonic_vf_forward(CS_vf.vf, CS_vf.VF)  # True
        is_monotonic_vf_forward(CS_vf.Vf, CS_vf.Vf)  # False (no change)
        is_monotonic_vf_forward(CS_vf.VF, CS_vf.Vf)  # False (F un-set)
    """
    return _is_monotonic_forward(source.value, dest.value)


def is_monotonic_d_forward(source: CS_d, dest: CS_d) -> bool:
    """Return True if (source → dest) advances D without regressing.

    Examples::

        is_monotonic_d_forward(CS_d.d, CS_d.D)  # True
        is_monotonic_d_forward(CS_d.D, CS_d.d)  # False (D un-set)
        is_monotonic_d_forward(CS_d.d, CS_d.d)  # False (no change)
    """
    return _is_monotonic_forward(source.value, dest.value)


def is_monotonic_pxa_forward(source: CS_pxa, dest: CS_pxa) -> bool:
    """Return True if (source → dest) advances PXA without regressing.

    The P/X/A components are mutually independent one-way latches, so any
    combination of them being newly set is monotone forward — including
    multi-component jumps such as ``pxa → PXA`` that
    :func:`is_valid_pxa_transition` does not recognise.

    Equality returns ``False`` (nothing advanced).  Mirrors
    :func:`vultron.core.states.rm.is_monotonic_rm_forward`.

    Examples::

        is_monotonic_pxa_forward(CS_pxa.pxa, CS_pxa.PXa)  # True
        is_monotonic_pxa_forward(CS_pxa.Pxa, CS_pxa.pxa)  # False (P un-set)
        is_monotonic_pxa_forward(CS_pxa.PxA, CS_pxa.PXa)  # False (A un-set)
    """
    return _is_monotonic_forward(source.value, dest.value)


def is_pxa_assertion_acceptable(current: CS_pxa, asserted: CS_pxa) -> bool:
    """Return True if a received CaseStatus may move PXA *current* → *asserted*.

    The PXA acceptance rule for a received status (RSH-09-003, RSH-09-005):
    the asserted state is the current one, or a monotone forward move from
    it.  Deliberately weaker than :func:`is_valid_pxa_transition`, which
    applies only to local writes (CSB-16-002).  The CASE_MANAGER applies it
    to a received ``CaseStatus`` and ``ParticipantStatus`` and when adopting a
    report's P/X/A; a replica copies the entry instead (CM-23-016).
    """
    return asserted == current or is_monotonic_pxa_forward(current, asserted)
