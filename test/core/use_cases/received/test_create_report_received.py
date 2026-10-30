#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Tests for CreateReportReceivedUseCase: creation, no-standalone-status, duplicate handling."""

from unittest.mock import MagicMock

import pytest

from test.support.case_owner import CASE_OWNER_ID
from test.support.received import with_evidence
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    CreateReportReceivedEvent,
    SubmitReportReceivedEvent,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases.received.case import CreateCaseReceivedUseCase
from vultron.core.use_cases.received.report import (
    CreateReportReceivedUseCase,
    SubmitReportReceivedUseCase,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)


class TestUseCaseExecution:
    """Test that use cases execute with valid semantics."""

    def test_create_report_executes_with_valid_semantics(self, make_payload):
        """CreateReportReceivedUseCase executes when semantics match.

        The event carries a ``receiving_actor_id``, which is not incidental: a
        received-side use case executes as the receiving actor, and with a
        ``MagicMock`` DataLayer there is no store to fall back to — ``getattr(dl,
        "actor_id")`` yields another Mock rather than a string, so
        ``resolve_receiving_actor_id`` raises rather than inventing an identity
        that would select an empty scratch store (ARCH-15-001).  The inbox
        adapter always sets this field in production.
        """
        report = as_VulnerabilityReport(
            name="TEST-002", content="Test vulnerability report"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester",
            object_=report,
            to=["https://example.org/actors/receiver"],
        )
        event = make_payload(
            create_activity,
            receiving_actor_id="https://example.org/actors/receiver",
        )

        mock_dl = MagicMock()
        result = CreateReportReceivedUseCase(mock_dl, event).execute()
        assert result == HandlerResult.applied()

    def test_create_case_executes_with_valid_semantics(self, make_payload):
        """CreateCaseReceivedUseCase executes when semantics match."""
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            name="TEST-CASE-002",
            content="Test vulnerability case",
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester",
            object_=case,
            to=["https://test.example/api/v2/actors/test-actor"],
        )
        event = make_payload(create_activity)

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        result = CreateCaseReceivedUseCase(dl, event).execute()
        # No ReportCaseLink names the sender: an untrusted Create is refused
        # (HP-01-003, CBT-01-011).
        assert result.disposition == HandlerDisposition.REFUSED

    def test_use_case_executes_with_real_datalayer(self, make_payload):
        """CreateReportReceivedUseCase executes without raising on real DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        report = as_VulnerabilityReport(
            name="TEST-003", content="Test report for shim delegation"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester",
            object_=report,
            to=[dl.actor_id],
        )
        event = make_payload(create_activity)
        result = CreateReportReceivedUseCase(dl, event).execute()
        assert result == HandlerResult.applied()


_FINDER_ID = "https://example.org/users/finder"
_RECEIVER_ID = "https://test.example/api/v2/actors/test-actor"


def _run_create_report(
    report_id: str,
    activity_id: str,
    sender_id: str = _FINDER_ID,
    dl: SqliteDataLayer | None = None,
) -> tuple[HandlerResult, SqliteDataLayer]:
    """Run ``CreateReportReceivedUseCase`` for ``Create(Report)`` from *sender_id*.

    The activity is addressed to the receiving store's actor, so it passes the
    received tree's addressee door (HP-01-005).
    """
    if dl is None:
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER_ID)
    activity = VultronActivity(
        id_=activity_id, type_="Create", actor=sender_id, to=[dl.actor_id]
    )
    event = with_evidence(
        CreateReportReceivedEvent(
            semantic_type=MessageSemantics.CREATE_REPORT,
            activity_id=activity_id,
            actor_id=sender_id,
            object_=VulnerabilityReport(id_=report_id),
            activity=activity,
        )
    )
    return CreateReportReceivedUseCase(dl, event).execute(), dl


class TestCreateReportNoStandaloneParticipantStatus:
    """CreateReportReceivedUseCase must NOT create standalone ParticipantStatus.

    Per IDEA-260408-01-6: RM history lives in CaseParticipant.participant_statuses
    within case objects, not in standalone ParticipantStatus records.
    """

    def test_create_report_does_not_persist_participant_status(self):
        """CreateReportReceivedUseCase stores the report and activity only."""
        _, dl = _run_create_report(
            "https://example.org/reports/r-persist-1",
            "https://example.org/activities/create-p1",
        )

        all_statuses = dl.get_all("ParticipantStatus")
        assert all_statuses == [], (
            "CreateReportReceivedUseCase must not create standalone "
            "ParticipantStatus records (IDEA-260408-01-6)"
        )

    def test_create_report_still_stores_report_and_activity(self):
        """CreateReportReceivedUseCase still stores the report and activity."""
        _, dl = _run_create_report(
            "https://example.org/reports/r-store-1",
            "https://example.org/activities/create-store-1",
        )

        stored_report = dl.read("https://example.org/reports/r-store-1")
        assert stored_report is not None, (
            "as_VulnerabilityReport should be stored"
        )


class TestCreateReportSenderEntitlement:
    """Any actor may send a new report (HP-01-010, HP-01-011)."""

    STRANGER_ID = "https://example.org/users/stranger"

    @pytest.mark.spec("HP-01-010")
    @pytest.mark.spec("HP-01-030")
    def test_sender_outside_the_receivers_case_is_applied(self):
        """A sender in none of the receiver's cases still has its report kept."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER_ID)
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/c-other", attributed_to=_RECEIVER_ID
        )
        dl.save(case)
        assert self.STRANGER_ID not in case.actor_participant_index

        result, dl = _run_create_report(
            "https://example.org/reports/r-stranger-1",
            "https://example.org/activities/create-stranger-1",
            sender_id=self.STRANGER_ID,
            dl=dl,
        )

        assert result.disposition == HandlerDisposition.APPLIED
        assert dl.read("https://example.org/reports/r-stranger-1") is not None

    @pytest.mark.spec("HP-01-011")
    def test_declares_any_actor(self):
        assert (
            CreateReportReceivedUseCase.sender_entitlement
            == SenderRule.before_case(SenderEntitlementKind.ANY_ACTOR)
        )


class TestDuplicateReportHandling:
    """Tests that duplicate as_VulnerabilityReport warnings are not emitted.

    The receiver may already hold the report, for example from an earlier
    delivery of the same activity.  When the use case then tries to store the
    same report, the duplicate must be silently demoted to DEBUG — not
    WARNING — because it is an expected idempotency condition, not a real
    error (D5-6-DUP).  The inbox ingress stores no inline object
    (IO-03-004), so the earlier copy is never ingress's.
    """

    def _make_submit_event(
        self,
        report_id: str,
        activity_id: str,
        vendor_id: str = "https://example.org/actors/vendor",
    ):
        report = VulnerabilityReport(id_=report_id)
        activity = VultronActivity(
            id_=activity_id,
            type_="Offer",
            actor="https://example.org/users/finder",
            to=[vendor_id],
        )
        event = with_evidence(
            SubmitReportReceivedEvent(
                semantic_type=MessageSemantics.SUBMIT_REPORT,
                activity_id=activity_id,
                actor_id="https://example.org/users/finder",
                object_=report,
                activity=activity,
                receiving_actor_id=vendor_id,
            )
        )
        return (report, event)

    def test_submit_report_no_warning_on_duplicate_report(self, caplog):
        """SubmitReportReceivedUseCase emits no WARNING when report already stored.

        A report already held from an earlier delivery is a duplicate; the
        use case must degrade to DEBUG, not WARNING.
        Per D5-6-DUP.
        """
        import logging

        from vultron.config.actor import ActorConfig

        report, event = self._make_submit_event(
            "https://example.org/reports/r-dup-1",
            "https://example.org/activities/offer-dup-1",
        )
        # The store is the receiving vendor's own (BT-05-005).
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/actors/vendor",
        )
        # The receiver already holds the report from an earlier delivery.
        dl.save(report)

        with caplog.at_level(logging.WARNING):
            # Case creation off: the tree keeps the report (the duplicate
            # path under test) and proposes nothing.
            SubmitReportReceivedUseCase(
                dl,
                event,
                trigger_activity=TriggerActivityAdapter(dl),
                actor_config=ActorConfig(auto_create_case=False),
            ).execute()

        warning_records = [
            r for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert warning_records == [], (
            "No WARNING should be emitted when as_VulnerabilityReport is "
            f"already stored; got: {[r.message for r in warning_records]}"
        )

    def test_create_report_no_warning_on_duplicate_report(self, caplog):
        """CreateReportReceivedUseCase emits no WARNING when report already stored.

        Per D5-6-DUP.
        """
        import logging

        report = VulnerabilityReport(
            id_="https://example.org/reports/r-dup-create-1"
        )
        activity = VultronActivity(
            id_="https://example.org/activities/create-dup-1",
            type_="Create",
            actor="https://example.org/users/finder",
            to=["https://test.example/api/v2/actors/test-actor"],
        )
        event = with_evidence(
            CreateReportReceivedEvent(
                semantic_type=MessageSemantics.CREATE_REPORT,
                activity_id="https://example.org/activities/create-dup-1",
                actor_id="https://example.org/users/finder",
                object_=report,
                activity=activity,
            )
        )
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        # The receiver already holds the report from an earlier delivery.
        dl.save(report)

        with caplog.at_level(logging.WARNING):
            CreateReportReceivedUseCase(dl, event).execute()

        warning_records = [
            r for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert warning_records == [], (
            "No WARNING should be emitted when as_VulnerabilityReport is "
            f"already stored; got: {[r.message for r in warning_records]}"
        )


class TestCreateReportDisposition:
    @pytest.mark.spec("HP-01-003")
    def test_store_failure_raises(self, make_payload, monkeypatch):
        """Every CreateReportReceivedBT failure is a local storage fault (#2255).

        The tree only stores the report and the activity, so its failure says
        nothing about the sender's message and must not read as a refusal.
        """
        import py_trees

        from vultron.core.behaviors.report import received_report_trees
        from vultron.errors import VultronBTInternalError

        monkeypatch.setattr(
            received_report_trees,
            "create_report_received_tree",
            lambda request: py_trees.behaviours.Failure(name="StoreFailed"),
        )
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        report = as_VulnerabilityReport(name="TEST-004", content="x")
        event = make_payload(
            as_Create(actor="https://example.org/users/tester", object_=report)
        )
        with pytest.raises(
            VultronBTInternalError, match="CreateReportReceivedBT"
        ):
            CreateReportReceivedUseCase(dl, event).execute()
