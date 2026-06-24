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
  - CreateCaseProposalReceivedUseCase (AC-1, CP-05-001 through CP-05-004)
  - AcceptCaseProposalReceivedUseCase (AC-2, CP-06-001, CP-06-003)
  - RejectCaseProposalReceivedUseCase (AC-3, CP-06-002, CP-06-004)

Spec: specs/case-proposal.yaml CP-05 through CP-07.
"""

import logging

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
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
    VulnerabilityReport,
)

_CASE_ACTOR_URI = "https://example.org/case-actors/svc-1"
_VENDOR_URI = "https://example.org/vendors/acme"


def _make_proposal() -> as_CaseProposal:
    return as_CaseProposal(
        attributed_to=_VENDOR_URI,
        object_=gen_report(),
        target=_CASE_ACTOR_URI,
    )


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
        assert isinstance(report_obj, VulnerabilityReport)
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


class TestAcceptCaseProposalReceivedUseCase:
    """Tests for AcceptCaseProposalReceivedUseCase (CP-06-001, CP-06-003)."""

    def test_execute_records_case_actor_uri(self, make_payload):
        """accept_case_proposal_received updates VultronReportCaseLink.trusted_case_actor_id."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        proposal = _make_proposal()
        assert isinstance(
            proposal.object_, VulnerabilityReport
        ), "_make_proposal() must embed a full VulnerabilityReport"
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
        # TODO(#1088): CP-06-004 MUST — update vendor local state to reflect
        # rejection (e.g., mark VultronReportCaseLink as rejected). Tracked
        # in https://github.com/CERTCC/Vultron/issues/1088.
