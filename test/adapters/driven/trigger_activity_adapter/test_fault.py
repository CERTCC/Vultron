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

import json
from typing import Any

import pytest

from test.support.objects import authored_at
from test.support.signing import resigned, signed_body
from vultron.adapters.outbox_sealed_body import (
    dump_outbound_body,
    is_sealed,
    sealed_body_id,
)
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
)
from vultron.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.examples.status import (
    add_fix_readiness_to_participant,
)

_ACTOR = "https://example.org/actors/coordinator"
#: The actor whose store the adapter writes to (SIG-05-004).
STORE_OWNER = _ACTOR
_SENDER = "https://example.org/actors/vendor"
_FAILED_ACTIVITY = "https://example.org/activities/act-001"


class TestEmitProcessingFault:
    @pytest.mark.spec("SIG-01-001")
    def test_a_fault_that_cannot_be_signed_leaves_nothing_behind(
        self, adapter, dl, monkeypatch
    ):
        """Store, seal and queue are one transaction, so all roll back."""
        from vultron.adapters import outbox_sealed_body
        from vultron.wire.as2.errors import VultronUnsignableJsonError

        def _refuse(_activity: Any, _owner_id: str) -> str:
            raise VultronUnsignableJsonError("value cannot be canonicalized")

        monkeypatch.setattr(
            outbox_sealed_body, "signed_outbound_body", _refuse
        )
        fault_id = derived_activity_id(
            "processing-fault",
            _ACTOR,
            _FAILED_ACTIVITY,
            VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
        )

        with pytest.raises(VultronUnsignableJsonError):
            adapter.emit_processing_fault(
                actor=_ACTOR,
                failed_activity_id=_FAILED_ACTIVITY,
                failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
                to=[_SENDER],
                at=authored_at(),
            )

        assert dl.read(fault_id) is None
        assert not is_sealed(dl, fault_id)
        assert dl.outbox_list() == []

    def test_returns_activity_id(self, adapter, dl):
        activity_id = adapter.emit_processing_fault(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
            at=authored_at(),
        )

        assert activity_id
        assert isinstance(activity_id, str)

    def test_persists_activity(self, adapter, dl):
        activity_id = adapter.emit_processing_fault(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
            at=authored_at(),
        )

        assert dl.read(activity_id) is not None

    def test_queues_activity_in_outbox(self, adapter, dl):
        activity_id = adapter.emit_processing_fault(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
            at=authored_at(),
        )

        assert activity_id in dl.outbox_list()

    def test_case_id_is_optional(self, adapter, dl):
        activity_id = adapter.emit_processing_fault(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
            case_id="https://example.org/cases/case-001",
            at=authored_at(),
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
        first = adapter.emit_processing_fault(**kwargs, at=authored_at())
        second = adapter.emit_processing_fault(**kwargs, at=authored_at())

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
        first = adapter.emit_processing_fault(**kwargs, at=authored_at())
        assert dl.outbox_pop() is not None  # the drain took it

        adapter.emit_processing_fault(**kwargs, at=authored_at())
        adapter.emit_processing_fault(**kwargs, at=authored_at())

        # Delivered and never-queued look alike, so it is queued again under
        # the same id (the receiver deduplicates) - once, not per redelivery.
        assert dl.outbox_list() == [first]

    @pytest.mark.spec("ID-04-005")
    def test_a_fault_stored_but_not_sealed_is_sealed_and_queued(
        self, adapter, dl
    ):
        kwargs = dict(
            actor=_ACTOR,
            failed_activity_id=_FAILED_ACTIVITY,
            failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
            to=[_SENDER],
        )
        first = adapter.emit_processing_fault(**kwargs, at=authored_at())
        # Simulate a crash between the create and the seal.
        dl.outbox_pop()
        dl.delete("SealedOutboundBody", sealed_body_id(first))
        assert not is_sealed(dl, first)

        second = adapter.emit_processing_fault(**kwargs, at=authored_at())

        assert second == first
        assert is_sealed(dl, first)
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
                at=authored_at(),
            )
            for n in range(2)
        }

        assert len(ids) == 2
        assert set(dl.outbox_list()) == ids


class TestRefusalNotice:
    """The CASE_MANAGER's refusal notice (CLP-05-001)."""

    @staticmethod
    def _refused() -> dict[str, Any]:
        # The refused activity as its sender delivered it, signed
        # (SIG-01-001).
        return signed_body(
            json.loads(dump_outbound_body(add_fix_readiness_to_participant()))
        )

    @pytest.mark.spec("CLP-05-001")
    @pytest.mark.spec("ID-04-004")
    def test_id_is_derived_from_the_case_manager_and_the_refused_activity(
        self, adapter, dl
    ):
        refused = self._refused()
        kwargs = dict(
            case_id="https://example.org/cases/case-001",
            actor=_ACTOR,
            refused_activity=refused,
            asserter=_SENDER,
            reason="refused",
        )

        first, _ = adapter.refusal_notice(**kwargs, at=authored_at())
        second, _ = adapter.refusal_notice(**kwargs, at=authored_at())

        assert (
            first
            == second
            == derived_activity_id("refusal-notice", _ACTOR, refused["id"])
        )
        assert is_sealed(dl, first)

    def test_a_refused_activity_with_no_id_is_refused(self, adapter):
        refused = resigned(self._refused(), alter=lambda b: b.pop("id"))

        with pytest.raises(VultronActivityConstructionError):
            adapter.refusal_notice(
                case_id=None,
                actor=_ACTOR,
                refused_activity=refused,
                asserter=_SENDER,
                reason="refused",
                at=authored_at(),
            )
