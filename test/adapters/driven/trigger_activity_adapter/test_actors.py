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

import json

import pytest

from test.support.received import archive_received
from vultron.errors import (
    VultronActivityConstructionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.factories import (
    offer_case_participant_activity,
    recommend_actor_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseStub,
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


class TestInviteActorToCaseWithInlineEmbargo:
    """A case seeded from a sealed Announce carries ``active_embargo`` inline.

    ``VulnerabilityCase.inline_required_refs`` names ``active_embargo``, so a
    stored case may hold the ``EmbargoEvent`` object rather than its id.  The
    adapter used to hand that object to ``dl.read`` and the Coordinator's
    invite trigger failed with "expected string or bytes-like object, got
    'EmbargoEvent'" (fvcv-handoff, #3923).  The stub must still carry the
    embargo's id and end time (CM-17-002).
    """

    @pytest.mark.spec("CM-17-002")
    def test_invite_stub_carries_the_inline_embargo(self, adapter, dl):
        from vultron.core.models._helpers import days_from_now_utc
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_status import CaseStatus
        from vultron.core.models.dimensions import EmDimension
        from vultron.core.models.embargo_event import EmbargoEvent
        from vultron.core.states.em import EM

        case_id = "https://example.org/cases/case-inline-embargo"
        embargo = EmbargoEvent(context=case_id, end_time=days_from_now_utc(30))
        case = VulnerabilityCase(
            id_=case_id,
            name="CVE-2025-009",
            attributed_to=_ACTOR,
            case_statuses=[
                CaseStatus(
                    context=case_id,
                    attributed_to=_ACTOR,
                    em=EmDimension(state=EM.ACTIVE),
                )
            ],
            active_embargo=embargo,
        )
        dl.create(case)
        stored = dl.read(case_id)
        assert isinstance(stored.active_embargo, EmbargoEvent), (
            "precondition: the store hands the embargo back inline"
        )

        _, blob = adapter.invite_actor_to_case(
            invitee_id=_INVITEE, case_id=case_id, actor=_ACTOR, to=[_INVITEE]
        )

        target = json.loads(blob)["target"]
        assert target["type"] == "VulnerabilityCaseStub"
        assert target["id"] == f"{case_id}/stub"
        assert target["caseId"] == case_id
        assert target["activeEmbargo"]["id"] == embargo.id_
        assert target["activeEmbargo"]["endTime"]
        assert target["caseStatus"]["emState"] == "ACTIVE"


class TestInviteActorToCase:
    def test_returns_id_and_dict(self, adapter, dl):
        activity_id, activity_dict = adapter.invite_actor_to_case(
            invitee_id=_INVITEE,
            case_id=_CASE_ID,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, str)
        assert "id" in json.loads(activity_dict)

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

        assert json.loads(activity_dict).get("attributedTo") == owner


class TestAcceptCaseInvite:
    def _make_invite(self, dl) -> str:
        invitee = as_Service(id_=_INVITEE, name="Vendor")
        # Store invitee so _rehydrate_fields can expand the dehydrated
        # object_ URI back to a full actor when reading the invite.
        dl.create(invitee)
        invite = rm_invite_to_case_activity(
            invitee,
            target=as_VulnerabilityCaseStub(case_id=_CASE_ID),
            actor=_ACTOR,
            to=[_INVITEE],
        )
        # A received Invite that reached its use case is archived by intake
        # (CLP-10-017, ADR-0111).
        archive_received(dl, invite)
        return invite.id_

    def test_returns_id_and_dict(self, adapter, dl):
        invite_id = self._make_invite(dl)

        activity_id, activity_dict = adapter.accept_case_invite(
            invite_id=invite_id,
            actor=_INVITEE,
        )

        assert activity_id
        assert isinstance(activity_dict, str)

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

    def test_verbatim_reconstitution_preserves_invite_id(self, adapter, dl):
        """Accept(Invite) must embed the original invite id in in_reply_to.

        DL-06-004: envelope reconstitution reads the stored invite and embeds
        the verbatim original as the ``object_`` of the Accept.  The
        ``in_reply_to`` field (set automatically by the factory's
        model_validator) MUST equal the original invite id.
        """
        invite_id = self._make_invite(dl)

        activity_id, _ = adapter.accept_case_invite(
            invite_id=invite_id,
            actor=_INVITEE,
        )

        accept = dl.read(activity_id)
        assert accept is not None
        assert getattr(accept, "in_reply_to", None) == invite_id

    def test_verbatim_reconstitution_preserves_inline_object(
        self, adapter, dl
    ):
        """Accept(Invite) object_ must be a full inline object, not a bare URI.

        DL-06-004: the original invite activity is reconstituted verbatim as
        the ``object_`` of the Accept; it must have its own ``id`` field set
        (i.e., not be a bare string reference).
        """
        invite_id = self._make_invite(dl)

        _, activity_dict = adapter.accept_case_invite(
            invite_id=invite_id,
            actor=_INVITEE,
        )

        obj = json.loads(activity_dict).get("object")
        assert isinstance(obj, dict), (
            "object_ must be an inline dict, not a URI"
        )
        assert obj.get("id") == invite_id

    @pytest.mark.spec("AKM-02-003")
    @pytest.mark.spec("CM-11-013")
    def test_embedded_invite_keeps_the_case_stub(self, adapter, dl):
        """The reply embeds the Invite as received, stub target and all.

        The stub's ``type`` is what tells the reply apart from a reply to a
        full-case Invite (CM-11-013), and its ``caseId`` names the case
        (AKM-02-003 permits the stub in ``target``).
        """
        invite_id = self._make_invite(dl)

        _, activity_dict = adapter.accept_case_invite(
            invite_id=invite_id, actor=_INVITEE
        )

        target = json.loads(activity_dict)["object"]["target"]
        assert target["type"] == "VulnerabilityCaseStub"
        assert target["caseId"] == _CASE_ID

    @pytest.mark.spec("AKM-02-003")
    def test_an_invite_the_inbox_holds_until_the_case_bootstrap_is_answered(
        self, adapter, dl
    ):
        """A deferred Invite has not reached intake; the inbox holds it bare.

        The invitee holds no case before its Accept brings the bootstrap, so
        the inbox defers the Invite and keeps it under the sender's id.  That
        copy is the one the invitee answers.
        """
        invite = rm_invite_to_case_activity(
            _INVITEE,
            target=as_VulnerabilityCaseStub(case_id=_CASE_ID),
            actor=_ACTOR,
            to=[_INVITEE],
        )
        dl.create(invite)

        _, activity_dict = adapter.accept_case_invite(
            invite_id=invite.id_, actor=_INVITEE
        )

        accept = json.loads(activity_dict)
        assert accept["object"]["id"] == invite.id_
        assert accept["object"]["target"]["caseId"] == _CASE_ID

    def test_an_invite_this_store_never_received_is_not_found(
        self, adapter, dl
    ):
        with pytest.raises(VultronNotFoundError):
            adapter.accept_case_invite(
                invite_id="urn:uuid:never-received", actor=_INVITEE
            )

    def test_a_held_record_that_is_not_a_model_is_refused(
        self, adapter, dl, monkeypatch
    ):
        from vultron.adapters.driven.trigger_activity_adapter import actors

        monkeypatch.setattr(
            actors, "read_received_activity", lambda *_args: object()
        )

        with pytest.raises(VultronValidationError, match="not as an activity"):
            adapter.accept_case_invite(
                invite_id="urn:uuid:held-oddly", actor=_INVITEE
            )

    @pytest.mark.parametrize(
        "held_target",
        [{"type": "VulnerabilityCase"}, {"type": "VulnerabilityCaseStub"}],
        ids=["case-without-id", "stub-without-case-id"],
    )
    def test_a_held_invite_that_does_not_name_its_case_is_refused(
        self, adapter, monkeypatch, held_target
    ):
        from pydantic import BaseModel

        from vultron.adapters.driven.trigger_activity_adapter import actors

        class _Held(BaseModel):
            actor: str = _ACTOR
            target: dict[str, str] = held_target

        monkeypatch.setattr(
            actors, "read_received_activity", lambda *_args: _Held()
        )

        with pytest.raises(
            VultronValidationError, match="does not validate as an Invite"
        ):
            adapter.accept_case_invite(
                invite_id="urn:uuid:held-without-case-id", actor=_INVITEE
            )

    def test_a_held_record_that_does_not_validate_as_an_invite_is_refused(
        self, adapter, monkeypatch
    ):
        """The adapter validates the held record into ``as_Invite`` at its
        edge (ADR-0032), so a malformed one is refused there."""
        from pydantic import BaseModel

        from vultron.adapters.driven.trigger_activity_adapter import actors

        class _Held(BaseModel):
            type: str = "Invite"
            actor: int = 42
            target: str = _CASE_ID

        monkeypatch.setattr(
            actors, "read_received_activity", lambda *_args: _Held()
        )

        with pytest.raises(
            VultronValidationError, match="does not validate as an Invite"
        ):
            adapter.accept_case_invite(
                invite_id="urn:uuid:held-malformed", actor=_INVITEE
            )

    def test_an_archived_activity_that_is_not_an_invite_is_refused(
        self, adapter, dl
    ):
        offer = recommend_actor_activity(
            _INVITEE,
            target=as_VulnerabilityCase(id_=_CASE_ID, name="Not an Invite"),
            actor=_ACTOR,
            to=[_INVITEE],
        )
        archive_received(dl, offer)

        with pytest.raises(
            VultronActivityConstructionError, match="not a case Invite"
        ):
            adapter.accept_case_invite(invite_id=offer.id_, actor=_INVITEE)


class TestSuggestActorToCase:
    def test_returns_id_and_dict(self, adapter):
        activity_id, activity_dict = adapter.suggest_actor_to_case(
            recommended_id=_INVITEE,
            case_id=_CASE_ID,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, str)

    def test_persists_offer_activity(self, adapter, dl):
        activity_id, _ = adapter.suggest_actor_to_case(
            recommended_id=_INVITEE,
            case_id=_CASE_ID,
            actor=_ACTOR,
            to=[_ACTOR],
        )

        assert dl.read(activity_id) is not None


class TestAddParticipantToCase:
    def test_returns_id_and_blob(self, adapter, dl):
        case = _make_case(dl)
        participant = _make_participant(dl, case.id_)

        activity_id, blob = adapter.add_participant_to_case(
            participant_id=participant.id_,
            case_id=case.id_,
            actor=_ACTOR,
        )

        assert activity_id
        body = json.loads(blob)
        assert body["type"] == "Add"
        assert body["object"]["type"] == "CaseParticipant"
        # The factory, not the emitting node, completes ``context`` (#2654).
        assert body["context"] == case.id_

    def test_persists_add_activity(self, adapter, dl):
        case = _make_case(dl)
        participant = _make_participant(dl, case.id_)

        activity_id, _blob = adapter.add_participant_to_case(
            participant_id=participant.id_,
            case_id=case.id_,
            actor=_ACTOR,
            to=[_ACTOR],
        )

        assert dl.read(activity_id) is not None


class TestAcceptCaseParticipantOffer:
    def _make_cp_offer(self, dl) -> str:
        vendor = as_Service(id_=_INVITEE, name="Vendor")
        dl.create(vendor)
        offer = offer_case_participant_activity(
            recommended=vendor,
            actor=_ACTOR,
            to=[_ACTOR],
        )
        # Store the nested CaseParticipant so _rehydrate_fields can expand the
        # dehydrated object_ URI back to a full participant when reading the offer.
        dl.create(offer.object_)
        dl.create(offer)
        return offer.id_

    def test_returns_id_and_dict(self, adapter, dl):
        cp_offer_id = self._make_cp_offer(dl)

        activity_id, activity_dict = adapter.accept_case_participant_offer(
            cp_offer_id=cp_offer_id,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, str)

    def test_verbatim_reconstitution_preserves_inline_object(
        self, adapter, dl
    ):
        """Accept(Offer(CaseParticipant)) object_ must embed the original offer inline.

        DL-06-004: the adapter reads the stored offer activity and passes it
        verbatim as ``object_`` of the Accept.  The serialised dict MUST
        contain the offer id as ``object.id``, not a bare URI string.
        """
        cp_offer_id = self._make_cp_offer(dl)

        _, activity_dict = adapter.accept_case_participant_offer(
            cp_offer_id=cp_offer_id,
            actor=_ACTOR,
        )

        obj = json.loads(activity_dict).get("object")
        assert isinstance(obj, dict), (
            "object_ must be an inline dict, not a URI"
        )
        assert obj.get("id") == cp_offer_id


_VENDOR = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/actors/case-actor"
_OFFER_ID = "https://example.org/activities/offer-role-1"


def _make_role_case(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case = as_VulnerabilityCase(id_=_CASE_ID, name="Role Test Case")
    dl.create(case)
    return case


class TestAcceptCaseParticipantRole:
    """Tests for accept_case_participant_role adapter method (ADR-0039)."""

    def test_returns_id_and_dict(self, adapter, dl):
        _make_role_case(dl)
        from vultron.enums.roles import CVDRole

        activity_id, activity_dict = adapter.accept_case_participant_role(
            offer_id=_OFFER_ID,
            case_id=_CASE_ID,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=_CASE_ACTOR,
            vendor_id=_VENDOR,
            actor=_CASE_ACTOR,
            to=[_VENDOR],
        )

        assert activity_id
        assert isinstance(activity_dict, str)
        assert "id" in json.loads(activity_dict)

    def test_persists_accept_activity(self, adapter, dl):
        _make_role_case(dl)
        from vultron.enums.roles import CVDRole

        activity_id, _ = adapter.accept_case_participant_role(
            offer_id=_OFFER_ID,
            case_id=_CASE_ID,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=_CASE_ACTOR,
            vendor_id=_VENDOR,
            actor=_CASE_ACTOR,
            to=[_VENDOR],
        )

        assert dl.read(activity_id) is not None


class TestRejectCaseParticipantRole:
    """Tests for reject_case_participant_role adapter method (ADR-0039)."""

    def test_returns_activity_id(self, adapter, dl):
        _make_role_case(dl)
        from vultron.enums.roles import CVDRole

        activity_id, activity_json = adapter.reject_case_participant_role(
            offer_id=_OFFER_ID,
            case_id=_CASE_ID,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=_CASE_ACTOR,
            vendor_id=_VENDOR,
            actor=_CASE_ACTOR,
            to=[_VENDOR],
        )

        assert activity_id
        assert activity_json

    def test_persists_reject_activity(self, adapter, dl):
        _make_role_case(dl)
        from vultron.enums.roles import CVDRole

        activity_id, _ = adapter.reject_case_participant_role(
            offer_id=_OFFER_ID,
            case_id=_CASE_ID,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=_CASE_ACTOR,
            vendor_id=_VENDOR,
            actor=_CASE_ACTOR,
            to=[_VENDOR],
        )

        assert dl.read(activity_id) is not None
