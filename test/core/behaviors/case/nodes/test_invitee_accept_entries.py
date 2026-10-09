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

"""The entries on the CASE_MANAGER's side of the stub path (ADR-0114).

The ledger holds the wire messages exchanged: the invitee's Accept is already
the entry for the consent row it signs and its ``joined`` mark, so those two
writes commit nothing of their own (they take the Accept's ``published`` as the
record's time).  Creating the record is the CASE_MANAGER's own act, with its own
``create_case_participant`` entry.  The vendor's VF status is a CASE_MANAGER
-written object, so ``CommitInviteeAcceptEntriesNode`` ledgers it as an
``add_participant_status_to_participant`` entry.  VF is a vendor-only status: no
entry carries one for any other role (CM-11-006, CM-11-009, CM-31-012).
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.embargo_register import activate
from vultron.core.behaviors.case.nodes.invite_embargo_consent import (
    _SignEmbargoConsentLeafNode,
)
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    AdvanceInviteeVFToVendorAwareNode,
    CreateInertInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.invite_participant_persist import (
    ActivateInviteeParticipantNode,
    CommitInviteeAcceptEntriesNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.cs import CS_vf
from vultron.enums.roles import CVDRole

MANAGER_ID = "https://example.org/actors/manager"
INVITEE_ID = "https://example.org/actors/invitee"
CASE_ID = "https://example.org/cases/accept-entries"
EMBARGO_ID = f"{CASE_ID}/embargo_events/active"
ACCEPT_PUBLISHED = datetime(2099, 10, 9, 13, 0, 0, tzinfo=UTC)
ACCEPT = SimpleNamespace(
    activity_id="https://example.org/activities/accept-1",
    activity=SimpleNamespace(published=ACCEPT_PUBLISHED),
)

ROLES = [
    pytest.param([CVDRole.VENDOR], id="vendor"),
    pytest.param([CVDRole.COORDINATOR], id="coordinator"),
    pytest.param([CVDRole.VENDOR, CVDRole.COORDINATOR], id="vendor+other"),
]


def _scenario(roles: list[CVDRole], embargo: bool) -> BTTestScenario:
    case = VulnerabilityCase(
        id_=CASE_ID, name="Case", attributed_to=MANAGER_ID
    )
    if embargo:
        activate(case, EMBARGO_ID)
    s = BTTestScenario(actor_id=MANAGER_ID).seed(
        CaseActor(id_=MANAGER_ID, name="Manager"), case
    )
    s.assert_success(
        s.run(
            CreateInertInviteeParticipantNode(
                invitee_id=INVITEE_ID,
                case_id=CASE_ID,
                roles=[r.value for r in roles],
            ),
            case_id=CASE_ID,
        )
    )
    return s


def _record(s: BTTestScenario) -> CaseParticipant:
    case = s.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    record = s.dl.read(case.actor_participant_index[INVITEE_ID])
    assert isinstance(record, CaseParticipant)
    return record


def _entries(s: BTTestScenario) -> list[CaseLedgerEntry]:
    found = [
        e
        for e in s.dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry) and e.case_id == CASE_ID
    ]
    return sorted(found, key=lambda e: e.log_index)


def _accept(s: BTTestScenario, embargo: bool = True) -> Status:
    record = _record(s)
    sign = (
        [_SignEmbargoConsentLeafNode(invitee_id=INVITEE_ID)] if embargo else []
    )
    tree = py_trees.composites.Sequence(
        name="Accept",
        memory=False,
        children=[
            *sign,
            ActivateInviteeParticipantNode(
                case_id=CASE_ID, invitee_id=INVITEE_ID
            ),
            AdvanceInviteeVFToVendorAwareNode(
                case_id=CASE_ID, invitee_id=INVITEE_ID
            ),
            CommitInviteeAcceptEntriesNode(
                case_id=CASE_ID, invitee_id=INVITEE_ID
            ),
        ],
    )
    return s.run(
        tree,
        case_id=CASE_ID,
        new_invite_participant=record,
        active_embargo_id=EMBARGO_ID,
        activity=ACCEPT,
    ).status


@pytest.mark.spec("CM-11-006")
@pytest.mark.parametrize("roles", ROLES)
def test_creating_the_record_emits_its_own_entry_carrying_it(roles):
    s = _scenario(roles, embargo=True)

    created = [
        e for e in _entries(s) if e.event_type == "create_case_participant"
    ]
    assert len(created) == 1
    carried = created[0].payload_snapshot["object"]
    stored = _record(s)
    assert carried["id"] == stored.id_
    assert carried["joined"] is False
    statuses = carried["participantStatuses"]
    assert [x["id"] for x in statuses] == [
        x.id_ for x in stored.participant_statuses
    ]
    # VF is a vendor-only status: only a vendor's birth status carries one.
    assert any("vfState" in x for x in statuses) is (CVDRole.VENDOR in roles)


@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("CM-11-009")
@pytest.mark.parametrize("roles", ROLES)
@pytest.mark.parametrize("embargo", [True, False])
def test_the_accept_commits_only_a_vendors_status_entry(roles, embargo):
    """Consent and ``joined`` are the Accept's entry; only VF is a new entry."""
    s = _scenario(roles, embargo)
    before = len(_entries(s))

    assert _accept(s, embargo) == Status.SUCCESS

    new = [e.event_type for e in _entries(s)[before:]]
    assert new == (
        ["add_participant_status_to_participant"]
        if CVDRole.VENDOR in roles
        else []
    )
    record = _record(s)
    assert record.joined is True
    # The record's time is the Accept's ``published``, never the local clock.
    assert record.updated == ACCEPT_PUBLISHED
    vfs = [x.vf.state for x in record.participant_statuses if x.vf]
    assert vfs == ([CS_vf.vf, CS_vf.Vf] if CVDRole.VENDOR in roles else [])
    if embargo:
        assert record.is_signatory(EMBARGO_ID)


@pytest.mark.spec("CM-31-012")
def test_a_resumed_accept_that_changes_nothing_emits_nothing():
    s = _scenario([CVDRole.VENDOR], embargo=True)
    assert _accept(s) == Status.SUCCESS
    before = len(_entries(s))

    assert _accept(s) == Status.SUCCESS

    assert len(_entries(s)) == before
