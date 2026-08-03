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
  - The marker is removed when Create(as_VulnerabilityCase) is delivered
    successfully (AC-3).
  - The marker remains when Create(as_VulnerabilityCase) delivery fails (AC-2
    partial-failure path).
  - The marker stores at minimum: proposal_id, case_actor_id, vendor_uri,
    and the pre-constructed Create(as_VulnerabilityCase) payload (AC-1).
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
    as_VulnerabilityCase,
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


_CASE_URI = "https://example.org/cases/c-001"


class TestWriteCreateCaseMarkerNode:
    """Unit tests for _WriteCreateCaseMarkerNode."""

    def _seed_case(self, dl: SqliteDataLayer, case_id: str) -> None:
        """Seed a minimal VulnerabilityCase so _build_case_object succeeds."""
        from vultron.core.models.case import VulnerabilityCase

        dl.save(VulnerabilityCase(id_=case_id, attributed_to=_CASE_ACTOR_URI))

    def _run_node(
        self,
        dl: SqliteDataLayer,
        actor_id: str,
        case_id: str,
        accept_id: str,
        seed: bool = True,
    ) -> py_trees.common.Status:
        """Execute _WriteCreateCaseMarkerNode via BTBridge."""
        if seed:
            self._seed_case(dl, case_id)
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
        case_id = "https://example.org/cases/c-001"
        accept_id = "https://example.org/activities/a-001"
        self._run_node(
            dl,
            actor_id=_CASE_ACTOR_URI,
            case_id=case_id,
            accept_id=accept_id,
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

    def test_marker_payload_uses_case_id_as_context(self):
        """AC-1 (ADR-0045): Create(VulnerabilityCase) payload carries context=case_uri.

        CP-05-003 requires context = case URI for inbox deferral routing.  The
        old assignment (context = Accept URI) caused a bootstrap deadlock.
        """
        dl = SqliteDataLayer("sqlite:///:memory:")
        case_id = "https://example.org/cases/c-field-test"
        accept_id = "https://example.org/activities/accept-field-test"
        self._run_node(
            dl,
            actor_id=_CASE_ACTOR_URI,
            case_id=case_id,
            accept_id=accept_id,
        )
        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity)
        payload = marker.create_activity_payload
        assert payload.get("context") == case_id, (
            "context MUST be the case URI (CP-05-003, ADR-0045); "
            f"got {payload.get('context')!r}"
        )
        assert payload.get("inReplyTo") == accept_id, (
            "inReplyTo MUST be the Accept URI (CP-05-003, ADR-0045); "
            f"got {payload.get('inReplyTo')!r}"
        )

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
        self._seed_case(dl, _CASE_URI)

        with patch.object(dl, "save", side_effect=RuntimeError("disk full")):
            status = self._run_node(
                dl,
                actor_id=_CASE_ACTOR_URI,
                case_id=_CASE_URI,
                accept_id="https://example.org/activities/a-001",
                seed=False,
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
        """AC-3: Marker is removed when Create(as_VulnerabilityCase) succeeds."""
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

    def test_emit_node_uses_marker_activity_id(self, make_payload):
        """AC-4: The activity id_ enqueued by node 4 matches the marker payload id_.

        ``_WriteCreateCaseMarkerNode`` (node 3) and
        ``_EmitCreateVulnerabilityCaseNode`` (node 4) must share the same
        activity ``id_``.  If they diverge, the retry runner checks the
        marker's ``id_`` against the outbox and — not finding it — enqueues
        a second ``Create(as_VulnerabilityCase)`` as a duplicate.

        This test asserts ID consistency by:
        1. Running the full BT with ``_ClearCreateCaseMarkerNode`` no-oped so
           the marker is preserved after node 4 succeeds.
        2. Reconstructing the activity from the marker's stored payload.
        3. Verifying that ``id_`` is present in the case-actor's outbox.
        """
        from vultron.core.behaviors.case.case_proposal_received_tree import (
            _ClearCreateCaseMarkerNode,
        )
        from vultron.core.models.activity import VultronCreateCaseActivity
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        event = self._make_event(make_payload)

        # Patch the clear node to skip deletion so the marker stays in the DL.
        def _skip_delete(
            self_node: _ClearCreateCaseMarkerNode,
        ) -> py_trees.common.Status:  # noqa: N803
            return py_trees.common.Status.SUCCESS

        with patch.object(_ClearCreateCaseMarkerNode, "update", _skip_delete):
            CreateCaseProposalReceivedUseCase(dl, event).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(
            marker, PendingCreateCaseActivity
        ), "Marker should still be present (clear was no-oped)"

        stored_activity = VultronCreateCaseActivity.model_validate(
            marker.create_activity_payload
        )
        marker_activity_id = stored_activity.id_

        outbox = dl.outbox_list_for_actor(_CASE_ACTOR_URI)
        assert marker_activity_id in outbox, (
            "Activity id_ in the marker's payload must match the id_ in the"
            " outbox. A mismatch causes the retry runner to enqueue a"
            " duplicate Create(as_VulnerabilityCase) after crash/restart."
        )


# ---------------------------------------------------------------------------
# ADR-0041 native-initialization tests (AC-1 through AC-6)
# ---------------------------------------------------------------------------

_REPORT_URI = "https://example.org/reports/r-001"
_REPORTER_URI = "https://example.org/actors/reporter-01"


def _make_full_event(make_payload, *, report_id: str | None = _REPORT_URI):
    """Build a CreateCaseProposalReceivedEvent with an optional report URI."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )

    proposal = as_CaseProposal(
        id_=_PROPOSAL_URI,
        attributed_to=_VENDOR_URI,
        object_=report_id or "https://example.org/reports/none",
        target=_CASE_ACTOR_URI,
    )
    activity = as_Create(
        actor=_VENDOR_URI,
        object_=proposal,
        to=[_CASE_ACTOR_URI],
    )
    event = make_payload(activity)
    return event.model_copy(update={"receiving_actor_id": _CASE_ACTOR_URI})


def _seed_report(dl: SqliteDataLayer) -> None:
    """Store a VulnerabilityReport attributed to the reporter."""
    from vultron.core.models.report import VulnerabilityReport

    # noqa: F401 — ensure VulnerabilityReport is in the vocabulary registry
    from vultron.wire.as2.vocab.objects.vulnerability_report import (  # noqa: F401
        as_VulnerabilityReport,
    )

    report = VulnerabilityReport(id_=_REPORT_URI, attributed_to=_REPORTER_URI)
    dl.save(report)


def _run_full_bt(make_payload, dl: SqliteDataLayer, actor_config=None) -> None:
    from vultron.core.use_cases.received.case_proposal import (
        CreateCaseProposalReceivedUseCase,
    )

    event = _make_full_event(make_payload)
    CreateCaseProposalReceivedUseCase(
        dl, event, actor_config=actor_config
    ).execute()


def _owner_roles(dl: SqliteDataLayer) -> list:
    """Return the CVD roles of the proposing actor's participant record."""
    from vultron.core.models.case import VulnerabilityCase

    cases = list(dl.list_objects("VulnerabilityCase"))
    assert cases
    case = cases[0]
    assert isinstance(case, VulnerabilityCase)
    participant_id = case.actor_participant_index.get(_VENDOR_URI)
    assert participant_id is not None
    participant = dl.read(participant_id)
    assert participant is not None
    return list(getattr(participant, "case_roles", []))


class TestADR0041VendorParticipant:
    """ADR-0041 AC-1: vendor added as CASE_OWNER at RM.RECEIVED."""

    def test_vendor_participant_created(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        # Find the created case
        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases, "At least one VulnerabilityCase must exist"
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        assert (
            _VENDOR_URI in case.actor_participant_index
        ), "Vendor must be in actor_participant_index as CASE_OWNER (AC-1)"

    def test_vendor_participant_rm_received(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.rm import RM

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)

        participant_id = case.actor_participant_index.get(_VENDOR_URI)
        assert participant_id is not None, "Vendor participant must exist"
        participant = dl.read(participant_id)
        assert participant is not None, "Vendor participant must be readable"
        statuses = getattr(participant, "participant_statuses", [])
        assert statuses, "Vendor participant must have at least one status"
        rm_state = statuses[0].rm.state
        assert (
            rm_state == RM.RECEIVED
        ), f"Vendor must be at RM.RECEIVED, got {rm_state}"

    def test_vendor_has_case_owner_role(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)

        participant_id = case.actor_participant_index.get(_VENDOR_URI)
        assert participant_id is not None
        participant = dl.read(participant_id)
        assert participant is not None
        roles = getattr(participant, "case_roles", [])
        assert (
            CVDRole.CASE_OWNER in roles
        ), f"Vendor must have CASE_OWNER role, got {roles}"


class TestOwnerRolesComeFromActorConfig:
    """The owner's non-CASE_OWNER roles come from ``ActorConfig`` (CFG-07-002).

    Regression guard: the node used to hard-code ``[CASE_OWNER, VENDOR]``.
    That mislabelled a coordinator that receives a report as a vendor, after
    which VFD fix-lifecycle checks demanded a fix the coordinator never
    produces (fccv-extension M6/M7 failure).
    """

    def test_vendor_config_yields_vendor_role(self, make_payload):
        from vultron.config.actor import ActorConfig
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(
            make_payload,
            dl,
            actor_config=ActorConfig(default_case_roles=[CVDRole.VENDOR]),
        )

        roles = _owner_roles(dl)
        assert CVDRole.CASE_OWNER in roles
        assert CVDRole.VENDOR in roles

    def test_coordinator_config_does_not_yield_vendor_role(self, make_payload):
        from vultron.config.actor import ActorConfig
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(
            make_payload,
            dl,
            actor_config=ActorConfig(default_case_roles=[CVDRole.COORDINATOR]),
        )

        roles = _owner_roles(dl)
        assert CVDRole.CASE_OWNER in roles
        assert CVDRole.COORDINATOR in roles
        assert (
            CVDRole.VENDOR not in roles
        ), f"a coordinator must not be labelled VENDOR, got {roles}"

    def test_no_actor_config_yields_case_owner_only(self, make_payload):
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl, actor_config=None)

        roles = _owner_roles(dl)
        assert roles == [CVDRole.CASE_OWNER]


class TestADR0041ReporterParticipant:
    """ADR-0041 AC-2: reporter added as REPORTER at RM.ACCEPTED."""

    def test_reporter_participant_created(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        assert (
            _REPORTER_URI in case.actor_participant_index
        ), "Reporter must be in actor_participant_index (AC-2)"

    def test_reporter_participant_rm_accepted(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.rm import RM

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)

        participant_id = case.actor_participant_index.get(_REPORTER_URI)
        assert participant_id is not None
        participant = dl.read(participant_id)
        assert participant is not None
        statuses = getattr(participant, "participant_statuses", [])
        assert statuses, "Reporter participant must have at least one status"
        rm_state = statuses[0].rm.state
        assert (
            rm_state == RM.ACCEPTED
        ), f"Reporter must be at RM.ACCEPTED, got {rm_state}"

    def test_no_reporter_when_report_absent(self, make_payload):
        """AC-2 graceful degradation: no reporter if report not in DataLayer."""
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer("sqlite:///:memory:")
        # Deliberately NOT seeding the report
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases, "Case must still be created even without a seeded report"
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        # Vendor participant must still be present even without the reporter
        assert _VENDOR_URI in case.actor_participant_index


class TestADR0041EmbargoInit:
    """ADR-0041 AC-3: default embargo initialized."""

    def test_active_embargo_set(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        assert (
            case.active_embargo is not None
        ), "Case must have an active embargo after initialization (AC-3)"

    def test_embargo_event_stored(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.embargo_event import EmbargoEvent

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)

        embargo_id = case.active_embargo
        assert embargo_id is not None
        embargo_obj = dl.read(embargo_id)
        assert isinstance(
            embargo_obj, EmbargoEvent
        ), "EmbargoEvent must be stored in DataLayer (AC-3)"

    def test_vendor_owner_seeded_as_signatory(self, make_payload):
        """CM-13: vendor (CASE_OWNER) is SIGNATORY on the active embargo.

        Regression for the gap where InitializeDefaultEmbargoNode's
        SeedOwnerAsSignatoryNode keys on actor_id (the CaseActor, not a
        participant here) and silently no-ops, leaving an ACTIVE embargo with
        no signatory.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.states.participant_embargo_consent import PEC

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        assert case.active_embargo is not None

        vendor_pid = case.actor_participant_index.get(_VENDOR_URI)
        assert vendor_pid, "vendor must have a participant entry"
        vendor_participant = dl.read(vendor_pid)
        assert isinstance(vendor_participant, CaseParticipant)
        assert vendor_participant.embargo_consent_state == PEC.SIGNATORY, (
            "Vendor (CASE_OWNER) must be seeded SIGNATORY on the active"
            " embargo at case creation (CM-13)"
        )
        assert (
            case.active_embargo in vendor_participant.accepted_embargo_ids
        ), "Active embargo id must be recorded in vendor's accepted list"


class TestCM14005ReporterSignatory:
    """CM-14-005: reporter seeded as embargo SIGNATORY at case initialization."""

    def _get_reporter_participant(self, dl):
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        participant_id = case.actor_participant_index.get(_REPORTER_URI)
        if participant_id is None:
            return None, case
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        return participant, case

    def test_reporter_seeded_as_signatory(self, make_payload):
        """AC-1: reporter is SIGNATORY after initialization."""
        from vultron.core.states.participant_embargo_consent import PEC

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        participant, case = self._get_reporter_participant(dl)
        assert participant is not None, "Reporter participant must exist"
        assert participant.embargo_consent_state == PEC.SIGNATORY, (
            "Reporter must be seeded SIGNATORY on the active embargo"
            f" at case initialization (CM-14-005), got"
            f" {participant.embargo_consent_state!r}"
        )

    def test_reporter_accepted_embargo_ids_populated(self, make_payload):
        """AC-2: reporter's accepted_embargo_ids includes the active embargo."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        participant, case = self._get_reporter_participant(dl)
        assert participant is not None, "Reporter participant must exist"
        assert case.active_embargo is not None
        assert case.active_embargo in participant.accepted_embargo_ids, (
            "Reporter's accepted_embargo_ids must include the active embargo"
            " (CM-14-005 AC-2)"
        )

    def test_no_active_embargo_reporter_remains_no_embargo(self):
        """AC-3: _SeedReporterSignatoryNode no-ops gracefully when no active embargo."""
        from vultron.core.behaviors.case.case_proposal_received_tree import (
            _SeedReporterSignatoryNode,
        )
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.report import VulnerabilityReport
        from vultron.core.states.participant_embargo_consent import PEC

        dl = SqliteDataLayer("sqlite:///:memory:")
        # Build a minimal case with no active embargo and a reporter participant
        case = VulnerabilityCase(id_=_CASE_URI)
        reporter_participant = CaseParticipant(
            id_="https://example.org/participants/reporter",
            attributed_to=_REPORTER_URI,
            context=_CASE_URI,
        )
        dl.save(reporter_participant)
        case.actor_participant_index[_REPORTER_URI] = reporter_participant.id_
        case.case_participants.append(reporter_participant.id_)
        dl.save(case)
        report = VulnerabilityReport(
            id_=_REPORT_URI, attributed_to=_REPORTER_URI
        )
        dl.save(report)

        node = _SeedReporterSignatoryNode(report_id=_REPORT_URI)
        tree = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[node]
        )
        client = py_trees.blackboard.Client(name="TestSetupAC3")
        client.register_key(key="case_id", access=py_trees.common.Access.WRITE)
        client.case_id = _CASE_URI

        from vultron.core.behaviors.bridge import BTBridge

        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=tree, actor_id=_CASE_ACTOR_URI
        )
        assert result.status == py_trees.common.Status.SUCCESS, (
            "_SeedReporterSignatoryNode must return SUCCESS when no active"
            " embargo (AC-3, best-effort)"
        )
        stored_participant = dl.read(reporter_participant.id_)
        assert isinstance(stored_participant, CaseParticipant)
        assert stored_participant.embargo_consent_state == PEC.NO_EMBARGO, (
            "Reporter must remain NO_EMBARGO when no active embargo exists"
            " (CM-14-005 AC-3)"
        )

    def test_reporter_signatory_ledger_snapshot_consistent(self, make_payload):
        """AC-4: ledger snapshot for reporter shows SIGNATORY consent.

        The ``_CommitNativeLedgerEntriesNode`` runs *after*
        ``_SeedReporterSignatoryNode``, so the participant status it snapshots
        must already carry ``emConsentState=SIGNATORY`` and
        ``embargoAdherence=True`` — no contradictory pair.
        """
        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        participant, case = self._get_reporter_participant(dl)
        assert participant is not None

        entries = list(dl.list_objects("CaseLedgerEntry"))
        reporter_status_entries = [
            e
            for e in entries
            if getattr(e, "event_type", None)
            == "add_participant_status_to_participant"
            and getattr(e, "case_id", None) == case.id_
        ]
        assert (
            reporter_status_entries
        ), "add_participant_status_to_participant entries must be present"

        # The snapshot structure is:
        # { "type": "Add", "actor": CaseActor, "object": {ParticipantStatus...},
        #   "target": {CaseParticipant...}, "context": case_id }
        # The reporter's entry has object["attributedTo"] == _REPORTER_URI.
        reporter_entries = [
            e
            for e in reporter_status_entries
            if _REPORTER_URI
            in str(
                (getattr(e, "payload_snapshot", {}).get("object") or {}).get(
                    "attributedTo", ""
                )
            )
        ]
        assert reporter_entries, (
            "At least one ledger entry's object.attributedTo must be the"
            " reporter URI"
        )
        for entry in reporter_entries:
            snap = getattr(entry, "payload_snapshot", {})
            obj = snap.get("object", {})
            em_consent = obj.get("emConsentState") or obj.get(
                "em_consent_state"
            )
            embargo_adherence = obj.get("embargoAdherence") or obj.get(
                "embargo_adherence"
            )
            if em_consent is not None:
                assert em_consent in ("SIGNATORY", "signatory"), (
                    f"Ledger snapshot emConsentState must be SIGNATORY for"
                    f" reporter, got {em_consent!r} (CM-14-005 AC-4)"
                )
            if embargo_adherence is not None:
                assert embargo_adherence is True, (
                    f"Ledger snapshot embargoAdherence must be True for"
                    f" reporter, got {embargo_adherence!r} (CM-14-005 AC-4)"
                )

    def test_reporter_embargo_adherence_true(self, make_payload):
        """AC-5: embargo_adherence is True in reporter's latest ParticipantStatus."""
        from vultron.core.states.participant_embargo_consent import PEC

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        participant, _case = self._get_reporter_participant(dl)
        assert participant is not None
        assert participant.embargo_consent_state == PEC.SIGNATORY

        # embargo_adherence lives on ParticipantStatus, not on CaseParticipant.
        # The latest status is exposed via participant.participant_status.
        latest_status = participant.participant_status
        assert (
            latest_status is not None
        ), "Reporter must have at least one ParticipantStatus"
        assert latest_status.embargo_adherence is True, (
            "reporter ParticipantStatus.embargo_adherence must be True after"
            f" initialization (CM-14-005 AC-5),"
            f" got {latest_status.embargo_adherence!r}"
        )

    def test_no_report_reporter_seeding_does_not_fail_sequence(
        self, make_payload
    ):
        """Reporter seeding skips gracefully when report is absent."""
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer("sqlite:///:memory:")
        # Deliberately NOT seeding the report
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases, "Case must still be created even without a seeded report"
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        # Vendor participant must still be present
        assert _VENDOR_URI in case.actor_participant_index


class TestADR0041LedgerEntries:
    """ADR-0041 AC-4: canonical ledger entries committed natively."""

    def test_create_case_ledger_entry_present(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        case_id = case.id_

        entries = list(dl.list_objects("CaseLedgerEntry"))
        event_types = {getattr(e, "event_type", None) for e in entries}
        assert (
            "create_case" in event_types
        ), "create_case ledger entry must be committed natively (AC-4)"

        # All create_case entries must have actor = CaseActor
        create_entries = [
            e
            for e in entries
            if getattr(e, "event_type", None) == "create_case"
            and getattr(e, "case_id", None) == case_id
        ]
        assert create_entries, "create_case entry must reference the case_id"
        for entry in create_entries:
            snapshot = getattr(entry, "payload_snapshot", {})
            assert (
                snapshot.get("actor") == _CASE_ACTOR_URI
            ), f"create_case actor must be CaseActor, got {snapshot.get('actor')}"

    def test_add_report_to_case_entry_present(self, make_payload):
        """add_report_to_case ledger entry must be committed with actor=CaseActor (AC-4)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case_id = cases[0].id_

        entries = list(dl.list_objects("CaseLedgerEntry"))
        report_entries = [
            e
            for e in entries
            if getattr(e, "event_type", None) == "add_report_to_case"
            and getattr(e, "case_id", None) == case_id
        ]
        assert (
            report_entries
        ), "add_report_to_case ledger entry must be committed natively (AC-4)"
        for entry in report_entries:
            snapshot = getattr(entry, "payload_snapshot", {})
            assert (
                snapshot.get("actor") == _CASE_ACTOR_URI
            ), f"add_report_to_case actor must be CaseActor, got {snapshot.get('actor')}"

    def test_add_participant_status_entries_present(self, make_payload):
        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        entries = list(dl.list_objects("CaseLedgerEntry"))
        event_types = [getattr(e, "event_type", None) for e in entries]
        assert (
            "add_participant_status_to_participant" in event_types
        ), "add_participant_status_to_participant entries must be present (AC-4)"

    def test_add_case_status_uses_vendor_actor(self, make_payload):
        """add_case_status_to_case must use vendor URI as actor (not CaseActor)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        entries = list(dl.list_objects("CaseLedgerEntry"))
        cs_entries = [
            e
            for e in entries
            if getattr(e, "event_type", None) == "add_case_status_to_case"
        ]
        assert cs_entries, "add_case_status_to_case entry must be present"
        for entry in cs_entries:
            snapshot = getattr(entry, "payload_snapshot", {})
            actor = snapshot.get("actor", "")
            assert actor != _CASE_ACTOR_URI, (
                "add_case_status_to_case must NOT use CaseActor as actor"
                " — the vendor set the genesis status, so the vendor URI is"
                " the correct provenance (the signature IS case-authored per"
                " CLP-12-001, so the guard would not have caught this)"
            )
            assert (
                actor == _VENDOR_URI
            ), f"add_case_status_to_case actor must be vendor URI, got {actor!r}"


class TestCM18007InitLedgerEntries:
    """CM-18-007 and CM-14-003: one init entry per participant; vendor is SIGNATORY."""

    def test_exactly_one_participant_status_entry_per_participant(
        self, make_payload
    ):
        """Each participant gets exactly one add_participant_status_to_participant
        ledger entry — no NO_EMBARGO placeholder followed by a corrective entry
        (CM-18-007 AC-3)."""
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        participant_count = len(case.case_participants)

        entries = list(dl.list_objects("CaseLedgerEntry"))
        ps_entries = [
            e
            for e in entries
            if getattr(e, "event_type", None)
            == "add_participant_status_to_participant"
        ]
        assert len(ps_entries) == participant_count, (
            f"Expected exactly {participant_count} "
            "add_participant_status_to_participant entries (one per participant),"
            f" got {len(ps_entries)} (CM-18-007)"
        )

    def test_vendor_case_owner_appears_as_signatory_in_init_ledger(
        self, make_payload
    ):
        """Vendor (CASE_OWNER) init ledger entry must show SIGNATORY consent
        (CM-14-003 AC-4)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        entries = list(dl.list_objects("CaseLedgerEntry"))
        vendor_ps_entries = [
            e
            for e in entries
            if getattr(e, "event_type", None)
            == "add_participant_status_to_participant"
            and _VENDOR_URI
            in str(
                getattr(e, "payload_snapshot", {})
                .get("object", {})
                .get("attributedTo", "")
            )
        ]
        assert vendor_ps_entries, (
            "Vendor must have an add_participant_status_to_participant"
            " init ledger entry (CM-14-003)"
        )
        entry = vendor_ps_entries[0]
        obj = getattr(entry, "payload_snapshot", {}).get("object", {})
        assert obj.get("emConsentState") == "SIGNATORY", (
            f"Vendor init entry must show SIGNATORY, got"
            f" {obj.get('emConsentState')!r} (CM-14-003)"
        )


class TestADR0041InlineParticipantsPayload:
    """ADR-0041 AC-5: Create(VulnerabilityCase) embeds inline participant objects."""

    def test_marker_payload_has_inline_participants(self, make_payload):
        """Create payload in marker must embed participants as objects, not IDs."""
        from vultron.core.behaviors.case.case_proposal_received_tree import (
            _ClearCreateCaseMarkerNode,
        )
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        event = _make_full_event(make_payload)

        def _skip_delete(self_node):
            return py_trees.common.Status.SUCCESS

        with patch.object(_ClearCreateCaseMarkerNode, "update", _skip_delete):
            CreateCaseProposalReceivedUseCase(dl, event).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity)

        payload = marker.create_activity_payload
        assert payload, "Marker payload must not be empty"

        obj_field = payload.get("object") or payload.get("object_")
        assert isinstance(obj_field, dict), (
            "Create(VulnerabilityCase) payload.object must be an inline dict,"
            f" not {type(obj_field).__name__!r}"
        )
        participants = obj_field.get("case_participants", [])
        assert (
            participants
        ), "Inline case object must have at least one participant (AC-5)"
        # Each participant must be a dict (inline object), not a bare ID string.
        for p in participants:
            assert isinstance(
                p, dict
            ), f"case_participants entries must be inline dicts, got {type(p).__name__!r}"

    def test_vendor_participant_inline_in_payload(self, make_payload):
        """Vendor participant must appear as inline object in Create payload."""
        from vultron.core.behaviors.case.case_proposal_received_tree import (
            _ClearCreateCaseMarkerNode,
        )
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        event = _make_full_event(make_payload)

        def _skip_delete(self_node):
            return py_trees.common.Status.SUCCESS

        with patch.object(_ClearCreateCaseMarkerNode, "update", _skip_delete):
            CreateCaseProposalReceivedUseCase(dl, event).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity)

        payload = marker.create_activity_payload
        obj_field = payload.get("object") or payload.get("object_")
        assert isinstance(obj_field, dict)

        participants = obj_field.get("case_participants", [])
        attributed_tos = {
            p.get("attributed_to") or p.get("attributedTo")
            for p in participants
            if isinstance(p, dict)
        }
        assert _VENDOR_URI in attributed_tos, (
            f"Vendor '{_VENDOR_URI}' must appear as inline participant in"
            " Create(VulnerabilityCase) payload (AC-5)"
        )


class TestADR0041Idempotency:
    """ADR-0041 / CP-05-006: re-processing a proposal is idempotent.

    The ADR explicitly warns that a prior attempt shifted ledger indices and
    broke replication timing.  A duplicate ``Create(as_CaseProposal)`` (after
    the retry marker is cleared) must reuse the existing case and must NOT
    create duplicate participants or duplicate ledger entries.
    """

    def test_duplicate_proposal_no_duplicate_participants_or_entries(
        self, make_payload
    ):
        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)

        # First delivery — creates the case, participants, ledger entries,
        # and clears the retry marker on success.
        _run_full_bt(make_payload, dl)

        from vultron.core.models.case import VulnerabilityCase

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert len(cases) == 1
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        case_id = case.id_
        first_index = dict(case.actor_participant_index)
        entries_before = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if getattr(e, "case_id", None) == case_id
        ]

        # Second delivery of the SAME proposal — marker was cleared, so the
        # AC-3 guard falls through; _LoadExistingCaseNode must reuse the case.
        _run_full_bt(make_payload, dl)

        cases_after = list(dl.list_objects("VulnerabilityCase"))
        assert (
            len(cases_after) == 1
        ), "duplicate proposal must not create a second case"
        reused = cases_after[0]
        assert isinstance(reused, VulnerabilityCase)
        assert reused.id_ == case_id

        assert dict(reused.actor_participant_index) == first_index, (
            "duplicate proposal must not add duplicate participants"
            " (participant index must be unchanged)"
        )

        entries_after = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if getattr(e, "case_id", None) == case_id
        ]
        assert len(entries_after) == len(entries_before), (
            "duplicate proposal must not append duplicate ledger entries"
            f" (before={len(entries_before)}, after={len(entries_after)}) —"
            " ledger-index stability is required (ADR-0041)"
        )


class TestADR0041GenesisCommitFailure:
    """The genesis create_case commit failure must not be masked."""

    def test_genesis_create_case_failure_aborts(self, make_payload):
        """A failed genesis create_case commit returns FAILURE (not SUCCESS).

        The genesis entry is the root of the CaseActor's hash chain; a
        best-effort SUCCESS here would tell the vendor a case exists while the
        canonical ledger has no root.
        """
        from py_trees.common import Status

        from vultron.core.behaviors.case.case_proposal_received_tree import (
            _CommitNativeLedgerEntriesNode,
        )

        node = _CommitNativeLedgerEntriesNode(
            vendor_uri=_VENDOR_URI, report_id=_REPORT_URI
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        _seed_report(dl)
        # Build a real case so the node reaches the commit step.
        _run_full_bt(make_payload, dl)
        case = list(dl.list_objects("VulnerabilityCase"))[0]

        # Wire up the node against the real DL + case, forcing every commit
        # (including genesis create_case) to report failure.
        node.datalayer = dl
        node.actor_id = _CASE_ACTOR_URI

        class _BB:
            def get(self, _key):
                return case.id_

        node.blackboard = _BB()  # type: ignore[assignment]

        with patch.object(
            _CommitNativeLedgerEntriesNode,
            "_commit_one",
            return_value=False,
        ):
            result = node.update()

        assert result == Status.FAILURE, (
            "genesis create_case commit failure must propagate as FAILURE,"
            " not be masked as best-effort SUCCESS"
        )

    def test_case_not_found_is_best_effort_success(self, make_payload):
        """case-not-found in the ledger node is best-effort SUCCESS."""
        from py_trees.common import Status

        from vultron.core.behaviors.case.case_proposal_received_tree import (
            _CommitNativeLedgerEntriesNode,
        )

        node = _CommitNativeLedgerEntriesNode(
            vendor_uri=_VENDOR_URI, report_id=_REPORT_URI
        )
        dl = SqliteDataLayer("sqlite:///:memory:")
        node.datalayer = dl
        node.actor_id = _CASE_ACTOR_URI

        class _BB:
            def get(self, _key):
                return "urn:uuid:does-not-exist"

        node.blackboard = _BB()  # type: ignore[assignment]

        assert node.update() == Status.SUCCESS, (
            "case-not-found must be best-effort SUCCESS (the ledger is an"
            " audit record, not a precondition for the outbound emissions)"
        )
