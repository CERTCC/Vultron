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

"""VF is a vendor-only status on an invitee's record (CM-11-006, CM-11-009).

The vendor fix path (``v`` at invite, ``Vf`` once the vendor is aware) applies
only to a participant whose roles include ``VENDOR``.  A coordinator, finder,
reporter or observer carries no VF status at all, on the CASE_MANAGER and on a
replica (#4384).  Covers the shared builder, the CASE_MANAGER's birth node, and
the Accept-time advance.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.stub_invite import STUB_PUBLISHED, store_stub_invite
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    AdvanceInviteeVFToVendorAwareNode,
    CreateInertInviteeParticipantNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.inert_invitee import (
    build_inert_invitee_participant,
)
from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/vf-vendor-only"
MANAGER_ID = "https://example.org/actors/manager"
INVITEE_ID = "https://example.org/actors/invitee"
INVITE_ID = f"{CASE_ID}/invitations/stub-1"
ACCEPT = SimpleNamespace(
    activity_id="https://example.org/activities/accept-1",
    activity=SimpleNamespace(published=datetime(2026, 10, 9, 13, tzinfo=UTC)),
)

NON_VENDOR_ROLES = [
    [CVDRole.COORDINATOR],
    [CVDRole.FINDER],
    [CVDRole.REPORTER],
    [CVDRole.OBSERVER],
    [CVDRole.COORDINATOR, CVDRole.OBSERVER],
]
VENDOR_ROLES = [
    [CVDRole.VENDOR],
    [CVDRole.VENDOR, CVDRole.COORDINATOR],
    [CVDRole.COORDINATOR, CVDRole.VENDOR],
]


def _build(roles):
    return build_inert_invitee_participant(
        _case(),
        INVITEE_ID,
        roles,
        invite_id=INVITE_ID,
        published=STUB_PUBLISHED,
    )


def _case() -> VulnerabilityCase:
    return VulnerabilityCase(id_=CASE_ID, attributed_to=MANAGER_ID)


def _manager() -> BTTestScenario:
    scenario = BTTestScenario(actor_id=MANAGER_ID).seed(_case())
    store_stub_invite(
        scenario.dl,
        case_id=CASE_ID,
        issuer_id=MANAGER_ID,
        invitee_id=INVITEE_ID,
        invite_id=INVITE_ID,
    )
    return scenario


def _record(scenario: BTTestScenario) -> CaseParticipant:
    case = scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    record = scenario.dl.read(case.actor_participant_index[INVITEE_ID])
    assert isinstance(record, CaseParticipant)
    return record


@pytest.mark.spec("CM-11-006")
@pytest.mark.parametrize("roles", NON_VENDOR_ROLES)
def test_builder_writes_no_vf_status_for_a_non_vendor(roles):
    record = _build(roles)

    assert record.participant_statuses[-1].rm.state == RM.RECEIVED
    assert all(s.vf is None for s in record.participant_statuses)


@pytest.mark.spec("CM-11-006")
@pytest.mark.parametrize("roles", VENDOR_ROLES)
def test_builder_writes_vf_v_when_vendor_is_among_the_roles(roles):
    record = _build(roles)

    vf = record.participant_statuses[-1].vf
    assert vf is not None
    assert vf.state == CS_vf.vf


@pytest.mark.spec("CM-11-006")
@pytest.mark.parametrize("roles", NON_VENDOR_ROLES + VENDOR_ROLES)
def test_case_manager_birth_node_follows_the_builder(roles):
    scenario = _manager()

    result = scenario.run(
        CreateInertInviteeParticipantNode(
            invitee_id=INVITEE_ID,
            case_id=CASE_ID,
            roles=[r.value for r in roles],
        )
    )

    scenario.assert_success(result)
    # The node stores exactly what the shared builder makes: same ids, same times.
    record = _record(scenario)
    assert record.model_dump(mode="json") == _build(roles).model_dump(
        mode="json"
    )
    vf = record.participant_statuses[-1].vf
    assert (vf is not None) == (CVDRole.VENDOR in roles)


@pytest.mark.spec("CM-11-009")
@pytest.mark.parametrize("roles", NON_VENDOR_ROLES)
def test_accept_advance_is_a_no_op_for_a_non_vendor(roles):
    scenario = _manager()
    scenario.run(
        CreateInertInviteeParticipantNode(
            invitee_id=INVITEE_ID,
            case_id=CASE_ID,
            roles=[r.value for r in roles],
        )
    )
    before = len(_record(scenario).participant_statuses)

    result = scenario.run(
        AdvanceInviteeVFToVendorAwareNode(
            case_id=CASE_ID, invitee_id=INVITEE_ID
        ),
        activity=ACCEPT,
    )

    scenario.assert_success(result)
    after = _record(scenario).participant_statuses
    assert len(after) == before
    assert all(s.vf is None for s in after)


@pytest.mark.spec("CM-11-009")
@pytest.mark.parametrize("roles", VENDOR_ROLES)
def test_accept_advance_moves_a_vendor_to_vf_aware(roles):
    scenario = _manager()
    scenario.run(
        CreateInertInviteeParticipantNode(
            invitee_id=INVITEE_ID,
            case_id=CASE_ID,
            roles=[r.value for r in roles],
        )
    )

    result = scenario.run(
        AdvanceInviteeVFToVendorAwareNode(
            case_id=CASE_ID, invitee_id=INVITEE_ID
        ),
        activity=ACCEPT,
    )

    scenario.assert_success(result)
    vf = _record(scenario).participant_statuses[-1].vf
    assert vf is not None
    assert vf.state == CS_vf.Vf
