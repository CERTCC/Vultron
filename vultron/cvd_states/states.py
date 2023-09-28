#!/usr/bin/env python
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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
The `vultron.cvd_states.states` module implements the CVD Case State Model enums.

It also provides functions for converting between state strings and enums.
"""

from enum import Enum, Flag, IntEnum
from typing import List, NamedTuple, Tuple

from vultron.cvd_states.validations import ensure_valid_state


@ensure_valid_state
def state_string_to_enums(s: str) -> Tuple[Enum]:
    """
    Convert a state string to a tuple of enums that define the state `(CS_vfd, CS_pxa)`

    Args:
        s: the state string

    Returns:
        a tuple of enums

    """
    (s1, s2) = (s[:3], s[3:])
    vfd = CS_vfd[s1]
    pxa = CS_pxa[s2]
    return (vfd, pxa)


@ensure_valid_state
def state_string_to_enum2(s: str) -> Tuple[Enum]:
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


class VendorAwareness(IntEnum):
    """
    Represents the vendor awareness state of a case.
    """

    VENDOR_UNAWARE = 0
    VENDOR_AWARE = 1

    NO = VENDOR_UNAWARE
    YES = VENDOR_AWARE

    v = VENDOR_UNAWARE
    V = VENDOR_AWARE


class FixReadiness(IntEnum):
    """
    Represents the fix readiness state of a case.
    """

    FIX_NOT_READY = 0
    FIX_READY = 1

    NO = FIX_NOT_READY
    YES = FIX_READY

    f = FIX_NOT_READY
    F = FIX_READY


class FixDeployment(IntEnum):
    """
    Represents the fix deployment state of a case.
    """

    FIX_NOT_DEPLOYED = 0
    FIX_DEPLOYED = 1

    NO = FIX_NOT_DEPLOYED
    YES = FIX_DEPLOYED

    d = FIX_NOT_DEPLOYED
    D = FIX_DEPLOYED


class PublicAwareness(IntEnum):
    """
    Represents the public awareness state of a case.
    """

    PUBLIC_UNAWARE = 0
    PUBLIC_AWARE = 1

    NO = PUBLIC_UNAWARE
    YES = PUBLIC_AWARE

    p = PUBLIC_UNAWARE
    P = PUBLIC_AWARE


class ExploitPublication(IntEnum):
    """
    Represents the exploit publication state of a case.
    """

    NO_PUBLIC_EXPLOIT = 0
    EXPLOIT_PUBLIC = 1

    NO = NO_PUBLIC_EXPLOIT
    YES = EXPLOIT_PUBLIC

    x = NO_PUBLIC_EXPLOIT
    X = EXPLOIT_PUBLIC


class AttackObservation(IntEnum):
    """
    Represents the attack observation state of a case.
    """

    NO_ATTACKS_OBSERVED = 0
    ATTACKS_OBSERVED = 1

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
    - `Pxa` indicates the public is aware, an exploit has been published, and no attacks have been observed.
    - `PXA` indicates the public is aware, an exploit has been published, and attacks have been observed.

    Note that pXa and pXA are not valid states because once an exploit is published, the public is aware.
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


class CompoundState(NamedTuple):
    vfd_state: VfdState
    pxa_state: PxaState


# TODO this is still broken
class CS_vfdpxa(Enum):
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


class CS(Flag):
    """Represents the state of a case. The state is a combination of the vendor fix path state and the public state.

    Vendor fix path states:
    v = vendor unaware
    V = vendor aware

    f = fix not ready
    F = fix ready

    d = fix not deployed
    D = fix deployed

    Public case states:
    p = public unaware
    P = public aware

    x = exploit not published
    X = exploit published

    a = attacks not observed
    A = attacks observed
    """

    vfDpxa = 32
    vFdpxa = 16
    Vfdpxa = 8
    vfdPxa = 4
    vfdpXa = 2
    vfdpxA = 1
    vfdpxa = 0

    D = vfDpxa
    F = vFdpxa
    V = Vfdpxa
    P = vfdPxa
    X = vfdpXa
    A = vfdpxA

    VFdpxa = V | F
    VFDpxa = V | F | D

    vfdpXA = X | A
    vfdPxA = P | A
    vfdPXa = P | X
    vfdPXA = P | X | A

    VfdpxA = V | A
    VfdpXa = V | X
    VfdpXA = V | X | A
    VfdPxa = V | P
    VfdPxA = V | P | A
    VfdPXa = V | P | X
    VfdPXA = V | P | X | A

    VFdpxA = V | F | A
    VFdpXa = V | F | X
    VFdpXA = V | F | X | A
    VFdPxa = V | F | P
    VFdPxA = V | F | P | A
    VFdPXa = V | F | P | X
    VFdPXA = V | F | P | X | A

    VFDpxA = V | F | D | A
    VFDpXa = V | F | D | X
    VFDpXA = V | F | D | X | A
    VFDPxa = V | F | D | P
    VFDPxA = V | F | D | P | A
    VFDPXa = V | F | D | P | X
    VFDPXA = V | F | D | P | X | A

    vfd = vfdpxa
    Vfd = Vfdpxa
    VFd = VFdpxa
    VFD = VFDpxa

    pxa = vfdpxa
    Pxa = vfdPxa
    pXa = vfdpXa
    pxA = vfdpxA
    PXa = vfdPXa
    pXA = vfdpXA
    PxA = vfdPxA
    PXA = vfdPXA

    # pairs
    VF = VFdpxa
    VP = VfdPxa
    VX = VfdpXa
    VA = VfdpxA

    # triples
    VFP = VFdPxa
    VFX = VFdpXa
    VFA = VFdpxA
    VPA = VfdPxA
    VPX = VfdPXa
    VXA = VfdpXA

    # quads
    VFDP = VFDPxa
    VFDX = VFDpXa
    VFDA = VFDpxA

    VFPX = VFdPXa
    VFPA = VFdPxA
    VFXA = VFdpXA

    VPXA = VfdPXA

    # quintuples
    VFDPA = VFDPxA
    VFDPX = VFDPXa
    VFDXA = VFDpXA
    VFPXA = VFdPXA


# convenience aliases for the states
all_states = (
    # vendor unaware
    CS.vfdpxa,
    CS.vfdpxA,
    CS.vfdpXa,
    CS.vfdpXA,
    CS.vfdPxa,
    CS.vfdPxA,
    CS.vfdPXa,
    CS.vfdPXA,
    # vendor aware, fix not ready
    CS.Vfdpxa,
    CS.VfdpxA,
    CS.VfdpXa,
    CS.VfdpXA,
    CS.VfdPxa,
    CS.VfdPxA,
    CS.VfdPXa,
    CS.VfdPXA,
    # vendor aware, fix ready, fix not deployed
    CS.VFdpxa,
    CS.VFdpxA,
    CS.VFdpXa,
    CS.VFdpXA,
    CS.VFdPxa,
    CS.VFdPxA,
    CS.VFdPXa,
    CS.VFdPXA,
    # vendor aware, fix ready, fix deployed
    CS.VFDpxa,
    CS.VFDpxA,
    CS.VFDpXa,
    CS.VFDpXA,
    CS.VFDPxa,
    CS.VFDPxA,
    CS.VFDPXa,
    CS.VFDPXA,
)


def _last3(s):
    return s[-3:]


def _first3(s):
    return s[:3]


@ensure_valid_state
def vfd(state):
    (vfd, pxa) = state_string_to_enums(state)
    value = vfd.value
    return value


@ensure_valid_state
def pxa(state):
    (vfd, pxa) = state_string_to_enums(state)
    value = pxa.value
    return value


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


if __name__ == "__main__":
    main()
