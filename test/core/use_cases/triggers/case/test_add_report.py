#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Unit tests for SvcAddReportToCaseUseCase trigger use case.

Tests exercise the use case's execute() path against an in-memory DataLayer,
verifying state mutation, outbox effect, and error handling.
Spec: specs/triggerable-behaviors.yaml TRIG-10-002.
"""

import pytest

from test.support.case_manager import (
    CASE_MANAGER_ID,
    make_case_with_case_manager,
)
from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import (
    _reset_stores,
    get_pending_assertion_store,
)
from vultron.core.use_cases.triggers.case import (
    SvcAddObjectToCaseUseCase,
    SvcAddReportToCaseUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AddReportToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_actor_dl(actor_name: str):
    """Create an as_Service actor and a matching per-actor SqliteDataLayer."""
    actor = as_Service(name=actor_name)
    actor_id = actor.id_
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _activity_in_outbox(actor, dl: SqliteDataLayer) -> bool:
    """Check if actor's outbox has any items queued."""
    return len(dl.outbox_list()) > 0


def _get_outbox_activity_id(actor, dl: SqliteDataLayer) -> str | None:
    """Return the first activity ID in actor's outbox."""
    items = dl.outbox_list()
    return items[0] if items else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSvcAddReportToCaseUseCase:
    """SvcAddReportToCaseUseCase adds a report to a case and queues activity."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up actor and in-memory DataLayer."""
        self.actor, self.dl = _make_actor_dl("Vendor Co")
        self.case = make_case_with_case_manager(self.dl)
        yield
        self.dl.clear_all()
        reset_datalayer(self.actor.id_)
        _reset_stores()

    def _execute(self, report_id: str, case_id: str | None = None):
        request = AddReportToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=case_id or self.case.id_,
            report_id=report_id,
        )
        return SvcAddReportToCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

    def test_add_report_to_case_happy_path(self):
        """SvcAddReportToCaseUseCase adds a report to a case."""
        # Create a report
        report = as_VulnerabilityReport(
            name="Test Report",
            content="Test report content",
        )
        self.dl.create(report)

        request = AddReportToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            report_id=report.id_,
        )
        result = SvcAddReportToCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Verify activity was queued in outbox
        assert _activity_in_outbox(self.actor, self.dl), (
            "Activity should be queued in actor's outbox"
        )

        # Verify result contains activity
        activity_dict = activity_of(result)
        assert activity_dict.get("type") == "Add"

    @pytest.mark.spec("PCR-08-005")
    def test_add_report_to_case_addresses_case_manager_alone(self):
        """The queued Add goes to the CASE_MANAGER and no one else."""
        report = as_VulnerabilityReport(name="To-Field Report", content="c")
        self.dl.create(report)

        result = self._execute(report.id_)

        activity = self.dl.read(activity_of(result)["id"])
        assert activity is not None
        assert getattr(activity, "to", None) == [CASE_MANAGER_ID]

    @pytest.mark.spec("PCR-08-016")
    def test_add_report_to_case_without_case_manager_queues_nothing(self):
        """A case with no CASE_MANAGER fails fast with nothing queued."""
        case = as_VulnerabilityCase(name="No Manager")
        self.dl.create(case)
        report = as_VulnerabilityReport(name="Orphan", content="c")
        self.dl.create(report)

        with pytest.raises(VultronValidationError):
            self._execute(report.id_, case_id=case.id_)

        assert self.dl.outbox_list() == []

    @pytest.mark.spec("SYNC-11-002")
    def test_add_report_to_case_records_pending_assertion(self):
        """The Add is pending under ``add_report_to_case``, the event type the
        CASE_MANAGER commits."""
        report = as_VulnerabilityReport(name="Pending", content="c")
        self.dl.create(report)

        result = self._execute(report.id_)

        store = get_pending_assertion_store(self.actor.id_)
        assert store.is_suppressed(
            self.case.id_,
            MessageSemantics.ADD_REPORT_TO_CASE.value,
            activity_of(result)["id"],
        )

    def test_add_report_to_case_raises_when_report_not_found(self):
        """SvcAddReportToCaseUseCase raises VultronNotFoundError when report
        not found."""
        request = AddReportToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            report_id="https://example.org/nonexistent",
        )
        with pytest.raises(VultronNotFoundError, match="VulnerabilityReport"):
            SvcAddReportToCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_add_report_to_case_raises_when_report_wrong_type(self):
        """SvcAddReportToCaseUseCase raises VultronValidationError when report_id
        is not a VulnerabilityReport."""
        # Create a wrong type object (as_VulnerabilityCase instead)
        case_obj = as_VulnerabilityCase(name="Not a Report")
        self.dl.create(case_obj)

        request = AddReportToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            report_id=case_obj.id_,
        )
        with pytest.raises(
            VultronValidationError, match="not a VulnerabilityReport"
        ):
            SvcAddReportToCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_add_report_to_case_raises_when_case_not_found(self):
        """SvcAddReportToCaseUseCase raises VultronNotFoundError when case
        not found."""
        report = as_VulnerabilityReport(
            name="Test Report",
            content="Test report content",
        )
        self.dl.create(report)

        request = AddReportToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id="https://example.org/nonexistent",
            report_id=report.id_,
        )
        with pytest.raises(VultronNotFoundError, match="VulnerabilityCase"):
            SvcAddReportToCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_add_report_to_case_activity_queued_in_delivery_queue(self):
        """SvcAddReportToCaseUseCase queues activity in delivery queue for
        outbox_handler."""
        report = as_VulnerabilityReport(
            name="Test Report",
            content="Test report content",
        )
        self.dl.create(report)

        request = AddReportToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            report_id=report.id_,
        )
        result = SvcAddReportToCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Verify activity ID is in result
        activity_dict = activity_of(result)
        activity_id = activity_dict.get("id")
        assert activity_id is not None

        # Verify activity was queued in outbox
        outbox_activity_id = _get_outbox_activity_id(self.actor, self.dl)
        assert outbox_activity_id == activity_id, (
            "Activity ID in outbox should match returned activity ID"
        )

    @pytest.mark.spec("TRIG-10-002")
    def test_add_report_to_case_delegates_to_add_object(self):
        """SvcAddReportToCaseUseCase validates report type then delegates to
        SvcAddObjectToCaseUseCase."""
        assert issubclass(SvcAddReportToCaseUseCase, SvcAddObjectToCaseUseCase)
        report = as_VulnerabilityReport(
            name="Test Report",
            content="Test report content",
        )
        self.dl.create(report)

        request = AddReportToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            report_id=report.id_,
        )
        result = SvcAddReportToCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Verify the result structure (should match SvcAddObjectToCaseUseCase result)
        activity_dict = activity_of(result)
        assert activity_dict.get("type") == "Add"

    def test_add_multiple_reports_to_case(self):
        """SvcAddReportToCaseUseCase can add multiple reports (called multiple times)."""
        report1 = as_VulnerabilityReport(
            name="Test Report 1",
            content="Test report content 1",
        )
        report2 = as_VulnerabilityReport(
            name="Test Report 2",
            content="Test report content 2",
        )
        self.dl.create(report1)
        self.dl.create(report2)

        # Add first report
        request1 = AddReportToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            report_id=report1.id_,
        )
        result1 = SvcAddReportToCaseUseCase(
            self.dl,
            request1,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Add second report
        request2 = AddReportToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            report_id=report2.id_,
        )
        result2 = SvcAddReportToCaseUseCase(
            self.dl,
            request2,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Verify both activities were queued
        items = self.dl.outbox_list()
        assert len(items) == 2, "Both activities should be queued"

        # Verify result contains activities
        assert result1.activity is not None
        assert result2.activity is not None
