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

"""Unit tests for status condition nodes (submodule path).

Verifies SenderIsParticipantNode (formerly SenderIsActiveParticipantNode)
imported from the consolidated sender_entitlement module.
Per DEMOMA-07-003 step 1.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sender_entitlement import (
    SenderIsActiveParticipantNode,
    SenderIsParticipantNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/vendor"
OUTSIDER_ID = "https://example.org/actors/outsider"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/case-01"
PARTICIPANT_ID = "https://example.org/cases/case-01/participants/vendor"
CM_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/case-actor"
STATUS_ID = "https://example.org/cases/case-01/statuses/s1"


@pytest.fixture
def dl():
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=CASE_MANAGER_ID,
    )


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def participant():
    return as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )


@pytest.fixture
def case_manager_participant():
    return as_CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )


@pytest.fixture
def status_obj():
    return as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID)


@pytest.fixture
def populated_dl(dl, participant, case_manager_participant, status_obj):
    case = VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=CASE_MANAGER_ID
    )
    case.add_participant(participant)
    case.add_participant(case_manager_participant)
    dl.create(case)
    dl.create(participant)
    dl.create(case_manager_participant)
    dl.create(status_obj)
    return dl


@pytest.fixture
def populated_bridge(populated_dl):
    return BTBridge(datalayer=populated_dl)


class TestSenderIsParticipantNode:
    def test_known_sender_succeeds(self, populated_bridge):
        node = SenderIsParticipantNode(
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_unknown_sender_fails(self, populated_bridge):
        node = SenderIsParticipantNode(
            sender_actor_id=OUTSIDER_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    def test_no_case_id_fails(self, populated_bridge):
        node = SenderIsParticipantNode(
            sender_actor_id=ACTOR_ID,
            case_id=None,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    def test_missing_case_fails(self, bridge):
        node = SenderIsParticipantNode(
            sender_actor_id=ACTOR_ID,
            case_id="https://example.org/cases/nonexistent",
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


def _save_vendor(dl, **fields):
    """Re-save the vendor's participant record with *fields* changed."""
    dl.save(
        CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            **fields,
        )
    )
    return BTBridge(datalayer=dl)


_INACTIVE = {
    "inert": {"joined": False},
    "removed": {"removal_activity": "https://example.org/activities/rm-1"},
}


class TestParticipantKindsDiffer:
    """``PARTICIPANT`` is any record on the case; ``ACTIVE_PARTICIPANT`` is
    an active one (CM-10-004, HP-01-009)."""

    @pytest.mark.spec("HP-01-009")
    @pytest.mark.parametrize("state", sorted(_INACTIVE))
    def test_participant_kind_admits_an_inactive_record(
        self, populated_dl, state
    ):
        bridge = _save_vendor(populated_dl, **_INACTIVE[state])
        node = SenderIsParticipantNode(
            sender_actor_id=ACTOR_ID, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS

    @pytest.mark.spec("CM-10-004")
    @pytest.mark.parametrize("state", sorted(_INACTIVE))
    def test_active_participant_kind_refuses_an_inactive_record(
        self, populated_dl, state
    ):
        bridge = _save_vendor(populated_dl, **_INACTIVE[state])
        node = SenderIsActiveParticipantNode(
            sender_actor_id=ACTOR_ID, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE
        assert "not an active participant" in node.feedback_message

    @pytest.mark.spec("CM-10-004")
    def test_active_participant_kind_admits_an_active_record(
        self, populated_bridge
    ):
        node = SenderIsActiveParticipantNode(
            sender_actor_id=ACTOR_ID, case_id=CASE_ID
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    @pytest.mark.spec("HP-01-006")
    @pytest.mark.parametrize(
        "sender, case_id",
        [(OUTSIDER_ID, CASE_ID), (ACTOR_ID, None)],
        ids=["unlisted", "no-case"],
    )
    def test_active_participant_kind_refuses_without_standing(
        self, populated_bridge, sender, case_id
    ):
        node = SenderIsActiveParticipantNode(
            sender_actor_id=sender, case_id=case_id
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    @pytest.mark.spec("HP-01-006")
    def test_both_kinds_report_a_missing_case_the_same_way(
        self, populated_bridge, caplog
    ):
        """With no case to check against, each kind refuses with a WARNING
        naming the sender, not a Regime 1 ERROR."""
        for node_cls in (
            SenderIsParticipantNode,
            SenderIsActiveParticipantNode,
        ):
            caplog.clear()
            node = node_cls(sender_actor_id=ACTOR_ID, case_id=None)
            with caplog.at_level("WARNING"):
                result = populated_bridge.execute_with_setup(
                    tree=node, actor_id=CASE_MANAGER_ID
                )
            assert result.status == Status.FAILURE
            assert "No case in this store to check sender" in (
                node.feedback_message
            )
            assert ACTOR_ID in node.feedback_message
            assert not [r for r in caplog.records if r.levelname == "ERROR"]


@pytest.fixture
def closed_sender_dl(populated_dl):
    """The vendor's closure recorded: its RM is ``CLOSED`` (CM-23-001)."""
    closed = CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        participant_statuses=[
            ParticipantStatus(
                context=CASE_ID,
                attributed_to=ACTOR_ID,
                rm=RmDimension(state=RM.CLOSED),
            )
        ],
    )
    populated_dl.save(closed)
    return populated_dl


class TestClosedSenderRefused:
    @pytest.mark.xfail(
        strict=True,
        reason="CM-23-018: the active-participant sender guard accepts a"
        " sender at RM CLOSED. Tracked by #4615.",
    )
    @pytest.mark.spec("CM-23-018")
    def test_closed_sender_fails(self, closed_sender_dl):
        node = SenderIsActiveParticipantNode(
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = BTBridge(datalayer=closed_sender_dl).execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE
