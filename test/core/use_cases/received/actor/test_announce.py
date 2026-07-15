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
from vultron.core.use_cases.received.actor.announce import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.wire.as2.factories import announce_vulnerability_case_activity
from vultron.wire.as2.vocab.objects.case_actor import CaseActor
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

_OWNER_ID = "https://example.org/actors/owner"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_IMPOSTER_ID = "https://example.org/actors/imposter"
_VENDOR_ID = "https://example.org/actors/vendor"
_CASE_ID = "https://example.org/cases/case-ann-001"
_CASE_ID2 = "https://example.org/cases/case-ann-002"
_REPORT_ID = "https://example.org/reports/report-ann-001"
_CASE_ACTOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/case-actor"
_VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor"


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


# ---------------------------------------------------------------------------
# #566: Embedded participants must be stored during Announce seeding
# ---------------------------------------------------------------------------


class TestAnnounceStoresEmbeddedParticipants:
    """Announce(VulnerabilityCase) seeding must store embedded participants.

    Regression tests for #566: ``AnnounceVulnerabilityCaseReceivedUseCase``
    was not calling ``_store_embedded_participants`` after saving the case,
    so late-joiner replicas never had independent ``CaseParticipant`` records.
    BT nodes (``CheckParticipantExists``, ``AppendParticipantStatusNode``)
    would then fail with participant-not-found on the Announce path.
    """

    @pytest.fixture()
    def case_with_participants(self):
        """VulnerabilityCase with two embedded participants (inline objects)."""
        case_actor_p = CaseParticipant(
            case_roles=[CVDRole.CASE_MANAGER],
            id_=_CASE_ACTOR_PARTICIPANT_ID,
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
            name="DR-10 Announce Case with Participants",
            case_participants=[
                case_actor_p,
                vendor_p,
            ],
        )
        case.actor_participant_index[_CASE_ACTOR_ID] = (
            _CASE_ACTOR_PARTICIPANT_ID
        )
        case.actor_participant_index[_VENDOR_ID] = _VENDOR_PARTICIPANT_ID
        return case, case_actor_p, vendor_p

    @pytest.fixture()
    def announce_with_participants_event(
        self, make_payload, case_with_participants
    ):
        case, _, _ = case_with_participants
        activity = announce_vulnerability_case_activity(
            case,
            actor=_CASE_ACTOR_ID,
            context=_CASE_ID,
        )
        return make_payload(activity)

    def test_embedded_case_actor_participant_stored_after_announce(
        self, dl, announce_with_participants_event
    ):
        """CaseActorParticipant embedded in Announce payload is stored
        independently (#566 — Announce path mirrors Create bootstrap path)."""
        AnnounceVulnerabilityCaseReceivedUseCase(
            dl, announce_with_participants_event
        ).execute()

        stored = dl.read(_CASE_ACTOR_PARTICIPANT_ID)
        assert stored is not None, (
            "CaseActorParticipant must be stored as an independent DataLayer "
            "record after Announce seeding (#566)"
        )

    def test_embedded_vendor_participant_stored_after_announce(
        self, dl, announce_with_participants_event
    ):
        """Vendor CaseParticipant embedded in Announce payload is stored
        independently — BT nodes can then look it up by UUID (#566)."""
        AnnounceVulnerabilityCaseReceivedUseCase(
            dl, announce_with_participants_event
        ).execute()

        stored = dl.read(_VENDOR_PARTICIPANT_ID)
        assert stored is not None, (
            "Vendor CaseParticipant must be stored as an independent DataLayer "
            "record after Announce seeding (#566)"
        )

    def test_string_participant_refs_not_stored_as_objects(
        self, dl, make_payload
    ):
        """String ID refs in case_participants are skipped (no object to store).

        Only inline participant objects are stored; bare ID strings are left
        as-is (they reference objects the receiver doesn't have locally).
        """
        case = VulnerabilityCase(
            id_=_CASE_ID,
            name="Announce with string participants",
            case_participants=[_VENDOR_PARTICIPANT_ID],  # bare string ref
        )
        activity = announce_vulnerability_case_activity(
            case, actor=_CASE_ACTOR_ID, context=_CASE_ID
        )
        event = make_payload(activity)

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        # The bare string ref must NOT cause a spurious record to appear
        stored = dl.read(_VENDOR_PARTICIPANT_ID)
        assert (
            stored is None
        ), "String participant refs must not create spurious DataLayer records"

    def test_embedded_participants_stored_when_case_already_exists(
        self,
        dl,
        announce_with_participants_event,
        case_with_participants,
    ):
        """Participants are stored even when the case already exists locally.

        Regression: the inbox router's ``_store_nested_inbox_object`` can seed
        the case before dispatch, so the Announce use-case may enter the
        idempotent early-return path.  Embedded participants must still be
        persisted on that path (#566).
        """
        case, _, _ = case_with_participants
        # Pre-seed the case so the use-case hits the existing-case branch.
        dl.create(case)

        AnnounceVulnerabilityCaseReceivedUseCase(
            dl, announce_with_participants_event
        ).execute()

        stored_ca = dl.read(_CASE_ACTOR_PARTICIPANT_ID)
        stored_vendor = dl.read(_VENDOR_PARTICIPANT_ID)
        assert stored_ca is not None, (
            "CaseActorParticipant must be stored even when the case already "
            "exists (idempotent early-return path, #566)"
        )
        assert stored_vendor is not None, (
            "Vendor CaseParticipant must be stored even when the case already "
            "exists (idempotent early-return path, #566)"
        )
