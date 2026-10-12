#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from vultron.core.models.dimensions import (
    DDimension,
    EmDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_status_to_case_activity,
    add_status_to_participant_activity,
    create_case_status_activity,
    create_status_for_participant_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
)
from vultron.wire.as2.vocab.examples._base import (
    _example_stamp,
    case,
    vendor,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)


def case_status(pxa: CS_pxa = CS_pxa.pxa, number: int = 1) -> as_CaseStatus:
    """A case status for the example case, with *pxa* as its public state."""
    status = as_CaseStatus(
        id_=f"https://vultron.example/cases/1/status/{number}",
        context="https://vultron.example/cases/1",
        em=EmDimension(state=EM.EMBARGO_MANAGEMENT_NONE),
        pxa=PxaDimension(state=pxa),
        **_example_stamp(),
    )
    return status


def create_case_status():
    actor = vendor()
    status = case_status()
    _case = case()

    activity = create_case_status_activity(
        status, actor=actor.id_, context=_case.id_
    )
    return activity


def add_status_to_case() -> as_Add:
    _vendor = vendor()
    _case = case()
    _status = case_status()
    activity = add_status_to_case_activity(
        _status, actor=_vendor.id_, target=_case.id_
    )
    return activity


def _add_case_status(pxa: CS_pxa, number: int) -> as_Add:
    """``Add(CaseStatus)`` announcing *pxa* as the case's public state."""
    _case = case()
    return add_status_to_case_activity(
        case_status(pxa, number), actor=vendor().id_, target=_case.id_
    )


def add_public_awareness_to_case() -> as_Add:
    """Public awareness (CP): the case's public state moves to ``Pxa``."""
    return _add_case_status(CS_pxa.Pxa, 2)


def add_exploit_public_to_case() -> as_Add:
    """Exploit public (CX): the case's public state moves to ``PXa``.

    An exploit made public makes the public aware too (the pX → PX
    invariant), so the state is ``PXa`` rather than ``pXa``.
    """
    return _add_case_status(CS_pxa.PXa, 3)


def add_attacks_observed_to_case() -> as_Add:
    """Attacks observed (CA): the case's public state moves to ``pxA``."""
    return _add_case_status(CS_pxa.pxA, 4)


def participant_status() -> as_ParticipantStatus:
    status = as_ParticipantStatus(
        id_="https://vultron.example/cases/1/participants/vendor/status/1",
        context="https://vultron.example/cases/1/participants/vendor",
        attributed_to="https://vultron.example/organizations/vendor",
        rm=RmDimension(state=RM.RECEIVED),
        vf=VfDimension(state=CS_vf.Vf),
        case_status=case_status(),
        **_example_stamp(),
    )
    return status


def create_participant_status() -> as_Create:
    pstatus = participant_status()
    _vendor = vendor()

    activity = create_status_for_participant_activity(
        pstatus, actor=_vendor.id_
    )
    return activity


def _add_participant_status(
    number: int,
    role: CVDRole,
    vf: CS_vf | None = None,
    d: CS_d | None = None,
) -> as_Add:
    """``Add(ParticipantStatus)`` announcing a vendor- or deployer-path state.

    The sender is the participant whose state changed: the example Vendor for
    the vendor path, an example Deployer for the deployer path.
    """
    slug = "deployer" if role is CVDRole.DEPLOYER else "vendor"
    sender_id = (
        vendor().id_
        if role is CVDRole.VENDOR
        else "https://vultron.example/organizations/deployer"
    )
    participant_id = f"https://vultron.example/cases/1/participants/{slug}"
    pstatus = as_ParticipantStatus(
        id_=f"{participant_id}/status/{number}",
        context=participant_id,
        attributed_to=f"https://vultron.example/organizations/{slug}",
        rm=RmDimension(state=RM.ACCEPTED),
        vf=None if vf is None else VfDimension(state=vf),
        d=None if d is None else DDimension(state=d),
        cvd_role=[role],
        case_status=case_status(),
        **_example_stamp(),
    )
    return add_status_to_participant_activity(
        pstatus, actor=sender_id, target=participant_id
    )


def add_vendor_awareness_to_participant() -> as_Add:
    """Vendor awareness (CV): the Vendor's ``vf_state`` moves to ``Vf``."""
    return _add_participant_status(2, CVDRole.VENDOR, vf=CS_vf.Vf)


def add_fix_readiness_to_participant() -> as_Add:
    """Fix readiness (CF): the Vendor's ``vf_state`` moves to ``VF``."""
    return _add_participant_status(3, CVDRole.VENDOR, vf=CS_vf.VF)


def add_fix_deployment_to_participant() -> as_Add:
    """Fix deployed (CD): the Deployer's ``d_state`` moves to ``D``."""
    return _add_participant_status(4, CVDRole.DEPLOYER, d=CS_d.D)


def add_status_to_participant() -> as_Add:
    _vendor = vendor()
    pstatus = participant_status()

    activity = add_status_to_participant_activity(
        pstatus,
        actor=_vendor.id_,
        target="https://vultron.example/cases/1/participants/vendor",
    )
    return activity
