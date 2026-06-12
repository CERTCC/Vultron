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
"""Tests for _ensure_reporter_participant helper and EnsureReporterParticipantAtAcceptedNode
(CBT-05-006/007, #589, #624).

Covers:
  CBT-05-006  Bootstrap Create seeds the reporter participant at RM.ACCEPTED
              when the participant arrives as a bare string ID (fix for #589).
  CBT-05-007  Bootstrap Create upgrades an existing RM.START participant to
              RM.ACCEPTED (fix for #624).

Both requirements are now exercised via ``EnsureReporterParticipantAtAcceptedNode``
(a BT leaf node) called through BTBridge from ``CreateCaseReceivedUseCase._handle_bootstrap``
(BT-06-001, BT-15-001, #943).
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases.received.case.create import (
    CreateCaseReceivedUseCase,
)
from vultron.wire.as2.factories import create_case_activity
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

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

    The fix: _handle_bootstrap calls EnsureReporterParticipantAtAcceptedNode
    via BTBridge, which infers from the reporter's submitted report that they
    have already RM.ACCEPTED and creates the participant record with that state
    if it is not already present (BT-06-001, BT-15-001, #943).
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
        case_actor_participant = CaseParticipant(
            case_roles=[CVDRole.CASE_MANAGER],
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
    ``EnsureReporterParticipantAtAcceptedNode`` must detect this and upgrade the
    participant to ``RM.ACCEPTED`` via BTBridge (#624, BT-06-001, BT-15-001,
    #943).
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
        case_actor_participant = CaseParticipant(
            case_roles=[CVDRole.CASE_MANAGER],
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
