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
from datetime import UTC, datetime

import pytest

from test.support.case_owner import CASE_OWNER_ID
from test.support.embargo_register import register
from test.support.received import archive_received
from vultron.errors import (
    VultronActivityConstructionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.factories import (
    offer_case_ownership_transfer_activity,
    offer_case_participant_activity,
    recommend_actor_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Invite,
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
#: A receiver refuses a stub with no summary at parse (MV-10-001), so the
#: Invite a test delivers carries one.
_STUB = as_VulnerabilityCaseStub(case_id=_CASE_ID, summary="A case to join")


def _make_case(dl) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, name="CVE-2025-001"
    )
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
    'EmbargoEvent'" (rvcv-handoff, #3923).  The stub must still carry the
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
            stub_summary="Security issue — embargo active, details after acceptance",
            case_statuses=[
                CaseStatus(
                    context=case_id,
                    attributed_to=_ACTOR,
                    em=EmDimension(state=EM.ACTIVE),
                )
            ],
            embargo_register=register(active=embargo),
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


class TestInviteActorToCaseWithEmbargoHeldById:
    """A locally built case names its active embargo by id; the adapter reads
    the object from the store so the stub can embed it whole (CM-17-011)."""

    @staticmethod
    def _seed_case(dl, case_id: str, *, store_embargo: bool):
        from vultron.core.models._helpers import days_from_now_utc
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_status import CaseStatus
        from vultron.core.models.dimensions import EmDimension
        from vultron.core.models.embargo_event import EmbargoEvent
        from vultron.core.states.em import EM

        embargo = EmbargoEvent(
            context=case_id,
            name="Embargo for the stored-by-id case",
            attributed_to=_ACTOR,
            end_time=days_from_now_utc(30),
        )
        if store_embargo:
            dl.create(embargo)
        dl.create(
            VulnerabilityCase(
                id_=case_id,
                name="CVE-2025-013",
                attributed_to=_ACTOR,
                stub_summary="Security issue under embargo",
                case_statuses=[
                    CaseStatus(
                        context=case_id,
                        attributed_to=_ACTOR,
                        em=EmDimension(state=EM.ACTIVE),
                    )
                ],
                embargo_register=register(active=embargo.id_),
            )
        )
        return embargo

    @pytest.mark.spec("CM-17-011")
    def test_invite_stub_embeds_the_stored_embargo(self, adapter, dl):
        case_id = "https://example.org/cases/case-embargo-by-id"
        embargo = self._seed_case(dl, case_id, store_embargo=True)

        _, blob = adapter.invite_actor_to_case(
            invitee_id=_INVITEE, case_id=case_id, actor=_ACTOR, to=[_INVITEE]
        )

        expected = json.loads(
            embargo.model_dump_json(by_alias=True, exclude_none=True)
        )
        assert json.loads(blob)["target"]["activeEmbargo"] == expected

    @pytest.mark.spec("CM-17-011")
    def test_invite_is_refused_when_the_embargo_is_not_in_the_store(
        self, adapter, dl
    ):
        """No object to embed means no Invite, not a stub naming a bare id."""
        case_id = "https://example.org/cases/case-embargo-missing"
        self._seed_case(dl, case_id, store_embargo=False)

        with pytest.raises(
            VultronActivityConstructionError, match="CM-17-011"
        ):
            adapter.invite_actor_to_case(
                invitee_id=_INVITEE,
                case_id=case_id,
                actor=_ACTOR,
                to=[_INVITEE],
            )


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
            target=_STUB,
            actor=_ACTOR,
            to=[_INVITEE],
        )
        # A received Invite that reached its use case is archived by intake
        # as the body that arrived (CLP-10-017, ADR-0149).
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

    @pytest.mark.spec("DL-06-006")
    def test_an_invite_held_only_under_the_senders_id_is_not_answered(
        self, adapter, dl
    ):
        """A row under the sender's id is not a received Invite.

        Intake archives a stub Invite on arrival (PCR-06-005) and nothing
        holds it under the sender's id (#4871), so a bare row there is no
        Invite the invitee received.
        """
        invite = rm_invite_to_case_activity(
            _INVITEE,
            target=_STUB,
            actor=_ACTOR,
            to=[_INVITEE],
        )
        dl.create(invite)

        with pytest.raises(VultronNotFoundError):
            adapter.accept_case_invite(invite_id=invite.id_, actor=_INVITEE)

    def test_an_invite_this_store_never_received_is_not_found(
        self, adapter, dl
    ):
        with pytest.raises(VultronNotFoundError):
            adapter.accept_case_invite(
                invite_id="urn:uuid:never-received", actor=_INVITEE
            )

    @pytest.mark.spec("CM-11-013")
    @pytest.mark.parametrize(
        "held_target",
        [{"type": "VulnerabilityCase", "id": _CASE_ID}, _CASE_ID],
        ids=["full-case-target", "uri-target"],
    )
    def test_a_held_invite_that_does_not_carry_a_stub_is_refused(
        self, adapter, monkeypatch, held_target
    ):
        """Only a stub Invite is answered here, and a stub is recognised by
        its ``type`` alone (CM-11-013).  A stub that fails its own validation
        never gets this far: the parse of the archived body refuses it."""
        from vultron.adapters.driven.trigger_activity_adapter import actors

        held = as_Invite(
            actor=_ACTOR,
            object_=as_Service(id_=_INVITEE),
            target=held_target,
        )
        monkeypatch.setattr(
            actors, "read_received_as_received", lambda *_args: held
        )

        with pytest.raises(
            VultronActivityConstructionError, match="not a case Invite"
        ):
            adapter.accept_case_invite(
                invite_id="urn:uuid:held-without-a-stub", actor=_INVITEE
            )

    def test_an_archived_activity_that_is_not_an_invite_is_refused(
        self, adapter, dl
    ):
        offer = recommend_actor_activity(
            _INVITEE,
            target=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=_CASE_ID, name="Not an Invite"
            ),
            actor=_ACTOR,
            to=[_INVITEE],
        )
        archive_received(dl, offer)

        with pytest.raises(VultronValidationError, match="not as an Invite"):
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


class TestRemoveParticipantFromCase:
    """The CASE_MANAGER's removal notice (CM-31-006, CM-24)."""

    def test_returns_a_delegated_remove_naming_the_participant(
        self, adapter, dl
    ):
        case = _make_case(dl)
        participant = _make_participant(dl, case.id_)

        activity_id, blob = adapter.remove_participant_from_case(
            participant_id=participant.id_,
            case_id=case.id_,
            actor=_ACTOR,
            attributed_to=_INVITEE,
            to=[_INVITEE],
        )

        body = json.loads(blob)
        assert body["id"] == activity_id
        assert body["type"] == "Remove"
        assert body["actor"] == _ACTOR
        assert body["attributedTo"] == _INVITEE
        assert body["to"] == [_INVITEE]
        assert body["object"]["id"] == participant.id_
        assert body["target"] == case.id_
        assert body["context"] == case.id_
        assert dl.read(activity_id) is not None

    def test_unknown_participant_raises(self, adapter, dl):
        case = _make_case(dl)

        with pytest.raises(VultronNotFoundError):
            adapter.remove_participant_from_case(
                participant_id=f"{case.id_}/participants/missing",
                case_id=case.id_,
                actor=_ACTOR,
                attributed_to=_INVITEE,
                to=[_INVITEE],
            )


class TestAcceptCaseParticipantOffer:
    def _make_cp_offer(self, dl) -> str:
        vendor = as_Service(id_=_INVITEE, name="Vendor")
        dl.create(vendor)
        offer = offer_case_participant_activity(
            recommended=vendor,
            target=_CASE_ID,
            actor=_ACTOR,
            to=[_ACTOR],
        )
        # Held as intake archived it, participant inline, never under the
        # sender's id (DL-06-006).
        archive_received(dl, offer)
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

    def test_accept_embeds_the_participant_the_owner_received(
        self, adapter, dl
    ):
        """#3763: the Offer the owner received keeps its inline participant.

        Ingress stores neither the received Offer nor a participant record
        (DL-06-006), so the Accept reads the Offer from the intake archive,
        which holds it as the event carried it.
        """
        from vultron.adapters.driving.fastapi.inbox_orchestration import (
            FastAPIIngressAdapter,
        )

        case = _make_case(dl)
        vendor = as_Service(id_=_INVITEE, name="Vendor")
        offer = offer_case_participant_activity(
            recommended=vendor, target=case.id_, actor=_ACTOR, to=[_ACTOR]
        )
        FastAPIIngressAdapter(dl=dl).parse(
            offer.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
        archive_received(dl, offer)
        participant_id = getattr(offer.object_, "id_", None)
        assert participant_id is not None
        assert dl.read(participant_id) is None

        _, activity_dict = adapter.accept_case_participant_offer(
            cp_offer_id=offer.id_, actor=_ACTOR
        )

        embedded = json.loads(activity_dict)["object"]
        assert embedded["id"] == offer.id_
        assert isinstance(embedded["object"], dict)
        assert embedded["object"]["id"] == participant_id


_VENDOR = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/actors/case-actor"
_OFFER_ID = "https://example.org/activities/offer-role-1"


def _make_role_case(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=_CASE_ID, name="Role Test Case"
    )
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


@pytest.mark.spec("OX-06-002")
@pytest.mark.parametrize(
    "method", ["accept_case_participant_role", "reject_case_participant_role"]
)
def test_role_offer_answer_keeps_a_caller_supplied_id(adapter, dl, method):
    """A deterministic id survives the adapter, so a retry rebuilds it."""
    from vultron.enums.roles import CVDRole

    _make_role_case(dl)
    given_id = f"https://example.org/activities/{method}-given"

    activity_id, activity_json = getattr(adapter, method)(
        offer_id=_OFFER_ID,
        case_id=_CASE_ID,
        role=CVDRole.CASE_MANAGER,
        target_actor_id=_CASE_ACTOR,
        vendor_id=_VENDOR,
        actor=_CASE_ACTOR,
        to=[_VENDOR],
        id_=given_id,
    )

    assert activity_id == given_id
    assert json.loads(activity_json)["id"] == given_id
    assert dl.read(given_id) is not None


_OWNER = "https://example.org/actors/owner"


def _received_ownership_forward(dl) -> tuple[str, str]:
    """Archive the CASE_MANAGER's forward as the transferee's intake keeps it.

    Nothing is held under the forward's own id (DL-06-006).  Returns
    ``(offer_id, case_id)``.
    """
    case = _make_case(dl)
    offer = offer_case_ownership_transfer_activity(
        case=case,
        target=_INVITEE,
        actor=_ACTOR,
        attributed_to=_OWNER,
        to=[_INVITEE],
    )
    archive_received(dl, offer)
    assert dl.read(offer.id_) is None
    return offer.id_, case.id_


_OWNERSHIP_ANSWERS = [
    pytest.param("accept_case_ownership_transfer", "Accept", id="accept"),
    pytest.param("reject_case_ownership_transfer", "Reject", id="reject"),
]


class TestAnswerReceivedOwnershipOffer:
    """The transferee answers the forward from its archive (DL-06-006)."""

    @pytest.mark.spec("DL-06-006")
    @pytest.mark.spec("DL-06-004")
    @pytest.mark.parametrize(("method", "verb"), _OWNERSHIP_ANSWERS)
    def test_a_forward_held_only_as_received_is_answered(
        self, adapter, dl, method, verb
    ):
        offer_id, case_id = _received_ownership_forward(dl)

        _, blob = getattr(adapter, method)(offer_id=offer_id, actor=_INVITEE)

        body = json.loads(blob)
        assert body["type"] == verb
        assert body["object"]["id"] == offer_id
        assert body["object"]["object"]["id"] == case_id
        # With no ``to`` given, the reply goes to the forward's actor.
        assert body["to"] == [_ACTOR]
        assert dl.read(offer_id) is None

    @pytest.mark.parametrize(("method", "verb"), _OWNERSHIP_ANSWERS)
    def test_an_offer_this_store_does_not_hold_is_not_found(
        self, adapter, dl, method, verb
    ):
        with pytest.raises(VultronNotFoundError):
            getattr(adapter, method)(
                offer_id="urn:uuid:never-received", actor=_INVITEE
            )

    @pytest.mark.spec("DL-06-006")
    @pytest.mark.parametrize(("method", "verb"), _OWNERSHIP_ANSWERS)
    def test_an_offer_held_only_under_its_own_id_is_not_found(
        self, adapter, dl, method, verb
    ):
        """Only the archived Offer is answered, never one under its id (ADR-0148)."""
        case = _make_case(dl)
        offer = offer_case_ownership_transfer_activity(
            case=case,
            target=_INVITEE,
            actor=_ACTOR,
            attributed_to=_OWNER,
            to=[_INVITEE],
        )
        dl.create(offer)
        assert dl.read(offer.id_) is not None

        with pytest.raises(
            VultronNotFoundError, match=r"Offer\(VulnerabilityCase\)"
        ):
            getattr(adapter, method)(offer_id=offer.id_, actor=_INVITEE)
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-21-015")
    def test_the_owner_withdraws_the_proposal_it_sent(self, adapter, dl):
        """The owner's own proposal is held under its own id, and read there;
        the Undo names the proposal (ADR-0148)."""
        case = _make_case(dl)
        proposal_id, _ = adapter.propose_case_ownership_transfer(
            case_id=case.id_, transferee_id=_INVITEE, actor=_OWNER, to=[_ACTOR]
        )

        _, blob = adapter.withdraw_case_ownership_transfer(
            offer_id=proposal_id, actor=_OWNER, to=[_ACTOR]
        )

        body = json.loads(blob)
        assert body["type"] == "Undo"
        assert body["object"]["id"] == proposal_id
        assert body["object"]["object"]["type"] == "Offer"
        assert body["to"] == [_ACTOR]

    @pytest.mark.spec("CM-21-005")
    @pytest.mark.spec("CM-21-016")
    def test_the_proposal_nests_the_offer_it_asks_for(self, adapter, dl):
        case = _make_case(dl)
        deadline = datetime(2030, 1, 1, tzinfo=UTC)

        _, blob = adapter.propose_case_ownership_transfer(
            case_id=case.id_,
            transferee_id=_INVITEE,
            actor=_OWNER,
            to=[_ACTOR],
            end_time=deadline,
        )

        body = json.loads(blob)
        assert body["type"] == "Offer"
        assert body["context"] == case.id_
        assert body["to"] == [_ACTOR]
        inner = body["object"]
        assert inner["type"] == "Offer"
        assert inner["object"]["id"] == case.id_
        assert inner["target"]["id"] == _INVITEE
        assert inner["endTime"].startswith("2030-01-01")

    @pytest.mark.spec("CM-21-005")
    def test_the_offer_built_under_a_derived_id_is_built_once(
        self, adapter, dl
    ):
        """A retry under the same id hands back the sealed first build."""
        case = _make_case(dl)
        given_id = "urn:uuid:derived-ownership-offer"

        first = adapter.offer_case_ownership_transfer(
            case_id=case.id_,
            transferee_id=_INVITEE,
            actor=_ACTOR,
            attributed_to=_OWNER,
            id_=given_id,
        )
        again = adapter.offer_case_ownership_transfer(
            case_id=case.id_,
            transferee_id=_INVITEE,
            actor=_ACTOR,
            attributed_to=_OWNER,
            id_=given_id,
        )

        assert first == again
        body = json.loads(first[1])
        assert body["id"] == given_id
        assert body["context"] == case.id_
        assert body["attributedTo"] == _OWNER
