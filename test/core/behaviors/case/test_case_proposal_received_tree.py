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
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import patch

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes import (
    ClearCreateCaseMarkerNode,
    WriteCreateCaseMarkerNode,
)
from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.em import EM
from vultron.semantic_registry import extract_event

# imported for vocabulary registration side-effect
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


def _vendor_profile(policy_duration: timedelta | None = None) -> CoreActor:
    """The proposing vendor's inline profile (CP-01-010), optionally with a
    published embargo policy of *policy_duration*."""
    from vultron.core.models.actor import VultronOrganization
    from vultron.core.models.embargo_policy import EmbargoPolicy

    if policy_duration is None:
        return VultronOrganization(id_=_VENDOR_URI)
    return VultronOrganization(
        id_=_VENDOR_URI,
        embargo_policy=EmbargoPolicy(
            actor_id=_VENDOR_URI,
            inbox=f"{_VENDOR_URI}/inbox",
            preferred_duration=policy_duration,
        ),
    )


_PROPOSAL_URI = "https://example.org/proposals/p-001"


def _make_proposal() -> as_CaseProposal:
    return as_CaseProposal(
        id_=_PROPOSAL_URI,
        attributed_to=_VENDOR_URI,
        object_="https://example.org/reports/r-001",
        target=_CASE_ACTOR_URI,
    )


@pytest.mark.spec("CP-05-005")
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
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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


@pytest.mark.spec("CP-05-005")
class TestWriteCreateCaseMarkerNode:
    """Unit tests for WriteCreateCaseMarkerNode."""

    def _seed_case(self, dl: SqliteDataLayer, case_id: str) -> None:
        """Seed a minimal VulnerabilityCase so _build_case_object succeeds."""
        from vultron.core.models.case import VulnerabilityCase

        dl.save(VulnerabilityCase(id_=case_id, attributed_to=_VENDOR_URI))

    def _run_node(
        self,
        dl: SqliteDataLayer,
        actor_id: str,
        case_id: str,
        accept_id: str,
        seed: bool = True,
    ) -> py_trees.common.Status:
        """Execute WriteCreateCaseMarkerNode via BTBridge."""
        if seed:
            self._seed_case(dl, case_id)
        node = WriteCreateCaseMarkerNode(
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

        result = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute_with_setup(tree=tree, actor_id=actor_id)
        return result.status

    def test_writes_marker_to_datalayer(self):
        """Marker is persisted after node executes (AC-2)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        status = self._run_node(
            dl,
            actor_id=_CASE_ACTOR_URI,
            case_id="https://example.org/cases/c-001",
            accept_id="https://example.org/activities/a-001",
        )
        assert status == py_trees.common.Status.SUCCESS
        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity), (
            "Marker should be stored in DataLayer"
        )
        assert marker.proposal_id == _PROPOSAL_URI
        assert marker.case_actor_id == _CASE_ACTOR_URI
        assert marker.vendor_uri == _VENDOR_URI

    @pytest.mark.spec("EMB-18-003")
    def test_marker_payload_carries_the_active_embargo_inline(self):
        """The Create a recipient seeds from carries the embargo record."""
        from vultron.core.models._helpers import days_from_now_utc
        from vultron.core.models.embargo_event import EmbargoEvent

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        case_id = "https://example.org/cases/c-embargo"
        embargo = EmbargoEvent(
            id_=f"{case_id}/embargo_events/e1",
            context=case_id,
            end_time=days_from_now_utc(45),
        )
        dl.save(embargo)
        dl.save(
            VulnerabilityCase(
                id_=case_id,
                attributed_to=_CASE_ACTOR_URI,
                active_embargo=embargo.id_,
            )
        )

        status = self._run_node(
            dl,
            actor_id=_CASE_ACTOR_URI,
            case_id=case_id,
            accept_id="https://example.org/activities/a-embargo",
            seed=False,
        )

        assert status == py_trees.common.Status.SUCCESS
        marker = dl.read(PendingCreateCaseActivity.build_id(_PROPOSAL_URI))
        assert isinstance(marker, PendingCreateCaseActivity)
        case_obj = marker.create_activity_payload["object"]
        carried = case_obj.get("activeEmbargo", case_obj.get("active_embargo"))
        assert isinstance(carried, dict), carried
        assert carried["id"] == embargo.id_

    @pytest.mark.spec("EMB-18-003")
    def test_unreadable_active_embargo_fails_without_a_marker(self, caplog):
        """A case naming an embargo this store lacks is never sent."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        case_id = "https://example.org/cases/c-unheld"
        dl.save(
            VulnerabilityCase(
                id_=case_id,
                attributed_to=_CASE_ACTOR_URI,
                active_embargo=f"{case_id}/embargo_events/unheld",
            )
        )

        with caplog.at_level(logging.ERROR):
            status = self._run_node(
                dl,
                actor_id=_CASE_ACTOR_URI,
                case_id=case_id,
                accept_id="https://example.org/activities/a-unheld",
                seed=False,
            )

        assert status == py_trees.common.Status.FAILURE
        assert (
            dl.read(PendingCreateCaseActivity.build_id(_PROPOSAL_URI)) is None
        )
        assert any("EMB-18-003" in r.getMessage() for r in caplog.records)

    def test_marker_contains_create_payload(self):
        """Marker create_activity_payload is non-empty and contains actor (AC-1)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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

    @pytest.mark.spec("ARCH-20-001")
    def test_marker_payload_is_the_ports_rendering(self):
        """The retry payload is the port's AS2 rendering, not a core dump.

        ``@context`` comes only from a by-alias dump of a ``CoreObject``, and the
        rendering is JSON-mode, so both mark the payload as the port's.  It must
        also revalidate to the activity the retry runner re-sends (#1139).
        """
        from vultron.core.models.activity import VultronCreateCaseActivity

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        case_id = "https://example.org/cases/c-render"
        self._run_node(
            dl,
            actor_id=_CASE_ACTOR_URI,
            case_id=case_id,
            accept_id="https://example.org/activities/a-render",
        )
        marker = dl.read(PendingCreateCaseActivity.build_id(_PROPOSAL_URI))
        assert isinstance(marker, PendingCreateCaseActivity)
        payload = marker.create_activity_payload
        assert "@context" in payload
        assert isinstance(payload.get("published"), str)
        activity = VultronCreateCaseActivity.model_validate(payload)
        assert activity.context == case_id
        assert activity.actor == _CASE_ACTOR_URI

    @pytest.mark.spec("CM-10-004")
    def test_bootstrap_addressees_withhold_an_inert_finder(self) -> None:
        """Under an active embargo only a SIGNATORY reporter is bootstrapped.

        The ``Create(VulnerabilityCase)`` copy is case content, so its
        REPORTER/FINDER addressees come from the shared active selection
        (#4046 AC-2): a FINDER that is not SIGNATORY is left out.
        """
        from vultron.core.models._helpers import days_from_now_utc
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.embargo_event import EmbargoEvent
        from vultron.core.states.participant_embargo_consent import PEC
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        case_id = "https://example.org/cases/c-inert"
        embargo = EmbargoEvent(
            id_=f"{case_id}/embargo",
            context=case_id,
            end_time=days_from_now_utc(45),
        )
        dl.save(embargo)
        case = VulnerabilityCase(
            id_=case_id,
            attributed_to=_CASE_ACTOR_URI,
            active_embargo=embargo.id_,
        )
        reporter = "https://example.org/actors/reporter"
        finder = "https://example.org/actors/finder"
        for actor_id, role, pec in (
            (reporter, CVDRole.REPORTER, PEC.SIGNATORY),
            (finder, CVDRole.FINDER, PEC.UNBOUND),
        ):
            participant = CaseParticipant(
                id_=f"{actor_id}/participant",
                attributed_to=actor_id,
                context=case_id,
                case_roles=[role],
                embargo_consent_state=pec,
            )
            dl.save(participant)
            case.add_participant(participant)
        dl.save(case)

        status = self._run_node(
            dl,
            actor_id=_CASE_ACTOR_URI,
            case_id=case_id,
            accept_id="https://example.org/activities/a-inert",
            seed=False,
        )

        assert status == py_trees.common.Status.SUCCESS
        marker = dl.read(PendingCreateCaseActivity.build_id(_PROPOSAL_URI))
        assert isinstance(marker, PendingCreateCaseActivity)
        assert marker.create_activity_payload["to"] == [_VENDOR_URI, reporter]

    def test_fails_when_case_id_missing(self):
        """FAILURE returned when case_id is absent from blackboard."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        node = WriteCreateCaseMarkerNode(
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
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        node = WriteCreateCaseMarkerNode(
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
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        assert dl.read(marker_id) is None, (
            "No marker should be stored when save raises"
        )


@pytest.mark.spec("CP-05-005")
class TestClearCreateCaseMarkerNode:
    """Unit tests for ClearCreateCaseMarkerNode."""

    def _run_clear_node(
        self, dl: SqliteDataLayer, actor_id: str
    ) -> py_trees.common.Status:
        node = ClearCreateCaseMarkerNode(proposal_id=_PROPOSAL_URI)
        tree = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[node]
        )
        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=tree, actor_id=actor_id
        )
        return result.status

    def test_removes_existing_marker(self):
        """Marker is absent after ClearCreateCaseMarkerNode runs (AC-3)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        assert dl.read(marker.id_) is None, (
            "Marker should be removed after clear node"
        )

    def test_succeeds_when_marker_already_absent(self, caplog):
        """SUCCESS returned even if the marker was already removed (idempotent)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        with caplog.at_level(logging.WARNING, logger="vultron"):
            status = self._run_clear_node(dl, actor_id=_CASE_ACTOR_URI)
        assert status == py_trees.common.Status.SUCCESS

    def test_always_returns_success(self):
        """ClearCreateCaseMarkerNode always returns SUCCESS regardless of delete result."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        # Run without pre-seeding a marker — delete returns False.
        status = self._run_clear_node(dl, actor_id=_CASE_ACTOR_URI)
        assert status == py_trees.common.Status.SUCCESS


@pytest.mark.spec("CP-05-005")
class TestCreateCaseProposalReceivedBTMarkerWiring:
    """AC-4: end-to-end marker write/clear via the full BT tree."""

    def _make_event(self, make_payload):
        """Build a CreateCaseProposalReceivedEvent for the full tree."""
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )

        proposal = _make_proposal()
        activity = as_Create(
            actor=_vendor_profile(),
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        event = self._make_event(make_payload)

        CreateCaseProposalReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        assert dl.read(marker_id) is None, (
            "Marker must be cleared on full BT success (AC-3)"
        )

    def test_marker_present_when_create_fails(self, make_payload):
        """AC-2 / AC-4: Marker is written and persists when Create delivery fails."""
        from vultron.core.behaviors.case.nodes import (
            EmitCreateVulnerabilityCaseNode,
        )
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        event = self._make_event(make_payload)

        # Patch the Create-emit node so it fails after Accept and marker write.
        with patch.object(
            EmitCreateVulnerabilityCaseNode,
            "update",
            return_value=py_trees.common.Status.FAILURE,
        ):
            CreateCaseProposalReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            ).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity), (
            "Marker must be present when Create delivery fails (AC-2)"
        )
        assert marker.proposal_id == _PROPOSAL_URI
        assert marker.vendor_uri == _VENDOR_URI
        assert marker.case_actor_id == _CASE_ACTOR_URI

    def test_marker_payload_stored_on_partial_failure(self, make_payload):
        """AC-1 / AC-4: Marker payload is non-empty on partial failure."""
        from vultron.core.behaviors.case.nodes import (
            EmitCreateVulnerabilityCaseNode,
        )
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        event = self._make_event(make_payload)

        with patch.object(
            EmitCreateVulnerabilityCaseNode,
            "update",
            return_value=py_trees.common.Status.FAILURE,
        ):
            CreateCaseProposalReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            ).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity)
        assert marker.create_activity_payload, (
            "create_activity_payload must not be empty (AC-1)"
        )

    def test_emit_node_uses_marker_activity_id(self, make_payload):
        """AC-4: The activity id_ enqueued by node 4 matches the marker payload id_.

        ``WriteCreateCaseMarkerNode`` (node 3) and
        ``EmitCreateVulnerabilityCaseNode`` (node 4) must share the same
        activity ``id_``.  If they diverge, the retry runner checks the
        marker's ``id_`` against the outbox and — not finding it — enqueues
        a second ``Create(as_VulnerabilityCase)`` as a duplicate.

        This test asserts ID consistency by:
        1. Running the full BT with ``ClearCreateCaseMarkerNode`` no-oped so
           the marker is preserved after node 4 succeeds.
        2. Reconstructing the activity from the marker's stored payload.
        3. Verifying that ``id_`` is present in the case-actor's outbox.
        """
        from vultron.core.behaviors.case.nodes import (
            ClearCreateCaseMarkerNode,
        )
        from vultron.core.models.activity import VultronCreateCaseActivity
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        event = self._make_event(make_payload)

        # Patch the clear node to skip deletion so the marker stays in the DL.
        def _skip_delete(
            self_node: ClearCreateCaseMarkerNode,
        ) -> py_trees.common.Status:
            return py_trees.common.Status.SUCCESS

        with patch.object(ClearCreateCaseMarkerNode, "update", _skip_delete):
            CreateCaseProposalReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            ).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity), (
            "Marker should still be present (clear was no-oped)"
        )

        stored_activity = VultronCreateCaseActivity.model_validate(
            marker.create_activity_payload
        )
        marker_activity_id = stored_activity.id_

        outbox = dl.outbox_list()
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


def _make_full_event(
    make_payload,
    *,
    report_id: str | None = _REPORT_URI,
    actor: str | CoreActor | None = None,
):
    """Build a CreateCaseProposalReceivedEvent with an optional report URI.

    ``actor`` is the Create's ``actor``: the proposing actor's full profile
    inline, without a policy, by default (CP-01-010); a URI to exercise the
    refusal of a reference.
    """
    if actor is None:
        actor = _vendor_profile()
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
        actor=actor,
        object_=proposal,
        to=[_CASE_ACTOR_URI],
    )
    event = make_payload(activity)
    return event.model_copy(update={"receiving_actor_id": _CASE_ACTOR_URI})


def _seed_report(dl: SqliteDataLayer) -> None:
    """Store a VulnerabilityReport attributed to the reporter."""
    from vultron.core.models.report import VulnerabilityReport

    # ensure VulnerabilityReport is in the vocabulary registry
    from vultron.wire.as2.vocab.objects.vulnerability_report import (  # noqa: F401
        as_VulnerabilityReport,
    )

    report = VulnerabilityReport(id_=_REPORT_URI, attributed_to=_REPORTER_URI)
    dl.save(report)


def _run_full_bt(
    make_payload,
    dl: SqliteDataLayer,
    actor_config=None,
    *,
    actor: str | CoreActor | None = None,
) -> HandlerResult:
    from vultron.core.use_cases.received.case_proposal import (
        CreateCaseProposalReceivedUseCase,
    )

    event = _make_full_event(make_payload, actor=actor)
    return CreateCaseProposalReceivedUseCase(
        dl,
        event,
        actor_config=actor_config,
        wire_render_port=As2WireRenderAdapter(),
        trigger_activity=TriggerActivityAdapter(dl),
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


@pytest.mark.spec("CP-09-001")
@pytest.mark.spec("CP-09-002")
class TestADR0041VendorParticipant:
    """ADR-0041 AC-1: vendor added as CASE_OWNER at RM.RECEIVED."""

    def test_vendor_participant_created(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        # Find the created case
        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases, "At least one VulnerabilityCase must exist"
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        assert _VENDOR_URI in case.actor_participant_index, (
            "Vendor must be in actor_participant_index as CASE_OWNER (AC-1)"
        )

    def test_vendor_participant_rm_received(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.rm import RM

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        assert rm_state == RM.RECEIVED, (
            f"Vendor must be at RM.RECEIVED, got {rm_state}"
        )

    def test_vendor_has_case_owner_role(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        assert CVDRole.CASE_OWNER in roles, (
            f"Vendor must have CASE_OWNER role, got {roles}"
        )


def _object_type(activity: Any) -> str | None:
    """Return the ``type`` of *activity*'s object, inline dict or model."""
    obj = getattr(activity, "object_", None)
    if isinstance(obj, dict):
        return obj.get("type")
    return getattr(obj, "type_", None)


def _run_proposal_to_case(
    make_payload,
) -> tuple[SqliteDataLayer, VulnerabilityCase]:
    """Run the full proposal tree in the case actor's store; return the case."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
    _seed_report(dl)
    _run_full_bt(make_payload, dl)
    cases = list(dl.list_objects("VulnerabilityCase"))
    assert len(cases) == 1
    case = cases[0]
    assert isinstance(case, VulnerabilityCase)
    return dl, case


def _created_case_activity(dl: SqliteDataLayer) -> Any:
    """Return the one queued ``Create(VulnerabilityCase)``."""
    creates = []
    for activity_id in dl.outbox_list():
        activity = dl.read(activity_id)
        if (
            getattr(activity, "type_", None) == "Create"
            and _object_type(activity) == "VulnerabilityCase"
        ):
            creates.append(activity)
    assert len(creates) == 1, (
        f"expected one Create(VulnerabilityCase), got {creates}"
    )
    return creates[0]


@pytest.mark.spec("CP-09-001")
@pytest.mark.spec("CM-22-001")
@pytest.mark.spec("CM-02-008")
@pytest.mark.spec("CP-05-003")
class TestCP09001CaseAttributedToOwner:
    """The CASE_MANAGER creates the case; the proposer owns it."""

    def test_stored_case_is_attributed_to_the_proposing_actor(
        self, make_payload
    ):
        _, case = _run_proposal_to_case(make_payload)
        assert case.attributed_to == _VENDOR_URI
        assert case.attributed_to != _CASE_ACTOR_URI

    def test_owner_field_and_case_owner_participant_name_the_same_actor(
        self, make_payload
    ):
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.enums.roles import CVDRole

        dl, case = _run_proposal_to_case(make_payload)
        participant = dl.read(case.actor_participant_index[_VENDOR_URI])
        assert isinstance(participant, CaseParticipant)
        assert CVDRole.CASE_OWNER in participant.case_roles

    def test_create_is_by_the_case_manager_about_an_owner_attributed_case(
        self, make_payload
    ):
        """AS2 carries authorship on the activity, ownership on the object."""
        dl, _case = _run_proposal_to_case(make_payload)
        create = _created_case_activity(dl)
        assert create.actor == _CASE_ACTOR_URI
        obj = create.object_
        attributed = (
            obj.get("attributedTo", obj.get("attributed_to"))
            if isinstance(obj, dict)
            else getattr(obj, "attributed_to", None)
        )
        assert attributed == _VENDOR_URI

    @pytest.mark.spec("CLP-08-002")
    def test_genesis_hash_stays_bound_to_the_case_actor(self, make_payload):
        """Moving the owner field does not move the ledger's origin binding."""
        from vultron.core.models.case_ledger import compute_genesis_hash

        _, case = _run_proposal_to_case(make_payload)
        assert case.published is not None
        assert case.genesis_hash == compute_genesis_hash(
            case_id=case.id_,
            created_at=case.published,
            case_actor_id=_CASE_ACTOR_URI,
        )


@pytest.mark.spec("CM-21-002")
@pytest.mark.spec("CM-21-003")
def test_ownership_transfer_moves_the_owner_of_a_proposal_created_case(
    make_payload,
):
    """A transfer rewrites ``attributed_to`` and moves CASE_OWNER with it.

    It strips CASE_OWNER from whoever ``attributed_to`` names, so the
    attribution must name the vendor; were it the CaseActor, the transfer
    would strip nobody and leave the vendor a second CASE_OWNER beside the new
    one (CM-21-001).
    """
    from test.core.behaviors.bt_harness import BTTestScenario
    from vultron.core.behaviors.case.nodes.ownership_transfer import (
        AcceptCaseOwnershipTransferNode,
    )
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole

    new_owner = "https://example.org/actors/coordinator"
    dl, case = _run_proposal_to_case(make_payload)
    coordinator = CaseParticipant(
        attributed_to=new_owner,
        context=case.id_,
        case_roles=[CVDRole.COORDINATOR],
    )
    dl.create(coordinator)
    case.add_participant(coordinator)
    dl.save(case)

    result = BTTestScenario(actor_id=_CASE_ACTOR_URI, dl=dl).run(
        AcceptCaseOwnershipTransferNode(
            case_id=case.id_, new_owner_id=new_owner
        )
    )

    assert result.status.name == "SUCCESS"
    stored = dl.read(case.id_)
    assert isinstance(stored, VulnerabilityCase)
    assert stored.attributed_to == new_owner
    owners = {
        actor
        for actor, pid in stored.actor_participant_index.items()
        if CVDRole.CASE_OWNER in getattr(dl.read(pid), "case_roles", [])
    }
    assert owners == {new_owner}


def _proposed_case_with_open_revision(
    make_payload,
) -> tuple[SqliteDataLayer, VulnerabilityCase, str]:
    """A case the CASE_MANAGER created from a proposal, with a revision open.

    Returns the CASE_MANAGER's store, the case, and the id of a proposed
    revision of the active embargo (EM.REVISE).
    """
    from datetime import datetime

    from vultron.core.models.embargo_event import EmbargoEvent
    from vultron.core.services.embargo_lifecycle import EmbargoLifecycle

    dl, case = _run_proposal_to_case(make_payload)
    assert case.active_embargo is not None
    revision = EmbargoEvent(
        end_time=datetime.now(UTC) + timedelta(days=200),
        context=case.id_,
    )
    dl.create(revision)
    EmbargoLifecycle(persistence=dl).propose_embargo(
        case_id=case.id_, embargo_id=revision.id_, actor_id=_VENDOR_URI
    )
    stored = dl.read(case.id_)
    assert isinstance(stored, VulnerabilityCase)
    assert stored.current_status.em.state == EM.REVISE
    return dl, stored, revision.id_


@pytest.mark.spec("CP-09-001")
@pytest.mark.spec("CM-13-001")
@pytest.mark.spec("CM-02-008")
class TestOwnerChecksOnACaseTheCaseActorCreated:
    """Every check that reads ``attributed_to`` treats the CASE_OWNER as owner.

    The case actor created the case, but it is not the owner, so each check
    admits the CASE_OWNER and refuses the CASE_MANAGER acting as owner.
    """

    @pytest.mark.parametrize(
        ("sender", "expected"),
        [(_VENDOR_URI, "SUCCESS"), (_CASE_ACTOR_URI, "FAILURE")],
    )
    def test_case_update_gate(self, make_payload, sender, expected):
        from test.core.behaviors.bt_harness import BTTestScenario
        from vultron.core.behaviors.case.nodes.update import (
            CheckCaseUpdateOwnerNode,
        )

        dl, case, _ = _proposed_case_with_open_revision(make_payload)
        scenario = BTTestScenario(actor_id=_CASE_ACTOR_URI, dl=dl)

        result = scenario.run(
            CheckCaseUpdateOwnerNode(case_id=case.id_, sender_actor_id=sender)
        )

        assert result.status.name == expected

    def test_owner_accepting_a_revision_activates_it(self, make_payload):
        """answers.py accept, and pec.py's owner-acceptance at activation."""
        from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
        from vultron.core.states.participant_embargo_consent import PEC

        dl, case, revision_id = _proposed_case_with_open_revision(make_payload)
        EmbargoLifecycle(persistence=dl).accept_embargo_invite(
            case_id=case.id_, embargo_id=revision_id, actor_id=_VENDOR_URI
        )

        stored = dl.read(case.id_)
        assert isinstance(stored, VulnerabilityCase)
        assert stored.active_embargo == revision_id
        assert stored.current_status.em.state == EM.ACTIVE
        from vultron.core.models.case_participant import CaseParticipant

        owner = dl.read(stored.actor_participant_index[_VENDOR_URI])
        assert isinstance(owner, CaseParticipant)
        assert owner.embargo_consent_state == PEC.SIGNATORY
        assert revision_id in owner.accepted_embargo_ids

    def test_case_actor_accepting_a_revision_only_consents(self, make_payload):
        from vultron.core.services.embargo_lifecycle import EmbargoLifecycle

        dl, case, revision_id = _proposed_case_with_open_revision(make_payload)
        prior = case.active_embargo
        EmbargoLifecycle(persistence=dl).accept_embargo_invite(
            case_id=case.id_, embargo_id=revision_id, actor_id=_CASE_ACTOR_URI
        )

        stored = dl.read(case.id_)
        assert isinstance(stored, VulnerabilityCase)
        assert stored.active_embargo == prior
        assert stored.current_status.em.state == EM.REVISE

    @pytest.mark.parametrize(
        ("rejecter", "em_after"),
        [(_VENDOR_URI, EM.ACTIVE), (_CASE_ACTOR_URI, EM.REVISE)],
    )
    def test_only_the_owners_reject_decides_a_revision(
        self, make_payload, rejecter, em_after
    ):
        """answers.py reject, and pec.py's owner-EJ consent rule."""
        from vultron.core.services.embargo_lifecycle import EmbargoLifecycle

        dl, case, revision_id = _proposed_case_with_open_revision(make_payload)
        result = EmbargoLifecycle(persistence=dl).reject_embargo_invite(
            case_id=case.id_, embargo_id=revision_id, actor_id=rejecter
        )

        stored = dl.read(case.id_)
        assert isinstance(stored, VulnerabilityCase)
        assert stored.current_status.em.state == em_after
        if rejecter == _VENDOR_URI:
            # The owner keeping the prior terms changes nobody's consent (EJ).
            assert result.participant_changes == []

    @pytest.mark.parametrize(
        ("decided_by", "pruned"),
        [(_VENDOR_URI, True), (_CASE_ACTOR_URI, False)],
    )
    def test_teardown_prune_authorization(
        self, make_payload, decided_by, pruned
    ):
        from test.core.behaviors.bt_harness import BTTestScenario
        from vultron.core.behaviors.embargo.nodes.teardown import (
            RemoveFromProposedEmbargoesNode,
        )

        dl, case, revision_id = _proposed_case_with_open_revision(make_payload)
        assert revision_id in case.proposed_embargoes
        scenario = BTTestScenario(actor_id=_CASE_ACTOR_URI, dl=dl)

        result = scenario.run(
            RemoveFromProposedEmbargoesNode(
                case_id=case.id_,
                embargo_id=revision_id,
                decided_by=decided_by,
            )
        )

        assert result.status.name == "SUCCESS"
        stored = dl.read(case.id_)
        assert isinstance(stored, VulnerabilityCase)
        assert (revision_id not in stored.proposed_embargoes) is pruned


@pytest.mark.spec("CP-09-007")
@pytest.mark.spec("CP-09-008")
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(
            make_payload,
            dl,
            actor_config=ActorConfig(default_case_roles=[CVDRole.COORDINATOR]),
        )

        roles = _owner_roles(dl)
        assert CVDRole.CASE_OWNER in roles
        assert CVDRole.COORDINATOR in roles
        assert CVDRole.VENDOR not in roles, (
            f"a coordinator must not be labelled VENDOR, got {roles}"
        )

    def test_no_actor_config_yields_case_owner_only(self, make_payload):
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl, actor_config=None)

        roles = _owner_roles(dl)
        assert roles == [CVDRole.CASE_OWNER]


@pytest.mark.spec("CBT-01-008")
@pytest.mark.spec("CBT-01-009")
@pytest.mark.spec("CP-09-006")
class TestADR0041ReporterParticipant:
    """ADR-0041 AC-2: reporter added as REPORTER at RM.ACCEPTED."""

    def test_reporter_participant_created(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        assert _REPORTER_URI in case.actor_participant_index, (
            "Reporter must be in actor_participant_index (AC-2)"
        )

    def test_reporter_participant_rm_accepted(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.rm import RM

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        assert rm_state == RM.ACCEPTED, (
            f"Reporter must be at RM.ACCEPTED, got {rm_state}"
        )

    def test_no_reporter_when_report_absent(self, make_payload):
        """AC-2 graceful degradation: no reporter if report not in DataLayer."""
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        # Deliberately NOT seeding the report
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases, "Case must still be created even without a seeded report"
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        # Vendor participant must still be present even without the reporter
        assert _VENDOR_URI in case.actor_participant_index


@pytest.mark.spec("CP-09-003")
class TestADR0041EmbargoInit:
    """ADR-0041 AC-3: default embargo initialized."""

    def test_active_embargo_set(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        assert case.active_embargo is not None, (
            "Case must have an active embargo after initialization (AC-3)"
        )

    def test_embargo_event_stored(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.embargo_event import EmbargoEvent

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)

        embargo_id = case.active_embargo_id
        assert embargo_id is not None
        embargo_obj = dl.read(embargo_id)
        assert isinstance(embargo_obj, EmbargoEvent), (
            "EmbargoEvent must be stored in DataLayer (AC-3)"
        )

    @pytest.mark.spec("EP-04-005")
    def test_configured_protocol_default_sets_the_embargo_end(
        self, make_payload
    ):
        """The tree hands ``actor_config`` to the embargo subtree (EP-04-005)."""
        from datetime import datetime, timedelta

        from vultron.config.actor import ActorConfig
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.embargo_event import EmbargoEvent

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        _seed_report(dl)
        configured = timedelta(days=5)
        before = datetime.now(tz=UTC)
        _run_full_bt(
            make_payload,
            dl,
            actor_config=ActorConfig(
                protocol_default_embargo_duration=configured
            ),
        )
        after = datetime.now(tz=UTC)

        case = next(iter(dl.list_objects("VulnerabilityCase")))
        assert isinstance(case, VulnerabilityCase)
        assert case.active_embargo_id is not None
        embargo = dl.read(case.active_embargo_id)
        assert isinstance(embargo, EmbargoEvent)
        assert embargo.end_time is not None
        slack = timedelta(seconds=1)
        assert (
            before + configured - slack
            <= embargo.end_time
            <= after + configured + slack
        )

    @pytest.mark.spec("CP-01-009")
    @pytest.mark.spec("CP-01-010")
    def test_inline_actor_profile_policy_is_the_actor_default(
        self, make_payload
    ):
        """The inline ``actor`` profile's policy is the actor default (CP-01-009).

        The proposing actor's profile travels inline as the Create's ``actor``,
        carrying its embargo policy. With no sender proposal, that policy is
        the CASE_OWNER's actor default (EP-04-002), so the embargo the tree
        activates ends ``preferred_duration`` from now rather than at the
        protocol default.
        """
        from datetime import datetime

        from vultron.config.actor import ActorConfig
        from vultron.core.models.actor import VultronOrganization
        from vultron.core.models.embargo_event import EmbargoEvent
        from vultron.core.models.embargo_policy import EmbargoPolicy

        policy_duration = timedelta(days=3)
        protocol_default = timedelta(days=5)
        profile = VultronOrganization(
            id_=_VENDOR_URI,
            embargo_policy=EmbargoPolicy(
                actor_id=_VENDOR_URI,
                inbox=f"{_VENDOR_URI}/inbox",
                preferred_duration=policy_duration,
            ),
        )

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        _seed_report(dl)
        before = datetime.now(tz=UTC)
        _run_full_bt(
            make_payload,
            dl,
            actor_config=ActorConfig(
                protocol_default_embargo_duration=protocol_default
            ),
            actor=profile,
        )
        after = datetime.now(tz=UTC)

        case = next(iter(dl.list_objects("VulnerabilityCase")))
        assert isinstance(case, VulnerabilityCase)
        assert case.active_embargo_id is not None
        embargo = dl.read(case.active_embargo_id)
        assert isinstance(embargo, EmbargoEvent)
        assert embargo.end_time is not None
        slack = timedelta(seconds=1)
        assert (
            before + policy_duration - slack
            <= embargo.end_time
            <= after + policy_duration + slack
        ), "the actor default must come from the inline profile's policy"

    @pytest.mark.spec("CP-01-010")
    def test_a_bare_uri_actor_is_refused_and_creates_nothing(
        self, make_payload
    ):
        """No inline profile means no actor default can be read, and the
        CASE_MANAGER does not fetch one: the proposal is refused before it
        reaches core, so no event — and no case — exists."""
        from vultron.wire.as2.errors import VultronParseValidationError

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        _seed_report(dl)

        with pytest.raises(VultronParseValidationError, match="CP-01-010"):
            _run_full_bt(make_payload, dl, actor=_VENDOR_URI)

        assert list(dl.list_objects("VulnerabilityCase")) == []

    @pytest.mark.spec("CP-01-010")
    @pytest.mark.spec("PCR-01-003")
    def test_a_policy_in_the_case_managers_store_is_not_the_actor_default(
        self, make_payload
    ):
        """A record of the owner's profile in the CASE_MANAGER's own store —
        with a policy the inline profile does not carry — is never read."""
        from vultron.config.actor import ActorConfig
        from vultron.core.models.embargo_event import EmbargoEvent

        protocol_default = timedelta(days=5)
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        _seed_report(dl)
        dl.save(_vendor_profile(timedelta(days=3)))
        before = datetime.now(tz=UTC)
        _run_full_bt(
            make_payload,
            dl,
            actor_config=ActorConfig(
                protocol_default_embargo_duration=protocol_default
            ),
            actor=_vendor_profile(),
        )
        after = datetime.now(tz=UTC)

        case = next(iter(dl.list_objects("VulnerabilityCase")))
        assert isinstance(case, VulnerabilityCase)
        embargo = dl.read(case.active_embargo_id or "")
        assert isinstance(embargo, EmbargoEvent)
        slack = timedelta(seconds=1)
        assert (
            before + protocol_default - slack
            <= embargo.end_time
            <= after + protocol_default + slack
        )

    @pytest.mark.spec("CP-01-010")
    def test_a_policy_on_one_proposal_is_not_the_default_for_the_next(
        self, make_payload
    ):
        """Three proposals from the same vendor carry different policies: each
        case takes its own proposal's policy — the shorter earlier one does
        not win for the longer later one, and the last, with none, takes the
        protocol default — so no profile is retained (AC-4)."""
        from vultron.config.actor import ActorConfig
        from vultron.core.models.embargo_event import EmbargoEvent
        from vultron.core.models.report import VulnerabilityReport
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )

        config = ActorConfig(
            protocol_default_embargo_duration=timedelta(days=5)
        )
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        report_ids = (
            _REPORT_URI,
            "https://example.org/reports/r-002",
            "https://example.org/reports/r-003",
        )
        for report_id in report_ids:
            dl.save(
                VulnerabilityReport(id_=report_id, attributed_to=_REPORTER_URI)
            )

        expected: dict[str, timedelta] = {}
        for index, (report_id, policy) in enumerate(
            zip(
                report_ids,
                (timedelta(days=3), timedelta(days=20), None),
                strict=True,
            )
        ):
            activity = as_Create(
                actor=_vendor_profile(policy),
                object_=as_CaseProposal(
                    id_=f"{_PROPOSAL_URI}-{index}",
                    attributed_to=_VENDOR_URI,
                    object_=report_id,
                    target=_CASE_ACTOR_URI,
                ),
                to=[_CASE_ACTOR_URI],
            )
            event = make_payload(activity).model_copy(
                update={"receiving_actor_id": _CASE_ACTOR_URI}
            )
            CreateCaseProposalReceivedUseCase(
                dl,
                event,
                actor_config=config,
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            ).execute()
            expected[report_id] = policy or timedelta(days=5)

        slack = timedelta(minutes=1)
        now = datetime.now(tz=UTC)
        cases = [
            c
            for c in dl.list_objects("VulnerabilityCase")
            if isinstance(c, VulnerabilityCase)
        ]
        assert len(cases) == 3
        for case in cases:
            (report_id,) = [
                r
                for r in report_ids
                if r in [str(x) for x in case.vulnerability_reports]
            ]
            embargo = dl.read(case.active_embargo_id or "")
            assert isinstance(embargo, EmbargoEvent)
            assert abs(embargo.end_time - (now + expected[report_id])) < slack

    @pytest.mark.spec("EP-04-008")
    def test_ineligible_case_is_created_without_an_embargo(
        self, make_payload, monkeypatch
    ):
        """P/X/A refusal: case created at EM.NONE, no embargo, tree succeeds."""
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
        from vultron.core.states.em import EM
        from vultron.errors import VultronInvalidStateTransitionError

        def _pxa_set(self, **_):
            raise VultronInvalidStateTransitionError("P/X/A is set")

        monkeypatch.setattr(
            EmbargoLifecycle, "assert_embargo_eligible", _pxa_set
        )
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        case = next(iter(dl.list_objects("VulnerabilityCase")))
        assert isinstance(case, VulnerabilityCase)
        assert case.active_embargo is None
        assert case.current_status.em.state == EM.NONE
        assert list(dl.list_objects("EmbargoEvent")) == []
        assert (
            dl.read(PendingCreateCaseActivity.build_id(_PROPOSAL_URI)) is None
        )

    def test_vendor_owner_seeded_as_signatory(self, make_payload):
        """CM-13: vendor (CASE_OWNER) is SIGNATORY on the active embargo.

        ``InitializeDefaultEmbargoNode``'s ``SeedOwnerAsSignatoryNode`` is the
        one path that seeds it: it reads the owner from the case's
        ``attributed_to`` (CP-09-001), not from the executing CaseActor, which
        is not a participant here and once left an ACTIVE embargo with no
        signatory.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.states.participant_embargo_consent import PEC

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        participant, _case = self._get_reporter_participant(dl)
        assert participant is not None, "Reporter participant must exist"
        assert participant.embargo_consent_state == PEC.SIGNATORY, (
            "Reporter must be seeded SIGNATORY on the active embargo"
            f" at case initialization (CM-14-005), got"
            f" {participant.embargo_consent_state!r}"
        )

    def test_reporter_accepted_embargo_ids_populated(self, make_payload):
        """AC-2: reporter's accepted_embargo_ids includes the active embargo."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        """AC-3: SeedReporterSignatoryNode no-ops gracefully when no active embargo."""
        from vultron.core.behaviors.case.nodes import (
            SeedReporterSignatoryNode,
        )
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.report import VulnerabilityReport
        from vultron.core.states.participant_embargo_consent import PEC

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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

        node = SeedReporterSignatoryNode(report_id=_REPORT_URI)
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
            "SeedReporterSignatoryNode must return SUCCESS when no active"
            " embargo (AC-3, best-effort)"
        )
        stored_participant = dl.read(reporter_participant.id_)
        assert isinstance(stored_participant, CaseParticipant)
        assert stored_participant.embargo_consent_state == PEC.UNBOUND, (
            "Reporter must remain UNBOUND when no active embargo exists"
            " (CM-14-005 AC-3)"
        )

    def test_reporter_signatory_ledger_snapshot_consistent(self, make_payload):
        """AC-4: ledger snapshot for reporter shows SIGNATORY consent.

        The ``CommitNativeLedgerEntriesNode`` runs *after*
        ``SeedReporterSignatoryNode``, so the participant status it snapshots
        must already carry ``emConsentState=SIGNATORY`` and
        ``embargoAdherence=True`` — no contradictory pair.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        assert reporter_status_entries, (
            "add_participant_status_to_participant entries must be present"
        )

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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        participant, _case = self._get_reporter_participant(dl)
        assert participant is not None
        assert participant.embargo_consent_state == PEC.SIGNATORY

        # embargo_adherence lives on ParticipantStatus, not on CaseParticipant.
        # The latest status is exposed via participant.participant_status.
        latest_status = participant.participant_status
        assert latest_status is not None, (
            "Reporter must have at least one ParticipantStatus"
        )
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)
        case_id = case.id_

        entries = list(dl.list_objects("CaseLedgerEntry"))
        event_types = {getattr(e, "event_type", None) for e in entries}
        assert "create_case" in event_types, (
            "create_case ledger entry must be committed natively (AC-4)"
        )

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
            assert snapshot.get("actor") == _CASE_ACTOR_URI, (
                f"create_case actor must be CaseActor, got {snapshot.get('actor')}"
            )

    def test_add_report_to_case_entry_present(self, make_payload):
        """add_report_to_case ledger entry must be committed with actor=CaseActor (AC-4)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        assert report_entries, (
            "add_report_to_case ledger entry must be committed natively (AC-4)"
        )
        for entry in report_entries:
            snapshot = getattr(entry, "payload_snapshot", {})
            assert snapshot.get("actor") == _CASE_ACTOR_URI, (
                f"add_report_to_case actor must be CaseActor, got {snapshot.get('actor')}"
            )

    def test_add_participant_status_entries_present(self, make_payload):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        entries = list(dl.list_objects("CaseLedgerEntry"))
        event_types = [getattr(e, "event_type", None) for e in entries]
        assert "add_participant_status_to_participant" in event_types, (
            "add_participant_status_to_participant entries must be present (AC-4)"
        )

    def test_add_case_status_uses_vendor_actor(self, make_payload):
        """add_case_status_to_case must use vendor URI as actor (not CaseActor)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
            assert actor == _VENDOR_URI, (
                f"add_case_status_to_case actor must be vendor URI, got {actor!r}"
            )


class TestCM18007InitLedgerEntries:
    """CM-18-007 and CM-14-003: one init entry per participant; vendor is SIGNATORY."""

    def test_exactly_one_participant_status_entry_per_participant(
        self, make_payload
    ):
        """CaseActor gets 3 bootstrap entries (CM-23-007); other participants get 1.

        Total add_participant_status_to_participant ledger entries ==
        (participant_count - 1) + 3 == participant_count + 2 (CM-18-007 AC-3,
        CM-23-005/ADR-0051).
        """
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        # CaseActor contributes 3 bootstrap RM entries (CM-23-007/ADR-0051);
        # every other participant contributes 1.
        expected = participant_count + 2
        assert len(ps_entries) == expected, (
            f"Expected {expected} add_participant_status_to_participant entries"
            f" ({participant_count} participants, CaseActor has 3 bootstrap"
            f" entries per CM-23-007), got {len(ps_entries)} (CM-18-007)"
        )

    def test_vendor_case_owner_appears_as_signatory_in_init_ledger(
        self, make_payload
    ):
        """Vendor (CASE_OWNER) init ledger entry must show SIGNATORY consent
        (CM-14-003 AC-4)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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


@pytest.mark.spec("CP-09-004")
class TestADR0041InlineParticipantsPayload:
    """ADR-0041 AC-5: Create(VulnerabilityCase) embeds inline participant objects."""

    def test_marker_payload_has_inline_participants(self, make_payload):
        """Create payload in marker must embed participants as objects, not IDs."""
        from vultron.core.behaviors.case.nodes import (
            ClearCreateCaseMarkerNode,
        )
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        event = _make_full_event(make_payload)

        def _skip_delete(self_node):
            return py_trees.common.Status.SUCCESS

        with patch.object(ClearCreateCaseMarkerNode, "update", _skip_delete):
            CreateCaseProposalReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            ).execute()

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
        participants = obj_field.get("caseParticipants", [])
        assert participants, (
            "Inline case object must have at least one participant (AC-5)"
        )
        # Each participant must be a dict (inline object), not a bare ID string.
        for p in participants:
            assert isinstance(p, dict), (
                f"caseParticipants entries must be inline dicts, got {type(p).__name__!r}"
            )

    def test_vendor_participant_inline_in_payload(self, make_payload):
        """Vendor participant must appear as inline object in Create payload."""
        from vultron.core.behaviors.case.nodes import (
            ClearCreateCaseMarkerNode,
        )
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        event = _make_full_event(make_payload)

        def _skip_delete(self_node):
            return py_trees.common.Status.SUCCESS

        with patch.object(ClearCreateCaseMarkerNode, "update", _skip_delete):
            CreateCaseProposalReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            ).execute()

        marker_id = PendingCreateCaseActivity.build_id(_PROPOSAL_URI)
        marker = dl.read(marker_id)
        assert isinstance(marker, PendingCreateCaseActivity)

        payload = marker.create_activity_payload
        obj_field = payload.get("object") or payload.get("object_")
        assert isinstance(obj_field, dict)

        participants = obj_field.get("caseParticipants", [])
        attributed_tos = {
            p.get("attributedTo") or p.get("attributed_to")
            for p in participants
            if isinstance(p, dict)
        }
        assert _VENDOR_URI in attributed_tos, (
            f"Vendor '{_VENDOR_URI}' must appear as inline participant in"
            " Create(VulnerabilityCase) payload (AC-5)"
        )


@pytest.mark.spec("CP-05-006")
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
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
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
        # AC-3 guard falls through; LoadExistingCaseNode must reuse the case.
        _run_full_bt(make_payload, dl)

        cases_after = list(dl.list_objects("VulnerabilityCase"))
        assert len(cases_after) == 1, (
            "duplicate proposal must not create a second case"
        )
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

    def test_idempotent_even_when_the_clock_moves_between_deliveries(
        self, make_payload, monkeypatch
    ):
        """The same guarantee, with the timing coincidence removed.

        The test above only holds when both deliveries land inside one clock
        second.  ``now_utc`` truncates to whole seconds and ``as_Base`` stamps
        ``published``/``updated`` with it at construction, so rebuilding a
        snapshot a second later restamps every object it embeds — and a dedup
        comparing snapshots byte-for-byte then misses and appends duplicate
        indices.  That made this class's guarantee a coin flip: green locally,
        red on slower CI, which is how it was found.

        Advancing the clock on every read forces the worst case rather than
        sleeping for it, so a regression fails here every time instead of
        occasionally somewhere else.
        """
        from datetime import datetime, timedelta, timezone

        from vultron.core.models import _helpers

        class _AdvancingClock:
            """A ``datetime`` stand-in whose ``now()`` steps forward a second.

            Patched into ``_helpers`` rather than onto the models: the
            ``published``/``updated`` defaults capture ``now_utc`` itself at
            class-definition time, so patching that name has no effect once the
            fields are built.  ``now_utc`` looks ``datetime`` up in its own
            module at call time, which does.
            """

            def __init__(self, start: datetime) -> None:
                self._t = start

            def now(self, tz: timezone | None = None) -> datetime:
                self._t += timedelta(seconds=1)
                return self._t

        monkeypatch.setattr(
            _helpers,
            "datetime",
            _AdvancingClock(datetime.now(UTC)),
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        case_id = next(iter(dl.list_objects("VulnerabilityCase"))).id_
        entries_before = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if getattr(e, "case_id", None) == case_id
        ]
        assert entries_before, "first delivery must have written the ledger"

        _run_full_bt(make_payload, dl)

        entries_after = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if getattr(e, "case_id", None) == case_id
        ]
        assert len(entries_after) == len(entries_before), (
            "a retry is the same assertion no matter how much later it"
            " arrives; restamped published/updated values must not defeat the"
            f" ledger dedup (before={len(entries_before)},"
            f" after={len(entries_after)}) — ADR-0041"
        )


class TestADR0041GenesisCommitFailure:
    """The genesis create_case commit failure must not be masked."""

    def test_genesis_create_case_failure_aborts(self, make_payload):
        """A failed genesis create_case commit returns FAILURE (not SUCCESS).

        The genesis entry is the root of the CaseActor's hash chain; a
        best-effort SUCCESS would hide that the canonical ledger has no root.
        Since CP-09-009 the node runs after the emits, so the FAILURE no
        longer withholds Accept/Create — it makes the broken ledger visible
        (see test_genesis_commit_failure_is_reported_after_accept_and_create_are_queued).
        """
        from py_trees.common import Status

        from vultron.core.behaviors.case.nodes import (
            CommitNativeLedgerEntriesNode,
        )

        node = CommitNativeLedgerEntriesNode(
            vendor_uri=_VENDOR_URI, report_id=_REPORT_URI
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        # Build a real case so the node reaches the commit step.
        _run_full_bt(make_payload, dl)
        case = next(iter(dl.list_objects("VulnerabilityCase")))

        # Wire up the node against the real DL + case, forcing every commit
        # (including genesis create_case) to report failure.
        node.datalayer = dl
        node.actor_id = _CASE_ACTOR_URI

        class _BB:
            def get(self, _key):
                return case.id_

        node.blackboard = _BB()  # type: ignore[assignment]

        with patch.object(
            CommitNativeLedgerEntriesNode,
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

        from vultron.core.behaviors.case.nodes import (
            CommitNativeLedgerEntriesNode,
        )

        node = CommitNativeLedgerEntriesNode(
            vendor_uri=_VENDOR_URI, report_id=_REPORT_URI
        )
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        node.datalayer = dl
        node.actor_id = _CASE_ACTOR_URI
        node._case_id_bb = "urn:uuid:does-not-exist"

        assert node.update() == Status.SUCCESS, (
            "case-not-found must be best-effort SUCCESS (the ledger is an"
            " audit record, not a precondition for the outbound emissions)"
        )


# ---------------------------------------------------------------------------
# CM-23-005/006/007 — CaseActor RM lifecycle bootstrap (ADR-0051)
# ---------------------------------------------------------------------------


class TestCaseActorRMLifecycleBootstrap:
    """CM-23-005/007: CaseActor emits 3 bootstrap ParticipantStatus records."""

    @pytest.mark.spec("CM-24-006")
    def test_bootstrap_statuses_created_on_case_init(self, make_payload):
        """Three bootstrap ParticipantStatus records exist after initialization.

        CM-23-005: CaseActor MUST track its own RM lifecycle via a
        CaseParticipant record with RM.RECEIVED, RM.VALID, and RM.ACCEPTED
        ParticipantStatus entries during case initialization.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.rm import RM
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases, "A VulnerabilityCase must be created"
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)

        # Locate the CaseActor participant
        participant_id = case.actor_participant_index.get(_CASE_ACTOR_URI)
        assert participant_id is not None, (
            "CaseActor must be in actor_participant_index"
        )
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        assert CVDRole.CASE_MANAGER in participant.roles

        # Extract inline or persisted ParticipantStatus records
        statuses = []
        for ps_ref in participant.participant_statuses:
            if isinstance(ps_ref, ParticipantStatus):
                statuses.append(ps_ref)
            elif isinstance(ps_ref, str):
                ps = dl.read(ps_ref)
                if isinstance(ps, ParticipantStatus):
                    statuses.append(ps)

        rm_states = [ps.rm.state for ps in statuses if ps.rm is not None]
        assert RM.RECEIVED in rm_states, (
            "Bootstrap must include RM.RECEIVED (CM-23-005, CM-23-006)"
        )
        assert RM.VALID in rm_states, (
            "Bootstrap must include RM.VALID (CM-23-005, CM-23-006)"
        )
        assert RM.ACCEPTED in rm_states, (
            "Bootstrap must include RM.ACCEPTED (CM-23-005, CM-23-006)"
        )

    def test_bootstrap_statuses_produce_ledger_entries(self, make_payload):
        """Three RM transitions are represented in the canonical ledger.

        CM-23-007: CaseActor MUST emit CaseLedgerEntry records for each of its
        RM transitions (RM.RECEIVED, RM.VALID, RM.ACCEPTED) during
        initialization.  CommitNativeLedgerEntriesNode iterates all
        participant_statuses entries, including the CaseActor's three bootstrap
        records.
        """
        from vultron.core.states.rm import RM

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        # Each CaseLedgerEntry for add_participant_status_to_participant has
        # payload_snapshot["object"]["attributedTo"] = the actor URI and
        # payload_snapshot["object"]["rmState"] (or "rm_state") for RM state.
        entries = list(dl.list_objects("CaseLedgerEntry"))
        case_actor_rm_states = set()
        for entry in entries:
            et = getattr(entry, "event_type", None)
            if et != "add_participant_status_to_participant":
                continue
            snap = getattr(entry, "payload_snapshot", {}) or {}
            obj = snap.get("object", {}) or {}
            attributed = obj.get("attributedTo") or obj.get("attributed_to")
            if attributed != _CASE_ACTOR_URI:
                continue
            rm_val = obj.get("rmState") or obj.get("rm_state")
            if rm_val is None:
                # Try nested dimension object: {"rm": {"state": "..."}}
                rm_dim = obj.get("rm") or {}
                rm_val = (
                    rm_dim.get("state") if isinstance(rm_dim, dict) else None
                )
            if rm_val is not None:
                try:
                    case_actor_rm_states.add(RM(rm_val))
                except ValueError:
                    pass

        assert RM.RECEIVED in case_actor_rm_states, (
            "Ledger must have add_participant_status entry for CaseActor"
            " RM.RECEIVED (CM-23-007)"
        )
        assert RM.VALID in case_actor_rm_states, (
            "Ledger must have add_participant_status entry for CaseActor"
            " RM.VALID (CM-23-007)"
        )
        assert RM.ACCEPTED in case_actor_rm_states, (
            "Ledger must have add_participant_status entry for CaseActor"
            " RM.ACCEPTED (CM-23-007)"
        )

    def test_bootstrap_statuses_idempotent_on_duplicate(self, make_payload):
        """Duplicate proposal does not add extra CaseActor statuses.

        The idempotency guard in AddCaseActorParticipantNode returns SUCCESS
        immediately when the CaseActor is already in actor_participant_index,
        so a second CreateCaseProposalReceivedUseCase run must not grow the
        participant's status list.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.participant_status import ParticipantStatus

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        # Run a second time — duplicate delivery
        _run_full_bt(make_payload, dl)

        cases = list(dl.list_objects("VulnerabilityCase"))
        assert cases
        case = cases[0]
        assert isinstance(case, VulnerabilityCase)

        participant_id = case.actor_participant_index.get(_CASE_ACTOR_URI)
        assert participant_id is not None
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)

        statuses = [
            ps
            for ps_ref in participant.participant_statuses
            for ps in [
                (
                    ps_ref
                    if isinstance(ps_ref, ParticipantStatus)
                    else dl.read(ps_ref)
                )
            ]
            if isinstance(ps, ParticipantStatus)
            and getattr(ps, "attributed_to", None) == _CASE_ACTOR_URI
        ]
        assert len(statuses) == 3, (
            f"Expected exactly 3 bootstrap statuses for CaseActor, got"
            f" {len(statuses)} — duplicate delivery must not add extras"
        )


# ---------------------------------------------------------------------------
# AllParticipantsRMClosedConditionNode — Case Actor participates in check
# ---------------------------------------------------------------------------


class TestAllParticipantsRMClosedIncludesCaseActor:
    """ADR-0051: CASE_MANAGER skip removed; CaseActor RM.CLOSED is required."""

    def _make_case_with_participants(self, dl):
        """Seed a case with vendor (CASE_OWNER) and case-actor (CASE_MANAGER)."""
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.dimensions import PecDimension, RmDimension
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.participant_embargo_consent import PEC
        from vultron.core.states.rm import RM
        from vultron.enums.roles import CVDRole

        def _mk_ps(actor_uri, rm_state):
            ps = ParticipantStatus(
                context=_CASE_URI,
                rm=RmDimension(state=rm_state),
                attributed_to=actor_uri,
                cvd_role=[CVDRole.CASE_OWNER],
                consent=PecDimension(state=PEC.UNBOUND),
            )
            dl.save(ps)
            return ps

        vendor_ps = _mk_ps(_VENDOR_URI, RM.CLOSED)
        vendor_participant = CaseParticipant(
            attributed_to=_VENDOR_URI,
            context=_CASE_URI,
            case_roles=[CVDRole.CASE_OWNER],
            participant_statuses=[vendor_ps],
        )
        dl.save(vendor_participant)

        case_actor_ps_list = [
            _mk_ps(_CASE_ACTOR_URI, RM.RECEIVED),
            _mk_ps(_CASE_ACTOR_URI, RM.VALID),
            _mk_ps(_CASE_ACTOR_URI, RM.ACCEPTED),
        ]
        case_actor_participant = CaseParticipant(
            attributed_to=_CASE_ACTOR_URI,
            context=_CASE_URI,
            case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
            participant_statuses=case_actor_ps_list,
        )
        dl.save(case_actor_participant)

        case = VulnerabilityCase(id_=_CASE_URI, attributed_to=_VENDOR_URI)
        case.add_participant(vendor_participant)
        case.add_participant(case_actor_participant)
        dl.save(case)
        return case

    def test_returns_failure_when_case_actor_not_closed(self):
        """FAILURE when CaseActor is at RM.ACCEPTED, not RM.CLOSED.

        ADR-0051: the CASE_MANAGER skip was removed so that the CaseActor's
        RM.CLOSED participates in the all-closed check.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.status.nodes.conditions import (
            AllParticipantsRMClosedConditionNode,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        self._make_case_with_participants(dl)
        # CaseActor is at RM.ACCEPTED (not RM.CLOSED) — should block.

        node = AllParticipantsRMClosedConditionNode(case_id=_CASE_URI)
        node.datalayer = dl

        from py_trees.common import Status

        result = node.update()
        assert result == Status.FAILURE, (
            "AllParticipantsRMClosed must return FAILURE when CaseActor is"
            " not yet at RM.CLOSED (ADR-0051 — CASE_MANAGER skip removed)"
        )

    def test_returns_success_when_all_including_case_actor_closed(self):
        """SUCCESS when every participant (including CaseActor) is RM.CLOSED."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.status.nodes.conditions import (
            AllParticipantsRMClosedConditionNode,
        )
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.dimensions import PecDimension, RmDimension
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.participant_embargo_consent import PEC
        from vultron.core.states.rm import RM
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        case = self._make_case_with_participants(dl)

        # Advance CaseActor to RM.CLOSED
        participant_id = case.actor_participant_index.get(_CASE_ACTOR_URI)
        assert participant_id is not None
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)

        closed_ps = ParticipantStatus(
            context=_CASE_URI,
            rm=RmDimension(state=RM.CLOSED),
            attributed_to=_CASE_ACTOR_URI,
            cvd_role=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
            consent=PecDimension(state=PEC.UNBOUND),
        )
        dl.save(closed_ps)
        participant.participant_statuses.append(closed_ps)
        dl.save(participant)

        node = AllParticipantsRMClosedConditionNode(case_id=_CASE_URI)
        node.datalayer = dl

        from py_trees.common import Status

        result = node.update()
        assert result == Status.SUCCESS, (
            "AllParticipantsRMClosed must return SUCCESS when all participants"
            " including the CaseActor are at RM.CLOSED (ADR-0051)"
        )


# ---------------------------------------------------------------------------
# Per-actor isolation: the case-actor's records land in the case-actor's store
# and are invisible from any other actor's (CM-01-001, ADR-0073).
#
# These tests used to compare the injected DataLayer against the process-global
# singleton for the *same* actor.  ADR-0073 makes those the same store by
# construction — store identity is the configured URL plus the actor — so that
# comparison can no longer fail and would assert nothing.  The invariant worth
# guarding is the one #2238 was filed about: another actor must not be able to
# see these writes.  A leak now shows up as records appearing in the vendor's
# store, which is a real defect rather than a naming accident.
# ---------------------------------------------------------------------------


class TestCreateCaseProposalReceivedBTCaseActorRecords:
    """Records land in the case-actor's store and nowhere else (CM-01-001).

    ``CreateCaseProposalReceivedUseCase`` runs as the case actor, so all its
    writes (VulnerabilityCase, CaseParticipant, CaseLedgerEntry, …) belong in
    the case actor's store.  The vendor's store — a different actor, and the
    other participant in this exchange — must show none of them.
    """

    @pytest.fixture
    def vendor_dl(self):
        """The vendor's own store — must stay empty of the case actor's writes."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_URI)
        yield dl
        dl.close()

    def _run(self, make_payload, case_actor_dl):
        """Run the full BT against *case_actor_dl*; seed report there too."""
        _seed_report(case_actor_dl)
        _run_full_bt(make_payload, case_actor_dl)

    def test_vulnerability_case_not_visible_to_vendor(
        self, make_payload, vendor_dl
    ):
        """VulnerabilityCase is written to the case actor's store only (AC-1)."""
        case_actor_dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        self._run(make_payload, case_actor_dl)

        cases_on_injected = list(
            case_actor_dl.list_objects("VulnerabilityCase")
        )
        cases_on_vendor = list(vendor_dl.list_objects("VulnerabilityCase"))

        assert cases_on_injected, (
            "VulnerabilityCase must be created on the injected DataLayer (AC-1)"
        )
        assert not cases_on_vendor, (
            "VulnerabilityCase must NOT appear in the vendor's store"
            " (CM-01-001)"
        )

    def test_case_participants_not_visible_to_vendor(
        self, make_payload, vendor_dl
    ):
        """CaseParticipant records land in the case actor's store only."""
        case_actor_dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        self._run(make_payload, case_actor_dl)

        participants_on_injected = list(
            case_actor_dl.list_objects("CaseParticipant")
        )
        participants_on_vendor = list(
            vendor_dl.list_objects("CaseParticipant")
        )

        assert participants_on_injected, (
            "CaseParticipant records must be created on the injected DataLayer"
        )
        assert not participants_on_vendor, (
            "CaseParticipant records must NOT appear in the vendor's store"
        )

    def test_ledger_entries_not_visible_to_vendor(
        self, make_payload, vendor_dl
    ):
        """CaseLedgerEntry records land in the case actor's store only."""
        case_actor_dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        self._run(make_payload, case_actor_dl)

        entries_on_injected = list(
            case_actor_dl.list_objects("CaseLedgerEntry")
        )
        entries_on_vendor = list(vendor_dl.list_objects("CaseLedgerEntry"))

        assert entries_on_injected, (
            "CaseLedgerEntry records must be created on the injected DataLayer"
            " (ADR-0041)"
        )
        assert not entries_on_vendor, (
            "CaseLedgerEntry records must NOT appear in the vendor's store"
        )

    def test_vendor_participant_index_lives_in_the_case_actor_store(
        self, make_payload, vendor_dl
    ):
        """The vendor is indexed on the case in the *case actor's* store.

        The sharpest guard of the four: a node that wrote the case to some other
        actor's store would leave the case actor without the index entry that
        every later participant lookup depends on.
        """
        from vultron.core.models.case import VulnerabilityCase

        case_actor_dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        self._run(make_payload, case_actor_dl)

        cases_on_injected = list(
            case_actor_dl.list_objects("VulnerabilityCase")
        )
        assert cases_on_injected, (
            "VulnerabilityCase must exist on case_actor_dl"
        )
        case = cases_on_injected[0]
        assert isinstance(case, VulnerabilityCase)
        assert _VENDOR_URI in case.actor_participant_index, (
            "Vendor must be in actor_participant_index on the injected DL"
        )

        assert not list(vendor_dl.list_objects("VulnerabilityCase")), (
            "VulnerabilityCase must not appear in the vendor's store — the case"
            " actor creates the case in its own store only (CM-01-001)"
        )


# ---------------------------------------------------------------------------
# #2482: the stored report keeps its reporter
# ---------------------------------------------------------------------------

_REPORTER_URI_2482 = "https://example.org/actors/finder-2482"
_REPORT_URI_2482 = "urn:uuid:report-2482-0000-0000-000000000001"


def _proposal_with_inline_report() -> as_CaseProposal:
    """A proposal carrying its report inline, as CP-01-004 requires."""
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        id_=_REPORT_URI_2482,
        name="ISSUE-2482",
        content="the vulnerability the proposal is about",
        attributed_to=_REPORTER_URI_2482,
    )
    return as_CaseProposal(
        id_=_PROPOSAL_URI,
        attributed_to=_VENDOR_URI,
        object_=report,
        target=_CASE_ACTOR_URI,
    )


def test_store_proposal_report_keeps_the_reporter(caplog):
    """#2482: the report is stored *with* its ``attributed_to``.

    The reporter is the whole point of storing the report: three downstream
    nodes derive the reporter participant, its ledger entry and the embargo
    SIGNATORY seed from ``report.attributed_to``. Each skips "best-effort" when
    it is missing, so losing it costs the reporter a case replica and raises
    nothing.

    It was lost to a spelling mismatch. The tree received the proposal as a
    ``by_alias=True`` wire dump — needed because the ``Accept`` must carry the
    proposal inline (CP-05-003, AKM-03-001) — in which the reporter is spelled
    ``attributedTo``. Rebuilding the report by validating that dict against the
    *core* model, which declares ``attributed_to`` and sets
    ``extra="ignore"``, dropped the key silently and reported "has no
    attributed_to" from three nodes away.
    """
    from vultron.core.behaviors.case.nodes import (
        StoreProposalReportNode,
    )
    from vultron.core.models.report import VulnerabilityReport

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
    proposal = _proposal_with_inline_report()

    node = StoreProposalReportNode(
        report_id=_REPORT_URI_2482,
        # by_alias=True is what the real use case passes.
        proposal_dict=proposal.model_dump(
            by_alias=True, serialize_as_any=True
        ),
        inline_report=cast(Any, proposal.object_),
    )
    py_trees.blackboard.Blackboard.storage.clear()
    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=node, actor_id=_CASE_ACTOR_URI
    )
    assert result.status == py_trees.common.Status.SUCCESS

    stored = dl.read(_REPORT_URI_2482)
    assert isinstance(stored, VulnerabilityReport), (
        f"the report must be stored; got {type(stored).__name__}"
    )
    assert stored.attributed_to == _REPORTER_URI_2482, (
        "the reporter must survive into the store — it is who becomes a"
        f" participant; got {stored.attributed_to!r}"
    )
    assert stored.content == "the vulnerability the proposal is about"


def test_store_proposal_report_falls_back_to_the_wire_dict(caplog):
    """Without a pre-converted report the node still stores what it can.

    Paths that do not come through the received-side use case (replay, CLI)
    have only the proposal dict. That fallback must keep working, so the
    reporter-preserving path is an addition rather than a replacement.
    """
    from vultron.core.behaviors.case.nodes import (
        StoreProposalReportNode,
    )
    from vultron.core.models.report import VulnerabilityReport

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
    proposal = _proposal_with_inline_report()

    node = StoreProposalReportNode(
        report_id=_REPORT_URI_2482,
        # Core spelling, as a non-wire caller would already have.
        proposal_dict=proposal.model_dump(serialize_as_any=True),
    )
    py_trees.blackboard.Blackboard.storage.clear()
    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=node, actor_id=_CASE_ACTOR_URI
    )
    assert result.status == py_trees.common.Status.SUCCESS
    assert isinstance(dl.read(_REPORT_URI_2482), VulnerabilityReport)


# ---------------------------------------------------------------------------
# CM-02-001 / CM-02-010 — one CaseActor per case, distinct from the case owner
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-02-001")
@pytest.mark.spec("CM-02-010")
class TestCaseActorIsOneParticipantDistinctFromTheOwner:
    """The bootstrap snapshot names exactly one CaseActor, and it is not the owner.

    Under ADR-0041 "CaseActor" is the participant holding
    ``CVDRole.CASE_MANAGER``, not a per-case ``Service`` object — the earlier
    reading is what produced the phantom per-case identity (#1872), and the
    tests that covered these two requirements went with the node that minted it.
    Both requirements survive the rewording and are asserted here against the
    snapshot the CaseActor actually builds.

    Co-location is what makes CM-02-010 worth asserting: this store belongs to
    the CaseActor and the vendor is a participant in it, so nothing about the
    layout would stop the two from collapsing into one identity. Under ADR-0073
    that collapse would also merge two stores that must stay separate.
    """

    def _bootstrap_case(self, make_payload):
        from vultron.core.models.case import VulnerabilityCase

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_ACTOR_URI,
        )
        _seed_report(dl)
        _run_full_bt(make_payload, dl)

        cases = [
            c
            for c in dl.list_objects("VulnerabilityCase")
            if isinstance(c, VulnerabilityCase)
        ]
        assert len(cases) == 1, "the proposal bootstraps exactly one case"
        self._dl = dl
        return cases[0]

    def _managers(self, case) -> list[str]:
        """Return the actor ids of the participants holding CASE_MANAGER."""
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.enums.roles import CVDRole

        managers = []
        for actor_id, participant_id in case.actor_participant_index.items():
            participant = self._dl.read(participant_id)
            if not isinstance(participant, CaseParticipant):
                continue
            if CVDRole.CASE_MANAGER in participant.roles:
                managers.append(actor_id)
        return managers

    def test_exactly_one_participant_holds_case_manager(self, make_payload):
        """CM-02-001, read as the role rather than as a ``Service`` record.

        Two managers would mean two actors each entitled to write the canonical
        ledger, which is the authority CM-02-002 makes exclusive.
        """
        case = self._bootstrap_case(make_payload)
        assert self._managers(case) == [_CASE_ACTOR_URI]

    def test_the_case_manager_is_not_the_case_owner(self, make_payload):
        """CM-02-010: distinct identities, co-located in one store or not.

        If these ever coincided, the CaseActor's replication to the owner would
        become a message an actor sends itself — delivery discards those, so the
        owner would silently never receive its own case.
        """
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.enums.roles import CVDRole

        case = self._bootstrap_case(make_payload)
        owner_participant_id = case.actor_participant_index.get(_VENDOR_URI)
        assert owner_participant_id is not None, (
            "the proposer is a participant"
        )
        owner = self._dl.read(owner_participant_id)
        assert isinstance(owner, CaseParticipant)
        assert CVDRole.CASE_OWNER in owner.roles

        assert _VENDOR_URI not in self._managers(case)
        assert CVDRole.CASE_MANAGER not in owner.roles


# ---------------------------------------------------------------------------
# EP-04-003 / EP-04-004: the Reporter's proposed terms at case creation
# ---------------------------------------------------------------------------


class TestEP04SenderProposalAtCaseCreation:
    """The Reporter's proposed embargo reaches creation and is compared.

    The proposal arrives on the Offer the CaseProposal carries inline
    (CP-01-008).  Shortest-wins runs between it and the case owner's actor
    default (EP-04-003); the protocol default is never a candidate
    (EP-04-006); the winning sender event keeps its identity with its
    ``context`` rewritten to the case (EP-04-004); the loser becomes a pending
    revision (EP-04-003).  #3392.
    """

    _SENDER_END_DAYS = 10
    _ACTOR_DEFAULT = timedelta(days=30)
    #: The policy the proposing vendor's inline profile carries, if any.
    _owner_policy: timedelta | None = None

    def _event_with_terms(
        self,
        make_payload,
        *,
        sender_days: int,
        terms_context: str = _REPORT_URI,
        proposal_id: str = _PROPOSAL_URI,
        terms: Any = None,
    ):
        from datetime import datetime

        from vultron.core.models.embargo_event import EmbargoEvent
        from vultron.wire.as2.factories import rm_submit_report_activity
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        report = as_VulnerabilityReport(
            id_=_REPORT_URI, attributed_to=_REPORTER_URI, content="x"
        )
        if terms is None:
            terms = EmbargoEvent(
                id_=f"{_REPORT_URI}/embargo_proposals/1",
                context=terms_context,
                end_time=datetime.now(tz=UTC) + timedelta(days=sender_days),
            )
        if terms_context == _REPORT_URI:
            offer = rm_submit_report_activity(
                report,
                to=_VENDOR_URI,
                actor=_REPORTER_URI,
                proposed_embargo=terms,
            )
        else:
            # The factory refuses terms about another subject on the sending
            # side (EP-04-009); a non-conforming sender is simulated past it.
            offer = rm_submit_report_activity(
                report, to=_VENDOR_URI, actor=_REPORTER_URI
            ).model_copy(update={"proposed_embargo": terms})
        proposal = as_CaseProposal(
            id_=proposal_id,
            attributed_to=_VENDOR_URI,
            object_=report,
            target=_CASE_ACTOR_URI,
            offer_id=offer.id_,
            offer_actor_id=_REPORTER_URI,
            in_reply_to=offer,
        )
        activity = as_Create(
            actor=_vendor_profile(self._owner_policy),
            object_=proposal,
            to=[_CASE_ACTOR_URI],
        )
        event = make_payload(activity)
        return (
            event.model_copy(update={"receiving_actor_id": _CASE_ACTOR_URI}),
            terms,
        )

    def _publish_owner_policy(self) -> None:
        """Give the CASE_OWNER an actor default — the proposing vendor's.

        The case is attributed to the proposing actor (CP-09-001), so it is
        that actor's policy that competes under shortest-wins (EP-04-003),
        never one the CaseActor published.  It travels on the vendor's inline
        profile, the Create's ``actor`` (CP-01-010).
        """
        self._owner_policy = self._ACTOR_DEFAULT

    def _run(
        self,
        make_payload,
        dl: SqliteDataLayer,
        *,
        sender_days: int,
        **terms_kwargs,
    ):
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        event, terms = self._event_with_terms(
            make_payload, sender_days=sender_days, **terms_kwargs
        )
        CreateCaseProposalReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()
        (case,) = [
            c
            for c in dl.list_objects("VulnerabilityCase")
            if isinstance(c, VulnerabilityCase)
        ]
        return case, terms

    @staticmethod
    def _store() -> SqliteDataLayer:
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        _seed_report(dl)
        return dl

    @pytest.mark.spec("EP-04-004")
    @pytest.mark.spec("EP-04-007")
    def test_a_lone_sender_proposal_becomes_the_active_embargo_about_the_case(
        self, make_payload
    ):
        """No actor default: the sender's terms win outright, at their stated
        length (shorter than nothing competes with, EP-04-007), and the event
        the Reporter sent is the case's embargo with its context rewritten."""
        from vultron.core.models.embargo_event import EmbargoEvent

        dl = self._store()
        case, terms = self._run(
            make_payload, dl, sender_days=self._SENDER_END_DAYS
        )

        assert case.current_status.em.state == EM.ACTIVE
        assert case.active_embargo_id == terms.id_
        embargo = dl.read(terms.id_)
        assert isinstance(embargo, EmbargoEvent)
        assert embargo.context == case.id_
        assert embargo.end_time == terms.end_time
        assert case.proposed_embargoes == []

    @pytest.mark.spec("EP-04-003")
    def test_shorter_sender_proposal_wins_and_the_actor_default_is_a_revision(
        self, make_payload
    ):
        from vultron.core.models.embargo_event import EmbargoEvent

        dl = self._store()
        self._publish_owner_policy()
        case, terms = self._run(
            make_payload, dl, sender_days=self._SENDER_END_DAYS
        )

        assert case.active_embargo_id == terms.id_
        assert case.current_status.em.state == EM.REVISE
        (revision_id,) = case.proposed_embargoes
        revision = dl.read(revision_id)
        assert isinstance(revision, EmbargoEvent)
        assert revision.context == case.id_
        assert revision.end_time > terms.end_time
        assert revision.end_time - terms.end_time > timedelta(days=19)

    @pytest.mark.spec("EP-04-003")
    @pytest.mark.spec("CP-09-001")
    def test_the_case_actors_own_policy_is_not_the_actor_default(
        self, make_payload
    ):
        """The CASE_MANAGER creates the case but its policy never competes.

        A five-day CaseActor policy would beat the sender's ten days; the
        owner's thirty-day default must not, so the sender's terms win.
        """
        from vultron.core.models.actor import VultronService
        from vultron.core.models.embargo_policy import EmbargoPolicy

        dl = self._store()
        self._publish_owner_policy()
        dl.save(
            VultronService(
                id_=_CASE_ACTOR_URI,
                embargo_policy=EmbargoPolicy(
                    actor_id=_CASE_ACTOR_URI,
                    inbox=f"{_CASE_ACTOR_URI}/inbox",
                    preferred_duration=timedelta(days=5),
                ),
            )
        )
        case, terms = self._run(
            make_payload, dl, sender_days=self._SENDER_END_DAYS
        )

        assert case.attributed_to == _VENDOR_URI
        assert case.active_embargo_id == terms.id_

    @pytest.mark.spec("EP-04-003")
    @pytest.mark.spec("EP-04-004")
    def test_shorter_actor_default_wins_and_the_sender_proposal_is_a_revision(
        self, make_payload
    ):
        from vultron.core.models.embargo_event import EmbargoEvent

        dl = self._store()
        self._publish_owner_policy()
        case, terms = self._run(make_payload, dl, sender_days=60)

        assert case.active_embargo_id != terms.id_
        active = dl.read(case.active_embargo_id or "")
        assert isinstance(active, EmbargoEvent)
        assert active.end_time < terms.end_time
        assert case.current_status.em.state == EM.REVISE
        # The Reporter's own event is the pending revision, now about the case.
        assert case.proposed_embargoes == [terms.id_]
        revision = dl.read(terms.id_)
        assert isinstance(revision, EmbargoEvent)
        assert revision.context == case.id_
        assert revision.end_time == terms.end_time

    @pytest.mark.spec("EP-04-003")
    @pytest.mark.spec("CP-05-006")
    def test_a_second_proposal_for_the_same_report_registers_no_second_revision(
        self, make_payload
    ):
        """The same Offer re-delivered makes the vendor propose again under a
        new proposal id; the CaseActor reuses the case and must leave its
        creation-time embargo alone — one active, one pending, no orphan.
        The report-with-embargo demo found two revisions here (#3393)."""
        from vultron.core.models.embargo_event import EmbargoEvent

        dl = self._store()
        self._publish_owner_policy()
        case, terms = self._run(
            make_payload, dl, sender_days=self._SENDER_END_DAYS
        )
        events_after_first = {e.id_ for e in dl.list_objects("EmbargoEvent")}
        assert case.current_status.em.state == EM.REVISE
        assert len(case.proposed_embargoes) == 1

        again, _ = self._run(
            make_payload,
            dl,
            sender_days=self._SENDER_END_DAYS,
            proposal_id="https://example.org/proposals/p-002",
            terms=terms,
        )

        assert again.id_ == case.id_
        assert again.current_status.em.state == EM.REVISE
        assert again.active_embargo_id == terms.id_
        assert again.proposed_embargoes == case.proposed_embargoes
        assert {
            e.id_ for e in dl.list_objects("EmbargoEvent")
        } == events_after_first
        revision = dl.read(again.proposed_embargoes[0])
        assert isinstance(revision, EmbargoEvent)

    @pytest.mark.spec("EP-04-012")
    @pytest.mark.spec("CP-05-006")
    def test_a_redelivery_after_the_embargo_exited_initializes_nothing(
        self, make_payload
    ):
        """The same proposal redelivered after the case's embargo has ended
        reuses the case and is answered, and the terms it carries are not
        reconciled against the case: EM stays ``EXITED``, no embargo is
        attached and no ``EmbargoEvent`` is stored (EP-04-012, #3986).

        Before the guard read the EM state, termination's cleared reference
        let the creation arm run: an orphan event, then the EM machine's
        refusal of ``EXITED → PROPOSED`` failed the tree before the Accept.
        """
        from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
        from vultron.core.use_cases.received.case_proposal import (
            CreateCaseProposalReceivedUseCase,
        )

        dl = self._store()
        case, terms = self._run(
            make_payload, dl, sender_days=self._SENDER_END_DAYS
        )
        assert case.current_status.em.state == EM.ACTIVE
        EmbargoLifecycle(persistence=dl).terminate_active_embargo(
            case_id=case.id_, actor_id=_VENDOR_URI
        )
        while dl.outbox_pop() is not None:
            pass
        events_before = {e.id_ for e in dl.list_objects("EmbargoEvent")}

        event, _ = self._event_with_terms(
            make_payload, sender_days=self._SENDER_END_DAYS, terms=terms
        )
        result = CreateCaseProposalReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.APPLIED, result
        assert "Accept(CaseProposal)" in _outbox_labels(dl)
        (again,) = [
            c
            for c in dl.list_objects("VulnerabilityCase")
            if isinstance(c, VulnerabilityCase)
        ]
        assert again.id_ == case.id_
        assert again.current_status.em.state == EM.EXITED
        assert again.active_embargo_id is None
        assert again.proposed_embargoes == []
        assert {
            e.id_ for e in dl.list_objects("EmbargoEvent")
        } == events_before

    @pytest.mark.spec("EP-04-004")
    def test_an_expired_proposal_is_no_proposal(self, make_payload):
        """Terms that have already run out do not stop the case; the owner's
        default applies and nothing is registered as a revision."""
        dl = self._store()
        case, terms = self._run(make_payload, dl, sender_days=-1)

        assert case.current_status.em.state == EM.ACTIVE
        assert case.active_embargo_id != terms.id_
        assert case.proposed_embargoes == []

    @pytest.mark.spec("EP-04-003")
    @pytest.mark.spec("CM-14-005")
    def test_contested_creation_leaves_vendor_and_reporter_as_signatories(
        self, make_payload
    ):
        """Consent is seeded to the active terms even though a revision is
        pending: CM-14-005 seeds SIGNATORY on the *active* embargo, and the
        revision registered inside ``InitializeDefaultEmbargoNode`` precedes
        those seeds (see notes/embargo-default-semantics.md)."""
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.states.participant_embargo_consent import PEC

        dl = self._store()
        self._publish_owner_policy()
        case, _terms = self._run(
            make_payload, dl, sender_days=self._SENDER_END_DAYS
        )
        assert case.current_status.em.state == EM.REVISE

        states = {}
        for actor_uri in (_VENDOR_URI, _REPORTER_URI):
            pid = case.actor_participant_index[actor_uri]
            participant = dl.read(pid)
            assert isinstance(participant, CaseParticipant)
            states[actor_uri] = participant.embargo_consent_state
        assert states == {
            _VENDOR_URI: PEC.SIGNATORY.value,
            _REPORTER_URI: PEC.SIGNATORY.value,
        }

    @pytest.mark.spec("EP-04-009")
    def test_terms_about_another_subject_are_no_proposal(
        self, make_payload, caplog
    ):
        """A proposal whose context is not this report is not terms for it:
        the case is created under the owner's default and nothing is
        registered, with the reason logged."""
        import logging

        dl = self._store()
        with caplog.at_level(logging.WARNING):
            case, terms = self._run(
                make_payload,
                dl,
                sender_days=self._SENDER_END_DAYS,
                terms_context="https://example.org/reports/someone-elses",
            )

        assert case.current_status.em.state == EM.ACTIVE
        assert case.active_embargo_id != terms.id_
        assert case.proposed_embargoes == []
        assert any(
            "not the proposal's report" in r.getMessage()
            for r in caplog.records
        )


# ---------------------------------------------------------------------------
# Outbound ordering: the case reaches a participant before its ledger entries
# ---------------------------------------------------------------------------


def _outbox_labels(dl: SqliteDataLayer) -> list[str]:
    """Describe the case-actor outbox as ``Verb(ObjectType)`` labels, in order."""
    labels: list[str] = []
    for activity_id in dl.outbox_list():
        activity = dl.read(activity_id)
        labels.append(
            f"{getattr(activity, 'type_', '?')}({_object_type(activity)})"
        )
    return labels


@pytest.mark.spec("CP-09-009")
@pytest.mark.spec("CM-14-011")
@pytest.mark.spec("CP-05-003")
def test_accept_and_create_are_queued_before_any_ledger_fanout(make_payload):
    """Accept, then Create(VulnerabilityCase), then the ledger fan-out.

    The outbox is FIFO (OX-01-002), so enqueue order is wire order.  If the
    native ledger commits fan out first, every recipient receives
    ``Announce(CaseLedgerEntry)`` for a case it does not hold yet, enters the
    pre-genesis path (SYNC-15), sends a ``Reject``, and the CASE_MANAGER
    replays the whole ledger — while ``Create(VulnerabilityCase)`` waits at
    the back of the queue.  That queue position is what timed out the fv and
    fcv-reject replica gates (#3033) and congested the CaseActor outbox in
    fcvcv (#2898).  CM-14-011's rationale states the rule: the reporter's
    system must hold the case object before any fan-out that references it.
    """
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.core.use_cases.received.case_proposal import (
        CreateCaseProposalReceivedUseCase,
    )

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
    _seed_report(dl)
    event = _make_full_event(make_payload)
    CreateCaseProposalReceivedUseCase(
        dl,
        event,
        wire_render_port=As2WireRenderAdapter(),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
    ).execute()

    labels = _outbox_labels(dl)
    announces = [lbl for lbl in labels if lbl.startswith("Announce(")]

    # Not vacuous: without an injected sync port the fan-out is skipped and
    # any order assertion would pass trivially.
    assert len(announces) >= 2, (
        f"expected the native ledger fan-out to reach the outbox, got {labels}"
    )
    assert labels[:2] == [
        "Accept(CaseProposal)",
        "Create(VulnerabilityCase)",
    ], f"Accept and Create must head the outbox, got {labels}"
    assert labels[2:] == announces, (
        "every Announce(CaseLedgerEntry) must follow Create(VulnerabilityCase),"
        f" got {labels}"
    )


@pytest.mark.spec("CP-09-009")
def test_genesis_commit_failure_is_reported_after_accept_and_create_are_queued(
    make_payload,
):
    """A genesis-commit failure is surfaced, not prevented, once the commit runs last.

    Before CP-09-009 the ledger commit preceded the emits, so a failed genesis
    ``create_case`` commit aborted the Sequence before ``Accept`` and
    ``Create`` were queued.  Now the commit runs after them (so the fan-out
    queues behind the ``Create``), and the trade-off is explicit: on genesis
    failure the handler does not report APPLIED, but ``Accept`` and ``Create``
    are already in the FIFO outbox, no ``Announce(CaseLedgerEntry)`` follows
    them, and the retry marker has already been cleared.  This test pins that
    shape so a future change to either half is a deliberate one.
    """
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.core.behaviors.case.nodes import (
        CommitNativeLedgerEntriesNode,
    )
    from vultron.core.use_cases.received.case_proposal import (
        CreateCaseProposalReceivedUseCase,
    )

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
    _seed_report(dl)
    event = _make_full_event(make_payload)
    with patch.object(
        CommitNativeLedgerEntriesNode, "_commit_one", return_value=False
    ):
        result = CreateCaseProposalReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

    assert result.disposition is not HandlerDisposition.APPLIED, (
        "a failed genesis commit must not read as a successful case creation"
    )
    assert "genesis create_case ledger commit failed" in (result.reason or "")
    assert _outbox_labels(dl) == [
        "Accept(CaseProposal)",
        "Create(VulnerabilityCase)",
    ], (
        "Accept and Create are queued before the commit runs, and nothing follows"
    )
    assert list(dl.list_objects("PendingCreateCaseActivity")) == [], (
        "the retry marker is cleared before the commit runs"
    )
