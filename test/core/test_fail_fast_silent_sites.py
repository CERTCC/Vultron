#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Dedicated unit tests for the named silent-failure sites (CONCERN-1360).

Each test demonstrates that the site now fails fast instead of silently
returning None or Status.SUCCESS when a required value is absent.

Reference: specs/architecture.yaml ARCH-15-001 and ARCH-15-002,
           notes/domain-validation.md, GitHub issue #1377.
"""

from unittest.mock import patch

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes import CommitCaseLedgerEntryNode
from vultron.core.models.actor import VultronService
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_FACTORY_PATH = (
    "vultron.core.behaviors.case.nodes.lifecycle.create_commit_log_entry_tree"
)
_INNER_BRIDGE_PATH = "vultron.core.behaviors.case.nodes.lifecycle.BTBridge"

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"
ACTIVITY_ID = "https://example.org/activities/act-001"
CM_ACTOR_ID = "https://example.org/actors/case-manager-001"
CM_CASE_ID = "https://example.org/cases/cm-case-001"
CM_PARTICIPANT_ID = f"{CM_CASE_ID}/participants/case-manager-001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def datalayer():
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )
    actor = VultronService(id_=ACTOR_ID, name="Vendor Co")
    dl.create(actor)
    return dl


@pytest.fixture()
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


# ---------------------------------------------------------------------------
# AC-1a: CommitCaseLedgerEntryNode returns FAILURE when case_id unresolvable
# ---------------------------------------------------------------------------


class TestCommitCaseLedgerEntryNodeFailFast:
    """ARCH-15-001: update() returns FAILURE when case_id is unresolvable."""

    def test_no_case_id_on_blackboard_returns_failure(self, bridge):
        """No case_id in blackboard → FAILURE, inner tree never built."""
        node = CommitCaseLedgerEntryNode()
        with (
            patch(_FACTORY_PATH) as mock_factory,
            patch(_INNER_BRIDGE_PATH) as mock_bridge,
        ):
            result = bridge.execute_with_setup(
                tree=node, actor_id=ACTOR_ID, activity=None
            )
        assert result.status == Status.FAILURE
        mock_factory.assert_not_called()
        mock_bridge.assert_not_called()

    def test_none_case_id_returns_failure(self, bridge):
        """case_id resolves to None → FAILURE (not SUCCESS no-op)."""
        node = CommitCaseLedgerEntryNode(case_id=None)
        with patch(_FACTORY_PATH) as mock_factory:
            result = bridge.execute_with_setup(
                tree=node, actor_id=ACTOR_ID, activity=None
            )
        assert result.status == Status.FAILURE
        mock_factory.assert_not_called()

    def test_empty_string_case_id_returns_failure(self, bridge):
        """Empty string case_id → FAILURE (falsy value treated as absent)."""
        node = CommitCaseLedgerEntryNode(case_id="")
        with patch(_FACTORY_PATH) as mock_factory:
            result = bridge.execute_with_setup(
                tree=node, actor_id=ACTOR_ID, activity=None
            )
        assert result.status == Status.FAILURE
        mock_factory.assert_not_called()


# ---------------------------------------------------------------------------
# AC-1d: resolve_case_manager_id callers return FAILURE when required
# ---------------------------------------------------------------------------


class TestResolveCaseManagerIdCallers:
    """ARCH-15-002: callers return FAILURE when resolve_case_manager_id is None."""

    def test_sender_node_returns_failure_when_no_case_manager(self):
        """ResolveCaseManagerNode returns FAILURE when no CASE_MANAGER exists."""
        from test.core.behaviors.bt_harness import BTTestScenario
        from vultron.core.behaviors.sender.nodes.actions import (
            ResolveCaseManagerNode,
        )

        scenario = BTTestScenario(actor_id=ACTOR_ID)
        # Seed case with no participants (empty actor_participant_index)
        case = as_VulnerabilityCase(id_=CASE_ID, name="No CM")
        scenario.dl.create(case)

        node = ResolveCaseManagerNode(case_id=CASE_ID)
        result = scenario.run(node, actor_id=ACTOR_ID)
        scenario.assert_failure(result)

    def test_check_is_case_manager_returns_failure_when_no_case_manager(self):
        """CheckIsCaseManagerNode returns FAILURE when no CASE_MANAGER found."""
        from test.core.behaviors.bt_harness import BTTestScenario
        from vultron.core.behaviors.case.nodes.conditions import (
            CheckIsCaseManagerNode,
        )

        scenario = BTTestScenario(actor_id=ACTOR_ID)
        case = as_VulnerabilityCase(id_=CASE_ID, name="No CM")
        scenario.dl.create(case)

        node = CheckIsCaseManagerNode()
        result = scenario.run(node, actor_id=ACTOR_ID, case_id=CASE_ID)
        scenario.assert_failure(result)
