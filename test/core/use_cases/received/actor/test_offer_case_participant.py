#!/usr/bin/env python
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
"""Tests for Offer(CaseParticipant) round-trip received use cases (ISSUE-1332).

Covers:
- OfferCaseParticipantReceivedUseCase (Case Owner inbox)
- AcceptOfferCaseParticipantReceivedUseCase (CaseActor inbox)
- RejectOfferCaseParticipantReceivedUseCase (CaseActor inbox)
- TestAcceptOfferCaseParticipantRolesThreading (AC-1/AC-2, ISSUE-1406)
"""

import logging
from typing import Any, Literal, cast
from unittest.mock import MagicMock

import py_trees
import pytest

from test.core.use_cases.received.conftest import (
    assert_only_refusal_notice,
    queued_bodies,
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.suggest_actor.recorded_offer import (
    RequireRecordedOfferAnswerNode,
    recorded_offer_answer_key,
)
from vultron.core.models.actor_recommendation_record import (
    ActorRecommendationRecord,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.actor import (
    AcceptOfferCaseParticipantReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases.received.actor.offer_case_participant import (
    AcceptOfferCaseParticipantReceivedUseCase,
    OfferCaseParticipantReceivedUseCase,
    RejectOfferCaseParticipantReceivedUseCase,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    accept_case_participant_offer_activity,
    offer_case_participant_activity,
    reject_case_participant_offer_activity,
    rm_accept_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor, as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

CASE_ID = "https://example.org/cases/offer-round-trip-case"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
CASE_OWNER_ID = "https://example.org/actors/case-owner"
RECOMMENDER_ID = "https://example.org/actors/finder"
RECOMMENDED_ID = "https://example.org/actors/vendor-new"
BYSTANDER_ID = "https://example.org/actors/bystander"
#: The original ``Offer(Actor)`` the transformed Offer carries as ``origin``.
RECOMMENDATION_ID = "https://example.org/activities/orig-offer-001"
#: The ``Offer(CaseParticipant)`` the CASE_MANAGER recorded and the Case Owner
#: answers; replies name it by this id.
OFFER_ID = "https://example.org/activities/offer-case-participant-001"


def _case_ref(case_id: str) -> as_VulnerabilityCase:
    """An inline case as ``target``, as the inbox rehydrates a bare id.

    The CASE_MANAGER's receipt commit refuses a bare-string ``target``, so a
    test that reaches that commit must send what production sends.
    """
    return as_VulnerabilityCase(id_=case_id, name="OfferRoundTripTest")


def _seed_dl_for_case_owner() -> tuple[SqliteDataLayer, str]:
    """DataLayer seeded as the Case Owner's own store.

    The Case Owner is the local actor that receives Offer(CaseParticipant)
    from the CASE_MANAGER, which is somebody else (``CASE_ACTOR_ID``).
    """
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=CASE_OWNER_ID,  # the receiving Case Owner's own store
    )
    owner_actor = as_Actor(id_=CASE_OWNER_ID)
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="OfferRoundTripTest",
        attributed_to=CASE_OWNER_ID,
    )
    seed_case_manager_participant(dl, case, CASE_ACTOR_ID)
    dl.create(owner_actor)  # type: ignore[arg-type]
    dl.create(case)
    return dl, CASE_OWNER_ID


def _seed_dl_for_case_actor(
    manager_id: str = CASE_ACTOR_ID,
) -> tuple[SqliteDataLayer, str]:
    """DataLayer seeded as the CaseActor's own store.

    The CaseActor is the local actor that receives Accept/Reject from the
    Case Owner, and holds ``CVDRole.CASE_MANAGER`` for the case unless
    *manager_id* names somebody else (BT-17-005).
    """
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=CASE_ACTOR_ID,  # the receiving CaseActor's own store
    )
    case_actor = as_Service(id_=CASE_ACTOR_ID)
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="OfferRoundTripTest",
        attributed_to=CASE_OWNER_ID,
        stub_summary="Security issue — details shared after acceptance",
    )
    seed_case_manager_participant(dl, case, manager_id)
    seed_case_owner_participant(dl, case, CASE_OWNER_ID)
    dl.create(case_actor)
    dl.create(case)
    _record_recommendation(dl)
    _record_offer(dl)
    return dl, CASE_ACTOR_ID


def _record_recommendation(
    dl: SqliteDataLayer,
    case_id: str = CASE_ID,
    recommender_id: str = RECOMMENDER_ID,
) -> None:
    """Store who recommended the actor, as the CASE_MANAGER's bookkeeping.

    What OfferActorToCaseReceivedUseCase records when the recommendation
    arrives (CM-16-004): the decision handlers read the recommender from this
    record, and refuse a decision on a recommendation never recorded.  It is
    kept beside the case, never on it (CLP-07-014).
    """
    dl.save(
        ActorRecommendationRecord(
            case_id=case_id,
            recommendation_id=RECOMMENDATION_ID,
            recommender_id=recommender_id,
        )
    )


def _record_offer(dl: SqliteDataLayer) -> None:
    """Store the ``Offer(CaseParticipant)`` the CASE_MANAGER forwarded.

    Accept and Reject act on this record (CM-16-019), as
    ``offer_actor_to_case()`` leaves it when the recommendation is forwarded.
    """
    offer = _build_offer_activity()
    dl.create(cast(CaseParticipant, offer.object_))
    dl.create(offer)


#: An ``Offer(CaseParticipant)`` id no CASE_MANAGER store records.
_NEVER_RECORDED_OFFER_ID = "https://example.org/activities/never-recorded"


def _assert_refused_in_tree_as_unrecorded(
    dl: SqliteDataLayer, result: Any, answer_id: str
) -> None:
    """The answer was refused by the tree's guard, archived and acted on nothing.

    Intake archived it (CLP-10-018), so the refusal came from inside the one
    received tree (CLP-10-005); the guard refused before the commit, so the
    store holds no ledger entry and the outbox holds only the refusal notice
    to the Case Owner (CLP-05-001).
    """
    assert result.disposition is HandlerDisposition.REFUSED
    assert "never recorded" in (result.reason or "")
    assert _NEVER_RECORDED_OFFER_ID in (result.reason or "")
    assert dl.read(ReceivedActivityRecord.build_id(answer_id)) is not None
    assert dl.list_objects("CaseLedgerEntry") == []
    assert_only_refusal_notice(dl, answer_id, CASE_OWNER_ID)


def _assert_only_notice_to_case_owner(dl: SqliteDataLayer) -> None:
    """The outbox holds only the refusal notice of the Case Owner's answer."""
    bodies = queued_bodies(dl)
    assert len(bodies) == 1, bodies
    refused_id = bodies[0]["inReplyTo"]
    assert isinstance(refused_id, str)
    assert_only_refusal_notice(dl, refused_id, CASE_OWNER_ID)


def _forget_recommendation(dl: SqliteDataLayer) -> None:
    """Drop the recorded recommender, as a store that never saw the Offer."""
    assert dl.delete(
        "ActorRecommendationRecord",
        ActorRecommendationRecord.build_id(CASE_ID, RECOMMENDATION_ID),
    )


def _build_offer_activity(
    actor: str = CASE_ACTOR_ID,
    to: list[str] | None = None,
    cc: list[str] | None = None,
    origin: str | None = RECOMMENDATION_ID,
    roles: list | None = None,
    recommended_id: str = RECOMMENDED_ID,
    offer_id: str = OFFER_ID,
):
    recommended = as_Actor(id_=recommended_id)
    extra: dict[str, Any] = {"origin": origin} if origin is not None else {}
    return offer_case_participant_activity(
        recommended,
        target=_case_ref(CASE_ID),
        actor=actor,
        to=to or [CASE_OWNER_ID],
        cc=cc or [],
        roles=roles,
        id_=offer_id,
        **extra,
    )


# ---------------------------------------------------------------------------
# OfferCaseParticipantReceivedUseCase (Case Owner inbox)
# ---------------------------------------------------------------------------


class TestOfferCaseParticipantReceivedUseCase:
    def _event(self) -> OfferCaseParticipantReceivedEvent:
        activity = _build_offer_activity()
        return cast(
            OfferCaseParticipantReceivedEvent, received_event(activity)
        )

    @pytest.mark.spec("HP-01-005")
    def test_case_owner_receipt_is_applied(self):
        """The addressee's receipt: the Offer is now the Case Owner's to decide."""
        dl, _ = _seed_dl_for_case_owner()
        event = self._event()
        # The Case Owner is not the CASE_MANAGER, so the CM-gated ledger
        # commit is correctly not done here; the Offer is addressed to it.
        result = OfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.spec("ID-04-004")
    def test_case_owner_redelivery_is_skipped(self):
        """Only the addressee's first receipt is APPLIED; a repeat is a skip."""
        dl, _ = _seed_dl_for_case_owner()
        event = self._event()

        def deliver() -> HandlerResult:
            return OfferCaseParticipantReceivedUseCase(
                dl,
                event,
                trigger_activity=TriggerActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()

        assert deliver().disposition is HandlerDisposition.APPLIED
        assert deliver().disposition is HandlerDisposition.SKIPPED

    @pytest.mark.spec("HP-01-005")
    def test_bystander_copy_is_refused(self):
        """Neither CASE_MANAGER nor addressee: a misaddressed copy is refused."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=BYSTANDER_ID)
        case = as_VulnerabilityCase(
            id_=CASE_ID, name="OfferRoundTripTest", attributed_to=CASE_OWNER_ID
        )
        seed_case_manager_participant(dl, case, CASE_ACTOR_ID)
        dl.create(case)
        event = self._event()  # to=[CASE_OWNER_ID]

        result = OfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert BYSTANDER_ID in result.reason

    @pytest.mark.spec("CM-16-004")
    def test_case_manager_addressee_commits_receipt(self):
        """The CASE_MANAGER, as addressee, records the Offer: the gate's control.

        A Case Owner that also manages its case receives the
        ``Offer(CaseParticipant)`` in ``to`` over the ordinary delivery path
        (ADR-0109 keeps that same-actor delivery; the former self-``cc:`` copy
        is retired).  Holding the role, it passes the gate and the receipt
        commit runs.
        """
        dl, _ = _seed_dl_for_case_actor()
        activity = _build_offer_activity(to=[CASE_ACTOR_ID])
        event = cast(
            OfferCaseParticipantReceivedEvent, received_event(activity)
        )

        result = OfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        assert dl.list_objects("CaseLedgerEntry"), (
            "the CASE_MANAGER's receipt commit must record the"
            " Offer(CaseParticipant)"
        )

    def test_never_fabricates_the_local_actor(self, caplog):
        """There is no "no local actor" case to skip for (ADR-0073).

        A DataLayer always belongs to exactly one actor, so "who am I?" always has
        an answer: ``resolve_receiving_actor_id`` prefers the inbox-supplied
        ``receiving_actor_id`` and otherwise asks the store. The old skip branch
        resolved it by scanning for the first actor object instead, which since
        peer records live in each actor's own address book could return a *peer* —
        so it was both unreachable by design and wrong when it did fire.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=CASE_ACTOR_ID,  # the receiving CaseActor's own store
        )
        event = self._event()
        with caplog.at_level(logging.WARNING):
            result = OfferCaseParticipantReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        # The store holds no such case (RSH rule 3).
        assert result.disposition is HandlerDisposition.REFUSED
        messages = " ".join(r.message.lower() for r in caplog.records)
        assert "no local actor" not in messages
        assert "'unknown'" not in messages

    def test_skips_when_missing_case_id(self, caplog):
        dl, _ = _seed_dl_for_case_owner()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/bad"
        mock_event.target_id = None
        mock_event.activity = None
        with caplog.at_level(logging.WARNING):
            result = OfferCaseParticipantReceivedUseCase(
                dl,
                mock_event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        assert any("missing" in r.message.lower() for r in caplog.records)
        assert result.disposition is HandlerDisposition.REFUSED


# ---------------------------------------------------------------------------
# AcceptOfferCaseParticipantReceivedUseCase (CaseActor inbox)
# ---------------------------------------------------------------------------


class TestAcceptOfferCaseParticipantReceivedUseCase:
    def _event(
        self, origin: str | None = RECOMMENDATION_ID
    ) -> AcceptOfferCaseParticipantReceivedEvent:
        offer = _build_offer_activity(origin=origin)
        accept = accept_case_participant_offer_activity(
            offer,
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        return cast(
            AcceptOfferCaseParticipantReceivedEvent, received_event(accept)
        )

    def _event_with_stored_offer(
        self,
        dl: SqliteDataLayer,
        origin: str | None = RECOMMENDATION_ID,
    ) -> AcceptOfferCaseParticipantReceivedEvent:
        """Build Accept(Offer(CaseParticipant)) and store offer + participant in DL.

        CM-11-019: the use case reads roles from the stored Offer's object_.
        Dehydration stores object_ as a bare IRI; the IRI is followed at read
        time via dl.read(). So both the Offer and its CaseParticipant object
        must be stored in the DL for the roles to be found.

        ``_seed_dl_for_case_actor`` already stores the same offer (via
        ``_record_offer``); ``dl.save`` overwrites any prior record so both
        the participant and the offer carry the expected roles.
        """
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        offer = _build_offer_activity(origin=origin, roles=[CVDRole.VENDOR])
        # Store the CaseParticipant object so the IRI follow-up in the use
        # case (AKM-03-003) succeeds and returns the roles.
        # dl.save() is used instead of dl.create() because _record_offer
        # (called by _seed_dl_for_case_actor) may have already stored these
        # records; save() overwrites without raising VultronAlreadyExistsError.
        participant = offer.object_
        if isinstance(participant, as_CaseParticipant):
            dl.save(participant)
        dl.save(offer)
        accept = accept_case_participant_offer_activity(
            offer,
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        return cast(
            AcceptOfferCaseParticipantReceivedEvent, received_event(accept)
        )

    def test_executes_without_error(self):
        # CM-11-019: use _event_with_stored_offer so the DL has the offer's
        # roles and CreateInertInviteeParticipantNode can resolve them.
        dl, _ = _seed_dl_for_case_actor()
        event = self._event_with_stored_offer(dl)
        result = AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

    @pytest.mark.spec("CM-16-006")
    @pytest.mark.spec("CS-08-001")
    def test_refuses_a_recommendation_it_never_recorded(self, caplog):
        """No recorded recommender means no one to notify, so refuse.

        Until #3877 the missing recommender travelled into the BT as ``""``
        and the ``AcceptActorRecommendation`` went out with a blank ``actor``
        — this test passed on a bogus activity.  A blank reference is now
        refused at construction, and the decision is taken at the edge.
        """
        dl, _ = _seed_dl_for_case_actor()
        _forget_recommendation(dl)
        event = self._event()
        with caplog.at_level(logging.WARNING):
            result = AcceptOfferCaseParticipantReceivedUseCase(
                dl,
                event,
                trigger_activity=TriggerActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        assert result.disposition is HandlerDisposition.REFUSED
        assert "never recorded" in (result.reason or "")
        assert RECOMMENDATION_ID in (result.reason or "")
        assert any(
            "never recorded" in r.message and "refusing" in r.message
            for r in caplog.records
        )
        _assert_only_notice_to_case_owner(dl)

    @pytest.mark.spec("CM-16-006")
    @pytest.mark.spec("CLP-07-014")
    def test_a_recommendation_recorded_for_another_case_is_not_found(self):
        """The record is keyed by case: another case's recommender is not used.

        The index this record replaces lived on each case (#4448), so a
        decision about one case could never pick up a recommender recorded on
        another; the case-keyed record id keeps that.
        """
        dl, _ = _seed_dl_for_case_actor()
        _forget_recommendation(dl)
        _record_recommendation(dl, case_id="https://example.org/cases/other")
        result = AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            self._event(),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.REFUSED
        assert "never recorded" in (result.reason or "")
        _assert_only_notice_to_case_owner(dl)

    @pytest.mark.spec("CM-16-006")
    @pytest.mark.spec("CS-08-001")
    def test_refuses_an_offer_that_names_no_recommendation(self):
        """An inner Offer without ``origin`` names no recommendation at all.

        CM-16-004 puts the original recommender's Offer id in ``origin``; with
        no ``origin`` there is nothing to look the recommender up by.  Before
        #3877 the absent id travelled into the BT as ``""``.
        """
        dl, _ = _seed_dl_for_case_actor()
        event = self._event(origin=None)
        result = AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.REFUSED
        assert "no recommendation" in (result.reason or "")
        _assert_only_notice_to_case_owner(dl)

    @pytest.mark.spec("CM-16-019")
    def test_invitee_comes_from_the_recorded_offer_not_the_reply(self):
        """The Accept's copy of the Offer names someone else; it is ignored.

        The Case Owner answers the recorded Offer by id, but the reply embeds
        a copy whose CaseParticipant names another actor.
        The Invite goes to the actor the CASE_MANAGER recorded (CM-16-019).
        """
        forged_id = "https://example.org/actors/forged-invitee"
        dl, _ = _seed_dl_for_case_actor()
        accept = accept_case_participant_offer_activity(
            _build_offer_activity(recommended_id=forged_id),
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        event = cast(
            AcceptOfferCaseParticipantReceivedEvent, received_event(accept)
        )

        result = AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        invites = [
            obj
            for obj in (dl.read(a) for a in dl.outbox_list())
            if str(getattr(obj, "type_", "")) == "Invite"
        ]
        assert invites, "the recorded invitee must be invited"
        invitees = {
            getattr(getattr(i, "object_", None), "id_", None)
            or getattr(i, "object_", None)
            for i in invites
        }
        assert invitees == {RECOMMENDED_ID}

    @pytest.mark.spec("CM-16-019")
    def test_offer_archived_from_a_stranger_is_not_a_record(self):
        """An Offer a stranger sent, archived by intake, is refused as a record.

        Intake stores every inbound activity, so the id the Case Owner names
        can resolve to an Offer the CASE_MANAGER never sent; the invitee
        must come only from one it did.
        """
        dl, _ = _seed_dl_for_case_actor()
        dl.save(
            _build_offer_activity(
                actor="https://example.org/actors/stranger",
                recommended_id="https://example.org/actors/forged-invitee",
            )
        )
        accept = accept_case_participant_offer_activity(
            _build_offer_activity(),
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        event = cast(
            AcceptOfferCaseParticipantReceivedEvent, received_event(accept)
        )

        result = AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert "never recorded" in (result.reason or "")
        _assert_only_notice_to_case_owner(dl)

    def test_never_fabricates_the_local_actor(self, caplog):
        """There is no "no local actor" case to skip for (ADR-0073).

        A DataLayer always belongs to exactly one actor, so "who am I?" always
        has an answer. The old skip branch scanned for the first actor object,
        which since peer records live in each actor's own address book could
        return a *peer* — unreachable by design and wrong when it did fire.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=CASE_ACTOR_ID,  # the receiving CaseActor's own store
        )
        event = self._event()
        with caplog.at_level(logging.WARNING):
            AcceptOfferCaseParticipantReceivedUseCase(
                dl,
                event,
                trigger_activity=TriggerActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        messages = " ".join(r.message.lower() for r in caplog.records)
        assert "no local actor" not in messages
        assert "'unknown'" not in messages

    def test_skips_when_missing_case_id(self, caplog):
        dl, _ = _seed_dl_for_case_actor()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/bad-accept"
        mock_event.target_id = None
        mock_event.inner_target_id = None
        mock_event.activity = None
        with caplog.at_level(logging.WARNING):
            result = AcceptOfferCaseParticipantReceivedUseCase(
                dl,
                mock_event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        assert any("missing" in r.message.lower() for r in caplog.records)
        assert result.disposition is HandlerDisposition.REFUSED

    @pytest.mark.spec("CM-16-019")
    @pytest.mark.spec("CLP-10-018")
    @pytest.mark.spec("CLP-10-005")
    def test_refuses_an_offer_it_never_recorded(self, caplog):
        """A reply naming an Offer this store never recorded has no invitee.

        The lookup is a precondition guard of the one received tree, so the
        Accept is archived by intake and refused before the commit, with no
        ledger entry and nothing sent.
        """
        dl, _ = _seed_dl_for_case_actor()
        accept = accept_case_participant_offer_activity(
            _build_offer_activity(offer_id=_NEVER_RECORDED_OFFER_ID),
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        event = cast(
            AcceptOfferCaseParticipantReceivedEvent, received_event(accept)
        )
        with caplog.at_level(logging.WARNING):
            result = AcceptOfferCaseParticipantReceivedUseCase(
                dl,
                event,
                trigger_activity=TriggerActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        assert any("never recorded" in r.message for r in caplog.records)
        _assert_refused_in_tree_as_unrecorded(dl, result, accept.id_)

    def test_recommender_notified_via_core_state(self):
        """AC-5: recommender notification emitted; recommender read from core state.

        Seeds the ActorRecommendationRecord (as OfferActorToCaseReceivedUseCase
        does at ingestion time), then runs
        AcceptOfferCaseParticipantReceivedUseCase and asserts that at least
        two outbox activities are queued — one Invite to the invitee and one
        AcceptActorRecommendation to the recommender — confirming the recommender
        ID came from core state, not from a dl.read(recommendation_id) re-read.
        """
        dl, _actor_id = _seed_dl_for_case_actor()
        # Seed the recommendation as OfferActorToCaseReceivedUseCase would.
        _record_recommendation(dl)

        # CM-11-019: store the offer with roles so CreateInertInviteeParticipantNode
        # can resolve them and the use case is APPLIED.
        event = self._event_with_stored_offer(dl)
        result = AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        outbox = dl.outbox_list()
        assert len(outbox) >= 2, (
            "Expected at least two outbox activities (Accept notification to "
            f"recommender + Invite to invitee); got {len(outbox)}"
        )
        # At least one queued activity must be addressed to the recommender.
        addressed_to_recommender = [
            act_id
            for act_id in outbox
            if RECOMMENDER_ID in (getattr(dl.read(act_id), "to", None) or [])
        ]
        assert addressed_to_recommender, (
            f"No outbox activity addressed to recommender '{RECOMMENDER_ID}'; "
            "recommender lookup must read the CASE_MANAGER's ActorRecommendationRecord"
        )

    @pytest.mark.spec("CM-11-015")
    @pytest.mark.parametrize("joined", [False, True])
    def test_closed_invitee_is_refused_before_anything_is_sent(self, joined):
        """An invitee already at RM.CLOSED is never re-invited (CM-11-015).

        The refusal comes before the commit and the emits, so neither the
        Invite nor the recommender notification is queued, only the refusal
        notice to the Case Owner, and the record is left as it was.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.dimensions import RmDimension
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.rm import RM
        from vultron.enums.roles import CVDRole

        dl, _ = _seed_dl_for_case_actor()
        closed_id = f"{CASE_ID}/participants/closed-invitee"
        closed = CaseParticipant(
            id_=closed_id,
            attributed_to=RECOMMENDED_ID,
            context=CASE_ID,
            case_roles=[CVDRole.VENDOR],
            participant_statuses=[
                ParticipantStatus(
                    context=CASE_ID,
                    attributed_to=RECOMMENDED_ID,
                    rm=RmDimension(state=RM.CLOSED),
                    cvd_role=[CVDRole.VENDOR],
                )
            ],
            joined=joined,
        )
        dl.create(closed)
        case = dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        case.add_participant(closed)
        dl.save(case)
        event = self._event_with_stored_offer(dl)

        result = AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is not HandlerDisposition.APPLIED
        assert result.reason is not None
        assert "CM-11-015" in result.reason
        # Only the refusal notice to the Case Owner is queued: no Invite and
        # no AcceptActorRecommendation (CM-11-015, CLP-05-001).
        assert_only_refusal_notice(dl, event.activity_id, CASE_OWNER_ID)
        stored = dl.read(closed_id)
        assert isinstance(stored, CaseParticipant)
        assert stored.rm_closed
        assert stored.joined is joined
        assert len(stored.participant_statuses) == 1


# ---------------------------------------------------------------------------
# RejectOfferCaseParticipantReceivedUseCase (CaseActor inbox)
# ---------------------------------------------------------------------------


class TestAcceptRefusesAnInviteeThatCannotBeInvited:
    """A second Accept after join, or one for a closed invitee, commits nothing.

    The Case Owner's Accept makes the CASE_MANAGER send and commit a stub
    Invite.  An invitee that has already joined or is at ``RM.CLOSED`` is sent
    no further one, so no second Invite entry reaches the ledger for it
    (CM-11-015, CM-16-006).
    """

    def _accept(self, dl: SqliteDataLayer) -> Any:
        helper = TestAcceptOfferCaseParticipantReceivedUseCase()
        event = helper._event_with_stored_offer(dl)
        return AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

    def _record(self, dl: SqliteDataLayer) -> CaseParticipant:
        from vultron.core.models.case import VulnerabilityCase

        case = dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        record = dl.read(case.actor_participant_index[RECOMMENDED_ID])
        assert isinstance(record, CaseParticipant)
        return record

    @pytest.mark.spec("CM-16-006")
    def test_first_accept_still_invites(self):
        dl, _ = _seed_dl_for_case_actor()
        result = self._accept(dl)
        assert result.disposition is HandlerDisposition.APPLIED
        assert self._record(dl).joined is False
        assert len(dl.list_objects("CaseLedgerEntry")) >= 1

    @pytest.mark.spec("CM-16-006")
    @pytest.mark.spec("CM-11-015")
    def test_second_accept_after_join_is_refused_and_commits_nothing(self):
        dl, _ = _seed_dl_for_case_actor()
        assert self._accept(dl).disposition is HandlerDisposition.APPLIED
        record = self._record(dl)
        record.joined = True
        dl.save(record)
        ledger_before = len(dl.list_objects("CaseLedgerEntry"))

        result = self._accept(dl)

        assert result.disposition is HandlerDisposition.REFUSED
        assert RECOMMENDED_ID in (result.reason or "")
        assert "joined" in (result.reason or "")
        assert len(dl.list_objects("CaseLedgerEntry")) == ledger_before

    @pytest.mark.spec("CM-16-006")
    @pytest.mark.spec("CM-11-015")
    def test_accept_for_a_closed_invitee_is_refused_and_commits_nothing(self):
        from vultron.core.models.dimensions import RmDimension
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.rm import RM

        dl, _ = _seed_dl_for_case_actor()
        assert self._accept(dl).disposition is HandlerDisposition.APPLIED
        record = self._record(dl)
        record.participant_statuses.append(
            ParticipantStatus(
                context=CASE_ID,
                attributed_to=RECOMMENDED_ID,
                rm=RmDimension(state=RM.CLOSED),
            )
        )
        dl.save(record)
        ledger_before = len(dl.list_objects("CaseLedgerEntry"))

        result = self._accept(dl)

        assert result.disposition is HandlerDisposition.REFUSED
        assert "RM.CLOSED" in (result.reason or "")
        assert len(dl.list_objects("CaseLedgerEntry")) == ledger_before


class TestRejectOfferCaseParticipantReceivedUseCase:
    def _event(
        self, origin: str | None = RECOMMENDATION_ID
    ) -> RejectOfferCaseParticipantReceivedEvent:
        offer = _build_offer_activity(origin=origin)
        reject = reject_case_participant_offer_activity(
            offer,
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        return cast(
            RejectOfferCaseParticipantReceivedEvent, received_event(reject)
        )

    def test_executes_without_error(self):
        dl, _ = _seed_dl_for_case_actor()
        event = self._event()
        result = RejectOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

    @pytest.mark.spec("CM-16-007")
    @pytest.mark.spec("CS-08-001")
    def test_refuses_a_recommendation_it_never_recorded(self, caplog):
        """The Reject mirror of the Accept case: no recommender, no notification."""
        dl, _ = _seed_dl_for_case_actor()
        _forget_recommendation(dl)
        event = self._event()
        with caplog.at_level(logging.WARNING):
            result = RejectOfferCaseParticipantReceivedUseCase(
                dl,
                event,
                trigger_activity=TriggerActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        assert result.disposition is HandlerDisposition.REFUSED
        assert "never recorded" in (result.reason or "")
        assert RECOMMENDATION_ID in (result.reason or "")
        assert any(
            "never recorded" in r.message and "refusing" in r.message
            for r in caplog.records
        )
        _assert_only_notice_to_case_owner(dl)

    @pytest.mark.spec("CM-16-007")
    @pytest.mark.spec("CS-08-001")
    def test_refuses_an_offer_that_names_no_recommendation(self):
        """An inner Offer without ``origin`` names no recommendation at all.

        CM-16-004 puts the original recommender's Offer id in ``origin``; with
        no ``origin`` there is nothing to look the recommender up by.  Before
        #3877 the absent id travelled into the BT as ``""``.
        """
        dl, _ = _seed_dl_for_case_actor()
        event = self._event(origin=None)
        result = RejectOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.REFUSED
        assert "no recommendation" in (result.reason or "")
        _assert_only_notice_to_case_owner(dl)

    @pytest.mark.spec("CM-16-019")
    @pytest.mark.spec("CLP-10-018")
    @pytest.mark.spec("CLP-10-005")
    def test_refuses_an_offer_it_never_recorded(self):
        """A Reject naming an Offer this store never recorded has nobody to name.

        ``RejectActorRecommendation`` carries the recommended actor, which is
        the recorded Offer's; with no record there is nobody to name, and the
        Reject's own ``object_id`` is not a substitute.  The lookup is a
        precondition guard of the one received tree, so the Reject is
        archived by intake and refused before the commit.
        """
        dl, _ = _seed_dl_for_case_actor()
        reject = reject_case_participant_offer_activity(
            _build_offer_activity(offer_id=_NEVER_RECORDED_OFFER_ID),
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        event = cast(
            RejectOfferCaseParticipantReceivedEvent, received_event(reject)
        )
        result = RejectOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        _assert_refused_in_tree_as_unrecorded(dl, result, reject.id_)

    @pytest.mark.spec("CM-16-019")
    def test_recommended_actor_comes_from_the_recorded_offer(self):
        """The Reject's copy of the Offer names someone else; it is ignored."""
        forged_id = "https://example.org/actors/forged-invitee"
        dl, _ = _seed_dl_for_case_actor()
        reject = reject_case_participant_offer_activity(
            _build_offer_activity(recommended_id=forged_id),
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        event = cast(
            RejectOfferCaseParticipantReceivedEvent, received_event(reject)
        )

        result = RejectOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        notices = [
            str(obj.model_dump())
            for obj in (dl.read(a) for a in dl.outbox_list())
            if obj is not None and str(getattr(obj, "type_", "")) == "Reject"
        ]
        assert len(notices) == 1, "the recommender must be told once"
        assert RECOMMENDED_ID in notices[0]
        assert forged_id not in notices[0]

    def test_never_fabricates_the_local_actor(self, caplog):
        """There is no "no local actor" case to skip for (ADR-0073).

        A DataLayer always belongs to exactly one actor, so "who am I?" always
        has an answer. The old skip branch scanned for the first actor object,
        which since peer records live in each actor's own address book could
        return a *peer* — unreachable by design and wrong when it did fire.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=CASE_ACTOR_ID,  # the receiving CaseActor's own store
        )
        event = self._event()
        with caplog.at_level(logging.WARNING):
            RejectOfferCaseParticipantReceivedUseCase(
                dl,
                event,
                trigger_activity=TriggerActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        messages = " ".join(r.message.lower() for r in caplog.records)
        assert "no local actor" not in messages
        assert "'unknown'" not in messages

    def test_skips_when_missing_case_id(self, caplog):
        dl, _ = _seed_dl_for_case_actor()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/bad-reject"
        mock_event.target_id = None
        mock_event.activity = None
        with caplog.at_level(logging.WARNING):
            result = RejectOfferCaseParticipantReceivedUseCase(
                dl,
                mock_event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        assert any("missing" in r.message.lower() for r in caplog.records)
        assert result.disposition is HandlerDisposition.REFUSED

    def test_recommender_notified_via_core_state(self):
        """AC-5: recommender notification emitted on reject; recommender from core state.

        Seeds the ActorRecommendationRecord and asserts that
        RejectOfferCaseParticipantReceivedUseCase queues a RejectActorRecommendation
        addressed to the recommender, read from core state.
        """
        dl, _actor_id = _seed_dl_for_case_actor()
        _record_recommendation(dl)

        event = self._event()
        result = RejectOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        outbox = dl.outbox_list()
        assert len(outbox) >= 1, (
            "Expected at least one outbox activity (RejectActorRecommendation "
            f"to recommender); got {len(outbox)}"
        )
        addressed_to_recommender = [
            act_id
            for act_id in outbox
            if RECOMMENDER_ID in (getattr(dl.read(act_id), "to", None) or [])
        ]
        assert addressed_to_recommender, (
            f"No outbox activity addressed to recommender '{RECOMMENDER_ID}'; "
            "recommender lookup must read the CASE_MANAGER's ActorRecommendationRecord"
        )


# ---------------------------------------------------------------------------
# The recorded-Offer lookup guard (#4863, CLP-10-005, CM-16-019)
# ---------------------------------------------------------------------------


def _answer_to_an_unrecorded_offer(verb: str) -> Any:
    """An Accept or Reject of an Offer the CASE_MANAGER never recorded."""
    build = (
        accept_case_participant_offer_activity
        if verb == "Accept"
        else reject_case_participant_offer_activity
    )
    return build(
        _build_offer_activity(offer_id=_NEVER_RECORDED_OFFER_ID),
        target=_case_ref(CASE_ID),
        actor=CASE_OWNER_ID,
        to=[CASE_ACTOR_ID],
    )


_ANSWER_USE_CASES = {
    "Accept": AcceptOfferCaseParticipantReceivedUseCase,
    "Reject": RejectOfferCaseParticipantReceivedUseCase,
}


@pytest.mark.spec("CM-16-019")
@pytest.mark.parametrize(
    ("verb", "named"),
    [
        (
            "Accept",
            "an Offer(CaseParticipant) this CASE_MANAGER never recorded",
        ),
        ("Reject", "a recommendation this CASE_MANAGER never recorded"),
    ],
)
def test_with_both_unrecorded_each_answer_reports_its_first_lookup(
    verb: str, named: str
) -> None:
    """An Accept checks the Offer first and a Reject the recommendation first.

    Each keeps the reason it gave before the lookup moved into the tree.
    """
    dl, _ = _seed_dl_for_case_actor()
    _forget_recommendation(dl)
    activity = _answer_to_an_unrecorded_offer(verb)
    result = _ANSWER_USE_CASES[verb](
        dl,
        received_event(activity),  # type: ignore[arg-type]
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()
    assert result.disposition is HandlerDisposition.REFUSED
    assert f"{verb}(Offer(CaseParticipant)) names {named}" in (
        result.reason or ""
    )
    assert dl.list_objects("CaseLedgerEntry") == []
    notice = assert_only_refusal_notice(dl, activity.id_, CASE_OWNER_ID)
    # The notice carries the refusing guard's reason (CLP-05-001).
    assert isinstance(notice["summary"], str)
    assert (result.reason or "").endswith(notice["summary"])


@pytest.mark.parametrize("verb", ["Accept", "Reject"])
def test_the_lookup_fails_for_a_case_this_store_does_not_hold(
    verb: Literal["Accept", "Reject"],
) -> None:
    """The guard resolves its case first (Regime 1) and publishes nothing."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_ACTOR_ID)
    activity = _answer_to_an_unrecorded_offer(verb)
    answer_id = f"{activity.id_}-no-case"
    try:
        result = BTBridge(datalayer=dl).execute_with_setup(
            RequireRecordedOfferAnswerNode(
                verb=verb, answer_id=answer_id, case_id=CASE_ID
            ),
            actor_id=CASE_ACTOR_ID,
            activity=received_event(activity),
        )
    finally:
        dl.close()
    assert result.status == py_trees.common.Status.FAILURE
    assert result.internal_error is False
    assert CASE_ID in result.feedback_message
    key = f"/{recorded_offer_answer_key(answer_id)}"
    assert key not in py_trees.blackboard.Blackboard.storage


# ---------------------------------------------------------------------------
# AC-1/AC-2: suggest-actor roles threading (ISSUE-1406)
# ---------------------------------------------------------------------------

AC1_CASE_ID = "https://example.org/cases/ac1-roles-threading"
AC1_CASE_ACTOR_ID = "https://example.org/actors/ac1-case-actor"
AC1_CASE_OWNER_ID = "https://example.org/actors/ac1-case-owner"
AC1_INVITEE_ID = "https://example.org/actors/ac1-vendor"
AC1_RECOMMENDER_ID = "https://example.org/actors/ac1-finder"


def _seed_dl_for_ac1() -> SqliteDataLayer:
    """DataLayer seeded for the full suggest-actor roles-threading round-trip.

    The CaseActor Service has ``context=AC1_CASE_ID`` so that
    ``_find_case_actor_id()`` resolves correctly when
    ``AcceptInviteActorToCaseReceivedUseCase`` runs.
    """
    from vultron.wire.as2.vocab.base.objects.actors import as_Organization

    # This scenario has its own CaseActor (AC1_CASE_ACTOR_ID), so the store is
    # that one's, not the module-level CASE_ACTOR_ID used elsewhere in the file.
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=AC1_CASE_ACTOR_ID)
    case_actor = as_Service(id_=AC1_CASE_ACTOR_ID, context=AC1_CASE_ID)
    case = as_VulnerabilityCase(
        id_=AC1_CASE_ID,
        name="AC1RolesThreading",
        attributed_to=AC1_CASE_OWNER_ID,
        stub_summary="Security issue — details shared after acceptance",
    )
    # The CaseActor holds CASE_MANAGER: both the Accept(Offer) effects and
    # the Accept(Invite) effects are role-gated (BT-17-001, BT-17-005).
    seed_case_manager_participant(dl, case, AC1_CASE_ACTOR_ID)
    seed_case_owner_participant(dl, case, AC1_CASE_OWNER_ID)
    invitee = as_Organization(id_=AC1_INVITEE_ID)
    dl.create(case_actor)
    dl.create(case)
    dl.create(invitee)
    # Recorded when the recommendation arrived (CM-16-004); the Accept
    # handler refuses a decision on a recommendation never recorded.
    _record_recommendation(dl, AC1_CASE_ID, AC1_RECOMMENDER_ID)
    return dl


class TestRolesFromStoredOffer:
    """Regression test for ISSUE-1745: roles must come from stored Offer, not blackboard.

    The suggest-actor path (ADR-0026) runs in two separate BT executions:
    1. CaseActor receives Offer(Actor, Case) → stores Offer(CaseParticipant) with roles
    2. CaseActor receives Accept(Offer(CaseParticipant)) → emits Invite with those roles

    The blackboard is not shared between executions, so roles must be read from
    the DataLayer (the stored Offer), not from a blackboard key that is always
    empty in the second execution.
    """

    def _seed_and_store_offer(
        self, roles: list
    ) -> tuple[SqliteDataLayer, "AcceptOfferCaseParticipantReceivedEvent"]:
        """Seed a DataLayer as the CaseActor would: store the Offer that was sent."""
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )

        dl = _seed_dl_for_ac1()
        adapter = TriggerActivityAdapter(dl)
        # Store the Offer as offer_actor_to_case() does when sending it to Case Owner.
        offer_id, _ = adapter.offer_actor_to_case(
            recommender_id=AC1_RECOMMENDER_ID,
            recommended_id=AC1_INVITEE_ID,
            case_id=AC1_CASE_ID,
            actor=AC1_CASE_ACTOR_ID,
            to=[AC1_CASE_OWNER_ID],
            origin=RECOMMENDATION_ID,
            roles=roles,
        )
        # Build Accept(Offer) using the STORED offer (as Case Owner would).
        stored_offer = dl.read(offer_id)
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Offer,
        )

        accept = accept_case_participant_offer_activity(
            cast(as_Offer, stored_offer),
            target=_case_ref(AC1_CASE_ID),
            actor=AC1_CASE_OWNER_ID,
            to=[AC1_CASE_ACTOR_ID],
        )
        event = cast(
            AcceptOfferCaseParticipantReceivedEvent, received_event(accept)
        )
        return dl, event

    @pytest.mark.spec("CM-16-018")
    def test_invite_carries_roles_from_stored_offer(self):
        """Roles from the stored Offer are threaded into the emitted Invite.

        ISSUE-1745: when CaseActor receives Accept(Offer(CaseParticipant[VENDOR])),
        the Invite it emits to the invitee must carry roles=[VENDOR], read from
        the stored Offer in the DataLayer (not from the blackboard, which is empty
        in this separate BT execution).
        """
        from vultron.enums.roles import CVDRole

        dl, event = self._seed_and_store_offer(roles=[CVDRole.VENDOR])
        AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        outbox = dl.outbox_list()
        invite_obj = None
        for act_id in outbox:
            obj = dl.read(act_id)
            if obj is not None and str(getattr(obj, "type_", "")) == "Invite":
                invite_obj = obj
                break

        assert invite_obj is not None, (
            "Invite must be stored in CaseActor outbox"
        )
        invite_roles = getattr(invite_obj, "roles", None)
        assert invite_roles == [CVDRole.VENDOR.value], (
            f"ISSUE-1745: Invite must carry roles from stored Offer; "
            f"expected ['{CVDRole.VENDOR.value}'], got {invite_roles!r}"
        )

    @pytest.mark.spec("CM-16-018")
    def test_participant_case_roles_vendor_after_full_round_trip(self):
        """Full round-trip: Accept(Invite) creates participant with VENDOR role.

        ISSUE-1745: after the fix, participant.case_roles should be [VENDOR]
        (read from the stored Offer), not [] (missing blackboard key).
        """
        from vultron.core.use_cases.received.actor.invite import (
            AcceptInviteActorToCaseReceivedUseCase,
        )
        from vultron.enums.roles import CVDRole

        dl, event = self._seed_and_store_offer(roles=[CVDRole.VENDOR])

        # Step 1: CaseActor receives Accept(Offer(CaseParticipant[VENDOR])) → emits Invite
        AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # Step 2: find the stored Invite
        outbox = dl.outbox_list()
        invite_obj = None
        for act_id in outbox:
            obj = dl.read(act_id)
            if obj is not None and str(getattr(obj, "type_", "")) == "Invite":
                invite_obj = obj
                break
        assert invite_obj is not None, (
            "Invite must be present in CaseActor outbox"
        )

        # Step 3: invitee accepts the Invite
        py_trees.blackboard.Blackboard.storage.clear()
        from vultron.core.models.events.actor import (
            AcceptInviteActorToCaseReceivedEvent,
        )
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Invite,
        )

        accept_invite = rm_accept_invite_to_case_activity(
            cast(as_Invite, invite_obj), actor=AC1_INVITEE_ID
        )
        accept_invite_event = cast(
            AcceptInviteActorToCaseReceivedEvent, received_event(accept_invite)
        )
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            accept_invite_event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        # Step 4: participant must have VENDOR role
        reloaded_case = cast(Any, dl.read(AC1_CASE_ID))
        participant_id = reloaded_case.actor_participant_index.get(
            AC1_INVITEE_ID
        )
        assert participant_id is not None, (
            "Invitee must be registered as participant"
        )
        participant = cast(Any, dl.get(id_=participant_id))
        assert participant is not None
        assert CVDRole.VENDOR in participant.case_roles, (
            f"ISSUE-1745: participant.case_roles must contain VENDOR after "
            f"full round-trip; got {participant.case_roles!r}"
        )


class TestAcceptOfferCaseParticipantRolesThreading:
    """AC-1/AC-2 (ISSUE-1406): roles threading through suggest-actor received path.

    AC-1: Full round-trip — Accept(Offer(CaseParticipant[roles])) →
          EmitInviteActorToCaseNode (roles=None, no blackboard key) →
          Invite(roles=None) stored → Accept(Invite) →
          CaseParticipant.case_roles == [].

    AC-2: Confirm that EmitInviteActorToCaseNode with no ``suggested_roles``
          blackboard key passes roles=None to invite_actor_to_case(), verifying
          no silent default substitution (ADR-0032 BT-HELPER-01).
    """

    @staticmethod
    def _ac1_offer(roles: list | None = None):
        """The ``Offer(CaseParticipant)`` for the AC1 invitee, by its fixed id."""
        extra: dict[str, Any] = {"roles": roles} if roles else {}
        return offer_case_participant_activity(
            as_Actor(id_=AC1_INVITEE_ID),
            target=_case_ref(AC1_CASE_ID),
            actor=AC1_CASE_ACTOR_ID,
            to=[AC1_CASE_OWNER_ID],
            id_=OFFER_ID,
            # CM-16-004: the transformed Offer names the recommendation it
            # answers; without it the CASE_MANAGER has nobody to notify.
            origin=RECOMMENDATION_ID,
            **extra,
        )

    def _build_accept_offer_event(
        self, dl: SqliteDataLayer
    ) -> AcceptOfferCaseParticipantReceivedEvent:
        """Record a VENDOR Offer, then build the Accept that embeds a forged copy.

        The Case Owner's Accept carries a copy of the Offer that adds
        CASE_OWNER to the roles, but the CASE_MANAGER recorded VENDOR only;
        the reply's copy is never used (CM-16-019, ISSUE-1745).
        """
        from vultron.enums.roles import CVDRole

        recorded = self._ac1_offer(roles=[CVDRole.VENDOR])
        dl.create(cast(CaseParticipant, recorded.object_))
        dl.create(recorded)
        accept = accept_case_participant_offer_activity(
            self._ac1_offer(roles=[CVDRole.VENDOR, CVDRole.CASE_OWNER]),
            target=_case_ref(AC1_CASE_ID),
            actor=AC1_CASE_OWNER_ID,
            to=[AC1_CASE_ACTOR_ID],
        )
        return cast(
            AcceptOfferCaseParticipantReceivedEvent, received_event(accept)
        )

    @pytest.mark.spec("CM-16-019")
    def test_invite_roles_are_the_recorded_offers_not_the_replys(self):
        """The Invite carries the recorded roles, not the reply's forged ones.

        The reply's copy of the Offer adds CASE_OWNER; the Invite still names
        only what the CASE_MANAGER recorded (CM-16-019, ISSUE-1745).
        """
        from vultron.enums.roles import CVDRole

        dl = _seed_dl_for_ac1()
        event = self._build_accept_offer_event(dl)
        AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        outbox = dl.outbox_list()
        invite_obj = None
        for act_id in outbox:
            obj = dl.read(act_id)
            if obj is not None and str(getattr(obj, "type_", "")) == "Invite":
                invite_obj = obj
                break

        assert invite_obj is not None, (
            "Invite must be stored in CaseActor outbox"
        )
        assert getattr(invite_obj, "roles", None) == [CVDRole.VENDOR.value], (
            "the Invite must carry the recorded Offer's roles, not the reply's"
        )

    @pytest.mark.spec("CM-11-019")
    def test_participant_case_roles_empty_refused_per_cm11019(self):
        """CM-11-019: Accept(Offer) with empty roles is REFUSED.

        Store an Offer whose CaseParticipant carries ``case_roles=[]``.
        ``RequireRecordedOfferAnswerNode`` publishes no roles, so
        ``SeatRecordedInviteeNode`` (CM-11-019) returns FAILURE and
        the overall use-case result is REFUSED.  No inert participant is
        created.
        """
        from vultron.core.models.case import VulnerabilityCase

        dl = _seed_dl_for_ac1()

        # Store an Offer with empty roles so the recorded answer carries
        # none → SeatRecordedInviteeNode refuses (CM-11-019).
        empty_roles_offer = offer_case_participant_activity(
            as_Actor(id_=AC1_INVITEE_ID),
            target=_case_ref(AC1_CASE_ID),
            actor=AC1_CASE_ACTOR_ID,
            to=[AC1_CASE_OWNER_ID],
            id_=OFFER_ID,
            origin=RECOMMENDATION_ID,
            roles=[],
        )
        dl.create(cast(CaseParticipant, empty_roles_offer.object_))
        dl.create(empty_roles_offer)
        accept = accept_case_participant_offer_activity(
            empty_roles_offer,
            target=_case_ref(AC1_CASE_ID),
            actor=AC1_CASE_OWNER_ID,
            to=[AC1_CASE_ACTOR_ID],
        )
        event = cast(
            AcceptOfferCaseParticipantReceivedEvent, received_event(accept)
        )

        result = AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.REFUSED, (
            f"Expected REFUSED for no-roles Accept(Offer), got {result.disposition}"
        )

        # No inert participant should have been created.
        reloaded_case = dl.read(AC1_CASE_ID)
        assert isinstance(reloaded_case, VulnerabilityCase)
        assert AC1_INVITEE_ID not in reloaded_case.actor_participant_index, (
            "CM-11-019: no inert participant must be created for a no-roles "
            "Accept(Offer(CaseParticipant))"
        )

    @pytest.mark.spec("CM-16-019")
    def test_participant_takes_only_the_recorded_roles(self):
        """Full round trip: the admitted participant holds the recorded roles.

        The reply's forged CASE_OWNER never reaches the Invite, so the invitee
        is admitted as VENDOR only (CM-16-019).
        """
        self._test_participant_case_roles_empty_after_full_round_trip_invite_obj()

    def _test_participant_case_roles_empty_after_full_round_trip_invite_obj(
        self,
    ):
        """Helper: find the Invite stored during step 1 of the round-trip."""

        dl = _seed_dl_for_ac1()
        event = self._build_accept_offer_event(dl)
        AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # Step 2: find the stored Invite
        outbox = dl.outbox_list()
        invite_obj = None
        for act_id in outbox:
            obj = dl.read(act_id)
            if obj is not None and str(getattr(obj, "type_", "")) == "Invite":
                invite_obj = obj
                break
        assert invite_obj is not None, (
            "Invite must be present in CaseActor outbox"
        )

        # Step 3: invitee sends Accept(Invite) — BT creates CaseParticipant
        py_trees.blackboard.Blackboard.storage.clear()
        from vultron.core.models.events.actor import (
            AcceptInviteActorToCaseReceivedEvent,
        )
        from vultron.core.use_cases.received.actor.invite import (
            AcceptInviteActorToCaseReceivedUseCase,
        )
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Invite,
        )

        accept_invite = rm_accept_invite_to_case_activity(
            cast(as_Invite, invite_obj), actor=AC1_INVITEE_ID
        )
        accept_invite_event = cast(
            AcceptInviteActorToCaseReceivedEvent, received_event(accept_invite)
        )
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            accept_invite_event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        # Step 4: assert participant.case_roles == [VENDOR]
        reloaded_case = cast(Any, dl.read(AC1_CASE_ID))
        participant_id = reloaded_case.actor_participant_index.get(
            AC1_INVITEE_ID
        )
        assert participant_id is not None, (
            "Invitee must be registered as participant"
        )
        participant = cast(Any, dl.get(id_=participant_id))
        assert participant is not None
        assert participant.case_roles == [CVDRole.VENDOR], (
            "participant.case_roles must be the recorded Offer's roles only"
        )


# ---------------------------------------------------------------------------
# #3752: a receiver that is not the CASE_MANAGER refuses and queues nothing
# ---------------------------------------------------------------------------


class TestOfferCaseParticipantDecisionsAtNonCaseManager:
    """Accept/Reject(Offer(CaseParticipant)) reach a copy-holder (#3752).

    Both decisions are addressed to the CASE_MANAGER, whose effects (notify the
    recommender, invite the actor) sit behind a role gate (BT-17-001).  A
    receiver that is not it — here the CaseActor store when another actor
    holds the role — queues nothing and refuses (HP-01-005).
    """

    OTHER_MANAGER_ID = "https://example.org/actors/other-case-manager"

    def _seed(self) -> SqliteDataLayer:
        dl, _ = _seed_dl_for_case_actor(manager_id=self.OTHER_MANAGER_ID)
        return dl

    @pytest.mark.spec("BT-17-001")
    @pytest.mark.spec("HP-01-005")
    def test_accept_at_non_case_manager_is_refused_and_queues_nothing(self):
        dl = self._seed()
        accept = accept_case_participant_offer_activity(
            _build_offer_activity(),
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        event = cast(
            AcceptOfferCaseParticipantReceivedEvent, received_event(accept)
        )

        result = AcceptOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "CASE_MANAGER" in result.reason
        assert dl.outbox_list() == [], (
            "a receiver that is not the CASE_MANAGER must neither notify the"
            " recommender nor invite the actor"
        )

    @pytest.mark.spec("BT-17-001")
    @pytest.mark.spec("HP-01-005")
    def test_reject_at_non_case_manager_is_refused_and_queues_nothing(self):
        dl = self._seed()
        reject = reject_case_participant_offer_activity(
            _build_offer_activity(),
            target=_case_ref(CASE_ID),
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        event = cast(
            RejectOfferCaseParticipantReceivedEvent, received_event(reject)
        )

        result = RejectOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "CASE_MANAGER" in result.reason
        assert dl.outbox_list() == [], (
            "a receiver that is not the CASE_MANAGER must not notify the"
            " recommender of the rejection"
        )


# ---------------------------------------------------------------------------
# CM-16-010: every step of the actor suggestion flow records its message
# after the message is sent or received (ADR-0119)
# ---------------------------------------------------------------------------


def _seed_a_recommendation_at_the_case_manager() -> tuple[
    SqliteDataLayer, Any
]:
    """The CASE_MANAGER's store and a participant's ``Offer(Actor, Case)``.

    The recommendation is not yet recorded, so the CASE_MANAGER forwards it to
    the Case Owner as ``Offer(CaseParticipant)`` (CM-16-004).
    """
    from test.core.use_cases.received.conftest import seed_case_participant
    from vultron.wire.as2.factories import recommend_actor_activity

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_ACTOR_ID)
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="OfferRoundTripTest", attributed_to=CASE_OWNER_ID
    )
    seed_case_manager_participant(dl, case, CASE_ACTOR_ID)
    seed_case_owner_participant(dl, case, CASE_OWNER_ID)
    seed_case_participant(dl, case, RECOMMENDER_ID)
    dl.create(as_Service(id_=CASE_ACTOR_ID))
    dl.create(case)
    recommendation = recommend_actor_activity(
        as_Actor(id_=RECOMMENDED_ID),
        target=_case_ref(CASE_ID),
        actor=RECOMMENDER_ID,
        to=[CASE_ACTOR_ID],
        suggested_roles=["vendor"],
    )
    return dl, received_event(recommendation)


def _assert_each_send_follows_its_queueing(
    events: list[tuple[str, str]], semantic_types: set[str]
) -> None:
    """Each entry of *semantic_types* follows the outbox write of its activity."""
    sent = [
        (kind, object_id)
        for kind, object_id in events
        if kind in semantic_types
    ]
    assert {kind for kind, _ in sent} == semantic_types, events
    for kind, object_id in sent:
        assert events.index(("queued", object_id)) < events.index(
            (kind, object_id)
        ), f"{kind} '{object_id}' was committed before it was queued: {events}"


class TestActorSuggestionFlowRecordsEachMessageAfterItIsSent:
    """CM-16-010: no step's entry is committed before its message.

    A message the CASE_MANAGER sends is recorded after it reaches the
    outbox; a message it receives is recorded after intake, before anything
    it sends in answer (ADR-0119, CLP-10-006).
    """

    @pytest.fixture(autouse=True)
    def _record(self, monkeypatch):
        from test.support.ledger import record_sends_and_commits

        self.events = record_sends_and_commits(monkeypatch, CASE_ACTOR_ID)

    @staticmethod
    def _execute(use_case_class, dl, event):
        result = use_case_class(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED, result

    @pytest.mark.spec("CM-16-010")
    def test_step_1_the_forward_to_the_owner_is_queued_then_recorded(self):
        from vultron.core.use_cases.received.actor.suggest import (
            OfferActorToCaseReceivedUseCase,
        )

        dl, event = _seed_a_recommendation_at_the_case_manager()

        self._execute(OfferActorToCaseReceivedUseCase, dl, event)

        assert self.events[0][0] != "queued", "the receipt is recorded first"
        _assert_each_send_follows_its_queueing(
            self.events, {"offer_case_participant"}
        )

    @pytest.mark.spec("CM-16-010")
    def test_step_3_the_owners_accept_is_recorded_then_each_answer(self):
        dl, _ = _seed_dl_for_case_actor()
        event = TestAcceptOfferCaseParticipantReceivedUseCase()._event_with_stored_offer(
            dl
        )

        self._execute(AcceptOfferCaseParticipantReceivedUseCase, dl, event)

        assert self.events[0][0] != "queued", "the Accept is recorded first"
        _assert_each_send_follows_its_queueing(
            self.events,
            {"invite_actor_to_case", "accept_actor_recommendation"},
        )

    @pytest.mark.spec("CM-16-010")
    def test_step_3_the_owners_reject_is_recorded_then_its_answer(self):
        dl, _ = _seed_dl_for_case_actor()
        event = TestRejectOfferCaseParticipantReceivedUseCase()._event()

        self._execute(RejectOfferCaseParticipantReceivedUseCase, dl, event)

        assert self.events[0][0] != "queued", "the Reject is recorded first"
        _assert_each_send_follows_its_queueing(
            self.events, {"reject_actor_recommendation"}
        )


class TestActorSuggestionAnswersAreSentOnceOnRetry:
    """A retry after a send whose commit failed sends nothing twice.

    Each answer's id is derived from the recommendation it answers, so the
    retry rebuilds the queued answer under the same id: the outbox does not
    queue it again (OX-06-002) and the commit records it once (ADR-0119).
    """

    @staticmethod
    def _run(use_case_class, dl, event):
        return use_case_class(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

    @staticmethod
    def _queued_of(dl: SqliteDataLayer, type_: str) -> list[str]:
        return [
            item
            for item in dl.outbox_list()
            if str(getattr(dl.read(item), "type_", "")) == type_
        ]

    @staticmethod
    def _entries_of(dl: SqliteDataLayer, semantic_type: str) -> list[str]:
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        return [
            e.log_object_id
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and e.semantic_type == semantic_type
        ]

    def _retry_after_a_failed_commit(
        self, use_case_class, dl, event, semantic_type
    ) -> str:
        from test.support.ledger import fail_commits
        from vultron.core.behaviors.sync import commit_tree

        with pytest.MonkeyPatch.context() as mp:
            failed = fail_commits(
                mp,
                commit_tree,
                when=lambda kw: kw["semantic_type"] == semantic_type,
            )
            # The answer is queued, so the failed commit escapes rather than
            # failing the tree into another arm (BT-14-001).
            with pytest.raises(VultronBTInternalError, match="commit failed"):
                self._run(use_case_class, dl, event)
        (answer_id,) = failed
        assert dl.outbox_list().count(answer_id) == 1
        assert self._entries_of(dl, semantic_type) == []

        retry = self._run(use_case_class, dl, event)

        assert retry.disposition is HandlerDisposition.APPLIED, retry
        assert dl.outbox_list().count(answer_id) == 1
        assert self._entries_of(dl, semantic_type) == [answer_id]
        return answer_id

    @pytest.mark.spec("OX-06-002")
    @pytest.mark.spec("CM-16-010")
    def test_the_forwarded_offer_is_sent_once(self):
        from vultron.core.use_cases.received.actor.suggest import (
            OfferActorToCaseReceivedUseCase,
        )

        dl, event = _seed_a_recommendation_at_the_case_manager()

        self._retry_after_a_failed_commit(
            OfferActorToCaseReceivedUseCase,
            dl,
            event,
            "offer_case_participant",
        )

    @pytest.mark.spec("OX-06-002")
    @pytest.mark.spec("CM-16-010")
    def test_accept_actor_recommendation_is_sent_once(self):
        dl, _ = _seed_dl_for_case_actor()
        event = TestAcceptOfferCaseParticipantReceivedUseCase()._event_with_stored_offer(
            dl
        )

        self._retry_after_a_failed_commit(
            AcceptOfferCaseParticipantReceivedUseCase,
            dl,
            event,
            "accept_actor_recommendation",
        )

    @pytest.mark.spec("OX-06-002")
    @pytest.mark.spec("CM-16-010")
    def test_reject_actor_recommendation_is_sent_once(self):
        dl, _ = _seed_dl_for_case_actor()
        event = TestRejectOfferCaseParticipantReceivedUseCase()._event()

        self._retry_after_a_failed_commit(
            RejectOfferCaseParticipantReceivedUseCase,
            dl,
            event,
            "reject_actor_recommendation",
        )


class TestAFailedAnswerCommitDoesNotFallThrough:
    """A queued answer whose commit fails ends the tree; no other arm runs.

    The answer is in the outbox before it is committed (ADR-0119), so a
    FAILURE would let the recommendation Selector try its next arm and
    forward a fresh ``Offer(CaseParticipant)`` after the ``Accept``.  The
    failed commit escapes as an internal error instead (BT-14-001).
    """

    @pytest.mark.spec("BT-14-001")
    @pytest.mark.spec("CM-16-010")
    def test_the_already_participant_accept_is_the_only_send(self):
        from test.core.use_cases.received.conftest import (
            seed_case_participant,
        )
        from test.support.ledger import fail_commits
        from vultron.core.behaviors.sync import commit_tree
        from vultron.core.use_cases.received.actor.suggest import (
            OfferActorToCaseReceivedUseCase,
        )

        dl, event = _seed_a_recommendation_at_the_case_manager()
        case = dl.read_case(CASE_ID)
        assert case is not None
        seed_case_participant(dl, case, RECOMMENDED_ID)
        dl.save(case)

        with pytest.MonkeyPatch.context() as mp:
            failed = fail_commits(
                mp,
                commit_tree,
                when=lambda kw: (
                    kw["semantic_type"] == "accept_actor_recommendation"
                ),
            )
            with pytest.raises(VultronBTInternalError, match="commit failed"):
                OfferActorToCaseReceivedUseCase(
                    dl,
                    event,
                    trigger_activity=TriggerActivityAdapter(dl),
                    wire_render_port=As2WireRenderAdapter(),
                    sync_port=SyncActivityAdapter(dl),
                ).execute()

        (accept_id,) = failed
        answers = [
            item
            for item in dl.outbox_list()
            if str(getattr(dl.read(item), "type_", "")) != "Announce"
        ]
        assert answers == [accept_id], (
            "only the Accept may be queued; no other arm may answer after it"
        )
