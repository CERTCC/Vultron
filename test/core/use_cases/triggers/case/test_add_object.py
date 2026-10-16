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
Spec: specs/triggerable-behaviors.yaml TRIG-10-001; the Add goes to the
CASE_MANAGER alone (PCR-08-005) and refused types queue nothing (TRIG-10-001).
"""

from unittest.mock import patch

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
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.pending_assertion import (
    _reset_stores,
    get_pending_assertion_store,
)
from vultron.core.use_cases.triggers.case import SvcAddObjectToCaseUseCase
from vultron.core.use_cases.triggers.requests import (
    AddObjectToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.base.objects.object_types import (
    as_Article,
    as_Note,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
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


class TestSvcAddObjectToCaseUseCase:
    """SvcAddObjectToCaseUseCase adds an object to a case and queues activity."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up actor and in-memory DataLayer."""
        self.actor, self.dl = _make_actor_dl("Vendor Co")
        self.case = make_case_with_case_manager(self.dl)
        yield
        self.dl.clear_all()
        reset_datalayer(self.actor.id_)
        _reset_stores()

    def _execute(self, object_id: str, case_id: str | None = None):
        request = AddObjectToCaseTriggerRequest(
            actor_id=self.actor.id_,
            case_id=case_id or self.case.id_,
            object_id=object_id,
        )
        return SvcAddObjectToCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

    def test_add_object_to_case_happy_path(self):
        """SvcAddObjectToCaseUseCase adds an existing object to a case."""
        # Create a report to add
        report = as_VulnerabilityReport(
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
        assert _activity_in_outbox(self.actor, self.dl), (
            "Activity should be queued in actor's outbox"
        )

        # Verify result contains activity
        activity_dict = activity_of(result)
        assert activity_dict.get("type") == "Add"

    @pytest.mark.spec("PCR-08-005")
    def test_add_object_to_case_addresses_case_manager_alone(self):
        """The queued Add goes to the CASE_MANAGER and no one else."""
        report = as_VulnerabilityReport(name="To Report", content="content")
        self.dl.create(report)

        result = self._execute(report.id_)

        activity = self.dl.read(activity_of(result)["id"])
        assert activity is not None
        assert getattr(activity, "to", None) == [CASE_MANAGER_ID]

    @pytest.mark.spec("PCR-08-016")
    def test_add_object_to_case_without_case_manager_queues_nothing(self):
        """A case with no CASE_MANAGER fails fast with nothing queued."""
        case = as_VulnerabilityCase(name="No Manager")
        self.dl.create(case)
        report = as_VulnerabilityReport(name="Orphan", content="content")
        self.dl.create(report)

        with pytest.raises(VultronValidationError):
            self._execute(report.id_, case_id=case.id_)

        assert self.dl.outbox_list() == []

    @pytest.mark.spec("SYNC-11-002")
    @pytest.mark.parametrize(
        ("make_object", "semantics"),
        [
            pytest.param(
                lambda: as_VulnerabilityReport(name="R", content="c"),
                MessageSemantics.ADD_REPORT_TO_CASE,
                id="report",
            ),
            pytest.param(
                lambda: as_Note(name="N", content="c"),
                MessageSemantics.ADD_NOTE_TO_CASE,
                id="note",
            ),
        ],
    )
    def test_add_object_to_case_records_pending_assertion(
        self, make_object, semantics
    ):
        """The Add is pending under the event type the CASE_MANAGER commits."""
        obj = make_object()
        self.dl.create(obj)

        result = self._execute(obj.id_)

        store = get_pending_assertion_store(self.actor.id_)
        assert store.is_suppressed(
            self.case.id_, semantics.value, activity_of(result)["id"]
        )

    @pytest.mark.spec("SYNC-11-002")
    def test_repeat_while_pending_is_suppressed(self):
        """Adding the same object again while the first Add is pending queues
        nothing and reports no activity."""
        report = as_VulnerabilityReport(name="Twice", content="c")
        self.dl.create(report)
        self._execute(report.id_)
        queued = len(self.dl.outbox_list())

        repeat = self._execute(report.id_)

        assert repeat.activity is None
        assert len(self.dl.outbox_list()) == queued

    @pytest.mark.spec("SYNC-11-003")
    def test_repeat_after_commit_is_sent(self):
        """Once the announced commit clears the assertion, the same object
        may be added again."""
        report = as_VulnerabilityReport(name="Again", content="c")
        self.dl.create(report)
        first = self._execute(report.id_)
        get_pending_assertion_store(self.actor.id_).clear(
            self.case.id_,
            MessageSemantics.ADD_REPORT_TO_CASE.value,
            activity_of(first)["id"],
        )

        second = self._execute(report.id_)

        assert second.activity is not None
        assert len(self.dl.outbox_list()) == 2

    @pytest.mark.spec("SYNC-11-002")
    def test_pending_add_does_not_suppress_another_object(self):
        """A pending Add of one object does not hold back another's."""
        first = as_VulnerabilityReport(name="One", content="c")
        second = as_VulnerabilityReport(name="Two", content="c")
        self.dl.create(first)
        self.dl.create(second)
        self._execute(first.id_)

        result = self._execute(second.id_)

        assert result.activity is not None

    @pytest.mark.spec("TRIG-10-001")
    @pytest.mark.parametrize(
        "make_object",
        [
            pytest.param(
                lambda case_id: as_Article(name="A", content="no pattern"),
                id="no-add-pattern",
            ),
            pytest.param(
                lambda case_id: as_EmbargoEvent(
                    context=case_id, end_time=days_from_now_utc(45)
                ),
                id="own-flow-embargo",
            ),
            pytest.param(
                lambda case_id: as_CaseParticipant(
                    attributed_to="https://example.org/actors/other",
                    context=case_id,
                ),
                id="own-flow-participant",
            ),
            pytest.param(
                lambda case_id: as_CaseStatus(context=case_id),
                id="own-flow-case-status",
            ),
        ],
    )
    def test_add_object_to_case_refuses_type_and_queues_nothing(
        self, make_object
    ):
        """A type no receiver routes as Add-to-case, or one with its own
        flow, is refused before anything is built or queued."""
        obj = make_object(self.case.id_)
        self.dl.create(obj)
        stored_before = len(self.dl.outbox_list())

        with pytest.raises(VultronValidationError):
            self._execute(obj.id_)

        assert len(self.dl.outbox_list()) == stored_before

    @pytest.mark.spec("TRIG-10-001")
    def test_object_with_no_wire_form_is_refused_and_queues_nothing(self):
        """A stored object with no AS2 form (a ``CoreRecord`` bookkeeping
        type) is the caller's bad request: refused with 422, never a 500."""
        record = VultronOfferRecord(
            id_="urn:test:offer-record-add-object",
            offer_id="urn:test:offer-1",
            report_id="urn:test:report-1",
            offer_actor_id=self.actor.id_,
        )
        real_read = self.dl.read

        def _read(object_id, *args, **kwargs):
            if object_id == record.id_:
                return record
            return real_read(object_id, *args, **kwargs)

        with patch.object(self.dl, "read", side_effect=_read):
            with pytest.raises(
                VultronValidationError, match="is not an AS2 object"
            ):
                self._execute(record.id_)

        assert self.dl.outbox_list() == []

    @pytest.mark.spec("SYNC-11-004")
    def test_case_manager_records_no_pending_assertion(self):
        """The CASE_MANAGER adding an object to its own case keeps no pending
        assertion, so a repeat is not suppressed (SYNC-11-004)."""
        case = make_case_with_case_manager(
            self.dl, case_manager_id=self.actor.id_
        )
        report = as_VulnerabilityReport(name="Own", content="c")
        self.dl.create(report)

        first = self._execute(report.id_, case_id=case.id_)
        repeat = self._execute(report.id_, case_id=case.id_)

        assert first.activity is not None
        assert len(get_pending_assertion_store(self.actor.id_)) == 0
        assert repeat.activity is not None

    def test_add_object_to_case_raises_when_actor_not_found(self):
        """SvcAddObjectToCaseUseCase raises VultronNotFoundError when actor
        not found."""
        report = as_VulnerabilityReport(
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
        report = as_VulnerabilityReport(
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
        report = as_VulnerabilityReport(
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
        activity_dict = activity_of(result)
        activity_id = activity_dict.get("id")
        assert activity_id is not None

        # Verify activity was queued in outbox
        outbox_activity_id = _get_outbox_activity_id(self.actor, self.dl)
        assert outbox_activity_id == activity_id, (
            "Activity ID in outbox should match returned activity ID"
        )

    def test_add_multiple_objects_to_case(self):
        """SvcAddObjectToCaseUseCase can add multiple objects (called multiple times)."""
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
        items = self.dl.outbox_list()
        assert len(items) == 2, "Both activities should be queued"

        # Verify result contains activities
        assert result1.activity is not None
        assert result2.activity is not None
