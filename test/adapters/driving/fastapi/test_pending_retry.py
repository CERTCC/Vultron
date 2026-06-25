#!/usr/bin/env python

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

"""Unit and integration tests for retry_pending_create_case_activities.

Acceptance criteria covered
---------------------------
- AC-1: Retry reads PendingCreateCaseActivity markers and re-sends
  Create(VulnerabilityCase) without re-creating the case or re-sending
  Accept(CaseProposal).
- AC-3: After successful delivery the marker is removed/marked-complete.
- AC-4: Running the retry runner multiple times does not produce duplicate
  Create(VulnerabilityCase) activities or duplicate VulnerabilityCase records.
- AC-5: Integration test covering the full scenario:
  Accept sent → Create fails → marker written → retry runner fires →
  Create(VulnerabilityCase) re-queued → marker removed.

Module under test:
  ``vultron/adapters/driving/fastapi/pending_retry.py``
"""

import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.activity import VultronCreateCaseActivity
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.adapters.driving.fastapi.pending_retry import (
    retry_pending_create_case_activities,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CASE_ACTOR_ID = "https://case-actor.test/actors/svc-001"
_VENDOR_URI = "https://vendor.test/actors/acme"
_PROPOSAL_ID = "https://vendor.test/proposals/p-100"
_CASE_ID = "https://case-actor.test/cases/c-001"
_ACCEPT_ID = "https://case-actor.test/activities/accept-001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dl() -> SqliteDataLayer:
    """Fresh in-memory DataLayer for each test."""
    return SqliteDataLayer("sqlite:///:memory:")


def _build_activity() -> VultronCreateCaseActivity:
    """Return a pre-constructed Create(VulnerabilityCase) activity."""
    return VultronCreateCaseActivity(
        actor=_CASE_ACTOR_ID,
        object_=_CASE_ID,
        context=_ACCEPT_ID,
        to=[_VENDOR_URI],
    )


def _build_marker(
    activity: VultronCreateCaseActivity | None = None,
) -> PendingCreateCaseActivity:
    """Return a PendingCreateCaseActivity marker."""
    act = activity or _build_activity()
    return PendingCreateCaseActivity(
        proposal_id=_PROPOSAL_ID,
        case_actor_id=_CASE_ACTOR_ID,
        vendor_uri=_VENDOR_URI,
        create_activity_payload=act.model_dump(by_alias=True),
    )


# ---------------------------------------------------------------------------
# AC-4: No-op when no markers present
# ---------------------------------------------------------------------------


class TestRetryNoMarkers:
    """retry_pending returns 0 and does nothing when no markers exist."""

    def test_empty_factory_returns_zero(self):
        """Returns 0 when the factory yields no DataLayers."""
        count = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {}
        )
        assert count == 0

    def test_dl_with_no_markers_returns_zero(self, dl):
        """Returns 0 when the DataLayer has no PendingCreateCaseActivity records."""
        count = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )
        assert count == 0


# ---------------------------------------------------------------------------
# AC-1 + AC-3: Happy path — marker present, activity re-queued, marker cleared
# ---------------------------------------------------------------------------


class TestRetryHappyPath:
    """Verify the basic retry flow end-to-end in memory."""

    def test_returns_one_for_single_marker(self, dl):
        """Returns 1 when exactly one pending marker is processed."""
        marker = _build_marker()
        dl.save(marker)

        count = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )

        assert count == 1

    def test_activity_persisted_in_datalayer(self, dl):
        """Create(VulnerabilityCase) is written to the DataLayer (AC-1)."""
        activity = _build_activity()
        marker = _build_marker(activity)
        dl.save(marker)

        retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )

        retrieved = dl.read(activity.id_)
        assert (
            retrieved is not None
        ), "Activity should be persisted after retry"

    def test_activity_enqueued_to_outbox(self, dl):
        """Activity is enqueued to the case-actor's outbox (AC-1)."""
        activity = _build_activity()
        marker = _build_marker(activity)
        dl.save(marker)

        retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )

        outbox = dl.outbox_list_for_actor(_CASE_ACTOR_ID)
        assert (
            activity.id_ in outbox
        ), "Activity id should appear in the case-actor's outbox"

    def test_marker_deleted_after_retry(self, dl):
        """PendingCreateCaseActivity marker is removed on success (AC-3)."""
        marker = _build_marker()
        dl.save(marker)

        retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )

        remaining = dl.read(marker.id_)
        assert remaining is None, "Marker should be deleted after retry"

    def test_accept_not_resent(self, dl):
        """Accept(CaseProposal) is NOT written to the DataLayer (AC-1)."""
        marker = _build_marker()
        dl.save(marker)

        retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )

        # Only the Create(VulnerabilityCase) should be in the DataLayer
        accepts = dl.list_objects("Accept")
        assert (
            not accepts
        ), "No Accept activity should be written by the retry runner"


# ---------------------------------------------------------------------------
# AC-4: Idempotency — running twice does not duplicate activities
# ---------------------------------------------------------------------------


class TestRetryIdempotency:
    """Running the retry runner twice must not produce duplicates (AC-4)."""

    def test_second_run_returns_zero(self, dl):
        """Second run (after marker is cleared) returns 0."""
        marker = _build_marker()
        dl.save(marker)

        first = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )
        second = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )

        assert first == 1
        assert second == 0

    def test_activity_not_duplicated_when_already_persisted(self, dl):
        """If activity already exists in DL, no duplicate is created (AC-4)."""
        activity = _build_activity()
        marker = _build_marker(activity)

        # Pre-persist the activity as if a previous partial run stored it
        # but failed to enqueue or delete the marker.
        dl.save(marker)
        dl.create(activity)

        count = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )

        assert count == 1  # still enqueued (marker existed)
        # Only one Create activity in the DataLayer
        creates = dl.list_objects("Create")
        activity_ids = [obj.id_ for obj in creates]
        assert (
            activity_ids.count(activity.id_) == 1
        ), "Activity should appear exactly once in the DataLayer"

    def test_outbox_entry_not_duplicated_on_second_run(self, dl):
        """Outbox entry count is not increased by a no-op second run."""
        marker = _build_marker()
        dl.save(marker)

        retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )
        outbox_after_first = list(dl.outbox_list_for_actor(_CASE_ACTOR_ID))

        # Second run — marker is gone so nothing should change.
        retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )
        outbox_after_second = list(dl.outbox_list_for_actor(_CASE_ACTOR_ID))

        assert outbox_after_first == outbox_after_second

    def test_no_duplicate_outbox_when_marker_deletion_fails(
        self, dl, monkeypatch
    ):
        """Stuck marker (delete fails) does not cause duplicate delivery (AC-4).

        Simulates the scenario where:
          1. First run: activity stored, enqueued, but marker delete fails.
          2. Second run: marker still present, but activity already in outbox.
        The second run must NOT insert a second outbox entry.
        """
        activity = _build_activity()
        marker = _build_marker(activity)
        dl.save(marker)

        # Patch dl.delete so it always returns False (simulating a stuck marker)
        original_delete = dl.delete

        def _failing_delete(table: str, id_: str) -> bool:
            if table == "PendingCreateCaseActivity":
                return False
            return original_delete(table, id_)

        monkeypatch.setattr(dl, "delete", _failing_delete)

        # First run: activity should be stored and enqueued; marker stays.
        first = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )
        assert first == 1
        assert dl.read(marker.id_) is not None, "Marker should still exist"
        outbox_after_first = list(dl.outbox_list_for_actor(_CASE_ACTOR_ID))
        assert activity.id_ in outbox_after_first

        # Second run: marker is still present but activity is already in outbox.
        second = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )
        assert (
            second == 1
        )  # marker found → processed (enqueue skipped, clear fails)
        outbox_after_second = list(dl.outbox_list_for_actor(_CASE_ACTOR_ID))

        # The critical AC-4 assertion: exactly one entry, not two.
        assert (
            outbox_after_second.count(activity.id_) == 1
        ), "Activity id should appear exactly once in the outbox"


# ---------------------------------------------------------------------------
# Multiple markers
# ---------------------------------------------------------------------------


class TestRetryMultipleMarkers:
    """Multiple markers across multiple DataLayers are all processed."""

    def test_two_markers_in_same_dl(self, dl):
        """Two markers in the same DataLayer produce count=2."""
        proposal_id_2 = "https://vendor.test/proposals/p-200"
        activity_1 = _build_activity()

        activity_2 = VultronCreateCaseActivity(
            actor=_CASE_ACTOR_ID,
            object_="https://case-actor.test/cases/c-002",
            context=_ACCEPT_ID,
            to=[_VENDOR_URI],
        )
        marker_1 = _build_marker(activity_1)
        marker_2 = PendingCreateCaseActivity(
            proposal_id=proposal_id_2,
            case_actor_id=_CASE_ACTOR_ID,
            vendor_uri=_VENDOR_URI,
            create_activity_payload=activity_2.model_dump(by_alias=True),
        )
        dl.save(marker_1)
        dl.save(marker_2)

        count = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )

        assert count == 2
        assert dl.read(marker_1.id_) is None
        assert dl.read(marker_2.id_) is None

    def test_markers_across_two_actor_dls(self):
        """Markers in distinct DataLayers are both processed."""
        dl_a = SqliteDataLayer("sqlite:///:memory:")
        dl_b = SqliteDataLayer("sqlite:///:memory:")
        actor_b = "https://case-actor-b.test/actors/svc-002"

        activity_a = _build_activity()
        activity_b = VultronCreateCaseActivity(
            actor=actor_b,
            object_="https://case-actor-b.test/cases/c-b01",
            context=_ACCEPT_ID,
            to=[_VENDOR_URI],
        )
        marker_a = _build_marker(activity_a)
        marker_b = PendingCreateCaseActivity(
            proposal_id="https://vendor.test/proposals/p-b01",
            case_actor_id=actor_b,
            vendor_uri=_VENDOR_URI,
            create_activity_payload=activity_b.model_dump(by_alias=True),
        )
        dl_a.save(marker_a)
        dl_b.save(marker_b)

        count = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {
                _CASE_ACTOR_ID: dl_a,
                actor_b: dl_b,
            }
        )

        assert count == 2


# ---------------------------------------------------------------------------
# AC-5: Full integration scenario
# ---------------------------------------------------------------------------


class TestRetryFullScenario:
    """AC-5: Accept sent → Create fails → marker written → retry runner fires
    → Create re-queued → marker removed.
    """

    def test_full_retry_scenario(self, dl):
        """Simulates the complete CP-05-005 failure-and-recovery path."""
        # 1. Simulate the BT tree: Accept was sent successfully.
        #    The _WriteCreateCaseMarkerNode wrote the marker.
        activity = _build_activity()
        marker = PendingCreateCaseActivity(
            proposal_id=_PROPOSAL_ID,
            case_actor_id=_CASE_ACTOR_ID,
            vendor_uri=_VENDOR_URI,
            create_activity_payload=activity.model_dump(by_alias=True),
        )
        dl.save(marker)

        # 2. Simulate Create(VulnerabilityCase) delivery failing:
        #    the marker was written but _EmitCreateVulnerabilityCaseNode failed,
        #    so the marker was NOT cleared. The activity is also not in the DL.
        assert (
            dl.read(activity.id_) is None
        ), "Activity should not exist before retry"
        assert (
            dl.read(marker.id_) is not None
        ), "Marker should exist before retry"
        assert not dl.outbox_list_for_actor(
            _CASE_ACTOR_ID
        ), "Outbox should be empty before retry"

        # 3. Retry runner fires (e.g., on next startup).
        count = retry_pending_create_case_activities(
            actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
        )

        # 4. Verify: Create(VulnerabilityCase) was re-queued.
        assert count == 1
        retrieved = dl.read(activity.id_)
        assert (
            retrieved is not None
        ), "Activity should be persisted after retry"
        outbox = dl.outbox_list_for_actor(_CASE_ACTOR_ID)
        assert (
            activity.id_ in outbox
        ), "Activity should be in outbox after retry"

        # 5. Verify: marker is removed (AC-3).
        assert (
            dl.read(marker.id_) is None
        ), "Marker should be deleted after successful retry"

        # 6. Accept was NOT resent (AC-1 — retry only covers Create).
        accepts = dl.list_objects("Accept")
        assert not accepts, "No Accept should be written by the retry runner"

    def test_retry_logs_info_on_success(self, dl, caplog):
        """Retry runner logs at INFO level when activities are re-queued."""
        marker = _build_marker()
        dl.save(marker)

        with caplog.at_level(logging.INFO, logger="vultron"):
            retry_pending_create_case_activities(
                actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
            )

        log_messages = " ".join(caplog.messages)
        assert (
            "re-queued" in log_messages.lower()
            or "retry" in log_messages.lower()
        )

    def test_retry_logs_debug_when_no_markers(self, dl, caplog):
        """Retry runner logs at DEBUG when no pending markers exist."""
        with caplog.at_level(logging.DEBUG, logger="vultron"):
            retry_pending_create_case_activities(
                actor_datalayers_factory=lambda: {_CASE_ACTOR_ID: dl}
            )

        # No INFO-level re-queue message should be emitted.
        info_messages = [
            r for r in caplog.records if r.levelno >= logging.INFO
        ]
        assert (
            not info_messages
        ), "No INFO messages expected when no markers are found"
