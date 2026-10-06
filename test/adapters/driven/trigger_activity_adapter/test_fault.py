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

"""Unit tests for _FaultMixin.emit_processing_fault() in TriggerActivityAdapter."""

import pytest

from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
)

_ACTOR = "https://example.org/actors/coordinator"
_SENDER = "https://example.org/actors/vendor"
_FAILED_ACTIVITY = "https://example.org/activities/act-001"


class TestEmitProcessingFault:
    def test_returns_activity_id(self, adapter, dl):
        activity_id = adapter.emit_processing_fault(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
        )

        assert activity_id
        assert isinstance(activity_id, str)

    def test_persists_activity(self, adapter, dl):
        activity_id = adapter.emit_processing_fault(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
        )

        assert dl.read(activity_id) is not None

    def test_queues_activity_in_outbox(self, adapter, dl):
        activity_id = adapter.emit_processing_fault(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
        )

        assert activity_id in dl.outbox_list()

    def test_case_id_is_optional(self, adapter, dl):
        activity_id = adapter.emit_processing_fault(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
            case_id="https://example.org/cases/case-001",
        )

        assert activity_id in dl.outbox_list()

    @pytest.mark.spec("ID-04-004")
    def test_same_failed_activity_is_faulted_once(self, adapter, dl):
        kwargs = dict(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
        )
        first = adapter.emit_processing_fault(**kwargs)
        second = adapter.emit_processing_fault(**kwargs)

        assert second == first
        assert dl.outbox_list() == [first]

    @pytest.mark.spec("ID-04-004")
    def test_a_delivered_fault_is_requeued_under_the_same_id(
        self, adapter, dl
    ):
        kwargs = dict(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
        )
        first = adapter.emit_processing_fault(**kwargs)
        assert dl.outbox_pop() is not None  # the drain took it

        adapter.emit_processing_fault(**kwargs)
        adapter.emit_processing_fault(**kwargs)

        # Delivered and never-queued look alike, so it is queued again under
        # the same id (the receiver deduplicates) - once, not per redelivery.
        assert dl.outbox_list() == [first]

    def test_different_failed_activities_get_different_faults(
        self, adapter, dl
    ):
        ids = {
            adapter.emit_processing_fault(
                actor=_ACTOR,
                failed_activity_id=f"{_FAILED_ACTIVITY}-{n}",
                failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
                to=[_SENDER],
            )
            for n in range(2)
        }

        assert len(ids) == 2
        assert set(dl.outbox_list()) == ids
