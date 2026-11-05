#!/usr/bin/env python

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
"""Tests for the on-behalf shape rule of the status-subject guard (RSH-08-014)."""

import pytest

from test.support.participant_status import impossible_state_reasons
from vultron.core.behaviors.status.nodes.status_subject import (
    on_behalf_status_roles,
    on_behalf_status_violations,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    DDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

_CASE = "https://example.org/cases/c1"


def _status(
    rm: RM = RM.ACCEPTED,
    vf: CS_vf | None = None,
    d: CS_d | None = None,
    case_status: CaseStatus | None = None,
) -> ParticipantStatus:
    roles = [
        *([CVDRole.VENDOR] if vf is not None else []),
        *([CVDRole.DEPLOYER] if d is not None else []),
    ]
    return ParticipantStatus(
        context=_CASE,
        rm=RmDimension(state=rm),
        vf=VfDimension(state=vf) if vf is not None else None,
        d=DDimension(state=d) if d is not None else None,
        cvd_role=roles or [CVDRole.OBSERVER],
        case_status=case_status,
    )


@pytest.mark.spec("RSH-08-007")
@pytest.mark.spec("RSH-08-014")
@pytest.mark.spec("CSB-17-001")
def test_both_moves_together_are_one_on_behalf_assertion():
    """RSH-08-014's "or both" passes the shape rule and no further.

    The only status that carries both on-behalf moves is ``v→V`` plus ``d→D``,
    which lands the target on the compound state ``VfD`` — a fix deployed
    before it was ready, one of the combinations CSB-17-001 rules out.  So the
    fixture is deliberately in an impossible state, and the test says so: the
    shape rule admits it, and the entailment rule that PRM-06-008 requires
    downstream refuses it.  Without the second assertion this test would read
    as "both moves together are accepted", which is not what happens (#3046).
    """
    status = _status(vf=CS_vf.Vf, d=CS_d.D)

    assert (
        on_behalf_status_violations(RM.ACCEPTED, CS_vf.vf, CS_d.d, status)
        == []
    )
    assert on_behalf_status_roles(status) == [
        CVDRole.VENDOR,
        CVDRole.DEPLOYER,
    ]
    assert impossible_state_reasons(status), (
        "VfD must stay impossible; if it becomes legal, the shape rule's"
        " 'or both' case is reachable end to end and needs its own test"
    )


@pytest.mark.spec("RSH-08-007")
def test_a_status_asserting_neither_move_has_no_roles_and_is_refused():
    status = _status(vf=CS_vf.vf)

    assert on_behalf_status_roles(status) is None
    violations = on_behalf_status_violations(
        RM.ACCEPTED, CS_vf.vf, None, status
    )
    assert len(violations) == 1
    assert "neither" in violations[0]


@pytest.mark.spec("RSH-08-007")
def test_every_overreach_is_reported():
    """RM, PXA, VF and D overreach are each named (EH-07-001)."""
    status = _status(
        rm=RM.DEFERRED,
        vf=CS_vf.VF,
        d=CS_d.D,
        case_status=CaseStatus(
            context=_CASE, pxa=PxaDimension(state=CS_pxa.Pxa)
        ),
    )

    violations = on_behalf_status_violations(
        RM.ACCEPTED, CS_vf.vf, CS_d.D, status
    )

    assert [v.split(":")[0] for v in violations] == ["RM", "PXA", "VF"]


@pytest.mark.spec("RSH-08-007")
def test_v_to_V_from_fix_ready_is_not_an_on_behalf_move():
    status = _status(vf=CS_vf.Vf)

    violations = on_behalf_status_violations(
        RM.ACCEPTED, CS_vf.VF, None, status
    )

    assert [v.split(":")[0] for v in violations] == ["VF"]
