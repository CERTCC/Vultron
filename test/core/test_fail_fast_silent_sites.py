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

"""Dedicated unit tests for the 5 named silent-failure sites (CONCERN-1360).

Each test demonstrates that the site now fails fast instead of silently
returning None or Status.SUCCESS when a required value is absent.

Reference: specs/architecture.yaml ARCH-15-001 through ARCH-15-003,
           notes/domain-validation.md, GitHub issue #1377.
"""

from unittest.mock import MagicMock, patch

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes import CommitCaseLedgerEntryNode
from vultron.core.behaviors.case.nodes.communication import (
    CreateAndPersistCaseActivityNode,
)
from vultron.core.dispatcher import DirectActivityDispatcher
from vultron.core.models.events import (
    AddNoteToCaseReceivedEvent,
    MessageSemantics,
)
from vultron.core.models.vultron_types import VultronCaseActor, VultronCase
from vultron.errors import UnroutableActivityError
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase as as_VulnerabilityCase,
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


@pytest.fixture(autouse=True)
def clear_blackboard():
    from vultron.core.models.pending_assertion import _reset_stores

    py_trees.blackboard.Blackboard.storage.clear()
    _reset_stores()
    yield
    py_trees.blackboard.Blackboard.storage.clear()
    _reset_stores()


@pytest.fixture()
def datalayer():
    dl = SqliteDataLayer("sqlite:///:memory:")
    actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor Co")
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
        with patch(_FACTORY_PATH) as mock_factory, patch(
            _INNER_BRIDGE_PATH
        ) as mock_bridge:
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
# AC-1b: _read_case_obj sets feedback_message; update returns FAILURE on None
# ---------------------------------------------------------------------------


class TestCreateAndPersistCaseActivityNodeFailFast:
    """ARCH-15-001: update() returns FAILURE when create_case_obj absent."""

    def test_missing_case_obj_returns_failure(self, bridge):
        """create_case_obj absent from blackboard → FAILURE."""
        node = CreateAndPersistCaseActivityNode()
        case_obj = VultronCase(id_=CASE_ID, name="Test Case")
        bridge.datalayer.create(case_obj)
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=ACTOR_ID,
            case_id=CASE_ID,
            # create_case_obj intentionally omitted
            create_case_addressees=[],
        )
        assert result.status == Status.FAILURE

    def test_missing_case_obj_sets_feedback_message(self, bridge, datalayer):
        """_read_case_obj KeyError sets feedback_message on the node."""
        node = CreateAndPersistCaseActivityNode()
        case_obj = VultronCase(id_=CASE_ID, name="Test Case")
        datalayer.create(case_obj)

        result = bridge.execute_with_setup(
            tree=node,
            actor_id=ACTOR_ID,
            case_id=CASE_ID,
            # create_case_obj intentionally omitted
            create_case_addressees=[],
        )
        assert result.status == Status.FAILURE
        # feedback_message should mention the missing key
        failure_reason = BTBridge.get_failure_reason(node)
        assert "create_case_obj" in failure_reason


# ---------------------------------------------------------------------------
# AC-1c: _extract_case_id raises UnroutableActivityError instead of None
# ---------------------------------------------------------------------------


class TestExtractCaseIdRaisesUnroutableActivityError:
    """ARCH-15-003: unroutable events are dropped, not silently swallowed."""

    def test_unroutable_event_is_dropped_not_retried(self):
        """Gated event with no case_id is dropped; use case is not invoked.

        An ADD_NOTE_TO_CASE event whose target.id_ is empty has no extractable
        case_id.  _extract_case_id raises UnroutableActivityError; _handle
        catches it, logs at ERROR, and returns without calling the use case.
        dispatch() completes normally (no exception propagates to the caller),
        which prevents the inbox re-queue loop (ARCH-15-003).
        """
        mock_dl = MagicMock()
        use_case_class = MagicMock()
        dispatcher = DirectActivityDispatcher(
            use_case_map={MessageSemantics.ADD_NOTE_TO_CASE: use_case_class}
        )

        # target.id_ = "" → target_id property = "" (falsy) → no extractable
        # case_id in case_id / context_id / origin_id / target_id attributes.
        event = AddNoteToCaseReceivedEvent(
            activity_id=ACTIVITY_ID,
            actor_id=ACTOR_ID,
            target=as_VulnerabilityCase(id_=""),
        )

        # dispatch() must not raise — unroutable events are dropped at _handle
        dispatcher.dispatch(event, mock_dl)
        use_case_class.assert_not_called()

    def test_extract_case_id_raises_unroutable_directly(self):
        """_extract_case_id raises UnroutableActivityError (not returns None).

        Test the internal method directly so the raise behaviour is explicit
        even if the caller (_handle) catches it.
        """
        mock_dl = MagicMock()
        dispatcher = DirectActivityDispatcher(use_case_map={})
        event = AddNoteToCaseReceivedEvent(
            activity_id=ACTIVITY_ID,
            actor_id=ACTOR_ID,
            target=as_VulnerabilityCase(id_=""),
        )

        with pytest.raises(UnroutableActivityError) as exc_info:
            dispatcher._extract_case_id(event, mock_dl)

        exc = exc_info.value
        assert exc.activity_id == ACTIVITY_ID
        assert "No case_id" in exc.reason

    def test_unroutable_error_has_activity_id_and_reason_fields(self):
        """UnroutableActivityError carries activity_id and reason attributes."""
        err = UnroutableActivityError(
            activity_id="act-xyz",
            reason="No case_id attribute found on event",
        )
        assert err.activity_id == "act-xyz"
        assert err.reason == "No case_id attribute found on event"
        assert "act-xyz" in str(err)
        assert "No case_id" in str(err)

    def test_unroutable_error_is_vultron_error_subclass(self):
        """UnroutableActivityError is a VultronError subclass."""
        from vultron.errors import VultronError

        err = UnroutableActivityError(activity_id="x", reason="test")
        assert isinstance(err, VultronError)


# ---------------------------------------------------------------------------
# AC-1d: _resolve_case_manager_id callers return FAILURE when required
# ---------------------------------------------------------------------------


class TestResolveCaseManagerIdCallers:
    """ARCH-15-002: callers return FAILURE when _resolve_case_manager_id is None."""

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
