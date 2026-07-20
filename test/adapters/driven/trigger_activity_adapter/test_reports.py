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

import pytest

from vultron.core.models.offer_record import VultronOfferRecord
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
        assert isinstance(offer_dict, dict)
        assert "id" in offer_dict

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
                raise RuntimeError("simulated DB failure")
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
        assert (
            len(activities) == 0
        ), "Offer activity should have been deleted by compensating rollback"

    def test_no_compensating_delete_on_duplicate_offer_record(
        self, adapter, dl
    ):
        """ValueError on offer record create does not trigger compensating delete."""
        report = _make_report(dl)

        original_create = dl.create

        def offer_record_raises_value_error(obj):
            if isinstance(obj, VultronOfferRecord):
                raise ValueError("already exists")
            return original_create(obj)

        dl.create = offer_record_raises_value_error

        # Call succeeds (ValueError is swallowed by the idempotent guard).
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
                raise RuntimeError("simulated DB failure")
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
        assert isinstance(reject_dict, dict)

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
        assert isinstance(activity_dict, dict)

    def test_persists_tentative_reject_activity(self, adapter, dl):
        offer_id = _make_offer(adapter, dl)

        activity_id, _ = adapter.invalidate_report(
            offer_id=offer_id,
            actor=_COORDINATOR,
        )

        assert dl.read(activity_id) is not None
