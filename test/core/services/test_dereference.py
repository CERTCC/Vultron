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
"""Which references a receiver fetches, and the case host's read (AKM-05)."""

from datetime import timedelta
from typing import Any

import pytest

from test.support.case_manager import (
    CASE_MANAGER_ID,
    make_case_with_case_manager,
)
from test.support.embargo_register import activate, propose
from test.support.received import TEST_SENDER_POSITION
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import now_utc
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.embargo import (
    AnnounceEmbargoEventToCaseReceivedEvent,
)
from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchUse,
    ObjectReference,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.services.dereference import (
    case_object_for_participant,
    references_to_fetch,
    with_fetched_object,
)
from vultron.core.states.rm import RM
from vultron.errors import (
    VultronNotACaseParticipantError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.parser import parse_activity

_PARTICIPANT = "https://example.org/actors/vendor"
_OUTSIDER = "https://example.org/actors/outsider"
_CASE_ACTOR = "https://example.org/actors/case-actor"


def _replica(actor_id: str = _PARTICIPANT) -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)


def _seat(
    dl: SqliteDataLayer, case: VulnerabilityCase, actor_id: str
) -> CaseParticipant:
    participant = CaseParticipant(attributed_to=actor_id, context=case.id_)
    case.add_participant(participant)
    dl.save(case)
    dl.create(participant)
    return participant


def _embargo(case_id: str, days: int = 30) -> EmbargoEvent:
    return EmbargoEvent(context=case_id, end_time=now_utc() + timedelta(days))


def _unresolvable(case_id: str, object_id: str) -> Any:
    activity = parse_activity(
        {
            "type": "Accept",
            "id": "https://example.org/activities/a-1",
            "published": "2026-10-26T12:00:00Z",
            "actor": CASE_MANAGER_ID,
            "object": object_id,
            "context": case_id,
            "to": [_PARTICIPANT],
        }
    )
    event = extract_event(activity)
    assert event.semantic_type is MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    return event


def _proposal(actor: Any) -> Any:
    activity = parse_activity(
        {
            "type": "Create",
            "id": "https://example.org/activities/create-proposal",
            "published": "2026-10-26T12:00:00Z",
            "actor": actor,
            "to": [_CASE_ACTOR],
            "object": {
                "type": "CaseProposal",
                "id": "https://example.org/proposals/p-1",
                "attributedTo": _PARTICIPANT,
                "object": {
                    "type": "VulnerabilityReport",
                    "id": "https://example.org/reports/r-1",
                    "name": "A report",
                    "content": "Details",
                    "attributedTo": _PARTICIPANT,
                },
                "target": _CASE_ACTOR,
            },
        }
    )
    return extract_event(activity)


def _announce(case: VulnerabilityCase, embargo: EmbargoEvent) -> Any:
    return AnnounceEmbargoEventToCaseReceivedEvent(
        ledger_position=TEST_SENDER_POSITION,
        activity_id="https://example.org/activities/announce-1",
        actor_id=CASE_MANAGER_ID,
        object_=embargo,
        context=case,
    )


class TestReferencesToFetch:
    @pytest.mark.spec("AKM-05-007")
    def test_a_bare_object_the_replica_lacks_is_fetched_from_the_case_host(
        self,
    ):
        dl = _replica()
        case = make_case_with_case_manager(dl)
        missing = "urn:uuid:not-held"

        refs = references_to_fetch(
            _unresolvable(case.id_, missing), dl, _PARTICIPANT, case.id_
        )

        assert refs == [
            ObjectReference(
                object_id=missing,
                source=ObjectFetchSource.CASE_HOST,
                host_actor_id=CASE_MANAGER_ID,
                case_id=case.id_,
                use=ObjectFetchUse.STORE,
            )
        ]

    @pytest.mark.spec("AKM-05-007")
    @pytest.mark.spec("VAM-01-009")
    def test_a_bare_object_inside_an_inline_activity_is_the_one_fetched(
        self,
    ):
        """``Accept(Invite(<id>))``: the Invite's bare object is fetched."""
        dl = _replica()
        case = make_case_with_case_manager(dl)
        missing = "urn:uuid:inner-not-held"
        activity = parse_activity(
            {
                "type": "Accept",
                "id": "https://example.org/activities/a-nested",
                "published": "2026-10-26T12:00:00Z",
                "actor": CASE_MANAGER_ID,
                "object": {
                    "type": "Invite",
                    "id": "https://example.org/activities/invite-1",
                    "published": "2026-10-26T12:00:00Z",
                    "actor": _PARTICIPANT,
                    "object": missing,
                    "context": case.id_,
                },
                "context": case.id_,
                "to": [_PARTICIPANT],
            }
        )
        event = extract_event(activity)
        assert (
            event.semantic_type is MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
        )

        refs = references_to_fetch(event, dl, _PARTICIPANT, case.id_)

        assert [r.object_id for r in refs] == [missing]

    @pytest.mark.spec("AKM-05-007")
    @pytest.mark.spec("VAM-01-009")
    def test_a_bare_object_two_activities_deep_is_the_one_fetched(self):
        """``Undo(Accept(Invite(<id>)))``: the innermost bare id is fetched.

        The replica holds the middle ``Accept``, so a fetch that looked only
        one level down would find it held and fetch nothing.
        """
        dl = _replica()
        case = make_case_with_case_manager(dl)
        missing = "urn:uuid:innermost-not-held"
        accept = {
            "type": "Accept",
            "id": "https://example.org/activities/accept-held",
            "published": "2026-10-26T12:00:00Z",
            "actor": _PARTICIPANT,
            "object": {
                "type": "Invite",
                "id": "https://example.org/activities/invite-2",
                "published": "2026-10-26T12:00:00Z",
                "actor": CASE_MANAGER_ID,
                "object": missing,
                "context": case.id_,
            },
            "context": case.id_,
        }
        dl.create(parse_activity(accept))
        activity = parse_activity(
            {
                "type": "Undo",
                "id": "https://example.org/activities/undo-nested",
                "published": "2026-10-26T12:00:00Z",
                "actor": CASE_MANAGER_ID,
                "object": accept,
                "context": case.id_,
                "to": [_PARTICIPANT],
            }
        )
        event = extract_event(activity)
        assert (
            event.semantic_type is MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
        )

        refs = references_to_fetch(event, dl, _PARTICIPANT, case.id_)

        assert [r.object_id for r in refs] == [missing]

    @pytest.mark.spec("AKM-05-011")
    @pytest.mark.spec("AKM-05-007")
    def test_the_case_manager_fetches_nothing_from_itself(self):
        dl = _replica(CASE_MANAGER_ID)
        case = make_case_with_case_manager(dl)

        refs = references_to_fetch(
            _unresolvable(case.id_, "urn:uuid:not-held"),
            dl,
            CASE_MANAGER_ID,
            case.id_,
        )

        assert refs == []

    @pytest.mark.spec("AKM-05-007")
    def test_nothing_is_fetched_for_a_case_the_receiver_does_not_hold(self):
        dl = _replica()

        refs = references_to_fetch(
            _unresolvable("https://example.org/cases/unknown", "urn:uuid:x"),
            dl,
            _PARTICIPANT,
            "https://example.org/cases/unknown",
        )

        assert refs == []

    @pytest.mark.spec("AKM-05-011")
    @pytest.mark.spec("AKM-05-007")
    def test_a_ledger_entry_is_never_fetched(self):
        """Replication carries its entry inline; replay needs no fetch."""
        dl = _replica()
        case = make_case_with_case_manager(dl)

        refs = references_to_fetch(
            _unresolvable(case.id_, f"{case.id_}/log/3"),
            dl,
            _PARTICIPANT,
            case.id_,
        )

        assert refs == []

    @pytest.mark.spec("AKM-05-012")
    @pytest.mark.spec("AKM-05-007")
    def test_an_object_the_receiver_holds_is_not_fetched(self):
        dl = _replica()
        case = make_case_with_case_manager(dl)
        embargo = _embargo(case.id_)
        dl.save(embargo)

        refs = references_to_fetch(
            _unresolvable(case.id_, embargo.id_), dl, _PARTICIPANT, case.id_
        )

        assert refs == []

    @pytest.mark.spec("CP-01-014")
    @pytest.mark.spec("CP-01-009")
    def test_a_proposers_profile_named_by_id_is_fetched_from_the_proposer(
        self,
    ):
        dl = _replica(_CASE_ACTOR)

        refs = references_to_fetch(
            _proposal(_PARTICIPANT), dl, _CASE_ACTOR, None
        )

        assert refs == [
            ObjectReference(
                object_id=_PARTICIPANT,
                source=ObjectFetchSource.ACTOR_PROFILE,
                host_actor_id=_PARTICIPANT,
                use=ObjectFetchUse.HAND_OFF,
            )
        ]

    @pytest.mark.spec("CP-01-010")
    def test_an_inline_proposer_profile_is_not_fetched(self):
        dl = _replica(_CASE_ACTOR)
        profile = {"type": "Organization", "id": _PARTICIPANT}

        assert references_to_fetch(_proposal(profile), dl, _CASE_ACTOR) == []

    @pytest.mark.spec("EMB-18-007")
    def test_a_replica_fetches_the_replaced_embargo_it_cannot_read(self):
        dl = _replica()
        case = make_case_with_case_manager(dl)
        replaced = _embargo(case.id_)
        activate(case, replaced.id_)
        dl.save(case)
        revision = _embargo(case.id_, days=10)

        refs = references_to_fetch(_announce(case, revision), dl, _PARTICIPANT)

        assert [r.object_id for r in refs] == [replaced.id_]
        assert refs[0].source is ObjectFetchSource.CASE_HOST
        assert refs[0].use is ObjectFetchUse.STORE

    @pytest.mark.spec("EMB-18-007")
    def test_a_replica_holding_the_replaced_embargo_fetches_nothing(self):
        dl = _replica()
        case = make_case_with_case_manager(dl)
        replaced = _embargo(case.id_)
        dl.save(replaced)
        activate(case, replaced)
        dl.save(case)

        refs = references_to_fetch(
            _announce(case, _embargo(case.id_, days=10)), dl, _PARTICIPANT
        )

        assert refs == []

    @pytest.mark.spec("EMB-18-007")
    def test_the_case_manager_does_not_fetch_the_replaced_embargo(self):
        dl = _replica(CASE_MANAGER_ID)
        case = make_case_with_case_manager(dl)
        activate(case, _embargo(case.id_).id_)
        dl.save(case)

        refs = references_to_fetch(
            _announce(case, _embargo(case.id_, days=10)), dl, CASE_MANAGER_ID
        )

        assert refs == []

    @pytest.mark.spec("EMB-18-007")
    def test_an_announced_embargo_that_is_the_active_one_fetches_nothing(
        self,
    ):
        dl = _replica()
        case = make_case_with_case_manager(dl)
        active = _embargo(case.id_)
        activate(case, active.id_)
        dl.save(case)

        refs = references_to_fetch(_announce(case, active), dl, _PARTICIPANT)

        assert refs == []

    @pytest.mark.spec("AKM-05-007")
    def test_a_case_naming_no_case_manager_has_no_one_to_fetch_from(self):
        dl = _replica()
        case = VulnerabilityCase(
            attributed_to="https://example.org/actors/owner", name="No CM"
        )
        dl.save(case)

        refs = references_to_fetch(
            _unresolvable(case.id_, "urn:uuid:x"), dl, _PARTICIPANT, case.id_
        )

        assert refs == []


class TestWithFetchedObject:
    _REF = ObjectReference(
        object_id=_PARTICIPANT,
        source=ObjectFetchSource.ACTOR_PROFILE,
        host_actor_id=_PARTICIPANT,
        use=ObjectFetchUse.HAND_OFF,
    )

    @pytest.mark.spec("CP-01-009")
    def test_the_fetched_profile_becomes_the_proposals_profile(self):
        profile = VultronOrganization(id_=_PARTICIPANT, name="Vendor")

        event = with_fetched_object(
            _proposal(_PARTICIPANT), self._REF, profile
        )

        assert getattr(event, "proposer_profile", None) == profile

    @pytest.mark.spec("CP-01-009")
    def test_a_fetched_object_that_is_not_the_one_named_is_refused(self):
        other = VultronOrganization(id_=_OUTSIDER)

        with pytest.raises(VultronValidationError, match="is not the"):
            with_fetched_object(_proposal(_PARTICIPANT), self._REF, other)

    @pytest.mark.spec("CP-01-009")
    def test_a_fetched_object_that_is_not_a_profile_is_refused(self):
        report = VulnerabilityReport(id_=_PARTICIPANT, name="not a profile")

        with pytest.raises(VultronValidationError, match="not an actor"):
            with_fetched_object(_proposal(_PARTICIPANT), self._REF, report)

    def test_an_event_with_no_slot_for_it_is_refused(self):
        dl = _replica()
        case = make_case_with_case_manager(dl)
        profile = VultronOrganization(id_=_PARTICIPANT)

        with pytest.raises(VultronValidationError, match="no slot"):
            with_fetched_object(
                _unresolvable(case.id_, "urn:uuid:x"), self._REF, profile
            )


class TestCaseObjectForParticipant:
    def _host(self) -> tuple[SqliteDataLayer, VulnerabilityCase]:
        dl = _replica(CASE_MANAGER_ID)
        case = make_case_with_case_manager(dl)
        _seat(dl, case, _PARTICIPANT)
        return dl, case

    @pytest.mark.spec("AKM-05-006")
    def test_an_embargo_the_case_names_is_served_to_a_participant(self):
        dl, case = self._host()
        embargo = _embargo("https://example.org/cases/carried-elsewhere")
        dl.save(embargo)
        # Proposed, not active: a participant is active under an embargo in
        # force only as its signatory, which is not what this test is about.
        propose(case, embargo)
        dl.save(case)

        found = case_object_for_participant(
            dl, CASE_MANAGER_ID, case.id_, embargo.id_, _PARTICIPANT
        )

        assert isinstance(found, EmbargoEvent)
        assert found.id_ == embargo.id_

    @pytest.mark.spec("AKM-05-006")
    def test_the_case_itself_is_served(self):
        dl, case = self._host()

        found = case_object_for_participant(
            dl, CASE_MANAGER_ID, case.id_, case.id_, f"{_PARTICIPANT}/"
        )

        assert isinstance(found, VulnerabilityCase)

    @pytest.mark.spec("AKM-05-009")
    @pytest.mark.spec("AKM-05-006")
    def test_a_non_participant_is_refused(self):
        dl, case = self._host()

        with pytest.raises(VultronNotACaseParticipantError):
            case_object_for_participant(
                dl, CASE_MANAGER_ID, case.id_, case.id_, _OUTSIDER
            )

    @pytest.mark.spec("AKM-05-006")
    def test_a_removed_participant_is_refused(self):
        dl, case = self._host()
        participant = dl.read(case.actor_participant_index[_PARTICIPANT])
        assert isinstance(participant, CaseParticipant)
        participant.record_removal("https://example.org/activities/remove-1")
        dl.save(participant)

        with pytest.raises(VultronNotACaseParticipantError):
            case_object_for_participant(
                dl, CASE_MANAGER_ID, case.id_, case.id_, _PARTICIPANT
            )

    @pytest.mark.spec("AKM-05-006")
    @pytest.mark.spec("CM-23-004")
    def test_a_participant_that_has_closed_is_refused(self):
        """A closed participant is sent nothing further, so it reads nothing."""
        dl, case = self._host()
        participant = dl.read(case.actor_participant_index[_PARTICIPANT])
        assert isinstance(participant, CaseParticipant)
        participant.participant_statuses = [
            ParticipantStatus(
                context=case.id_,
                attributed_to=_PARTICIPANT,
                rm=RmDimension(state=RM.CLOSED),
            )
        ]
        dl.save(participant)

        with pytest.raises(VultronNotACaseParticipantError):
            case_object_for_participant(
                dl, CASE_MANAGER_ID, case.id_, case.id_, _PARTICIPANT
            )

    @pytest.mark.spec("AKM-05-009")
    @pytest.mark.spec("AKM-05-006")
    def test_an_object_the_case_does_not_name_is_not_found(self):
        dl, case = self._host()
        elsewhere = _embargo("https://example.org/cases/other")
        dl.save(elsewhere)

        with pytest.raises(VultronNotFoundError):
            case_object_for_participant(
                dl, CASE_MANAGER_ID, case.id_, elsewhere.id_, _PARTICIPANT
            )

    @pytest.mark.spec("AKM-05-006")
    def test_an_object_scoped_to_the_case_by_its_context_is_served(self):
        dl, case = self._host()
        scoped = _embargo(case.id_)
        dl.save(scoped)

        found = case_object_for_participant(
            dl, CASE_MANAGER_ID, case.id_, scoped.id_, _PARTICIPANT
        )

        assert getattr(found, "id_", None) == scoped.id_

    @pytest.mark.spec("AKM-05-006")
    def test_an_object_the_host_does_not_hold_is_not_found(self):
        dl, case = self._host()

        with pytest.raises(VultronNotFoundError):
            case_object_for_participant(
                dl, CASE_MANAGER_ID, case.id_, "urn:uuid:absent", _PARTICIPANT
            )

    @pytest.mark.spec("AKM-05-006")
    def test_an_actor_that_is_not_the_case_manager_serves_nothing(self):
        """A participant's replica is not the case host."""
        dl, case = self._host()

        with pytest.raises(VultronNotFoundError):
            case_object_for_participant(
                dl, _PARTICIPANT, case.id_, case.id_, _PARTICIPANT
            )

    @pytest.mark.spec("AKM-05-009")
    @pytest.mark.spec("AKM-05-006")
    def test_a_case_the_host_does_not_hold_is_not_found(self):
        dl, _ = self._host()

        with pytest.raises(VultronNotFoundError):
            case_object_for_participant(
                dl,
                CASE_MANAGER_ID,
                "https://example.org/cases/unknown",
                "urn:uuid:x",
                _PARTICIPANT,
            )
