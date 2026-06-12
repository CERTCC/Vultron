#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Tests for embedded-participant storage during case bootstrap (CBT-05-005/006).

Covers:
  CBT-05-005  Embedded CaseParticipant objects are stored as independent
              DataLayer records so BT nodes (CheckParticipantExists,
              AppendParticipantStatusNode) can look them up by UUID.
  CBT-05-006  AddParticipantStatusBT succeeds on the reporter's replica after
              bootstrap (regression for #563 — M4 timeout in two-actor demo).
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.cs import CS_vfd
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases.received.case.create import (
    CreateCaseReceivedUseCase,
)
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_status_to_participant_activity,
    create_case_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    ParticipantStatus as WireParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_CREATOR_ID = "https://example.org/actors/creator"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_VENDOR_ID = "https://example.org/actors/vendor"
_CASE_ID = "https://example.org/cases/cbt-bp-001"
_REPORT_ID = "https://example.org/reports/cbt-bp-report-001"
_PARTICIPANT_ID = f"{_CASE_ID}/participants/case-actor"
_VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_link(
    *,
    trusted_case_creator_id: str | None = _CREATOR_ID,
    case_id: str | None = None,
    trusted_case_actor_id: str | None = None,
) -> VultronReportCaseLink:
    return VultronReportCaseLink(
        report_id=_REPORT_ID,
        case_id=case_id,
        trusted_case_creator_id=trusted_case_creator_id,
        trusted_case_actor_id=trusted_case_actor_id,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture()
def case_with_two_participants():
    """VulnerabilityCase with CASE_MANAGER and vendor participants inline."""
    case_actor_p = CaseParticipant(
        case_roles=[CVDRole.CASE_MANAGER],
        id_=_PARTICIPANT_ID,
        attributed_to=_CASE_ACTOR_ID,
        context=_CASE_ID,
    )
    vendor_p = CaseParticipant(
        id_=_VENDOR_PARTICIPANT_ID,
        attributed_to=_VENDOR_ID,
        context=_CASE_ID,
    )
    case = VulnerabilityCase(
        id_=_CASE_ID,
        name="CBT-05-005/006 participant storage case",
        case_participants=[case_actor_p, vendor_p],
    )
    case.actor_participant_index[_CASE_ACTOR_ID] = _PARTICIPANT_ID
    case.actor_participant_index[_VENDOR_ID] = _VENDOR_PARTICIPANT_ID
    return case, case_actor_p, vendor_p


@pytest.fixture()
def create_event(make_payload, case_with_two_participants):
    case, _, _ = case_with_two_participants
    activity = create_case_activity(case, actor=_CREATOR_ID)
    return make_payload(activity)


# ---------------------------------------------------------------------------
# CBT-05-005: Embedded participants are stored as separate DataLayer records
# ---------------------------------------------------------------------------


class TestBootstrapParticipantStorage:
    """CBT-05-005 — bootstrap Create stores embedded participants in DataLayer.

    BT nodes ``CheckParticipantExists`` (#561) and ``AppendParticipantStatus``
    (#562) look up participants by UUID via ``datalayer.read(participant_id)``.
    After a bootstrap ``Create(VulnerabilityCase)`` those participant records
    MUST exist as independent DataLayer entries so the BT nodes can find them.
    """

    def test_embedded_participant_stored_after_bootstrap(
        self, dl, create_event
    ):
        """Embedded CaseParticipant is stored as an independent DataLayer
        record after a valid bootstrap (CBT-05-005, fixes #561 and #562).
        """
        link = _build_link()
        dl.save(link)

        CreateCaseReceivedUseCase(dl, create_event).execute()

        stored = dl.read(_PARTICIPANT_ID)
        assert stored is not None, (
            "Embedded CaseActorParticipant must be stored as an independent "
            "DataLayer record after bootstrap so BT nodes can look it up by ID"
        )

    def test_participant_stored_when_case_already_existed(
        self, dl, create_event, case_with_two_participants
    ):
        """Participants are stored even when the case replica was already seeded
        (e.g. by ``_store_nested_inbox_object`` before dispatch) — #561, #562.
        """
        link = _build_link()
        dl.save(link)

        # Pre-seed the case to trigger the idempotency guard in _handle_bootstrap
        case, _, _ = case_with_two_participants
        dl.create(case)

        CreateCaseReceivedUseCase(dl, create_event).execute()

        stored = dl.read(_PARTICIPANT_ID)
        assert stored is not None, (
            "Participant must be stored even when the case was already seeded "
            "before _handle_bootstrap ran"
        )

    def test_save_failure_propagates_from_store_embedded_participants(
        self, dl, create_event
    ):
        """A DataLayer failure in _store_embedded_participants propagates as an
        exception rather than being silently swallowed (leaves replica
        consistent — fail loudly instead of leaving participants missing).
        """
        import unittest.mock as mock

        link = _build_link()
        dl.save(link)

        # Patch dl.save to raise after the first successful call (link save)
        original_save = dl.save
        call_count = {"n": 0}

        def _patched_save(obj):
            call_count["n"] += 1
            if call_count["n"] > 1:
                raise RuntimeError("storage failure")
            return original_save(obj)

        with mock.patch.object(dl, "save", side_effect=_patched_save):
            with pytest.raises(RuntimeError, match="storage failure"):
                CreateCaseReceivedUseCase(dl, create_event).execute()


# ---------------------------------------------------------------------------
# CBT-05-006: M4 AddParticipantStatusBT succeeds after bootstrap (#563)
# ---------------------------------------------------------------------------


class TestM4AddParticipantStatusAfterBootstrap:
    """CBT-05-006 — AddParticipantStatusBT succeeds on reporter's replica.

    Regression test for #563: M4 timeout in two-actor demo.

    Before the fix (PRs #561, #562):
    - ``_store_embedded_participants`` did not persist each embedded participant
      as an independent DataLayer record, so vendor's ``CaseParticipant`` could
      not be found by its UUID after bootstrap.
    - ``AppendParticipantStatusNode`` did ``dl.read(vendor_participant_id)``
      → ``None`` → ``FAILURE``, leaving finder's replica without the vendor's
      ``vfd_state`` update.
    - Finder's M4 poll returned 404 until timeout.

    After the fix:
    - ``_store_embedded_participants`` stores all embedded participant objects
      during bootstrap (CBT-05-005).
    - ``AppendParticipantStatusNode`` finds the participant and appends the
      status successfully.
    - M4 completes without timeout.
    """

    def test_add_participant_status_succeeds_after_bootstrap(
        self, dl, make_payload, case_with_two_participants
    ):
        """AddParticipantStatusBT appends VFd status on finder's replica.

        Full M4 path: bootstrap → verify participant stored → receive
        Add(ParticipantStatus) from case-actor → assert VFd status on vendor
        participant.  Regression for #563.
        """
        _vfd_status_id = f"{_VENDOR_PARTICIPANT_ID}/statuses/vfd-s1"
        case, _, vendor_p = case_with_two_participants

        activity = create_case_activity(case, actor=_CREATOR_ID)
        bootstrap_event = make_payload(activity)

        link = _build_link()
        dl.save(link)

        # Step 1: bootstrap — _store_embedded_participants saves vendor's
        # CaseParticipant as an independent DataLayer record (CBT-05-005).
        CreateCaseReceivedUseCase(dl, bootstrap_event).execute()

        # Step 2: confirm vendor participant is independently stored (core fix).
        stored_p = dl.read(_VENDOR_PARTICIPANT_ID)
        assert (
            stored_p is not None
        ), "Vendor CaseParticipant must be stored during bootstrap (CBT-05-005)"

        # Step 3: case-actor broadcasts Add(ParticipantStatus, vendor_p) to
        # finder.  actor=_CASE_ACTOR_ID so VerifySenderIsParticipantNode passes
        # (case.actor_participant_index contains _CASE_ACTOR_ID).
        # The status is NOT pre-created — it arrives inline in the activity, so
        # AppendParticipantStatusNode must resolve it from the fallback and
        # persist it independently.
        status = WireParticipantStatus(
            id_=_vfd_status_id,
            context=_CASE_ID,
            vfd_state=CS_vfd.VFd,
        )
        activity = add_status_to_participant_activity(
            status,
            target=vendor_p,
            actor=_CASE_ACTOR_ID,
        )
        event = make_payload(activity)

        AddParticipantStatusToParticipantReceivedUseCase(dl, event).execute()

        # Step 4: vendor participant now has the VFd status — M4 can observe it.
        updated_p = dl.read(_VENDOR_PARTICIPANT_ID)
        assert (
            updated_p is not None
        ), "Vendor participant must still exist after AddParticipantStatus"
        updated_p = cast(CaseParticipant, updated_p)
        status_ids = [
            getattr(s, "id_", s) for s in updated_p.participant_statuses
        ]
        assert _vfd_status_id in status_ids, (
            "Vendor participant must have the VFd status after M4 broadcast "
            "(regression for #563)"
        )
        # The status object must also exist as an independent DataLayer record.
        stored_status = dl.read(_vfd_status_id)
        assert stored_status is not None, (
            "ParticipantStatus must be persisted as an independent DataLayer"
            " record by AddParticipantStatusToParticipantReceivedUseCase"
        )
