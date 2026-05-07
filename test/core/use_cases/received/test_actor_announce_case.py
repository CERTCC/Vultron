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
"""Tests for AnnounceVulnerabilityCaseReceivedUseCase (DR-10 / MV-10-003,004)."""

from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.use_cases.received.actor import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.wire.as2.factories import announce_vulnerability_case_activity
from vultron.wire.as2.vocab.objects.case_actor import CaseActor
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

_OWNER_ID = "https://example.org/actors/owner"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_IMPOSTER_ID = "https://example.org/actors/imposter"
_CASE_ID = "https://example.org/cases/case-ann-001"
_CASE_ID2 = "https://example.org/cases/case-ann-002"
_REPORT_ID = "https://example.org/reports/report-ann-001"


@pytest.fixture()
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture()
def case():
    return VulnerabilityCase(id_=_CASE_ID, name="DR-10 Announce Case")


@pytest.fixture()
def case_actor():
    return CaseActor(
        id_=_CASE_ACTOR_ID,
        attributed_to=_OWNER_ID,
        context=_CASE_ID,
        name="CaseActor",
    )


@pytest.fixture()
def announce_activity(case, case_actor):
    return announce_vulnerability_case_activity(
        case,
        actor=case_actor.id_,
        context=case.id_,
    )


@pytest.fixture()
def event(make_payload, announce_activity):
    return make_payload(announce_activity)


class TestAnnounceVulnerabilityCaseReceivedUseCase:
    """AnnounceVulnerabilityCaseReceivedUseCase seeds the invitee's DataLayer."""

    def test_creates_case_when_absent(self, dl, event, case):
        """MV-10-003: Announce seeding creates the case in the invitee's DL."""
        dl.create(
            CaseActor(
                id_=_CASE_ACTOR_ID,
                attributed_to=_OWNER_ID,
                context=_CASE_ID,
                name="CaseActor",
            )
        )
        assert dl.read(_CASE_ID) is None

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        result = dl.read(_CASE_ID)
        assert result is not None

    def test_case_fields_preserved(self, dl, event, case, case_actor):
        """The seeded case retains the name from the Announce payload."""
        dl.create(case_actor)
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        result = cast(Any, dl.read(_CASE_ID))
        assert result.name == "DR-10 Announce Case"

    def test_creates_case_when_case_actor_not_yet_known_locally(
        self, dl, event, case
    ):
        """First-time replica seeding succeeds before the CaseActor is stored."""
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        result = dl.read(_CASE_ID)
        assert result is not None

    def test_updates_report_case_link_when_case_contains_report(
        self, dl, event, case, case_actor
    ):
        """A valid Announce links known reports to the seeded case replica."""
        dl.create(case_actor)
        case.vulnerability_reports.append(_REPORT_ID)
        dl.save(VultronReportCaseLink(report_id=_REPORT_ID))

        linked_event = event.model_copy(
            update={
                "activity": announce_vulnerability_case_activity(
                    case,
                    actor=case_actor.id_,
                    context=case.id_,
                )
            }
        )

        AnnounceVulnerabilityCaseReceivedUseCase(dl, linked_event).execute()

        link = dl.read(VultronReportCaseLink.build_id(_REPORT_ID))
        assert isinstance(link, VultronReportCaseLink)
        assert link.case_id == _CASE_ID

    def test_idempotent_when_case_already_exists(
        self, dl, event, case, case_actor
    ):
        """MV-10-004: A second Announce for an existing case is a no-op."""
        dl.create(case_actor)
        dl.create(case)

        # First call — case exists; should not fail or overwrite
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        # Confirm the case is still there and unchanged
        result = dl.read(_CASE_ID)
        assert result is not None

    def test_missing_activity_skips_gracefully(self, dl, event):
        """No-op (with a warning log) when event.activity is None."""
        event = event.model_copy(update={"activity": None})

        # Must not raise
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID) is None

    def test_non_case_object_skips_gracefully(self, dl, make_payload):
        """No-op when the activity object_ is not a VulnerabilityCase."""
        from vultron.wire.as2.factories import (
            announce_vulnerability_case_activity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        # Build an Announce that wraps a non-case object; we can't use the typed
        # factory here because it requires VulnerabilityCase,
        # so we inject via model_copy to simulate a malformed incoming payload.
        good_case = VulnerabilityCase(id_=_CASE_ID2, name="Placeholder")
        announce = announce_vulnerability_case_activity(
            good_case, actor=_OWNER_ID
        )
        event = make_payload(announce)

        # Replace the object_ on the raw activity with a non-case
        report = VulnerabilityReport(name="Not a case")
        patched_activity = announce.model_copy(update={"object_": report})
        event = event.model_copy(update={"activity": patched_activity})

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID2) is None

    def test_rejects_announce_from_non_case_actor(
        self, dl, case, make_payload
    ):
        """PCR-07-003: non-CaseActor senders cannot seed a case replica."""
        dl.create(
            CaseActor(
                id_=_CASE_ACTOR_ID,
                attributed_to=_OWNER_ID,
                context=_CASE_ID,
                name="CaseActor",
            )
        )
        announce = announce_vulnerability_case_activity(
            case,
            actor=_IMPOSTER_ID,
            context=case.id_,
        )
        event = make_payload(announce)

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID) is None
