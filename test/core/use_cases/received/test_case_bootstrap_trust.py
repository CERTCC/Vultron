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
"""Tests for Case Bootstrap Trust (CBT-05).

Covers:
  CBT-05-001  Reporter accepts CaseActor Announce after bootstrap Create.
  CBT-05-002  Bootstrap Create rejected when sender ≠ trusted_case_creator_id.
  CBT-05-003  No-link path: Create without a matching ReportCaseLink is a
              no-op (receiver is not the original reporter).
  CBT-05-004  trusted_case_actor_id is extracted from the CASE_MANAGER participant
              in the bootstrap snapshot and recorded in the ReportCaseLink.
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.wire.as2.vocab.objects.case_status import (
    ParticipantStatus as WireParticipantStatus,
)
from vultron.core.models.report import VultronReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.actor import (
    AnnounceVulnerabilityCaseReceivedUseCase,
    _find_case_actor_id,
)
from vultron.core.use_cases.received.case import (
    CreateCaseReceivedUseCase,
)
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_status_to_participant_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseActorParticipant,
    CaseParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_CREATOR_ID = "https://example.org/actors/creator"
_REPORTER_ID = "https://example.org/actors/reporter"
_IMPOSTER_ID = "https://example.org/actors/imposter"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_VENDOR_ID = "https://example.org/actors/vendor"
_CASE_ID = "https://example.org/cases/cbt-test-001"
_REPORT_ID = "https://example.org/reports/cbt-report-001"
_PARTICIPANT_ID = f"{_CASE_ID}/participants/case-actor"
_VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _case_with_case_actor_participant() -> tuple:
    """Build a VulnerabilityCase whose participant list includes a CASE_MANAGER.

    Returns a tuple of (VulnerabilityCase, CaseActorParticipant).  The
    participant is embedded INLINE in the case snapshot (not just an ID),
    matching what a real bootstrap ``Create(VulnerabilityCase)`` would carry.
    """
    participant = CaseActorParticipant(
        id_=_PARTICIPANT_ID,
        attributed_to=_CASE_ACTOR_ID,
        context=_CASE_ID,
        name="CaseActor",
    )
    case = VulnerabilityCase(
        id_=_CASE_ID,
        name="CBT test case",
        case_participants=[participant],  # inline — as in a real bootstrap
    )
    return case, participant


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
def case_with_participant():
    """Return (VulnerabilityCase, VultronParticipant) with CASE_MANAGER role."""
    return _case_with_case_actor_participant()


@pytest.fixture()
def create_activity(case_with_participant):
    case, _ = case_with_participant
    return create_case_activity(case, actor=_CREATOR_ID)


@pytest.fixture()
def create_event(make_payload, create_activity):
    return make_payload(create_activity)


# ---------------------------------------------------------------------------
# CBT-05-001: Bootstrap Create from trusted creator seeds the case replica
# ---------------------------------------------------------------------------


class TestBootstrapCreateAccepted:
    """CBT-05-001 — reporter accepts bootstrap Create from trusted creator."""

    def test_case_seeded_in_datalayer(
        self, dl, create_event, case_with_participant
    ):
        """After a valid bootstrap, the case replica exists in the DataLayer."""
        link = _build_link()
        dl.save(link)

        CreateCaseReceivedUseCase(dl, create_event).execute()

        stored = dl.read(_CASE_ID)
        assert (
            stored is not None
        ), "Case should be seeded after valid bootstrap"

    def test_report_case_link_updated_with_case_id(
        self, dl, create_event, case_with_participant
    ):
        """Bootstrap updates ReportCaseLink.case_id (CBT-01-006)."""
        link = _build_link()
        dl.save(link)

        CreateCaseReceivedUseCase(dl, create_event).execute()

        updated = dl.read(link.id_)
        assert isinstance(updated, VultronReportCaseLink)
        assert updated.case_id == _CASE_ID

    def test_report_case_link_updated_with_trusted_case_actor_id(
        self, dl, create_event, case_with_participant
    ):
        """Bootstrap extracts trusted_case_actor_id from CASE_MANAGER participant
        (CBT-01-003, CBT-01-006)."""
        link = _build_link()
        dl.save(link)

        CreateCaseReceivedUseCase(dl, create_event).execute()

        updated = dl.read(link.id_)
        assert isinstance(updated, VultronReportCaseLink)
        assert updated.trusted_case_actor_id == _CASE_ACTOR_ID


# ---------------------------------------------------------------------------
# CBT-05-002: Bootstrap Create rejected when sender ≠ trusted_case_creator_id
# ---------------------------------------------------------------------------


class TestBootstrapCreateRejectedBadSender:
    """CBT-05-002 — imposter sender is rejected; case is NOT seeded."""

    @pytest.fixture()
    def imposter_activity(self, case_with_participant):
        case, _ = case_with_participant
        return create_case_activity(case, actor=_IMPOSTER_ID)

    @pytest.fixture()
    def imposter_event(self, make_payload, imposter_activity):
        return make_payload(imposter_activity)

    def test_case_not_created(self, dl, imposter_event, case_with_participant):
        """Case must NOT be seeded when sender ≠ trusted_case_creator_id."""
        link = _build_link(trusted_case_creator_id=_CREATOR_ID)
        dl.save(link)

        CreateCaseReceivedUseCase(dl, imposter_event).execute()

        stored = dl.read(_CASE_ID)
        assert (
            stored is None
        ), "Case must not be seeded when sender is not trusted creator"

    def test_link_not_updated(self, dl, imposter_event, case_with_participant):
        """ReportCaseLink must NOT be updated when bootstrap is rejected."""
        link = _build_link(trusted_case_creator_id=_CREATOR_ID)
        dl.save(link)

        CreateCaseReceivedUseCase(dl, imposter_event).execute()

        updated = dl.read(link.id_)
        assert isinstance(updated, VultronReportCaseLink)
        assert updated.case_id is None
        assert updated.trusted_case_actor_id is None


# ---------------------------------------------------------------------------
# CBT-05-003: No ReportCaseLink means receiver is not the reporter — no-op
# ---------------------------------------------------------------------------


class TestBootstrapCreateNoLink:
    """CBT-05-003 — no matching ReportCaseLink → case is not a known reporter."""

    def test_case_not_created_without_link(
        self, dl, create_event, case_with_participant
    ):
        """Without a ReportCaseLink, CreateCaseReceivedUseCase is a no-op."""
        # Do NOT create a VultronReportCaseLink

        CreateCaseReceivedUseCase(dl, create_event).execute()

        stored = dl.read(_CASE_ID)
        assert (
            stored is None
        ), "Case should not be seeded when receiver has no matching ReportCaseLink"


# ---------------------------------------------------------------------------
# CBT-05-004: trusted_case_actor_id gates subsequent Announce acceptance
# ---------------------------------------------------------------------------


class TestAnnounceValidatedByTrustedCaseActorId:
    """CBT-05-004 — only the bootstrapped CaseActor may push Announce updates."""

    @pytest.fixture()
    def case_obj(self):
        return VulnerabilityCase(id_=_CASE_ID, name="CBT announce gate case")

    @pytest.fixture()
    def announce_from_trusted(self, case_obj):
        return announce_vulnerability_case_activity(
            case_obj, actor=_CASE_ACTOR_ID
        )

    @pytest.fixture()
    def announce_from_imposter(self, case_obj):
        return announce_vulnerability_case_activity(
            case_obj, actor=_IMPOSTER_ID
        )

    def test_trusted_actor_announce_accepted(
        self, dl, make_payload, case_obj, announce_from_trusted
    ):
        """Announce from trusted_case_actor_id is accepted (CBT-05-004)."""
        link = _build_link(
            case_id=_CASE_ID, trusted_case_actor_id=_CASE_ACTOR_ID
        )
        dl.save(link)

        event = make_payload(announce_from_trusted)
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(_CASE_ID)
        assert (
            stored is not None
        ), "Announce from trusted CaseActor must seed the case"

    def test_imposter_announce_rejected(
        self, dl, make_payload, case_obj, announce_from_imposter
    ):
        """Announce from actor other than trusted_case_actor_id is rejected."""
        link = _build_link(
            case_id=_CASE_ID, trusted_case_actor_id=_CASE_ACTOR_ID
        )
        dl.save(link)

        event = make_payload(announce_from_imposter)
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(_CASE_ID)
        assert stored is None, (
            "Announce from imposter must be rejected when trusted_case_actor_id "
            "is set (CBT-05-004, PCR-03-001)"
        )

    def test_find_case_actor_id_prefers_link_over_service(self, dl, case_obj):
        """_find_case_actor_id returns trusted_case_actor_id from link first."""
        link = _build_link(
            case_id=_CASE_ID, trusted_case_actor_id=_CASE_ACTOR_ID
        )
        dl.save(link)

        result = _find_case_actor_id(dl, _CASE_ID)
        assert result == _CASE_ACTOR_ID


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
        self, dl, create_event, case_with_participant
    ):
        """Participants are stored even when the case replica was already seeded
        (e.g. by ``_store_nested_inbox_object`` before dispatch) — #561, #562.
        """
        link = _build_link()
        dl.save(link)

        # Pre-seed the case to trigger the idempotency guard in _handle_bootstrap
        case, _ = case_with_participant
        dl.create(case)

        CreateCaseReceivedUseCase(dl, create_event).execute()

        stored = dl.read(_PARTICIPANT_ID)
        assert stored is not None, (
            "Participant must be stored even when the case was already seeded "
            "before _handle_bootstrap ran"
        )

    def test_save_failure_propagates_from_store_embedded_participants(
        self, dl, create_event, case_with_participant
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
    """CBT-05-006 — AddParticipantStatusBT succeeds on finder's replica.

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

    @pytest.fixture()
    def case_with_two_participants(self):
        """VulnerabilityCase with a CASE_MANAGER participant and a vendor
        participant, both embedded inline as in a real bootstrap snapshot."""
        case_actor_p = CaseActorParticipant(
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
            name="CBT-05-006 M4 regression case",
            case_participants=[case_actor_p, vendor_p],
        )
        case.actor_participant_index[_CASE_ACTOR_ID] = _PARTICIPANT_ID
        case.actor_participant_index[_VENDOR_ID] = _VENDOR_PARTICIPANT_ID
        return case, case_actor_p, vendor_p

    @pytest.fixture()
    def bootstrap_m4_event(self, make_payload, case_with_two_participants):
        case, _, _ = case_with_two_participants
        activity = create_case_activity(case, actor=_CREATOR_ID)
        return make_payload(activity)

    def test_add_participant_status_succeeds_after_bootstrap(
        self, dl, make_payload, bootstrap_m4_event, case_with_two_participants
    ):
        """AddParticipantStatusBT appends VFd status on finder's replica.

        Full M4 path: bootstrap → verify participant stored → receive
        Add(ParticipantStatus) from case-actor → assert VFd status on vendor
        participant.  Regression for #563.
        """
        _vfd_status_id = f"{_VENDOR_PARTICIPANT_ID}/statuses/vfd-s1"
        _, _, vendor_p = case_with_two_participants

        link = _build_link()
        dl.save(link)

        # Step 1: bootstrap — _store_embedded_participants saves vendor's
        # CaseParticipant as an independent DataLayer record (CBT-05-005).
        CreateCaseReceivedUseCase(dl, bootstrap_m4_event).execute()

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


# ---------------------------------------------------------------------------
# CBT-05-006: Reporter participant seeded with RM.ACCEPTED on bootstrap (#589)
# ---------------------------------------------------------------------------


class TestBootstrapCreateReporterParticipant:
    """Bootstrap Create must seed the reporter's participant at RM.ACCEPTED.

    When Create(VulnerabilityCase) arrives with participant IDs as bare
    strings, _store_embedded_participants skips them.  The reporter's own
    participant record would then be absent from their DataLayer, causing
    SvcAddParticipantStatusUseCase._resolve_current_participant_state to
    fall back to RM.START — the root cause of #589.

    The fix: _handle_bootstrap infers from the reporter's submitted report
    that they have already RM.ACCEPTED and creates the participant record
    with that state if it is not already present.
    """

    _VENDOR_ID = "https://vendor.example.org/actors/vendor-589"
    _FINDER_ID = "https://finder.example.org/actors/finder-589"
    _CASE_ID = "https://example.org/cases/case-589"
    _REPORT_ID = "https://example.org/reports/report-589"
    _FINDER_PARTICIPANT_ID = f"{_CASE_ID}/participants/finder-589"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-589"

    @pytest.fixture()
    def dl(self):
        return SqliteDataLayer("sqlite:///:memory:")

    @pytest.fixture()
    def seeded_dl(self, dl):
        """DataLayer with the Finder's pre-existing report and case link."""
        report = VultronReport(
            id_=self._REPORT_ID,
            attributed_to=self._FINDER_ID,
        )
        dl.create(report)

        link = VultronReportCaseLink(
            report_id=self._REPORT_ID,
            trusted_case_creator_id=self._VENDOR_ID,
        )
        dl.save(link)
        return dl

    @pytest.fixture()
    def case_with_string_participants(self):
        """VulnerabilityCase whose participants are bare string IDs.

        This is the common wire representation when the sender serialises the
        domain VultronCase (which stores participant IDs, not objects).
        The fixture also includes a CASE_MANAGER participant inline so that
        the bootstrap trust path extracts a trusted_case_actor_id.
        """
        case_actor_participant = CaseActorParticipant(
            id_=self._VENDOR_PARTICIPANT_ID,
            attributed_to=self._VENDOR_ID,
            context=self._CASE_ID,
        )
        case = VulnerabilityCase(
            id_=self._CASE_ID,
            name="Bug #589 regression case",
            case_participants=[
                case_actor_participant,  # inline so CBT-01-003 can extract it
                self._FINDER_PARTICIPANT_ID,  # bare string — typical case
            ],
        )
        case.actor_participant_index[self._VENDOR_ID] = (
            self._VENDOR_PARTICIPANT_ID
        )
        case.actor_participant_index[self._FINDER_ID] = (
            self._FINDER_PARTICIPANT_ID
        )
        return case

    @pytest.fixture()
    def create_event(self, make_payload, case_with_string_participants):
        activity = create_case_activity(
            case_with_string_participants, actor=self._VENDOR_ID
        )
        return make_payload(activity)

    def test_reporter_participant_created_after_bootstrap(
        self, seeded_dl, create_event
    ):
        """Reporter participant must exist in DataLayer after bootstrap (#589).

        When the bootstrap Create(VulnerabilityCase) carries the reporter's
        participant as a bare string ID, the DataLayer must still produce a
        standalone participant record for the reporter so that subsequent
        SvcAddParticipantStatusUseCase calls can read it.
        """
        CreateCaseReceivedUseCase(seeded_dl, create_event).execute()

        stored = seeded_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None, (
            "Reporter participant must be created in the DataLayer after "
            "bootstrap even when case_participants contains a bare string ID "
            "(regression #589)"
        )

    def test_reporter_participant_has_rm_accepted_after_bootstrap(
        self, seeded_dl, create_event
    ):
        """Reporter participant must start at RM.ACCEPTED after bootstrap.

        The reporter submitted a report — by definition they have accepted the
        vulnerability from their own RM perspective.  The seeded participant
        must reflect this so that _resolve_current_participant_state returns
        RM.ACCEPTED rather than RM.START (#589).
        """
        CreateCaseReceivedUseCase(seeded_dl, create_event).execute()

        stored = seeded_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert statuses, (
            "Reporter participant must have at least one ParticipantStatus "
            "after bootstrap (#589)"
        )
        latest = statuses[-1]
        rm_state = getattr(latest, "rm_state", None)
        assert rm_state == RM.ACCEPTED, (
            f"Reporter participant must have rm_state=RM.ACCEPTED after "
            f"bootstrap; got {rm_state!r} (#589)"
        )


# ---------------------------------------------------------------------------
# CBT-05-007: Reporter participant upgraded from RM.START to RM.ACCEPTED (#624)
# ---------------------------------------------------------------------------


class TestBootstrapReporterUpgradesFromStart:
    """Bootstrap Create upgrades an existing RM.START participant to RM.ACCEPTED.

    When ``_store_embedded_participants`` stores the wire-layer snapshot, it may
    seed the reporter's participant with ``rm_state=RM.START`` (the wire default).
    ``_ensure_reporter_participant`` must detect this and upgrade the participant
    to ``RM.ACCEPTED``.  See issue #624.
    """

    _VENDOR_ID = "https://vendor.example.org/actors/vendor-624"
    _FINDER_ID = "https://finder.example.org/actors/finder-624"
    _CASE_ID = "https://example.org/cases/case-624"
    _REPORT_ID = "https://example.org/reports/report-624"
    _FINDER_PARTICIPANT_ID = f"{_CASE_ID}/participants/finder-624"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-624"

    @pytest.fixture()
    def dl(self):
        return SqliteDataLayer("sqlite:///:memory:")

    @pytest.fixture()
    def base_dl(self, dl):
        """DataLayer with report and link pre-seeded."""
        report = VultronReport(
            id_=self._REPORT_ID,
            attributed_to=self._FINDER_ID,
        )
        dl.create(report)

        link = VultronReportCaseLink(
            report_id=self._REPORT_ID,
            trusted_case_creator_id=self._VENDOR_ID,
        )
        dl.save(link)
        return dl

    @pytest.fixture()
    def case_with_string_participants(self):
        case_actor_participant = CaseActorParticipant(
            id_=self._VENDOR_PARTICIPANT_ID,
            attributed_to=self._VENDOR_ID,
            context=self._CASE_ID,
        )
        case = VulnerabilityCase(
            id_=self._CASE_ID,
            name="Bug #624 regression case",
            case_participants=[
                case_actor_participant,
                self._FINDER_PARTICIPANT_ID,  # bare string
            ],
        )
        case.actor_participant_index[self._VENDOR_ID] = (
            self._VENDOR_PARTICIPANT_ID
        )
        case.actor_participant_index[self._FINDER_ID] = (
            self._FINDER_PARTICIPANT_ID
        )
        return case

    def _create_event(self, make_payload, case):
        activity = create_case_activity(case, actor=self._VENDOR_ID)
        return make_payload(activity)

    def _pre_seed_participant(self, dl, rm_state: RM) -> VultronParticipant:
        """Store a finder participant at the given rm_state before bootstrap."""
        status = ParticipantStatus(
            rm_state=rm_state,
            context=self._CASE_ID,
            attributed_to=self._FINDER_ID,
        )
        participant = VultronParticipant(
            id_=self._FINDER_PARTICIPANT_ID,
            attributed_to=self._FINDER_ID,
            context=self._CASE_ID,
            participant_statuses=[status],
        )
        dl.create(participant)
        return participant

    def test_reporter_participant_upgraded_from_start_to_accepted(
        self, base_dl, make_payload, case_with_string_participants
    ):
        """Reporter participant at RM.START must be upgraded to RM.ACCEPTED (#624).

        Pre-condition: reporter's participant is already in the DataLayer at
        RM.START (seeded by _store_embedded_participants or a prior bootstrap).
        Post-condition: after CreateCaseReceivedUseCase, the participant's latest
        rm_state is RM.ACCEPTED.
        """
        self._pre_seed_participant(base_dl, RM.START)
        event = self._create_event(make_payload, case_with_string_participants)

        CreateCaseReceivedUseCase(base_dl, event).execute()

        stored = base_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert statuses, "Reporter participant must have at least one status"
        latest_rm = statuses[-1].rm_state
        assert latest_rm == RM.ACCEPTED, (
            f"Reporter participant must be upgraded to RM.ACCEPTED from "
            f"RM.START; got {latest_rm!r} (#624)"
        )

    def test_reporter_participant_noop_if_already_accepted(
        self, base_dl, make_payload, case_with_string_participants
    ):
        """Reporter participant already at RM.ACCEPTED must not be modified (#624)."""
        self._pre_seed_participant(base_dl, RM.ACCEPTED)
        event = self._create_event(make_payload, case_with_string_participants)

        CreateCaseReceivedUseCase(base_dl, event).execute()

        stored = base_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert len(statuses) == 1, (
            "Reporter participant already at RM.ACCEPTED must not gain extra "
            f"statuses; got {len(statuses)} (#624)"
        )
        assert statuses[0].rm_state == RM.ACCEPTED

    def test_reporter_participant_noop_if_already_closed(
        self, base_dl, make_payload, case_with_string_participants
    ):
        """Reporter participant already at RM.CLOSED must not be downgraded (#624)."""
        self._pre_seed_participant(base_dl, RM.CLOSED)
        event = self._create_event(make_payload, case_with_string_participants)

        CreateCaseReceivedUseCase(base_dl, event).execute()

        stored = base_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert len(statuses) == 1, (
            "Reporter participant at RM.CLOSED must not gain extra statuses "
            f"(it is already beyond ACCEPTED); got {len(statuses)} (#624)"
        )
        assert statuses[0].rm_state == RM.CLOSED
