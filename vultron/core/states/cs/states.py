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


"""The CVD Case State compound enums: ``CS_vf``, ``CS_d``, ``CS_pxa`` and ``CS``.

The 32 members of ``CS`` are the valid compound states (ADR-0060,
ADR-0075).
"""

from enum import Enum, StrEnum
from typing import NamedTuple

from vultron.core.states.cs.dimensions import (
    AttackObservation,
    ExploitPublication,
    FixDeployment,
    FixReadiness,
    PublicAwareness,
    VendorAwareness,
)


# a named tuple of the enums above.
# NOTE (CONCERN-2099, planning group G06 / #2834): the earlier TODO here
# contemplated replacing this with a combination of VfdState and PxaState, or
# introducing a CaseState(BaseModel). The verdict is to KEEP the compound
# representation: the split sub-machine enums (CS_vf / CS_d / CS_pxa) already
# give structured decomposition (ADR-0075), and the monolithic CS is retained
# for the legacy vultron/bt/ simulator. No CaseState(BaseModel) is introduced.
# See notes/case-state-model.md § "CS Representation: Keep the Compound Enum".
class State(NamedTuple):
    """Represents the state of a case."""

    vendor_awareness: VendorAwareness
    fix_readiness: FixReadiness
    fix_deployment: FixDeployment
    public_awareness: PublicAwareness
    exploit_publication: ExploitPublication
    attack_observation: AttackObservation


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
    vf_state: CS_vf
    d_state: CS_d
    pxa_state: CS_pxa


class CS(Enum):
    # vf=vf, d=d
    vfdpxa = CompoundState(CS_vf.vf, CS_d.d, CS_pxa.pxa)
    vfdPxa = CompoundState(CS_vf.vf, CS_d.d, CS_pxa.Pxa)
    vfdpXa = CompoundState(CS_vf.vf, CS_d.d, CS_pxa.pXa)
    vfdpxA = CompoundState(CS_vf.vf, CS_d.d, CS_pxa.pxA)
    vfdPXa = CompoundState(CS_vf.vf, CS_d.d, CS_pxa.PXa)
    vfdpXA = CompoundState(CS_vf.vf, CS_d.d, CS_pxa.pXA)
    vfdPxA = CompoundState(CS_vf.vf, CS_d.d, CS_pxa.PxA)
    vfdPXA = CompoundState(CS_vf.vf, CS_d.d, CS_pxa.PXA)

    # vf=Vf, d=d
    Vfdpxa = CompoundState(CS_vf.Vf, CS_d.d, CS_pxa.pxa)
    VfdPxa = CompoundState(CS_vf.Vf, CS_d.d, CS_pxa.Pxa)
    VfdpXa = CompoundState(CS_vf.Vf, CS_d.d, CS_pxa.pXa)
    VfdpxA = CompoundState(CS_vf.Vf, CS_d.d, CS_pxa.pxA)
    VfdPXa = CompoundState(CS_vf.Vf, CS_d.d, CS_pxa.PXa)
    VfdpXA = CompoundState(CS_vf.Vf, CS_d.d, CS_pxa.pXA)
    VfdPxA = CompoundState(CS_vf.Vf, CS_d.d, CS_pxa.PxA)
    VfdPXA = CompoundState(CS_vf.Vf, CS_d.d, CS_pxa.PXA)

    # vf=VF, d=d
    VFdpxa = CompoundState(CS_vf.VF, CS_d.d, CS_pxa.pxa)
    VFdPxa = CompoundState(CS_vf.VF, CS_d.d, CS_pxa.Pxa)
    VFdpXa = CompoundState(CS_vf.VF, CS_d.d, CS_pxa.pXa)
    VFdpxA = CompoundState(CS_vf.VF, CS_d.d, CS_pxa.pxA)
    VFdPXa = CompoundState(CS_vf.VF, CS_d.d, CS_pxa.PXa)
    VFdpXA = CompoundState(CS_vf.VF, CS_d.d, CS_pxa.pXA)
    VFdPxA = CompoundState(CS_vf.VF, CS_d.d, CS_pxa.PxA)
    VFdPXA = CompoundState(CS_vf.VF, CS_d.d, CS_pxa.PXA)

    # vf=VF, d=D
    VFDpxa = CompoundState(CS_vf.VF, CS_d.D, CS_pxa.pxa)
    VFDPxa = CompoundState(CS_vf.VF, CS_d.D, CS_pxa.Pxa)
    VFDpXa = CompoundState(CS_vf.VF, CS_d.D, CS_pxa.pXa)
    VFDpxA = CompoundState(CS_vf.VF, CS_d.D, CS_pxa.pxA)
    VFDPXa = CompoundState(CS_vf.VF, CS_d.D, CS_pxa.PXa)
    VFDpXA = CompoundState(CS_vf.VF, CS_d.D, CS_pxa.pXA)
    VFDPxA = CompoundState(CS_vf.VF, CS_d.D, CS_pxa.PxA)
    VFDPXA = CompoundState(CS_vf.VF, CS_d.D, CS_pxa.PXA)
