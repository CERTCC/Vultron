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
Unit tests for SvcCreateCaseUseCase trigger use case.

Tests exercise the use case's execute() path against an in-memory DataLayer,
verifying state mutation, outbox effect, and error handling.
Spec: specs/triggerable-behaviors.yaml TRIG-09.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.core.use_cases.triggers.case import SvcCreateCaseUseCase
from vultron.core.use_cases.triggers.requests import CreateCaseTriggerRequest
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
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


class TestSvcCreateCaseUseCase:
    """SvcCreateCaseUseCase creates a VulnerabilityCase and queues activity."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up actor and in-memory DataLayer."""
        self.actor, self.dl = _make_actor_dl("Vendor Co")
        yield
        self.dl.clear_all()
        reset_datalayer(self.actor.id_)

    def test_create_case_happy_path_without_report(self):
        """SvcCreateCaseUseCase creates a case and queues CreateCaseActivity."""
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Vulnerability Case",
            content="A test case for a vulnerability",
        )
        result = SvcCreateCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Verify case was persisted
        case_id = None
        for obj in self.dl.list_objects("VulnerabilityCase"):
            if getattr(obj, "name", "") == "Test Vulnerability Case":
                case_id = obj.id_
                break

        assert case_id is not None, "Case should have been created"

        # Verify case attributes
        case = self.dl.read(case_id)
        assert case is not None
        assert getattr(case, "name", "") == "Test Vulnerability Case"
        assert (
            getattr(case, "content", "") == "A test case for a vulnerability"
        )
        assert getattr(case, "attributed_to", "") == self.actor.id_

        # Verify activity was queued in outbox
        assert _activity_in_outbox(
            self.actor, self.dl
        ), "Activity should be queued in actor's outbox"

        # Verify result contains activity
        assert "activity" in result, "Result should contain 'activity' key"
        activity_dict = result["activity"]
        assert activity_dict is not None
        assert activity_dict.get("type") == "Create"

    def test_create_case_with_linked_report(self):
        """SvcCreateCaseUseCase links a report to the new case."""
        # Create a report first
        report = VulnerabilityReport(
            name="Test Vulnerability Report",
            content="A test report",
        )
        self.dl.create(report)

        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case With Report",
            content="Case linked to report",
            report_id=report.id_,
        )
        result = SvcCreateCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Verify case was created
        case_id = None
        for obj in self.dl.list_objects("VulnerabilityCase"):
            if getattr(obj, "name", "") == "Test Case With Report":
                case_id = obj.id_
                break

        assert case_id is not None, "Case should have been created"

        # Verify report is linked
        case = self.dl.read(case_id)
        vul_reports = getattr(case, "vulnerability_reports", [])
        assert (
            report.id_ in vul_reports
        ), f"Report {report.id_} should be linked to case"

        # Verify activity queued
        assert _activity_in_outbox(self.actor, self.dl)
        assert "activity" in result

    def test_create_case_raises_when_actor_not_found(self):
        """SvcCreateCaseUseCase raises VultronNotFoundError when actor not found."""
        request = CreateCaseTriggerRequest(
            actor_id="https://example.org/nonexistent",
            name="Test Case",
            content="Test content",
        )
        with pytest.raises(VultronNotFoundError, match="Actor"):
            SvcCreateCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_create_case_raises_when_report_not_found(self):
        """SvcCreateCaseUseCase raises VultronNotFoundError when report_id not found."""
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case",
            content="Test content",
            report_id="https://example.org/nonexistent",
        )
        with pytest.raises(VultronNotFoundError, match="VulnerabilityReport"):
            SvcCreateCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_create_case_raises_when_report_wrong_type(self):
        """SvcCreateCaseUseCase raises VultronValidationError when report_id is
        not a VulnerabilityReport."""
        # Create a wrong type object (VulnerabilityCase instead)
        case = VulnerabilityCase(name="Not a Report")
        self.dl.create(case)

        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case",
            content="Test content",
            report_id=case.id_,
        )
        with pytest.raises(
            VultronValidationError, match="not a VulnerabilityReport"
        ):
            SvcCreateCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_create_case_activity_queued_in_delivery_queue(self):
        """SvcCreateCaseUseCase queues activity in delivery queue for outbox_handler."""
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case",
            content="Test content",
        )
        result = SvcCreateCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Verify activity ID is in result
        assert "activity" in result
        activity_dict = result["activity"]
        activity_id = activity_dict.get("id")
        assert activity_id is not None

        # Verify activity was queued in outbox
        outbox_activity_id = _get_outbox_activity_id(self.actor, self.dl)
        assert (
            outbox_activity_id == activity_id
        ), "Activity ID in outbox should match returned activity ID"
