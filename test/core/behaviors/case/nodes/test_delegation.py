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

from unittest.mock import MagicMock, patch

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.delegation import (
    AutoAcceptCaseParticipantRoleNode,
    EmitRejectCaseParticipantRoleNode,
    GrantCaseParticipantRoleNode,
)
from vultron.core.models.case_participant import CaseParticipant
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
    # These trees execute as ACTOR_ID, so the store under test is ACTOR_ID's
    # own (BT-05-005).  There is no unscoped DataLayer to open (ADR-0073).
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    case = as_VulnerabilityCase(id_=CASE_ID, name="Delegation Test Case")
    dl.create(case)
    return dl


@pytest.fixture
def factory(dl):
    return TriggerActivityAdapter(dl)


@pytest.fixture
def bridge(dl, factory):
    return BTBridge(datalayer=dl, trigger_activity=factory)


def _make_accept_node(
    offer_id: str = OFFER_ID,
    case_id: str = CASE_ID,
    role: CVDRole = CVDRole.CASE_MANAGER,
    target_actor_id: str = ACTOR_ID,
    vendor_id: str = VENDOR_ID,
) -> AutoAcceptCaseParticipantRoleNode:
    return AutoAcceptCaseParticipantRoleNode(
        offer_id=offer_id,
        case_id=case_id,
        role=role,
        target_actor_id=target_actor_id,
        vendor_id=vendor_id,
    )


def _make_reject_node(
    offer_id: str = OFFER_ID,
    case_id: str = CASE_ID,
    role: CVDRole = CVDRole.CASE_MANAGER,
    target_actor_id: str = ACTOR_ID,
    vendor_id: str = VENDOR_ID,
) -> EmitRejectCaseParticipantRoleNode:
    return EmitRejectCaseParticipantRoleNode(
        offer_id=offer_id,
        case_id=case_id,
        role=role,
        target_actor_id=target_actor_id,
        vendor_id=vendor_id,
    )


class TestAutoAcceptCaseParticipantRoleNode:
    """Unit tests for AutoAcceptCaseParticipantRoleNode (ADR-0039)."""

    def test_success_path(self, bridge, dl):
        """Happy path: creates Accept activity, commits to ledger, enqueues."""
        node = _make_accept_node()
        with patch.object(
            type(node), "_commit_accept_to_ledger", return_value=True
        ):
            result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS

    def test_accept_enqueued_to_outbox(self, bridge, dl):
        """Accept activity ID is enqueued to the actor's outbox after success."""
        node = _make_accept_node()
        with patch.object(
            type(node), "_commit_accept_to_ledger", return_value=True
        ):
            bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        queued = dl.outbox_list()
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

        queued = dl.outbox_list()
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


class TestGrantCaseParticipantRoleNode:
    """The CASE_MANAGER grants the role on its own copy at commit (CM-02-016)."""

    def _seed_target(self, dl, roles=(CVDRole.VENDOR,)):
        case = dl.read(CASE_ID)
        participant = CaseParticipant(
            id_=f"{CASE_ID}/participants/target",
            attributed_to=ACTOR_ID,
            context=CASE_ID,
            case_roles=list(roles),
        )
        case.add_participant(participant)
        dl.create(participant)
        dl.save(case)
        return case

    @pytest.mark.spec("CM-02-016")
    def test_grants_role_on_own_copy(self, bridge, dl):
        case = self._seed_target(dl)
        node = GrantCaseParticipantRoleNode(
            case_id=CASE_ID,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=ACTOR_ID,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        granted = dl.read(case.actor_participant_index[ACTOR_ID])
        assert granted.has_role(CVDRole.CASE_MANAGER)  # newly granted
        assert granted.has_role(CVDRole.VENDOR)  # pre-existing role kept

    @pytest.mark.spec("CM-02-016")
    def test_missing_participant_is_non_fatal(self, bridge, dl):
        """No participant for the target: SUCCESS, nothing written."""
        node = GrantCaseParticipantRoleNode(
            case_id=CASE_ID,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=ACTOR_ID,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        assert ACTOR_ID not in dl.read(CASE_ID).actor_participant_index
