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

"""Unit tests for CreateCaseProposalReceivedBT marker behaviour (CP-05-005).

AC-4: Verifies that
  - The ``PendingCreateCaseActivity`` marker is written after Accept succeeds
    and before Create fires (AC-2).
  - The marker is removed when Create(VulnerabilityCase) is delivered
    successfully (AC-3).
  - The marker remains when Create(VulnerabilityCase) delivery fails (AC-2
    partial-failure path).
  - The marker stores at minimum: proposal_id, case_actor_id, vendor_uri,
    and the pre-constructed Create(VulnerabilityCase) payload (AC-1).
"""

import logging
from unittest.mock import patch

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.case_proposal_received_tree import (
    _ClearCreateCaseMarkerNode,
    _WriteCreateCaseMarkerNode,
)
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.semantic_registry import extract_event

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    VulnerabilityCase,
)


@pytest.fixture
def make_payload():
    """Return a helper that extracts a VultronEvent from an AS2 activity."""

    def _make_payload(activity, **extra_fields):
        event = extract_event(activity)
        if extra_fields:
            return event.model_copy(update=extra_fields)
        return event

    return _make_payload


_CASE_ACTOR_URI = "https://example.org/case-actors/svc-1"
_VENDOR_URI = "https://example.org/vendors/acme"
_PROPOSAL_URI = "https://example.org/proposals/p-001"


def _make_proposal() -> as_CaseProposal:
    return as_CaseProposal(
        id_=_PROPOSAL_URI,
        attributed_to=_VENDOR_URI,
        object_="https://example.org/reports/r-001",
        target=_CASE_ACTOR_URI,
    )


class TestPendingCreateCaseActivityModel:
    """AC-1: model stores required fields and produces stable ID."""

    def test_build_id_is_stable(self):
        """build_id() returns the same value for the same proposal_id."""
        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        assert "pending-create-case/" in marker_id
        assert PendingCreateCaseActivity.build_id(_PROPOSAL_URI) == marker_id

    def test_id_is_set_from_proposal_id(self):
        """id_ is computed deterministically from proposal_id."""
        marker = PendingCreateCaseActivity(
            proposal_id=_PROPOSAL_URI,
            case_actor_id=_CASE_ACTOR_URI,
            vendor_uri=_VENDOR_URI,
        )
        assert marker.id_ == PendingCreateCaseActivity.build_id(_PROPOSAL_URI)

    def test_required_fields_present(self):
        """Model captures all four required fields (AC-1)."""
        payload = {"type": "Create", "actor": _CASE_ACTOR_URI}
        marker = PendingCreateCaseActivity(
            proposal_id=_PROPOSAL_URI,
            case_actor_id=_CASE_ACTOR_URI,
            vendor_uri=_VENDOR_URI,
            create_activity_payload=payload,
        )
        assert marker.proposal_id == _PROPOSAL_URI
        assert marker.case_actor_id == _CASE_ACTOR_URI
        assert marker.vendor_uri == _VENDOR_URI
        assert marker.create_activity_payload == payload

    def test_roundtrip_through_datalayer(self):
        """Marker survives a DataLayer save/read round-trip."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        marker = PendingCreateCaseActivity(
            proposal_id=_PROPOSAL_URI,
            case_actor_id=_CASE_ACTOR_URI,
            vendor_uri=_VENDOR_URI,
            create_activity_payload={"type": "Create"},
        )
        dl.save(marker)
        retrieved = dl.read(marker.id_)
        assert isinstance(retrieved, PendingCreateCaseActivity)
        assert retrieved.proposal_id == _PROPOSAL_URI
        assert retrieved.case_actor_id == _CASE_ACTOR_URI
        assert retrieved.vendor_uri == _VENDOR_URI


class TestWriteCreateCaseMarkerNode:
    """Unit tests for _WriteCreateCaseMarkerNode."""

    def _run_node(
        self, dl: SqliteDataLayer, actor_id: str, case_id: str, accept_id: str
    ) -> py_trees.common.Status:
        """Execute _WriteCreateCaseMarkerNode via BTBridge."""
        node = _WriteCreateCaseMarkerNode(
            proposal_id=_PROPOSAL_URI, vendor_uri=_VENDOR_URI
        )
        # Wrap in a Sequence so BTBridge can set up the blackboard.
        tree = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[node]
        )
        # Pre-populate blackboard keys the node reads.
        py_trees.blackboard.Blackboard.enable_activity_stream()
        client = py_trees.blackboard.Client(name="TestSetup")
        client.register_key(key="case_id", access=py_trees.common.Access.WRITE)
        client.register_key(
            key="accept_activity_id", access=py_trees.common.Access.WRITE
        )
        client.case_id = case_id
        client.accept_activity_id = accept_id

        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=tree, actor_id=actor_id
        )
        return result.status

    def test_writes_marker_to_datalayer(self):
        """Marker is persisted after node executes (AC-2)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        status = self._run_node(
            dl,
            actor_id=_CASE_ACTOR_URI,
            case_id="https://example.org/cases/c-001",
            accept_id="https://example.org/activities/a-001",
        )
        assert status == py_trees.common.Status.SUCCESS
        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(
            marker, PendingCreateCaseActivity
        ), "Marker should be stored in DataLayer"
        assert marker.proposal_id == _PROPOSAL_URI
        assert marker.case_actor_id == _CASE_ACTOR_URI
        assert marker.vendor_uri == _VENDOR_URI

    def test_marker_contains_create_payload(self):
        """Marker create_activity_payload is non-empty and contains actor (AC-1)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        self._run_node(
            dl,
            actor_id=_CASE_ACTOR_URI,
            case_id="https://example.org/cases/c-001",
            accept_id="https://example.org/activities/a-001",
        )
        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity)
        payload = marker.create_activity_payload
        assert payload, "create_activity_payload must not be empty"
        assert (
            payload.get("actor") == _CASE_ACTOR_URI
            or payload.get("attributedTo") == _CASE_ACTOR_URI
            or _CASE_ACTOR_URI in str(payload)
        ), "Payload must reference the case-actor URI"

    def test_fails_when_case_id_missing(self):
        """FAILURE returned when case_id is absent from blackboard."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        node = _WriteCreateCaseMarkerNode(
            proposal_id=_PROPOSAL_URI, vendor_uri=_VENDOR_URI
        )
        tree = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[node]
        )
        # Only set accept_activity_id — omit case_id.
        client = py_trees.blackboard.Client(name="TestSetup2")
        client.register_key(
            key="accept_activity_id", access=py_trees.common.Access.WRITE
        )
        client.accept_activity_id = "https://example.org/activities/a-001"

        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=tree, actor_id=_CASE_ACTOR_URI
        )
        assert result.status == py_trees.common.Status.FAILURE

    def test_fails_when_accept_activity_id_missing(self):
        """FAILURE returned when accept_activity_id is absent from blackboard."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        node = _WriteCreateCaseMarkerNode(
            proposal_id=_PROPOSAL_URI, vendor_uri=_VENDOR_URI
        )
        tree = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[node]
        )
        # Only set case_id — omit accept_activity_id.
        client = py_trees.blackboard.Client(name="TestSetup3")
        client.register_key(key="case_id", access=py_trees.common.Access.WRITE)
        client.case_id = "https://example.org/cases/c-001"

        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=tree, actor_id=_CASE_ACTOR_URI
        )
        assert result.status == py_trees.common.Status.FAILURE

    def test_fails_when_datalayer_save_raises(self):
        """FAILURE returned when DataLayer.save raises; no subsequent write occurs."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        with patch.object(dl, "save", side_effect=RuntimeError("disk full")):
            status = self._run_node(
                dl,
                actor_id=_CASE_ACTOR_URI,
                case_id="https://example.org/cases/c-001",
                accept_id="https://example.org/activities/a-001",
            )

        assert status == py_trees.common.Status.FAILURE
        # No marker should have been persisted.
        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        assert (
            dl.read(marker_id) is None
        ), "No marker should be stored when save raises"


class TestClearCreateCaseMarkerNode:
    """Unit tests for _ClearCreateCaseMarkerNode."""

    def _run_clear_node(
        self, dl: SqliteDataLayer, actor_id: str
    ) -> py_trees.common.Status:
        node = _ClearCreateCaseMarkerNode(proposal_id=_PROPOSAL_URI)
        tree = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[node]
        )
        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=tree, actor_id=actor_id
        )
        return result.status

    def test_removes_existing_marker(self):
        """Marker is absent after _ClearCreateCaseMarkerNode runs (AC-3)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        marker = PendingCreateCaseActivity(
            proposal_id=_PROPOSAL_URI,
            case_actor_id=_CASE_ACTOR_URI,
            vendor_uri=_VENDOR_URI,
        )
        dl.save(marker)
        # Confirm it's there before clearing.
        assert isinstance(dl.read(marker.id_), PendingCreateCaseActivity)

        status = self._run_clear_node(dl, actor_id=_CASE_ACTOR_URI)
        assert status == py_trees.common.Status.SUCCESS
        assert (
            dl.read(marker.id_) is None
        ), "Marker should be removed after clear node"

    def test_succeeds_when_marker_already_absent(self, caplog):
        """SUCCESS returned even if the marker was already removed (idempotent)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        with caplog.at_level(logging.WARNING, logger="vultron"):
            status = self._run_clear_node(dl, actor_id=_CASE_ACTOR_URI)
        assert status == py_trees.common.Status.SUCCESS

    def test_always_returns_success(self):
        """_ClearCreateCaseMarkerNode always returns SUCCESS regardless of delete result."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        # Run without pre-seeding a marker — delete returns False.
        status = self._run_clear_node(dl, actor_id=_CASE_ACTOR_URI)
        assert status == py_trees.common.Status.SUCCESS


class TestCreateCaseProposalReceivedBTMarkerWiring:
    """AC-4: end-to-end marker write/clear via the full BT tree."""

    def _make_event(self, make_payload):
        """Build a CreateCaseProposalReceivedEvent for the full tree."""
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )

        proposal = _make_proposal()
        activity = as_Create(
            actor=_VENDOR_URI,
            object_=proposal,
            to=[_CASE_ACTOR_URI],
        )
        event = make_payload(activity)
        return event.model_copy(update={"receiving_actor_id": _CASE_ACTOR_URI})

    def test_marker_absent_after_full_success(self, make_payload):
        """AC-3: Marker is removed when Create(VulnerabilityCase) succeeds."""
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        event = self._make_event(make_payload)

        CreateCaseProposalReceivedUseCase(dl, event).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        assert (
            dl.read(marker_id) is None
        ), "Marker must be cleared on full BT success (AC-3)"

    def test_marker_present_when_create_fails(self, make_payload):
        """AC-2 / AC-4: Marker is written and persists when Create delivery fails."""
        from vultron.core.behaviors.case.case_proposal_received_tree import (
            _EmitCreateVulnerabilityCaseNode,
        )
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        event = self._make_event(make_payload)

        # Patch the Create-emit node so it fails after Accept and marker write.
        with patch.object(
            _EmitCreateVulnerabilityCaseNode,
            "update",
            return_value=py_trees.common.Status.FAILURE,
        ):
            CreateCaseProposalReceivedUseCase(dl, event).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(
            marker, PendingCreateCaseActivity
        ), "Marker must be present when Create delivery fails (AC-2)"
        assert marker.proposal_id == _PROPOSAL_URI
        assert marker.vendor_uri == _VENDOR_URI
        assert marker.case_actor_id == _CASE_ACTOR_URI

    def test_marker_payload_stored_on_partial_failure(self, make_payload):
        """AC-1 / AC-4: Marker payload is non-empty on partial failure."""
        from vultron.core.behaviors.case.case_proposal_received_tree import (
            _EmitCreateVulnerabilityCaseNode,
        )
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        event = self._make_event(make_payload)

        with patch.object(
            _EmitCreateVulnerabilityCaseNode,
            "update",
            return_value=py_trees.common.Status.FAILURE,
        ):
            CreateCaseProposalReceivedUseCase(dl, event).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity)
        assert (
            marker.create_activity_payload
        ), "create_activity_payload must not be empty (AC-1)"
