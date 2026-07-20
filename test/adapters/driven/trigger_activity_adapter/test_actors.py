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

"""Unit tests for TriggerActivityAdapter actor-domain methods.

Covers invitations, recommendations, participant management, and
CASE_MANAGER delegation.
"""

import pytest

from vultron.errors import VultronValidationError
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    VulnerabilityCaseStub,
)

_ACTOR = "https://example.org/actors/coordinator"
_INVITEE = "https://example.org/actors/vendor"
_CASE_ID = "https://example.org/cases/case-001"


def _make_case(dl) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(name="CVE-2025-001")
    dl.create(case)
    return case


def _make_participant(dl, case_id: str) -> as_CaseParticipant:
    participant = as_CaseParticipant(
        context=case_id,
        attributed_to=_INVITEE,
    )
    dl.create(participant)
    return participant


class TestInviteActorToCase:
    def test_returns_id_and_dict(self, adapter, dl):
        activity_id, activity_dict = adapter.invite_actor_to_case(
            invitee_id=_INVITEE,
            case_id=_CASE_ID,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)
        assert "id" in activity_dict

    def test_persists_invite_activity(self, adapter, dl):
        activity_id, _ = adapter.invite_actor_to_case(
            invitee_id=_INVITEE,
            case_id=_CASE_ID,
            actor=_ACTOR,
            to=[_INVITEE],
        )

        assert dl.read(activity_id) is not None

    def test_attributed_to_included_when_provided(self, adapter):
        owner = "https://example.org/actors/owner"

        _, activity_dict = adapter.invite_actor_to_case(
            invitee_id=_INVITEE,
            case_id=_CASE_ID,
            actor=_ACTOR,
            attributed_to=owner,
        )

        assert activity_dict.get("attributedTo") == owner


class TestAcceptCaseInvite:
    def _make_invite(self, dl) -> str:
        invitee = as_Service(id_=_INVITEE, name="Vendor")
        # Store invitee so _rehydrate_fields can expand the dehydrated
        # object_ URI back to a full actor when reading the invite.
        dl.create(invitee)
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=_CASE_ID),
            actor=_ACTOR,
            to=[_INVITEE],
        )
        dl.create(invite)
        return invite.id_

    def test_returns_id_and_dict(self, adapter, dl):
        invite_id = self._make_invite(dl)

        activity_id, activity_dict = adapter.accept_case_invite(
            invite_id=invite_id,
            actor=_INVITEE,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)

    def test_persists_accept_activity(self, adapter, dl):
        invite_id = self._make_invite(dl)

        activity_id, _ = adapter.accept_case_invite(
            invite_id=invite_id,
            actor=_INVITEE,
        )

        assert dl.read(activity_id) is not None

    def test_raises_on_invite_without_routable_actor(
        self, adapter, dl, monkeypatch
    ):
        """An invite whose actor cannot be resolved raises VultronValidationError."""
        invite_id = self._make_invite(dl)

        import vultron.adapters.driven.trigger_activity_adapter.actors as _mod

        monkeypatch.setattr(_mod, "_as_id", lambda _: None)

        with pytest.raises(VultronValidationError):
            adapter.accept_case_invite(invite_id=invite_id, actor=_INVITEE)


class TestSuggestActorToCase:
    def test_returns_id_and_dict(self, adapter):
        activity_id, activity_dict = adapter.suggest_actor_to_case(
            recommended_id=_INVITEE,
            case_id=_CASE_ID,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)

    def test_persists_offer_activity(self, adapter, dl):
        activity_id, _ = adapter.suggest_actor_to_case(
            recommended_id=_INVITEE,
            case_id=_CASE_ID,
            actor=_ACTOR,
            to=[_ACTOR],
        )

        assert dl.read(activity_id) is not None


class TestAddParticipantToCase:
    def test_returns_activity_id(self, adapter, dl):
        case = _make_case(dl)
        participant = _make_participant(dl, case.id_)

        activity_id = adapter.add_participant_to_case(
            participant_id=participant.id_,
            case_id=case.id_,
            actor=_ACTOR,
        )

        assert activity_id

    def test_persists_add_activity(self, adapter, dl):
        case = _make_case(dl)
        participant = _make_participant(dl, case.id_)

        activity_id = adapter.add_participant_to_case(
            participant_id=participant.id_,
            case_id=case.id_,
            actor=_ACTOR,
            to=[_ACTOR],
        )

        assert dl.read(activity_id) is not None


class TestOfferCaseManagerRole:
    def test_returns_activity_id_and_dict(self, adapter, dl):
        case = _make_case(dl)
        participant = _make_participant(dl, case.id_)

        activity_id, activity_dict = adapter.offer_case_manager_role(
            case_id=case.id_,
            participant_id=participant.id_,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)
        assert activity_dict.get("type") == "Offer"

    def test_persists_offer_activity(self, adapter, dl):
        case = _make_case(dl)
        participant = _make_participant(dl, case.id_)

        activity_id, _ = adapter.offer_case_manager_role(
            case_id=case.id_,
            participant_id=participant.id_,
            actor=_ACTOR,
            to=[_INVITEE],
        )

        assert dl.read(activity_id) is not None


class TestAcceptCaseManagerRole:
    def test_returns_activity_id(self, adapter, dl):
        case = _make_case(dl)
        participant = _make_participant(dl, case.id_)

        offer_id, _ = adapter.offer_case_manager_role(
            case_id=case.id_,
            participant_id=participant.id_,
            actor=_ACTOR,
        )

        activity_id = adapter.accept_case_manager_role(
            offer_id=offer_id,
            case_id=case.id_,
            participant_id=participant.id_,
            vendor_id=_ACTOR,
            actor=_INVITEE,
        )

        assert activity_id

    def test_persists_accept_activity(self, adapter, dl):
        case = _make_case(dl)
        participant = _make_participant(dl, case.id_)

        offer_id, _ = adapter.offer_case_manager_role(
            case_id=case.id_,
            participant_id=participant.id_,
            actor=_ACTOR,
        )

        activity_id = adapter.accept_case_manager_role(
            offer_id=offer_id,
            case_id=case.id_,
            participant_id=participant.id_,
            vendor_id=_ACTOR,
            actor=_INVITEE,
            to=[_ACTOR],
        )

        assert dl.read(activity_id) is not None
