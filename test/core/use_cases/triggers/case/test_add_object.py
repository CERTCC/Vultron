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
Unit tests for SvcAddObjectToCaseUseCase trigger use case.

Tests exercise the use case's execute() path against an in-memory DataLayer,
verifying state mutation, outbox effect, and error handling.
Spec: specs/triggerable-behaviors.yaml TRIG-10-001.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.errors import VultronNotFoundError
from vultron.core.use_cases.triggers.case import SvcAddObjectToCaseUseCase
from vultron.core.use_cases.triggers.requests import (
    AddObjectToCaseTriggerRequest,
)
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
    actor_obj = dl.read(actor.id_)
    if actor_obj is None:
        return False
    outbox = getattr(actor_obj, "outbox", None)
    if outbox is None:
        return False
    items = getattr(outbox, "items", [])
    return len(items) > 0


def _get_outbox_activity_id(actor, dl: SqliteDataLayer) -> str | None:
    """Return the first activity ID in actor's outbox."""
    actor_obj = dl.read(actor.id_)
    if actor_obj is None:
        return None
    outbox = getattr(actor_obj, "outbox", None)
    if outbox is None:
        return None
    items = getattr(outbox, "items", [])
    if not items:
        return None
    first_item = items[0]
    return first_item if isinstance(first_item, str) else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSvcAddObjectToCaseUseCase:
    """SvcAddObjectToCaseUseCase adds an object to a case and queues activity."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up actor and in-memory DataLayer."""
        self.actor, self.dl = _make_actor_dl("Vendor Co")
        # Create a case for testing
        self.case = VulnerabilityCase(name="Test Case")
        self.dl.create(self.case)
        yield
        self.dl.clear_all()
        reset_datalayer(self.actor.id_)

    def test_add_object_to_case_happy_path(self):
        """SvcAddObjectToCaseUseCase adds an existing object to a case."""
        # Create a report to add
        report = VulnerabilityReport(
            name="Test Report",
            content="Test report content",
        )
        self.dl.create(report)

        request = AddObjectToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            object_id=report.id_,
        )
        result = SvcAddObjectToCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Verify activity was queued in outbox
        assert _activity_in_outbox(
            self.actor, self.dl
        ), "Activity should be queued in actor's outbox"

        # Verify result contains activity
        assert "activity" in result, "Result should contain 'activity' key"
        activity_dict = result["activity"]
        assert activity_dict is not None
        assert activity_dict.get("type") == "Add"

    def test_add_object_to_case_raises_when_actor_not_found(self):
        """SvcAddObjectToCaseUseCase raises VultronNotFoundError when actor
        not found."""
        report = VulnerabilityReport(
            name="Test Report",
            content="Test report content",
        )
        self.dl.create(report)

        request = AddObjectToCaseTriggerRequest(
            actor_id="https://example.org/nonexistent",
            case_id=self.case.id_,
            object_id=report.id_,
        )
        with pytest.raises(VultronNotFoundError, match="Actor"):
            SvcAddObjectToCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_add_object_to_case_raises_when_case_not_found(self):
        """SvcAddObjectToCaseUseCase raises VultronNotFoundError when case
        not found."""
        report = VulnerabilityReport(
            name="Test Report",
            content="Test report content",
        )
        self.dl.create(report)

        request = AddObjectToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id="https://example.org/nonexistent",
            object_id=report.id_,
        )
        with pytest.raises(VultronNotFoundError, match="VulnerabilityCase"):
            SvcAddObjectToCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_add_object_to_case_raises_when_object_not_found(self):
        """SvcAddObjectToCaseUseCase raises VultronNotFoundError when object_id
        not found."""
        request = AddObjectToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            object_id="https://example.org/nonexistent",
        )
        with pytest.raises(VultronNotFoundError, match="AS2Object"):
            SvcAddObjectToCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_add_object_to_case_activity_queued_in_delivery_queue(self):
        """SvcAddObjectToCaseUseCase queues activity in delivery queue for
        outbox_handler."""
        report = VulnerabilityReport(
            name="Test Report",
            content="Test report content",
        )
        self.dl.create(report)

        request = AddObjectToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            object_id=report.id_,
        )
        result = SvcAddObjectToCaseUseCase(
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

    def test_add_multiple_objects_to_case(self):
        """SvcAddObjectToCaseUseCase can add multiple objects (called multiple times)."""
        report1 = VulnerabilityReport(
            name="Test Report 1",
            content="Test report content 1",
        )
        report2 = VulnerabilityReport(
            name="Test Report 2",
            content="Test report content 2",
        )
        self.dl.create(report1)
        self.dl.create(report2)

        # Add first object
        request1 = AddObjectToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            object_id=report1.id_,
        )
        result1 = SvcAddObjectToCaseUseCase(
            self.dl,
            request1,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Add second object
        request2 = AddObjectToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            object_id=report2.id_,
        )
        result2 = SvcAddObjectToCaseUseCase(
            self.dl,
            request2,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Verify both activities were queued
        actor_obj = self.dl.read(self.actor.id_)
        outbox = getattr(actor_obj, "outbox", None)
        items = getattr(outbox, "items", [])
        assert len(items) == 2, "Both activities should be queued"

        # Verify result contains activities
        assert "activity" in result1
        assert "activity" in result2
