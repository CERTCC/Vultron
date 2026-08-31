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

"""
The `vultron.core.states.cs` module implements the CVD Case State Model enums.

It also provides functions for converting between state strings and enums.
"""

from enum import Enum, StrEnum
from typing import NamedTuple, Tuple

from transitions import Machine

from vultron.core.case_states.validations import ensure_valid_state
from vultron.core.states.common import TransitionBase, mermaid_machine


class VendorAwareness(StrEnum):
    """
    Represents the vendor awareness state of a case.
    """

    VENDOR_UNAWARE = "v"
    VENDOR_AWARE = "V"

    NO = VENDOR_UNAWARE
    YES = VENDOR_AWARE

    v = VENDOR_UNAWARE
    V = VENDOR_AWARE


class FixReadiness(StrEnum):
    """
    Represents the fix readiness state of a case.
    """

    FIX_NOT_READY = "f"
    FIX_READY = "F"

    NO = FIX_NOT_READY
    YES = FIX_READY

    f = FIX_NOT_READY
    F = FIX_READY


class FixDeployment(StrEnum):
    """
    Represents the fix deployment state of a case.
    """

    FIX_NOT_DEPLOYED = "d"
    FIX_DEPLOYED = "D"

    NO = FIX_NOT_DEPLOYED
    YES = FIX_DEPLOYED

    d = FIX_NOT_DEPLOYED
    D = FIX_DEPLOYED


class PublicAwareness(StrEnum):
    """
    Represents the public awareness state of a case.
    """

    PUBLIC_UNAWARE = "p"
    PUBLIC_AWARE = "P"

    NO = PUBLIC_UNAWARE
    YES = PUBLIC_AWARE

    p = PUBLIC_UNAWARE
    P = PUBLIC_AWARE


class ExploitPublication(StrEnum):
    """
    Represents the exploit publication state of a case.
    """

    NO_PUBLIC_EXPLOIT = "x"
    EXPLOIT_PUBLIC = "X"

    NO = NO_PUBLIC_EXPLOIT
    YES = EXPLOIT_PUBLIC

    x = NO_PUBLIC_EXPLOIT
    X = EXPLOIT_PUBLIC


class AttackObservation(StrEnum):
    """
    Represents the attack observation state of a case.
    """

    NO_ATTACKS_OBSERVED = "a"
    ATTACKS_OBSERVED = "A"

    NO = NO_ATTACKS_OBSERVED
    YES = ATTACKS_OBSERVED

    a = NO_ATTACKS_OBSERVED
    A = ATTACKS_OBSERVED


# a named tuple of the enums above
# todo consider replacing this with a combination of VfdState and PxaState
class State(NamedTuple):
    """Represents the state of a case."""

    vendor_awareness: VendorAwareness
    fix_readiness: FixReadiness
    fix_deployment: FixDeployment
    public_awareness: PublicAwareness
    exploit_publication: ExploitPublication
    attack_observation: AttackObservation


class VfdState(NamedTuple):
    """Represents the vendor fix path state of a case."""

    vendor_awareness: VendorAwareness
    fix_readiness: FixReadiness
    fix_deployment: FixDeployment


class VfState(NamedTuple):
    """Vendor-path sub-machine state (V+F bits only)."""

    vendor_awareness: VendorAwareness
    fix_readiness: FixReadiness


class DState(NamedTuple):
    """Deployer-path sub-machine state (D bit only)."""

    fix_deployment: FixDeployment


class PxaState(NamedTuple):
    """Represents the public exploit path state of a case."""

    public_awareness: PublicAwareness
    exploit_publication: ExploitPublication
    attack_observation: AttackObservation


class CS_vfd(Enum):
    """Represents the vendor fix path state of a case.

    - `vfd` indicates the vendor is unaware, no fix is ready and no fix is deployed.
    - `Vfd` indicates the vendor is aware, no fix is ready and no fix is deployed.
    - `VFd` indicates the vendor is aware, a fix is ready and no fix is deployed.
    - `VFD` indicates the vendor is aware, a fix is ready and a fix is deployed.
    """

    vfd = VfdState(
        VendorAwareness.VENDOR_UNAWARE,
        FixReadiness.FIX_NOT_READY,
        FixDeployment.FIX_NOT_DEPLOYED,
    )
    Vfd = VfdState(
        VendorAwareness.VENDOR_AWARE,
        FixReadiness.FIX_NOT_READY,
        FixDeployment.FIX_NOT_DEPLOYED,
    )
    VFd = VfdState(
        VendorAwareness.VENDOR_AWARE,
        FixReadiness.FIX_READY,
        FixDeployment.FIX_NOT_DEPLOYED,
    )
    VFD = VfdState(
        VendorAwareness.VENDOR_AWARE,
        FixReadiness.FIX_READY,
        FixDeployment.FIX_DEPLOYED,
    )


class CS_pxa(Enum):
    """Represents the public state of a case.

    - `pxa` indicates the public is unaware, no exploit has been published, and no attacks have been observed.
    - `Pxa` indicates the public is aware, no exploit has been published, and no attacks have been observed.
    - `pxA` indicates the public is unaware, no exploit has been published, and attacks have been observed.
    - `PxA` indicates the public is aware, no exploit has been published, and attacks have been observed.
    - `pXa` indicates the public is unaware, an exploit has been published, and no attacks have been observed.
    - `pXA` indicates the public is unaware, an exploit has been published, and attacks have been observed.
    - `PXa` indicates the public is aware, an exploit has been published, and no attacks have been observed.
    - `PXA` indicates the public is aware, an exploit has been published, and attacks have been observed.

    Note that pXa and pXA are ephemeral states: the pX→PX invariant means that once an exploit is
    published the public immediately becomes aware, so these states resolve to PXa/PXA in practice.
    """

    # pxa
    pxa = PxaState(
        PublicAwareness.PUBLIC_UNAWARE,
        ExploitPublication.NO_PUBLIC_EXPLOIT,
        AttackObservation.NO_ATTACKS_OBSERVED,
    )
    # Pxa
    Pxa = PxaState(
        PublicAwareness.PUBLIC_AWARE,
        ExploitPublication.NO_PUBLIC_EXPLOIT,
        AttackObservation.NO_ATTACKS_OBSERVED,
    )
    # pxA
    pxA = PxaState(
        PublicAwareness.PUBLIC_UNAWARE,
        ExploitPublication.NO_PUBLIC_EXPLOIT,
        AttackObservation.ATTACKS_OBSERVED,
    )
    # PxA
    PxA = PxaState(
        PublicAwareness.PUBLIC_AWARE,
        ExploitPublication.NO_PUBLIC_EXPLOIT,
        AttackObservation.ATTACKS_OBSERVED,
    )
    # pXa
    pXa = PxaState(
        PublicAwareness.PUBLIC_UNAWARE,
        ExploitPublication.EXPLOIT_PUBLIC,
        AttackObservation.NO_ATTACKS_OBSERVED,
    )
    # PXa
    PXa = PxaState(
        PublicAwareness.PUBLIC_AWARE,
        ExploitPublication.EXPLOIT_PUBLIC,
        AttackObservation.NO_ATTACKS_OBSERVED,
    )
    # pXA
    pXA = PxaState(
        PublicAwareness.PUBLIC_UNAWARE,
        ExploitPublication.EXPLOIT_PUBLIC,
        AttackObservation.ATTACKS_OBSERVED,
    )
    # PXA
    PXA = PxaState(
        PublicAwareness.PUBLIC_AWARE,
        ExploitPublication.EXPLOIT_PUBLIC,
        AttackObservation.ATTACKS_OBSERVED,
    )


class CS_vf(StrEnum):
    """Vendor-path sub-machine: vendor awareness + fix readiness (3 states).

    Monotone ladder: vf → Vf → VF.
    """

    vf = "vf"
    Vf = "Vf"
    VF = "VF"


class CS_d(StrEnum):
    """Deployer-path sub-machine: fix deployment (2 states).

    Monotone ladder: d → D.
    """

    d = "d"
    D = "D"


class CompoundState(NamedTuple):
    vfd_state: CS_vfd
    pxa_state: CS_pxa


# TODO consider replacing this with a combination of VfdState and PxaState
# either directly or just creating CaseState(BaseModel) class
class CS(Enum):
    # vfd pxa
    vfdpxa = CompoundState(CS_vfd.vfd, CS_pxa.pxa)
    # vfd Pxa
    vfdPxa = CompoundState(CS_vfd.vfd, CS_pxa.Pxa)
    # vfd pXa
    vfdpXa = CompoundState(CS_vfd.vfd, CS_pxa.pXa)
    # vfd pxA
    vfdpxA = CompoundState(CS_vfd.vfd, CS_pxa.pxA)
    # vfd PXa
    vfdPXa = CompoundState(CS_vfd.vfd, CS_pxa.PXa)
    # vfd pXA
    vfdpXA = CompoundState(CS_vfd.vfd, CS_pxa.pXA)
    # vfd PxA
    vfdPxA = CompoundState(CS_vfd.vfd, CS_pxa.PxA)
    # vfd PXA
    vfdPXA = CompoundState(CS_vfd.vfd, CS_pxa.PXA)

    # Vfd pxa
    Vfdpxa = CompoundState(CS_vfd.Vfd, CS_pxa.pxa)
    # vfd Pxa
    VfdPxa = CompoundState(CS_vfd.Vfd, CS_pxa.Pxa)
    # Vfd pXa
    VfdpXa = CompoundState(CS_vfd.Vfd, CS_pxa.pXa)
    # Vfd pxA
    VfdpxA = CompoundState(CS_vfd.Vfd, CS_pxa.pxA)
    # Vfd PXa
    VfdPXa = CompoundState(CS_vfd.Vfd, CS_pxa.PXa)
    # Vfd pXA
    VfdpXA = CompoundState(CS_vfd.Vfd, CS_pxa.pXA)
    # Vfd PxA
    VfdPxA = CompoundState(CS_vfd.Vfd, CS_pxa.PxA)
    # Vfd PXA
    VfdPXA = CompoundState(CS_vfd.Vfd, CS_pxa.PXA)

    # VFd pxa
    VFdpxa = CompoundState(CS_vfd.VFd, CS_pxa.pxa)
    # vfd Pxa
    VFdPxa = CompoundState(CS_vfd.VFd, CS_pxa.Pxa)
    # VFd pXa
    VFdpXa = CompoundState(CS_vfd.VFd, CS_pxa.pXa)
    # VFd pxA
    VFdpxA = CompoundState(CS_vfd.VFd, CS_pxa.pxA)
    # VFd PXa
    VFdPXa = CompoundState(CS_vfd.VFd, CS_pxa.PXa)
    # VFd pXA
    VFdpXA = CompoundState(CS_vfd.VFd, CS_pxa.pXA)
    # VFd PxA
    VFdPxA = CompoundState(CS_vfd.VFd, CS_pxa.PxA)
    # VFd PXA
    VFdPXA = CompoundState(CS_vfd.VFd, CS_pxa.PXA)

    # VFD pxa
    VFDpxa = CompoundState(CS_vfd.VFD, CS_pxa.pxa)
    # vfd Pxa
    VFDPxa = CompoundState(CS_vfd.VFD, CS_pxa.Pxa)
    # VFD pXa
    VFDpXa = CompoundState(CS_vfd.VFD, CS_pxa.pXa)
    # VFD pxA
    VFDpxA = CompoundState(CS_vfd.VFD, CS_pxa.pxA)
    # VFD PXa
    VFDPXa = CompoundState(CS_vfd.VFD, CS_pxa.PXa)
    # VFD pXA
    VFDpXA = CompoundState(CS_vfd.VFD, CS_pxa.pXA)
    # VFD PxA
    VFDPxA = CompoundState(CS_vfd.VFD, CS_pxa.PxA)
    # VFD PXA
    VFDPXA = CompoundState(CS_vfd.VFD, CS_pxa.PXA)


def _last3(s):
    return s[-3:]


def _first3(s):
    return s[:3]


@ensure_valid_state
def vfd(state):
    vfd, pxa = state_string_to_enums(state)
    value = vfd.value
    return value


@ensure_valid_state
def pxa(state):
    vfd, pxa = state_string_to_enums(state)
    value = pxa.value
    return value


@ensure_valid_state
def state_string_to_enums(s: str) -> Tuple[CS_vfd, CS_pxa]:
    """
    Convert a state string to a tuple of enums that define the state `(CS_vfd, CS_pxa)`

    Args:
        s: the state string

    Returns:
        a tuple of enums

    """
    s1, s2 = (s[:3], s[3:])
    vfd = CS_vfd[s1]
    pxa = CS_pxa[s2]
    return (vfd, pxa)


@ensure_valid_state
def state_string_to_enum2(
    s: str,
) -> Tuple[StrEnum, ...]:
    """
    Convert a state string to a list of enums that define the state

    Example:
        ```python
        state_string_to_enum2('vfdpxa')
        ```
        returns
        ```python
        ( VendorAwareness.VENDOR_UNAWARE,
          FixReadiness.FIX_NOT_READY,
          FixDeployment.FIX_NOT_DEPLOYED,
          PublicAwareness.PUBLIC_UNAWARE,
          ExploitPublication.NO_PUBLIC_EXPLOIT,
          AttackObservation.NO_ATTACKS_OBSERVED)
        ```

    Args:
        s: the state string

    Returns:
        a list of Enums
    """
    enums = [
        VendorAwareness,
        FixReadiness,
        FixDeployment,
        PublicAwareness,
        ExploitPublication,
        AttackObservation,
    ]

    resolved_enums = []
    for value, enum in zip(s, enums):
        resolved_enums.append(enum[value])

    return tuple(resolved_enums)


all_states = list(CS)

# --- vfd milestone groups and predicates (LST-04-001) ---

# Vendor is aware of the vulnerability (V bit set).
VFD_VENDOR_AWARE = (CS_vfd.Vfd, CS_vfd.VFd, CS_vfd.VFD)

# Fix has been developed and is ready (F bit set); implies vendor awareness.
VFD_FIX_READY = (CS_vfd.VFd, CS_vfd.VFD)

# Fix has been deployed (D bit set); implies fix readiness and vendor awareness.
VFD_FIX_DEPLOYED = (CS_vfd.VFD,)


def is_vfd_vendor_aware(state: CS_vfd) -> bool:
    """Return True if the vendor is aware of the vulnerability (V bit set).

    Examples::

        is_vfd_vendor_aware(CS_vfd.Vfd)  # True
        is_vfd_vendor_aware(CS_vfd.VFd)  # True
        is_vfd_vendor_aware(CS_vfd.VFD)  # True
        is_vfd_vendor_aware(CS_vfd.vfd)  # False
    """
    return state in VFD_VENDOR_AWARE


def is_vfd_fix_ready(state: CS_vfd) -> bool:
    """Return True if the fix is ready (F bit set; implies vendor awareness).

    Examples::

        is_vfd_fix_ready(CS_vfd.VFd)  # True
        is_vfd_fix_ready(CS_vfd.VFD)  # True
        is_vfd_fix_ready(CS_vfd.Vfd)  # False
        is_vfd_fix_ready(CS_vfd.vfd)  # False
    """
    return state in VFD_FIX_READY


def is_vfd_fix_deployed(state: CS_vfd) -> bool:
    """Return True if the fix is deployed (D bit set).

    Examples::

        is_vfd_fix_deployed(CS_vfd.VFD)  # True
        is_vfd_fix_deployed(CS_vfd.VFd)  # False
        is_vfd_fix_deployed(CS_vfd.vfd)  # False
    """
    return state in VFD_FIX_DEPLOYED


# --- CS_vf milestone groups and predicates ---

# Vendor is aware of the vulnerability (V bit set in the VF path).
VF_VENDOR_AWARE = (CS_vf.Vf, CS_vf.VF)

# Fix has been developed and is ready (F bit set in the VF path).
VF_FIX_READY = (CS_vf.VF,)


def is_vf_vendor_aware(state: CS_vf) -> bool:
    """Return True when vendor awareness is set (V bit in the VF path).

    Examples::

        is_vf_vendor_aware(CS_vf.Vf)  # True
        is_vf_vendor_aware(CS_vf.VF)  # True
        is_vf_vendor_aware(CS_vf.vf)  # False
    """
    return state in VF_VENDOR_AWARE


def is_vf_fix_ready(state: CS_vf) -> bool:
    """Return True when fix readiness is set (F bit; implies vendor awareness).

    Examples::

        is_vf_fix_ready(CS_vf.VF)  # True
        is_vf_fix_ready(CS_vf.Vf)  # False
        is_vf_fix_ready(CS_vf.vf)  # False
    """
    return state in VF_FIX_READY


# --- CS_d milestone groups and predicates ---

# Fix has been deployed (D bit set in the deployer path).
D_FIX_DEPLOYED = (CS_d.D,)


def is_d_fix_deployed(state: CS_d) -> bool:
    """Return True when fix deployment is set (D bit).

    Examples::

        is_d_fix_deployed(CS_d.D)  # True
        is_d_fix_deployed(CS_d.d)  # False
    """
    return state in D_FIX_DEPLOYED


# --- pxa milestone groups and predicates (LST-04-001) ---

# Public is aware of the vulnerability (P bit set).
PXA_PUBLIC_AWARE = (
    CS_pxa.Pxa,
    CS_pxa.PxA,
    CS_pxa.PXa,
    CS_pxa.PXA,
)

# Exploit code is publicly available (X bit set).
# Includes ephemeral pXa/pXA states (X set, P not yet set); those resolve to
# PXa/PXA immediately via the pX→PX invariant but are valid enum values.
PXA_EXPLOIT_PUBLIC = (
    CS_pxa.pXa,
    CS_pxa.pXA,
    CS_pxa.PXa,
    CS_pxa.PXA,
)

# Attacks have been observed in the wild (A bit set).
PXA_ATTACKS_OBSERVED = (
    CS_pxa.pxA,
    CS_pxa.PxA,
    CS_pxa.pXA,
    CS_pxa.PXA,
)


def is_pxa_public_aware(state: CS_pxa) -> bool:
    """Return True if the public is aware of the vulnerability (P bit set).

    Examples::

        is_pxa_public_aware(CS_pxa.Pxa)  # True
        is_pxa_public_aware(CS_pxa.PXA)  # True
        is_pxa_public_aware(CS_pxa.pxa)  # False
    """
    return state in PXA_PUBLIC_AWARE


def is_pxa_exploit_public(state: CS_pxa) -> bool:
    """Return True if exploit code is publicly available (X bit set).

    Note: pX is transient — the pX→PX invariant means an exploit being public
    without public awareness is ephemeral; in practice P will also be set.
    This predicate reflects the X bit only.

    Examples::

        is_pxa_exploit_public(CS_pxa.pXa)  # True
        is_pxa_exploit_public(CS_pxa.PXA)  # True
        is_pxa_exploit_public(CS_pxa.Pxa)  # False
    """
    return state in PXA_EXPLOIT_PUBLIC


def is_pxa_attacks_observed(state: CS_pxa) -> bool:
    """Return True if attacks have been observed in the wild (A bit set).

    Examples::

        is_pxa_attacks_observed(CS_pxa.pxA)  # True
        is_pxa_attacks_observed(CS_pxa.PXA)  # True
        is_pxa_attacks_observed(CS_pxa.pxa)  # False
    """
    return state in PXA_ATTACKS_OBSERVED


class VFD_Trigger(StrEnum):
    V = "vendor_becomes_aware"
    F = "fix_is_ready"
    D = "fix_is_deployed"


class VF_Trigger(StrEnum):
    V = "vendor_becomes_aware"
    F = "fix_is_ready"


class D_Trigger(StrEnum):
    D = "fix_is_deployed"


class PXA_Trigger(StrEnum):
    P = "public_becomes_aware"
    X = "exploit_made_public"
    A = "attacks_are_observed"


class VfdTransition(TransitionBase):
    trigger: VFD_Trigger
    source: CS_vfd
    dest: CS_vfd


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


_vfd_transitions = [
    VfdTransition(
        trigger=VFD_Trigger.V, source=CS_vfd.vfd, dest=CS_vfd.Vfd
    ).model_dump(),
    VfdTransition(
        trigger=VFD_Trigger.F, source=CS_vfd.Vfd, dest=CS_vfd.VFd
    ).model_dump(),
    VfdTransition(
        trigger=VFD_Trigger.D, source=CS_vfd.VFd, dest=CS_vfd.VFD
    ).model_dump(),
]
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


def is_valid_vfd_transition(source: CS_vfd, dest: CS_vfd) -> bool:
    """Return True if (source → dest) is a valid VFD state transition."""
    return any(
        t["source"] == source and t["dest"] == dest for t in _vfd_transitions
    )


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
    source: VfdState | PxaState | str,
    dest: VfdState | PxaState | str,
) -> bool:
    """Return True if *dest* strictly advances *source* with no component
    regressing.

    ``source`` and ``dest`` are the ``NamedTuple`` values of a ``CS_vfd`` or
    ``CS_pxa`` member; their components are compared position-wise.
    """
    if source == dest:
        return False
    return not any(
        _is_component_regression(s, d) for s, d in zip(source, dest)
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


def is_monotonic_vfd_forward(source: CS_vfd, dest: CS_vfd) -> bool:
    """Return True if (source → dest) advances VFD without regressing.

    ``is_valid_vfd_transition`` only recognises the three *adjacent*
    single-component steps of the VFD machine (``vfd → Vfd → VFd → VFD``).
    A peer may legitimately report a state several steps ahead — e.g. a vendor
    that became aware, readied and deployed a fix between two status updates
    reports ``vfd → VFD`` in one message.  That is monotone but not adjacent,
    so it needs this weaker check.

    Equality returns ``False`` (nothing advanced); callers that treat a status
    confirmation as acceptable must test equality separately.  Mirrors
    :func:`vultron.core.states.rm.is_monotonic_rm_forward`.

    Examples::

        is_monotonic_vfd_forward(CS_vfd.vfd, CS_vfd.VFD)  # True
        is_monotonic_vfd_forward(CS_vfd.Vfd, CS_vfd.Vfd)  # False (no change)
        is_monotonic_vfd_forward(CS_vfd.VFd, CS_vfd.Vfd)  # False (F un-set)
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


def create_vfd_machine() -> Machine:
    """
    Generates a new Case State Vendor Fix Deploy Machine object

    Returns:
        Machine: New Machine object
    """
    return Machine(
        states=CS_vfd,
        transitions=_vfd_transitions,
        initial=CS_vfd.vfd,
        auto_transitions=False,
        name="CS VFD State Machine",
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
    print("Vendor Fix Path States")
    for state in CS_vfd:
        print(state, state.name, state.value)
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
    print(mermaid_machine(create_vfd_machine()))
    print(mermaid_machine(create_pxa_machine()))


if __name__ == "__main__":
    main()
