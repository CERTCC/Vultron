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

"""Tests for AutoAcceptCaseParticipantRoleNode and EmitRejectCaseParticipantRoleNode (ADR-0039)."""

import pytest
from py_trees.common import Status
from unittest.mock import MagicMock

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.delegation import (
    AutoAcceptCaseParticipantRoleNode,
    EmitRejectCaseParticipantRoleNode,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

VENDOR_ID = "https://example.org/actors/vendor"
ACTOR_ID = "https://example.org/actors/case-actor"
OFFER_ID = "https://example.org/activities/offer-role-1"
ACCEPT_ID = "https://example.org/activities/accept-role-1"
REJECT_ID = "https://example.org/activities/reject-role-1"
CASE_ID = "https://example.org/cases/test-case-delegation"


@pytest.fixture
def dl():
    dl = SqliteDataLayer("sqlite:///:memory:")
    case = as_VulnerabilityCase(id_=CASE_ID, name="Delegation Test Case")
    dl.create(case)
    return dl


@pytest.fixture
def factory(dl):
    return TriggerActivityAdapter(dl)


@pytest.fixture
def bridge(dl, factory):
    return BTBridge(datalayer=dl, trigger_activity=factory)


def _make_accept_node(**kwargs):
    defaults = dict(
        offer_id=OFFER_ID,
        case_id=CASE_ID,
        role=CVDRole.CASE_MANAGER,
        target_actor_id=ACTOR_ID,
        vendor_id=VENDOR_ID,
    )
    defaults.update(kwargs)
    return AutoAcceptCaseParticipantRoleNode(**defaults)


def _make_reject_node(**kwargs):
    defaults = dict(
        offer_id=OFFER_ID,
        case_id=CASE_ID,
        role=CVDRole.CASE_MANAGER,
        target_actor_id=ACTOR_ID,
        vendor_id=VENDOR_ID,
    )
    defaults.update(kwargs)
    return EmitRejectCaseParticipantRoleNode(**defaults)


class TestAutoAcceptCaseParticipantRoleNode:
    """Unit tests for AutoAcceptCaseParticipantRoleNode (ADR-0039)."""

    def test_success_path(self, bridge, dl):
        """Happy path: creates Accept activity, commits to ledger, enqueues."""
        node = _make_accept_node()
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS

    def test_accept_enqueued_to_outbox(self, bridge, dl):
        """Accept activity ID is enqueued to the actor's outbox after success."""
        node = _make_accept_node()
        bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        queued = dl.outbox_list_for_actor(ACTOR_ID)
        assert len(queued) >= 1

    def test_failure_when_no_factory(self, dl):
        """Returns FAILURE when trigger_activity_factory is unavailable."""
        bridge_no_factory = BTBridge(datalayer=dl)
        node = _make_accept_node()
        result = bridge_no_factory.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )

        assert result.status == Status.FAILURE

    def test_failure_when_case_id_empty(self, bridge):
        """Returns FAILURE when case_id is empty."""
        node = _make_accept_node(case_id="")
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE

    def test_failure_when_target_actor_id_empty(self, bridge):
        """Returns FAILURE when target_actor_id is empty."""
        node = _make_accept_node(target_actor_id="")
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE

    def test_failure_when_factory_raises(self, dl):
        """Returns FAILURE when factory raises an exception."""
        mock_factory = MagicMock()
        mock_factory.accept_case_participant_role.side_effect = RuntimeError(
            "factory error"
        )
        bridge_bad_factory = BTBridge(
            datalayer=dl, trigger_activity=mock_factory
        )
        node = _make_accept_node()
        result = bridge_bad_factory.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )

        assert result.status == Status.FAILURE


class TestEmitRejectCaseParticipantRoleNode:
    """Unit tests for EmitRejectCaseParticipantRoleNode (ADR-0039)."""

    def test_success_path(self, bridge, dl):
        """Happy path: creates Reject activity and enqueues it."""
        node = _make_reject_node()
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS

    def test_reject_enqueued_to_outbox(self, bridge, dl):
        """Reject activity ID is enqueued to the actor's outbox after success."""
        node = _make_reject_node()
        bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        queued = dl.outbox_list_for_actor(ACTOR_ID)
        assert len(queued) >= 1

    def test_failure_when_no_factory(self, dl):
        """Returns FAILURE when trigger_activity_factory is unavailable."""
        bridge_no_factory = BTBridge(datalayer=dl)
        node = _make_reject_node()
        result = bridge_no_factory.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )

        assert result.status == Status.FAILURE

    def test_failure_when_case_id_empty(self, bridge):
        """Returns FAILURE when case_id is empty."""
        node = _make_reject_node(case_id="")
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE

    def test_failure_when_target_actor_id_empty(self, bridge):
        """Returns FAILURE when target_actor_id is empty."""
        node = _make_reject_node(target_actor_id="")
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE

    def test_failure_when_factory_raises(self, dl):
        """Returns FAILURE when factory raises an exception."""
        mock_factory = MagicMock()
        mock_factory.reject_case_participant_role.side_effect = RuntimeError(
            "factory error"
        )
        bridge_bad_factory = BTBridge(
            datalayer=dl, trigger_activity=mock_factory
        )
        node = _make_reject_node()
        result = bridge_bad_factory.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )

        assert result.status == Status.FAILURE
