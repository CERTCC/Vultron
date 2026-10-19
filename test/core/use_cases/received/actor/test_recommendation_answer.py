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
"""The recommender's receipt of the CASE_MANAGER's answer (CM-16-006/007/009).

Before #4527 no registry entry routed ``Accept``/``Reject(Offer(Actor))``, so
the recommender refused every answer as ``UNKNOWN``.  The answer is built here
by the adapter method the CASE_MANAGER sends it with and parsed as the inbox
parses it, so the shape tested is the one that goes out.
"""

import json
from collections.abc import Callable
from typing import Literal, cast

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.events.actor import (
    AcceptActorRecommendationReceivedEvent,
    RejectActorRecommendationReceivedEvent,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases.received.actor.recommendation_answer import (
    AcceptActorRecommendationReceivedUseCase,
    RejectActorRecommendationReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/recommendation-answer-case"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
CASE_OWNER_ID = "https://example.org/actors/case-owner"
RECOMMENDER_ID = "https://example.org/actors/finder"
RECOMMENDED_ID = "https://example.org/actors/vendor-new"
BYSTANDER_ID = "https://example.org/actors/bystander"
RECOMMENDATION_ID = "https://example.org/activities/recommendation-001"

Verb = Literal["accept", "reject"]
type AnswerEvent = (
    AcceptActorRecommendationReceivedEvent
    | RejectActorRecommendationReceivedEvent
)
_USE_CASES: dict[
    Verb,
    Callable[
        ...,
        AcceptActorRecommendationReceivedUseCase
        | RejectActorRecommendationReceivedUseCase,
    ],
] = {
    "accept": AcceptActorRecommendationReceivedUseCase,
    "reject": RejectActorRecommendationReceivedUseCase,
}
_SEMANTICS = {
    "accept": MessageSemantics.ACCEPT_ACTOR_RECOMMENDATION,
    "reject": MessageSemantics.REJECT_ACTOR_RECOMMENDATION,
}


def _answer(verb: Verb, sender_id: str = CASE_ACTOR_ID) -> as_Activity:
    """The answer as the CASE_MANAGER's adapter builds it (CM-16-006/007)."""
    builder = TriggerActivityAdapter(
        SqliteDataLayer("sqlite:///:memory:", actor_id=sender_id)
    )
    emit = (
        builder.emit_accept_actor_recommendation
        if verb == "accept"
        else builder.emit_reject_actor_recommendation
    )
    _, body = emit(
        recommender_id=RECOMMENDER_ID,
        recommendation_id=RECOMMENDATION_ID,
        recommended_id=RECOMMENDED_ID,
        case_id=CASE_ID,
        actor=sender_id,
    )
    return parse_activity(json.loads(body))


def _event(verb: Verb, sender_id: str = CASE_ACTOR_ID) -> AnswerEvent:
    event = extract_event(_answer(verb, sender_id))
    assert event.semantic_type is _SEMANTICS[verb]
    return cast(AnswerEvent, event)


def _store(receiver_id: str = RECOMMENDER_ID) -> SqliteDataLayer:
    """A participant replica whose case names ``CASE_ACTOR_ID`` as manager."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver_id)
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="RecommendationAnswerTest",
        attributed_to=CASE_OWNER_ID,
    )
    seed_case_manager_participant(dl, case, CASE_ACTOR_ID)
    seed_case_participant(dl, case, receiver_id, [CVDRole.REPORTER])
    dl.create(as_Actor(id_=receiver_id))  # type: ignore[arg-type]
    dl.create(case)
    return dl


def _run(
    dl: SqliteDataLayer, verb: Verb, event: AnswerEvent | None = None
) -> HandlerResult:
    use_case = _USE_CASES[verb]
    return use_case(
        dl,
        event if event is not None else _event(verb),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()


@pytest.mark.spec("CM-16-006")
@pytest.mark.spec("CM-16-007")
@pytest.mark.spec("VAM-04-016")
@pytest.mark.spec("VAM-04-017")
@pytest.mark.parametrize("verb", ["accept", "reject"])
def test_answer_routes_to_its_own_semantics_with_in_reply_to(verb: Verb):
    """The sent answer dispatches, and ``inReplyTo`` names the recommendation."""
    event = _event(verb)
    assert event.in_reply_to == RECOMMENDATION_ID
    assert event.object_id == RECOMMENDATION_ID


@pytest.mark.spec("CLP-02-013")
@pytest.mark.parametrize("verb", ["accept", "reject"])
def test_recommender_archives_the_answer_and_commits_nothing(verb: Verb):
    """A participant never commits; the CASE_MANAGER ledgered the answer."""
    dl = _store()
    event = _event(verb)

    result = _run(dl, verb, event)

    assert result.disposition is HandlerDisposition.APPLIED
    assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []


@pytest.mark.parametrize("verb", ["accept", "reject"])
def test_redelivered_answer_is_skipped(verb: Verb):
    dl = _store()
    event = _event(verb)
    assert _run(dl, verb, event).disposition is HandlerDisposition.APPLIED

    assert _run(dl, verb, event).disposition is HandlerDisposition.SKIPPED


@pytest.mark.spec("PCR-03-001")
@pytest.mark.parametrize("verb", ["accept", "reject"])
def test_answer_from_anyone_but_the_case_manager_is_refused(verb: Verb):
    """The Case Owner decides, but only the CASE_MANAGER answers (CM-16-019)."""
    dl = _store()

    result = _run(dl, verb, _event(verb, sender_id=CASE_OWNER_ID))

    assert result.disposition is HandlerDisposition.REFUSED
    assert "is not the CASE_MANAGER" in (result.reason or "")
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []


@pytest.mark.spec("HP-01-005")
@pytest.mark.parametrize("verb", ["accept", "reject"])
def test_bystander_copy_is_refused(verb: Verb):
    """A copy addressed to the recommender, held by someone else."""
    dl = _store(receiver_id=BYSTANDER_ID)

    result = _run(dl, verb)

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason is not None
    assert BYSTANDER_ID in result.reason


@pytest.mark.spec("CLP-10-018")
@pytest.mark.parametrize("verb", ["accept", "reject"])
def test_answer_naming_no_case_is_archived_and_refused(verb: Verb):
    """With no case to check the sender against, the tree refuses it."""
    dl = _store()
    event = _event(verb).model_copy(update={"target": None})

    result = _run(dl, verb, event)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "names no case" in (result.reason or "")
    assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))
