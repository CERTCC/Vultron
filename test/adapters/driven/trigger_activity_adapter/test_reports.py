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

"""Unit tests for TriggerActivityAdapter report-domain methods."""

import json

import pytest

from vultron.core.models.offer_record import VultronOfferRecord
from vultron.errors import VultronAlreadyExistsError
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_ACTOR = "https://example.org/actors/reporter"
_COORDINATOR = "https://example.org/actors/coordinator"
_CASE_ID = "https://example.org/cases/case-001"


def _make_report(dl) -> as_VulnerabilityReport:
    report = as_VulnerabilityReport(name="CVE-2025-001", content="PoC details")
    dl.create(report)
    return report


def _make_offer(adapter, dl):
    report = _make_report(dl)
    offer_id, _ = adapter.submit_report(
        report_id=report.id_,
        actor=_ACTOR,
        to=_COORDINATOR,
        target=_CASE_ID,
    )
    return offer_id


class TestSubmitReport:
    def test_returns_id_and_dict(self, adapter, dl):
        report = _make_report(dl)

        offer_id, offer_dict = adapter.submit_report(
            report_id=report.id_,
            actor=_ACTOR,
            to=_COORDINATOR,
            target=_CASE_ID,
        )

        assert offer_id
        assert isinstance(offer_dict, str)
        assert "id" in json.loads(offer_dict)

    def test_persists_offer_activity(self, adapter, dl):
        report = _make_report(dl)

        offer_id, _ = adapter.submit_report(
            report_id=report.id_,
            actor=_ACTOR,
            to=_COORDINATOR,
            target=_CASE_ID,
        )

        assert dl.read(offer_id) is not None

    def test_persists_offer_record(self, adapter, dl):
        report = _make_report(dl)

        offer_id, _ = adapter.submit_report(
            report_id=report.id_,
            actor=_ACTOR,
            to=_COORDINATOR,
            target=_CASE_ID,
        )

        record_id = VultronOfferRecord.build_id(offer_id)
        record = dl.read(record_id)
        assert record is not None
        assert isinstance(record, VultronOfferRecord)
        assert record.offer_id == offer_id
        assert record.report_id == report.id_
        assert record.offer_actor_id == _ACTOR
        assert _COORDINATOR in record.offer_to

    def test_compensating_delete_on_offer_record_failure(self, adapter, dl):
        """Offer activity is rolled back when VultronOfferRecord creation fails."""
        report = _make_report(dl)

        original_create = dl.create

        def failing_create(obj):
            if isinstance(obj, VultronOfferRecord):
                raise RuntimeError("simulated DB failure")  # noqa: TRY004  # ruff-baseline #3353
            return original_create(obj)

        dl.create = failing_create

        with pytest.raises(RuntimeError, match="simulated DB failure"):
            adapter.submit_report(
                report_id=report.id_,
                actor=_ACTOR,
                to=_COORDINATOR,
                target=_CASE_ID,
            )

        # The Offer activity must have been rolled back — list_objects("Offer")
        # should return no entries after the compensating delete.
        activities = list(dl.list_objects("Offer"))
        assert len(activities) == 0, (
            "Offer activity should have been deleted by compensating rollback"
        )

    def test_no_compensating_delete_on_duplicate_offer_record(
        self, adapter, dl
    ):
        """A duplicate offer record does not trigger a compensating delete.

        The double raises the exception ``crud.create`` actually raises for a
        duplicate.  It used to be a bare ``ValueError``, which the idempotent
        guard caught — but so was every *other* fault from that call, so a real
        projection failure was swallowed as "already exists" too.  The guard now
        matches ``VultronAlreadyExistsError`` specifically; simulating a
        duplicate with a bare ``ValueError`` would no longer reach it, and this
        test would be asserting against a fault that never happens in production.
        """
        report = _make_report(dl)

        original_create = dl.create

        def offer_record_already_exists(obj):
            if isinstance(obj, VultronOfferRecord):
                raise VultronAlreadyExistsError("already exists")
            return original_create(obj)

        dl.create = offer_record_already_exists

        # Call succeeds (the duplicate is swallowed by the idempotent guard).
        offer_id, _ = adapter.submit_report(
            report_id=report.id_,
            actor=_ACTOR,
            to=_COORDINATOR,
            target=_CASE_ID,
        )

        # The Offer activity MUST still be present — no compensating delete.
        assert dl.read(offer_id) is not None

    def test_original_error_raised_when_compensating_delete_also_fails(
        self, adapter, dl
    ):
        """Original RuntimeError propagates even when compensating delete raises."""
        report = _make_report(dl)

        original_create = dl.create
        original_delete = dl.delete

        def failing_create(obj):
            if isinstance(obj, VultronOfferRecord):
                raise RuntimeError("simulated DB failure")  # noqa: TRY004  # ruff-baseline #3353
            return original_create(obj)

        def failing_delete(table, id_):
            raise OSError("delete also broken")

        dl.create = failing_create
        dl.delete = failing_delete

        with pytest.raises(RuntimeError, match="simulated DB failure"):
            adapter.submit_report(
                report_id=report.id_,
                actor=_ACTOR,
                to=_COORDINATOR,
                target=_CASE_ID,
            )

        dl.delete = original_delete


class TestCloseReport:
    def test_returns_id_and_dict(self, adapter, dl):
        offer_id = _make_offer(adapter, dl)

        reject_id, reject_dict = adapter.close_report(
            offer_id=offer_id,
            report_id="unused",
            actor=_COORDINATOR,
            to=[_ACTOR],
        )

        assert reject_id
        assert isinstance(reject_dict, str)

    def test_persists_reject_activity(self, adapter, dl):
        offer_id = _make_offer(adapter, dl)

        reject_id, _ = adapter.close_report(
            offer_id=offer_id,
            report_id="unused",
            actor=_COORDINATOR,
        )

        assert dl.read(reject_id) is not None


class TestInvalidateReport:
    def test_returns_id_and_dict(self, adapter, dl):
        offer_id = _make_offer(adapter, dl)

        activity_id, activity_dict = adapter.invalidate_report(
            offer_id=offer_id,
            actor=_COORDINATOR,
            to=[_ACTOR],
        )

        assert activity_id
        assert isinstance(activity_dict, str)

    def test_persists_tentative_reject_activity(self, adapter, dl):
        offer_id = _make_offer(adapter, dl)

        activity_id, _ = adapter.invalidate_report(
            offer_id=offer_id,
            actor=_COORDINATOR,
        )

        assert dl.read(activity_id) is not None


class TestSubmitReportProposedEmbargo:
    """``proposed_embargo_id`` names the Reporter's stored terms (EP-04-004)."""

    def _terms(self, dl, report):
        from vultron.core.models._helpers import days_from_now_utc
        from vultron.core.models.embargo_event import EmbargoEvent

        terms = EmbargoEvent(
            context=report.id_, end_time=days_from_now_utc(10)
        )
        dl.create(terms)
        return terms

    def test_the_offer_carries_the_stored_terms(self, adapter, dl):
        report = _make_report(dl)
        terms = self._terms(dl, report)

        _, offer_json = adapter.submit_report(
            report_id=report.id_,
            actor=_ACTOR,
            to=_COORDINATOR,
            target=_CASE_ID,
            proposed_embargo_id=terms.id_,
        )

        proposed = json.loads(offer_json)["proposedEmbargo"]
        assert proposed["id"] == terms.id_
        assert proposed["context"] == report.id_

    def test_no_id_means_no_terms(self, adapter, dl):
        report = _make_report(dl)

        _, offer_json = adapter.submit_report(
            report_id=report.id_,
            actor=_ACTOR,
            to=_COORDINATOR,
            target=_CASE_ID,
        )

        assert "proposedEmbargo" not in json.loads(offer_json)

    def test_an_unknown_id_is_a_fault_not_a_dropped_proposal(
        self, adapter, dl
    ):
        from vultron.errors import VultronNotFoundError

        report = _make_report(dl)

        with pytest.raises(VultronNotFoundError):
            adapter.submit_report(
                report_id=report.id_,
                actor=_ACTOR,
                to=_COORDINATOR,
                target=_CASE_ID,
                proposed_embargo_id="urn:uuid:00000000-0000-0000-0000-000000000000",
            )
        assert list(dl.list_objects("Offer")) == []

    def test_terms_about_another_subject_are_refused(self, adapter, dl):
        """The factory's EP-04-009 rule holds through the adapter."""
        from vultron.core.models._helpers import days_from_now_utc
        from vultron.core.models.embargo_event import EmbargoEvent
        from vultron.errors import VultronActivityConstructionError

        report = _make_report(dl)
        foreign = EmbargoEvent(
            context="https://example.org/reports/someone-elses",
            end_time=days_from_now_utc(10),
        )
        dl.create(foreign)

        with pytest.raises(VultronActivityConstructionError):
            adapter.submit_report(
                report_id=report.id_,
                actor=_ACTOR,
                to=_COORDINATOR,
                target=_CASE_ID,
                proposed_embargo_id=foreign.id_,
            )
