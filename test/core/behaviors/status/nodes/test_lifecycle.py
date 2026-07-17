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

"""Unit tests for case lifecycle trigger nodes.

Tests PublicDisclosureBranchNode and AutoCloseBranchNode
from nodes.lifecycle.

Per DEMOMA-07-003 steps 4–5.
"""

import pytest
import py_trees
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.nodes.lifecycle import (
    AutoCloseBranchNode,
    PublicDisclosureBranchNode,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/case-01"
PARTICIPANT_ID = "https://example.org/cases/case-01/participants/vendor"
CM_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/case-actor"
STATUS_ID = "https://example.org/cases/case-01/statuses/s1"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def participant():
    return as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )


@pytest.fixture
def status_obj():
    return as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID)


@pytest.fixture
def populated_dl(dl, participant, status_obj):
    case_manager_participant = as_CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case = as_VulnerabilityCase(id_=CASE_ID, name="Test Case")
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


# ---------------------------------------------------------------------------
# PublicDisclosureBranchNode
# ---------------------------------------------------------------------------


class TestPublicDisclosureBranchNode:
    def test_always_succeeds_when_not_public_aware(
        self, populated_bridge, status_obj
    ):
        """Non-public-aware status → skip condition returns SUCCESS → branch
        returns SUCCESS without attempting embargo teardown."""
        node = PublicDisclosureBranchNode(
            status_obj=status_obj,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_none_case_id_succeeds(self, populated_bridge, status_obj):
        """None case_id → skip condition exits early → returns SUCCESS."""
        node = PublicDisclosureBranchNode(
            status_obj=status_obj,
            sender_actor_id=ACTOR_ID,
            case_id=None,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# AutoCloseBranchNode
# ---------------------------------------------------------------------------


class TestAutoCloseBranchNode:
    def test_always_succeeds(self, populated_bridge):
        node = AutoCloseBranchNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_succeeds_with_none_case_id(self, populated_bridge):
        node = AutoCloseBranchNode(case_id=None)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS
