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
"""Unit tests for CaseProposal received-side use cases.

Covers the execute() paths for:
  - CreateCaseProposalReceivedUseCase (AC-1 through AC-4, CP-05-001 through
    CP-05-006)
  - AcceptCaseProposalReceivedUseCase (AC-2, CP-06-001, CP-06-003)
  - RejectCaseProposalReceivedUseCase (AC-3, CP-06-002, CP-06-004)

Spec: specs/case-proposal.yaml CP-05 through CP-07.
"""

import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.protocols import is_case_model
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.use_cases.received.case_proposal import (
    AcceptCaseProposalReceivedUseCase,
    CreateCaseProposalReceivedUseCase,
    RejectCaseProposalReceivedUseCase,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Reject,
)
from vultron.wire.as2.vocab.examples._base import gen_report
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_CASE_ACTOR_URI = "https://example.org/case-actors/svc-1"
_VENDOR_URI = "https://example.org/vendors/acme"


def _make_proposal() -> as_CaseProposal:
    return as_CaseProposal(
        attributed_to=_VENDOR_URI,
        object_=gen_report(),
        target=_CASE_ACTOR_URI,
    )


def _run_create_proposal(dl, proposal, make_payload):
    """Helper: build and execute CreateCaseProposalReceivedUseCase."""
    activity = as_Create(
        actor=_VENDOR_URI,
        object_=proposal,
        to=[_CASE_ACTOR_URI],
    )
    event = make_payload(activity)
    event = event.model_copy(update={"receiving_actor_id": _CASE_ACTOR_URI})
    CreateCaseProposalReceivedUseCase(dl, event).execute()


class TestCreateCaseProposalReceivedUseCase:
    """Tests for CreateCaseProposalReceivedUseCase (CP-05-001 through CP-05-004)."""

    def test_execute_creates_case_and_queues_activities(self, make_payload):
        """Happy path: case created + Accept + Create(VulnerabilityCase) queued."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()
        activity = as_Create(
            actor=_VENDOR_URI,
            object_=proposal,
            to=[_CASE_ACTOR_URI],
        )
        event = make_payload(activity)
        event = event.model_copy(
            update={"receiving_actor_id": _CASE_ACTOR_URI}
        )

        CreateCaseProposalReceivedUseCase(dl, event).execute()

        # AC-1: VulnerabilityCase was created
        cases = [
            obj
            for obj in dl.list_objects("VulnerabilityCase")
            if is_case_model(obj)
        ]
        assert (
            len(cases) == 1
        ), "Expected exactly one VulnerabilityCase to be created"

        # Accept(CaseProposal) was stored
        accepts = dl.list_objects("Accept")
        assert len(accepts) == 1, "Expected one Accept activity"

        # The Accept must carry the full inline proposal (CP-05-003, MV-09-001).
        accept_obj = dl.read(accepts[0].id_)
        accept_object_ = getattr(accept_obj, "object_", None)
        assert (
            accept_object_ is not None
        ), "Accept.object_ must not be None (CP-05-003)"
        # After DataLayer round-trip the dict may be deserialized to an AS2 object;
        # the key invariant is that it is NOT a bare URI string.
        assert not isinstance(
            accept_object_, str
        ), "Accept.object_ must not be a bare URI string — inline object required (CP-05-003)"
        obj_type = getattr(accept_object_, "type_", None) or (
            accept_object_.get("type")
            if isinstance(accept_object_, dict)
            else None
        )
        assert (
            obj_type == "CaseProposal"
        ), f"Accept.object_ type should be 'CaseProposal', got {obj_type!r}"

        # Create(VulnerabilityCase) was stored
        creates = dl.list_objects("Create")
        assert (
            len(creates) == 1
        ), "Expected one Create(VulnerabilityCase) activity"

        # Both activities appear in the outbox
        outbox = dl.outbox_list_for_actor(_CASE_ACTOR_URI)
        assert len(outbox) == 2, f"Expected 2 outbox items, got {len(outbox)}"

    def test_execute_report_linked_to_case(self, make_payload):
        """The report from the proposal is linked to the created case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()
        activity = as_Create(
            actor=_VENDOR_URI,
            object_=proposal,
            to=[_CASE_ACTOR_URI],
        )
        event = make_payload(activity)
        event = event.model_copy(
            update={"receiving_actor_id": _CASE_ACTOR_URI}
        )

        CreateCaseProposalReceivedUseCase(dl, event).execute()

        case_rows = dl.list_objects("VulnerabilityCase")
        assert case_rows, "No VulnerabilityCase created"
        case_obj = dl.read(case_rows[0].id_)
        assert is_case_model(case_obj)

        report_obj = proposal.object_
        assert isinstance(report_obj, as_VulnerabilityReport)
        report_id = report_obj.id_
        assert (
            report_id in case_obj.vulnerability_reports
        ), f"Report '{report_id}' not linked to case"

    def test_execute_skips_without_receiving_actor_id(self, make_payload):
        """Missing receiving_actor_id causes a no-op (CLP-10-005)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()
        activity = as_Create(
            actor=_VENDOR_URI,
            object_=proposal,
            to=[_CASE_ACTOR_URI],
        )
        event = make_payload(activity)
        # receiving_actor_id is None by default when not set
        event = event.model_copy(update={"receiving_actor_id": None})

        CreateCaseProposalReceivedUseCase(dl, event).execute()

        # No case should have been created
        cases = dl.list_objects("VulnerabilityCase")
        assert (
            len(cases) == 0
        ), "No case should be created without receiving_actor_id"

    def test_create_activity_context_is_accept_uri(self, make_payload):
        """Create(VulnerabilityCase) context must point to the Accept activity (CP-05-003)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()
        activity = as_Create(
            actor=_VENDOR_URI,
            object_=proposal,
            to=[_CASE_ACTOR_URI],
        )
        event = make_payload(activity)
        event = event.model_copy(
            update={"receiving_actor_id": _CASE_ACTOR_URI}
        )

        CreateCaseProposalReceivedUseCase(dl, event).execute()

        accept_rows = dl.list_objects("Accept")
        assert accept_rows, "No Accept activity stored"
        accept_id = accept_rows[0].id_

        create_rows = dl.list_objects("Create")
        assert create_rows, "No Create activity stored"
        create_obj = dl.read(create_rows[0].id_)
        # After DataLayer round-trip, the object may come back as a wire-layer
        # _CreateCaseActivity rather than VultronCreateCaseActivity; check the
        # context attribute directly (CP-05-003).
        context_val = getattr(create_obj, "context", None)
        assert context_val == accept_id, (
            f"Create(VulnerabilityCase).context should be Accept URI '{accept_id}'"
            f", got '{context_val}'"
        )


class TestCreateCaseProposalIdempotency:
    """Tests for CP-05-006 duplicate-proposal idempotency."""

    def test_duplicate_proposal_does_not_create_second_case(
        self, make_payload
    ):
        """AC-1: Second proposal for same report creates no duplicate case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()

        _run_create_proposal(dl, proposal, make_payload)
        cases_after_first = list(dl.list_objects("VulnerabilityCase"))
        assert (
            len(cases_after_first) == 1
        ), "First proposal must create one case"

        # Resend the same proposal
        _run_create_proposal(dl, proposal, make_payload)

        all_cases = [
            obj
            for obj in dl.list_objects("VulnerabilityCase")
            if is_case_model(obj)
        ]
        assert (
            len(all_cases) == 1
        ), "Duplicate proposal must not create a second VulnerabilityCase (AC-1)"

    def test_duplicate_proposal_sends_accept_referencing_existing_case(
        self, make_payload
    ):
        """AC-2: Duplicate proposal triggers a new Accept referencing existing case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()

        _run_create_proposal(dl, proposal, make_payload)
        first_accepts = list(dl.list_objects("Accept"))
        assert first_accepts, "First proposal must produce an Accept"
        first_accept_ids = {a.id_ for a in first_accepts}
        first_case_id = list(dl.list_objects("VulnerabilityCase"))[0].id_

        # Resend with the same proposal
        _run_create_proposal(dl, proposal, make_payload)

        all_accepts = list(dl.list_objects("Accept"))
        # A new Accept should have been added for the duplicate
        assert (
            len(all_accepts) >= 2
        ), "Duplicate proposal should produce a second Accept (AC-2)"

        # Find the Accept added for the duplicate proposal
        duplicate_accepts = [
            a for a in all_accepts if a.id_ not in first_accept_ids
        ]
        assert (
            duplicate_accepts
        ), "Must have at least one new Accept for the duplicate proposal (AC-2)"

        # The duplicate Accept must reference the existing case via result field.
        dup_accept_obj = dl.read(duplicate_accepts[0].id_)
        raw_result = getattr(dup_accept_obj, "result", None) or (
            dup_accept_obj.get("result")
            if isinstance(dup_accept_obj, dict)
            else None
        )
        # After DataLayer round-trip the result field may be deserialized to a
        # full domain object; extract the id_ in that case.
        if isinstance(raw_result, str):
            result_val = raw_result
        elif raw_result is not None and hasattr(raw_result, "id_"):
            result_val = getattr(raw_result, "id_")
        elif isinstance(raw_result, dict):
            result_val = raw_result.get("id_") or raw_result.get("id")
        else:
            result_val = None
        assert result_val == first_case_id, (
            f"Duplicate Accept.result should be existing case '{first_case_id}'"
            f", got {result_val!r} (AC-2, CP-05-006)"
        )

    def test_in_flight_proposal_is_no_op(self, make_payload):
        """AC-3: Proposal with existing marker is a no-op (no duplicate Accept)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()

        # Run first proposal fully so a case and outbox entries exist
        _run_create_proposal(dl, proposal, make_payload)
        first_accepts = list(dl.list_objects("Accept"))
        first_creates = list(dl.list_objects("Create"))

        # Manually re-insert the marker to simulate an in-flight state
        marker = PendingCreateCaseActivity(
            proposal_id=proposal.id_,
            case_actor_id=_CASE_ACTOR_URI,
            vendor_uri=_VENDOR_URI,
            create_activity_payload={},
        )
        dl.save(marker)

        # Resend proposal — marker present, so use case should no-op
        _run_create_proposal(dl, proposal, make_payload)

        after_accepts = list(dl.list_objects("Accept"))
        after_creates = list(dl.list_objects("Create"))
        assert len(after_accepts) == len(
            first_accepts
        ), "No new Accept should be sent when marker is present (AC-3)"
        assert len(after_creates) == len(
            first_creates
        ), "No new Create should be sent when marker is present (AC-3)"


class TestCreateCaseProposalIdempotencyIntegration:
    """Integration tests for CP-05-006 duplicate-proposal idempotency (AC-4).

    These tests use a file-backed SQLite DataLayer to verify that the
    idempotency behaviour holds across real persistence boundaries.
    """

    @pytest.mark.integration
    def test_duplicate_proposal_no_second_case_file_backend(
        self, make_payload, tmp_path
    ):
        """AC-4: No second VulnerabilityCase is created on retry (file-backed DL).

        Uses a real SQLite file to ensure the idempotency guard works with
        a persistent backend, not just an in-memory one.
        """
        db_url = f"sqlite:///{tmp_path / 'test_idempotency.db'}"
        dl = SqliteDataLayer(db_url)
        proposal = _make_proposal()

        _run_create_proposal(dl, proposal, make_payload)
        cases_after_first = [
            obj
            for obj in dl.list_objects("VulnerabilityCase")
            if is_case_model(obj)
        ]
        assert (
            len(cases_after_first) == 1
        ), "First proposal must create one case"
        first_case_id = cases_after_first[0].id_

        # Resend the same proposal (network-retry scenario)
        _run_create_proposal(dl, proposal, make_payload)

        all_cases = [
            obj
            for obj in dl.list_objects("VulnerabilityCase")
            if is_case_model(obj)
        ]
        assert (
            len(all_cases) == 1
        ), "Duplicate proposal must not create a second VulnerabilityCase (AC-4)"
        assert (
            all_cases[0].id_ == first_case_id
        ), "The surviving case must be the original one (AC-4)"

        all_accepts = list(dl.list_objects("Accept"))
        assert (
            len(all_accepts) >= 2
        ), "Duplicate proposal should produce a second Accept (AC-4)"
        dl.close()


class TestAcceptCaseProposalReceivedUseCase:
    """Tests for AcceptCaseProposalReceivedUseCase (CP-06-001, CP-06-003)."""

    def test_execute_records_case_actor_uri(self, make_payload):
        """accept_case_proposal_received updates VultronReportCaseLink.trusted_case_actor_id."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()
        assert isinstance(
            proposal.object_, as_VulnerabilityReport
        ), "_make_proposal() must embed a full as_VulnerabilityReport"
        report_id = proposal.object_.id_

        # Seed a VultronReportCaseLink so the use case can find it
        link = VultronReportCaseLink(
            report_id=report_id,
            trusted_case_creator_id=_CASE_ACTOR_URI,
        )
        dl.create(link)

        activity = as_Accept(
            actor=_CASE_ACTOR_URI,
            object_=proposal,
            to=[_VENDOR_URI],
        )
        event = make_payload(activity)
        event = event.model_copy(update={"receiving_actor_id": _VENDOR_URI})

        AcceptCaseProposalReceivedUseCase(dl, event).execute()

        stored_link = dl.read(VultronReportCaseLink.build_id(report_id))
        assert isinstance(stored_link, VultronReportCaseLink)
        assert (
            stored_link.trusted_case_actor_id == _CASE_ACTOR_URI
        ), "trusted_case_actor_id should be set to the case-actor URI"

    def test_execute_no_link_is_non_fatal(self, make_payload):
        """Missing VultronReportCaseLink causes a warning but not an error (CP-06-003)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()

        activity = as_Accept(
            actor=_CASE_ACTOR_URI,
            object_=proposal,
            to=[_VENDOR_URI],
        )
        event = make_payload(activity)
        event = event.model_copy(update={"receiving_actor_id": _VENDOR_URI})

        # Should not raise
        AcceptCaseProposalReceivedUseCase(dl, event).execute()

    def test_execute_skips_when_no_inner_object_id(self, make_payload):
        """Missing report_id (inner_object_id) logs a warning and returns early."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        # Build an Accept whose object_ lacks a nested object (pathological case)
        activity = as_Accept(
            actor=_CASE_ACTOR_URI,
            object_="https://example.org/proposals/bare-id-only",
            to=[_VENDOR_URI],
        )
        event = make_payload(activity)
        event = event.model_copy(update={"receiving_actor_id": _VENDOR_URI})

        # Should not raise even without a valid inner_object_id
        AcceptCaseProposalReceivedUseCase(dl, event).execute()


class TestRejectCaseProposalReceivedUseCase:
    """Tests for RejectCaseProposalReceivedUseCase (CP-06-002, CP-06-004)."""

    def test_execute_marks_link_as_rejected(self, make_payload):
        """Rejection sets proposal_rejected=True on VultronReportCaseLink (CP-06-004)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()
        assert isinstance(proposal.object_, as_VulnerabilityReport)
        report_id = proposal.object_.id_

        # Seed a VultronReportCaseLink so the use case can find it
        link = VultronReportCaseLink(
            report_id=report_id,
            trusted_case_creator_id=_CASE_ACTOR_URI,
        )
        dl.create(link)

        activity = as_Reject(
            actor=_CASE_ACTOR_URI,
            object_=proposal,
            to=[_VENDOR_URI],
        )
        event = make_payload(activity)
        event = event.model_copy(update={"receiving_actor_id": _VENDOR_URI})

        RejectCaseProposalReceivedUseCase(dl, event).execute()

        stored_link = dl.read(VultronReportCaseLink.build_id(report_id))
        assert isinstance(stored_link, VultronReportCaseLink)
        assert (
            stored_link.proposal_rejected is True
        ), "proposal_rejected should be True after rejection"
        assert (
            stored_link.rejection_reason is None
        ), "rejection_reason should be None when not provided"

    def test_execute_records_rejection_reason(self, make_payload):
        """When Reject activity carries a summary, it is stored as rejection_reason (CP-06-004)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()
        assert isinstance(proposal.object_, as_VulnerabilityReport)
        report_id = proposal.object_.id_

        link = VultronReportCaseLink(
            report_id=report_id,
            trusted_case_creator_id=_CASE_ACTOR_URI,
        )
        dl.create(link)

        rejection_summary = "Duplicate report; case already exists."
        activity = as_Reject(
            actor=_CASE_ACTOR_URI,
            object_=proposal,
            to=[_VENDOR_URI],
            summary=rejection_summary,
        )
        event = make_payload(activity)
        event = event.model_copy(update={"receiving_actor_id": _VENDOR_URI})

        RejectCaseProposalReceivedUseCase(dl, event).execute()

        stored_link = dl.read(VultronReportCaseLink.build_id(report_id))
        assert isinstance(stored_link, VultronReportCaseLink)
        assert stored_link.proposal_rejected is True
        assert (
            stored_link.rejection_reason == rejection_summary
        ), "rejection_reason should match the Reject activity summary"

    def test_execute_no_link_is_non_fatal(self, make_payload):
        """Missing VultronReportCaseLink causes a warning but not an error (CP-06-004)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()

        activity = as_Reject(
            actor=_CASE_ACTOR_URI,
            object_=proposal,
            to=[_VENDOR_URI],
        )
        event = make_payload(activity)
        event = event.model_copy(update={"receiving_actor_id": _VENDOR_URI})

        # Should not raise even when no VultronReportCaseLink exists
        RejectCaseProposalReceivedUseCase(dl, event).execute()

    def test_execute_logs_rejection(self, make_payload, caplog):
        """Rejection is surfaced via a warning-level log message (CP-06-004)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()
        activity = as_Reject(
            actor=_CASE_ACTOR_URI,
            object_=proposal,
            to=[_VENDOR_URI],
        )
        event = make_payload(activity)
        event = event.model_copy(update={"receiving_actor_id": _VENDOR_URI})

        with caplog.at_level(logging.WARNING, logger="vultron"):
            RejectCaseProposalReceivedUseCase(dl, event).execute()

        assert any(
            "reject" in record.message.lower() for record in caplog.records
        ), "Expected a rejection log message"
