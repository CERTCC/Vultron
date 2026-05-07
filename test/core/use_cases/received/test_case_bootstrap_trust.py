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

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.use_cases.received.actor import (
    AnnounceVulnerabilityCaseReceivedUseCase,
    _find_case_actor_id,
)
from vultron.core.use_cases.received.case import (
    CreateCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    announce_vulnerability_case_activity,
    create_case_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseActorParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_CREATOR_ID = "https://example.org/actors/creator"
_REPORTER_ID = "https://example.org/actors/reporter"
_IMPOSTER_ID = "https://example.org/actors/imposter"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_CASE_ID = "https://example.org/cases/cbt-test-001"
_REPORT_ID = "https://example.org/reports/cbt-report-001"
_PARTICIPANT_ID = f"{_CASE_ID}/participants/case-actor"


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
