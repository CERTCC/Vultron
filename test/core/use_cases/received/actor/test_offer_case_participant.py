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
from typing import Any, cast
from unittest.mock import MagicMock

import py_trees
import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.events.actor import (
    AcceptOfferCaseParticipantReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.offer_case_participant import (
    AcceptOfferCaseParticipantReceivedUseCase,
    OfferCaseParticipantReceivedUseCase,
    RejectOfferCaseParticipantReceivedUseCase,
)
from vultron.semantic_registry import extract_event
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
        # What OfferActorToCaseReceivedUseCase records when the recommendation
        # arrives (CM-16-004): the decision handlers read the recommender
        # from here, and refuse a decision on a recommendation never recorded.
        recommendation_recommender_index={RECOMMENDATION_ID: RECOMMENDER_ID},
    )
    seed_case_manager_participant(dl, case, manager_id)
    dl.create(case_actor)
    dl.create(case)
    return dl, CASE_ACTOR_ID


def _forget_recommendation(dl: SqliteDataLayer) -> None:
    """Drop the recorded recommender, as a store that never saw the Offer."""
    from vultron.core.models.case import VulnerabilityCase

    case = dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    case.recommendation_recommender_index = {}
    dl.save(case)


def _build_offer_activity(
    actor: str = CASE_ACTOR_ID,
    to: list[str] | None = None,
    cc: list[str] | None = None,
    origin: str | None = RECOMMENDATION_ID,
):
    recommended = as_Actor(id_=RECOMMENDED_ID)
    extra: dict[str, Any] = {"origin": origin} if origin is not None else {}
    return offer_case_participant_activity(
        recommended,
        target=_case_ref(CASE_ID),
        actor=actor,
        to=to or [CASE_OWNER_ID],
        cc=cc or [],
        **extra,
    )


# ---------------------------------------------------------------------------
# OfferCaseParticipantReceivedUseCase (Case Owner inbox)
# ---------------------------------------------------------------------------


class TestOfferCaseParticipantReceivedUseCase:
    def _event(self) -> OfferCaseParticipantReceivedEvent:
        activity = _build_offer_activity()
        return cast(OfferCaseParticipantReceivedEvent, extract_event(activity))

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
            OfferCaseParticipantReceivedEvent, extract_event(activity)
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
            AcceptOfferCaseParticipantReceivedEvent, extract_event(accept)
        )

    def test_executes_without_error(self):
        dl, _ = _seed_dl_for_case_actor()
        event = self._event()
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
        assert dl.outbox_list() == []

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
        assert dl.outbox_list() == []

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

    def test_skips_when_missing_invitee_id(self, caplog):
        dl, _ = _seed_dl_for_case_actor()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/bad-accept-2"
        mock_event.target_id = CASE_ID
        mock_event.activity = MagicMock()
        # object_ has no attributed_to → invitee_id will be None
        inner_offer = MagicMock()
        inner_offer.object_ = MagicMock(attributed_to=None)
        inner_offer.origin = None
        mock_event.activity.object_ = inner_offer
        with caplog.at_level(logging.WARNING):
            result = AcceptOfferCaseParticipantReceivedUseCase(
                dl,
                mock_event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()
        assert any("missing" in r.message.lower() for r in caplog.records)
        assert result.disposition is HandlerDisposition.REFUSED

    def test_recommender_notified_via_core_state(self):
        """AC-5: recommender notification emitted; recommender read from core state.

        Seeds recommendation_recommender_index on the case (as
        OfferActorToCaseReceivedUseCase does at ingestion time), then runs
        AcceptOfferCaseParticipantReceivedUseCase and asserts that at least
        two outbox activities are queued — one Invite to the invitee and one
        AcceptActorRecommendation to the recommender — confirming the recommender
        ID came from core state, not from a dl.read(recommendation_id) re-read.
        """
        from vultron.core.models.case import VulnerabilityCase

        RECOMMENDATION_ID = "https://example.org/activities/orig-offer-001"

        dl, _actor_id = _seed_dl_for_case_actor()
        # Seed the recommender index as OfferActorToCaseReceivedUseCase would.
        case = dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        case.recommendation_recommender_index[RECOMMENDATION_ID] = (
            RECOMMENDER_ID
        )
        dl.save(case)

        event = self._event()
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
            "recommender lookup must read from core state (recommendation_recommender_index)"
        )


# ---------------------------------------------------------------------------
# RejectOfferCaseParticipantReceivedUseCase (CaseActor inbox)
# ---------------------------------------------------------------------------


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
            RejectOfferCaseParticipantReceivedEvent, extract_event(reject)
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
        assert dl.outbox_list() == []

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
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-16-007")
    def test_refuses_when_no_recommended_actor_can_be_named(self):
        """A Reject whose Offer names neither a participant nor an object id.

        ``RejectActorRecommendation`` carries the recommended actor; with no
        ``attributed_to`` on the CaseParticipant and no ``object_id`` on the
        event there is nobody to name, and before #3877 ``""`` was sent.
        """
        dl, _ = _seed_dl_for_case_actor()
        event = MagicMock()
        event.activity_id = "https://example.org/activities/reject-no-actor"
        event.target_id = CASE_ID
        event.object_id = None
        event.receiving_actor_id = CASE_ACTOR_ID
        event.activity.object_.origin = RECOMMENDATION_ID
        event.activity.object_.object_ = None
        result = RejectOfferCaseParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.REFUSED
        assert "no recommended actor" in (result.reason or "")
        assert dl.outbox_list() == []

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

        Seeds recommendation_recommender_index on the case and asserts that
        RejectOfferCaseParticipantReceivedUseCase queues a RejectActorRecommendation
        addressed to the recommender, read from core state.
        """
        from vultron.core.models.case import VulnerabilityCase

        RECOMMENDATION_ID = "https://example.org/activities/orig-offer-001"

        dl, _actor_id = _seed_dl_for_case_actor()
        case = dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        case.recommendation_recommender_index[RECOMMENDATION_ID] = (
            RECOMMENDER_ID
        )
        dl.save(case)

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
            "recommender lookup must read from core state (recommendation_recommender_index)"
        )


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
        # Recorded when the recommendation arrived (CM-16-004); the Accept
        # handler refuses a decision on a recommendation never recorded.
        recommendation_recommender_index={
            RECOMMENDATION_ID: AC1_RECOMMENDER_ID
        },
    )
    # The CaseActor holds CASE_MANAGER: both the Accept(Offer) effects and
    # the Accept(Invite) effects are role-gated (BT-17-001, BT-17-005).
    seed_case_manager_participant(dl, case, AC1_CASE_ACTOR_ID)
    invitee = as_Organization(id_=AC1_INVITEE_ID)
    dl.create(case_actor)
    dl.create(case)
    dl.create(invitee)
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
            AcceptOfferCaseParticipantReceivedEvent, extract_event(accept)
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
            AcceptInviteActorToCaseReceivedEvent, extract_event(accept_invite)
        )
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            accept_invite_event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
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

    def _build_accept_offer_event(
        self,
    ) -> AcceptOfferCaseParticipantReceivedEvent:
        from vultron.enums.roles import CVDRole

        recommended = as_Actor(id_=AC1_INVITEE_ID)
        offer = offer_case_participant_activity(
            recommended,
            target=_case_ref(AC1_CASE_ID),
            actor=AC1_CASE_ACTOR_ID,
            to=[AC1_CASE_OWNER_ID],
            roles=[CVDRole.VENDOR],
            # CM-16-004: the transformed Offer names the recommendation it
            # answers; without it the CASE_MANAGER has nobody to notify.
            origin=RECOMMENDATION_ID,
        )
        accept = accept_case_participant_offer_activity(
            offer,
            target=_case_ref(AC1_CASE_ID),
            actor=AC1_CASE_OWNER_ID,
            to=[AC1_CASE_ACTOR_ID],
        )
        return cast(
            AcceptOfferCaseParticipantReceivedEvent, extract_event(accept)
        )

    def test_invite_roles_none_when_no_blackboard_key(self):
        """AC-2: EmitInviteActorToCaseNode passes roles=None to factory.

        When Accept(Offer(CaseParticipant)) arrives, ``suggested_roles`` is
        absent from the blackboard (``create_accept_actor_recommendation_received_tree``
        does not write it).  ``EmitInviteActorToCaseNode._read_suggested_roles()``
        returns None, and the stored Invite has roles=None — no silent default
        substitution (ADR-0032, BT-HELPER-01).
        """
        dl = _seed_dl_for_ac1()
        event = self._build_accept_offer_event()
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
        assert getattr(invite_obj, "roles", "sentinel") is None, (
            "AC-2: EmitInviteActorToCaseNode must pass roles=None when "
            "suggested_roles is absent from blackboard (no default substitution)"
        )

    def test_participant_case_roles_empty_after_full_round_trip(self):
        """AC-1: Full suggest-actor round-trip ends with participant.case_roles==[].

        Roles from Accept(Offer(CaseParticipant[VENDOR])) are NOT threaded into
        the Invite when ``suggested_roles`` is absent from the blackboard.
        The resulting participant is created with an empty case_roles list.
        """
        from vultron.core.use_cases.received.actor.invite import (
            AcceptInviteActorToCaseReceivedUseCase,
        )

        dl = _seed_dl_for_ac1()
        event = self._build_accept_offer_event()

        # Step 1: CaseActor receives Accept(Offer(CaseParticipant)) → emits Invite
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
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Invite,
        )

        accept_invite = rm_accept_invite_to_case_activity(
            cast(as_Invite, invite_obj), actor=AC1_INVITEE_ID
        )
        accept_invite_event = cast(
            AcceptInviteActorToCaseReceivedEvent, extract_event(accept_invite)
        )
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            accept_invite_event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        # Step 4: assert participant.case_roles == []
        reloaded_case = cast(Any, dl.read(AC1_CASE_ID))
        participant_id = reloaded_case.actor_participant_index.get(
            AC1_INVITEE_ID
        )
        assert participant_id is not None, (
            "Invitee must be registered as participant"
        )
        participant = cast(Any, dl.get(id_=participant_id))
        assert participant is not None
        assert participant.case_roles == [], (
            "AC-1: participant.case_roles must be [] when roles were not "
            "threaded from CaseParticipant offer (suggested_roles absent)"
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
        from vultron.core.models.case import VulnerabilityCase

        dl, _ = _seed_dl_for_case_actor(manager_id=self.OTHER_MANAGER_ID)
        case = dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        case.recommendation_recommender_index[
            "https://example.org/activities/orig-offer-001"
        ] = RECOMMENDER_ID
        dl.save(case)
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
            AcceptOfferCaseParticipantReceivedEvent, extract_event(accept)
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
            RejectOfferCaseParticipantReceivedEvent, extract_event(reject)
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
