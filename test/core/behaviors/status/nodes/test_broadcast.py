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

"""Unit tests for broadcast nodes (submodule path).

Verifies FindCaseManagerNode, FilterPeerRecipientsNode,
BroadcastStatusToPeersNode, and _find_case_manager_id imported directly
from the submodule.

Per DEMOMA-07-003 step 3.
"""

import pytest
import py_trees
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.nodes.broadcast import (
    BroadcastStatusToPeersNode,
    FilterPeerRecipientsNode,
    FindCaseManagerNode,
    _find_case_manager_id,
)
from vultron.core.states.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
PEER_ID = "https://example.org/actors/peer"
CASE_ID = "https://example.org/cases/case-01"
PARTICIPANT_ID = "https://example.org/cases/case-01/participants/vendor"
CM_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/case-actor"
PEER_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/peer"
STATUS_ID = "https://example.org/cases/case-01/statuses/s1"
PARTICIPANT_REF_ID = PARTICIPANT_ID


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def vendor_participant():
    return CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )


@pytest.fixture
def case_manager_participant():
    return CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )


@pytest.fixture
def peer_participant():
    return CaseParticipant(
        id_=PEER_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=PEER_ID,
        case_roles=[CVDRole.COORDINATOR],
    )


@pytest.fixture
def case_with_peers(
    vendor_participant, case_manager_participant, peer_participant
):
    obj = VulnerabilityCase(id_=CASE_ID, name="Test Case")
    obj.add_participant(vendor_participant)
    obj.add_participant(case_manager_participant)
    obj.add_participant(peer_participant)
    return obj


@pytest.fixture
def populated_dl(
    dl,
    case_with_peers,
    vendor_participant,
    case_manager_participant,
    peer_participant,
):
    dl.create(case_with_peers)
    dl.create(vendor_participant)
    dl.create(case_manager_participant)
    dl.create(peer_participant)
    return dl


@pytest.fixture
def populated_bridge(populated_dl):
    return BTBridge(datalayer=populated_dl)


# ---------------------------------------------------------------------------
# _find_case_manager_id helper
# ---------------------------------------------------------------------------


class TestFindCaseManagerIdHelper:
    def test_finds_case_manager(self, populated_dl, case_with_peers):
        result = _find_case_manager_id(populated_dl, case_with_peers)
        assert result == CASE_MANAGER_ID

    def test_returns_none_when_no_case_manager(self, dl):
        case = VulnerabilityCase(id_=CASE_ID, name="Test Case")
        p = CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        case.add_participant(p)
        dl.create(case)
        dl.create(p)
        result = _find_case_manager_id(dl, case)
        assert result is None


# ---------------------------------------------------------------------------
# FindCaseManagerNode
# ---------------------------------------------------------------------------


class TestFindCaseManagerNode:
    def test_finds_case_manager_writes_blackboard(self, populated_bridge):
        node = FindCaseManagerNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_missing_case_fails(self, bridge):
        node = FindCaseManagerNode(case_id="https://example.org/cases/missing")
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_none_case_id_fails(self, populated_bridge):
        node = FindCaseManagerNode(case_id=None)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# FilterPeerRecipientsNode
# ---------------------------------------------------------------------------


class TestFilterPeerRecipientsNode:
    def test_returns_success_with_eligible_peer(self, populated_bridge):
        # Must run FindCaseManagerNode first to populate blackboard
        import py_trees as pt

        find = FindCaseManagerNode(case_id=CASE_ID)
        filt = FilterPeerRecipientsNode(
            sender_actor_id=ACTOR_ID, case_id=CASE_ID
        )
        seq = pt.composites.Sequence(
            name="TestSeq", memory=False, children=[find, filt]
        )
        result = populated_bridge.execute_with_setup(
            tree=seq, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_missing_case_fails(self, populated_bridge):
        find = FindCaseManagerNode(case_id=CASE_ID)
        filt = FilterPeerRecipientsNode(
            sender_actor_id=ACTOR_ID,
            case_id="https://example.org/cases/missing",
        )
        import py_trees as pt

        seq = pt.composites.Sequence(
            name="TestSeq", memory=False, children=[find, filt]
        )
        result = populated_bridge.execute_with_setup(
            tree=seq, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# BroadcastStatusToPeersNode
# ---------------------------------------------------------------------------


class TestBroadcastStatusToPeersNode:
    def test_returns_failure_without_factory(self, populated_bridge):
        """No trigger_activity_factory → FAILURE (BT-14-001)."""
        node = BroadcastStatusToPeersNode(
            status_id=STATUS_ID,
            participant_id=PARTICIPANT_REF_ID,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE
