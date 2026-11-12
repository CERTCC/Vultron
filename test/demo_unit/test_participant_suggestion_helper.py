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
"""Tests of :mod:`vultron.demo.helpers.participant_suggestion` (BT-24-007).

A cast member asks its participant suggester who else belongs: the
scenario's table is resolved to actor ids, the static adapter is asked
through the core service about a private copy of the asker's replica, and
the answer comes back grouped by actor with every role it was named in.
The asker's replica is a real store read the way the inspection route
serves it (:class:`~test.support.replica_client.StoreClient`).
"""

import json
from unittest.mock import MagicMock
from urllib.parse import unquote

import httpx2 as httpx
import pytest

from test.demo._helpers import mock_case, story_state
from test.support.objects import make
from test.support.replica_client import StoreClient, seed_case_replica
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    engine as sqlite_engine,
)
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_suggestion import ParticipantSuggestion
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.participant_suggestion import (
    Candidate,
    SuggestedActor,
    _grouped,
    ask_who_else_belongs,
    replica_copy,
)
from vultron.demo.helpers.story import StoryState
from vultron.enums import CVDRole
from vultron.errors import DemoStoryError

_CASE = "urn:test:case"
_ASKER = Part("asker", "Asker")
_OWNER = Part("owner", "Owner")
_NEWCOMER = Part("newcomer", "Newcomer")

_TABLE = (
    Candidate(_NEWCOMER, CVDRole.VENDOR, "ships the component"),
    Candidate(_NEWCOMER, CVDRole.DEPLOYER, "runs the component"),
)


def _state_with_replica(*in_case: Part) -> tuple[StoryState, StoreClient]:
    """A story whose asker reads a real replica holding *in_case*."""
    state = story_state(
        _ASKER.name, _OWNER.name, _NEWCOMER.name, case=mock_case(_CASE)
    )
    asker_id = state.actor_id(_ASKER.name)
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=asker_id)
    seed_case_replica(
        store,
        _CASE,
        {state.actor_id(p.name): [CVDRole.VENDOR] for p in in_case},
    )
    client = StoreClient(store)
    asker = state.actor(_ASKER.name)
    state.cast[_ASKER.name] = ActorSession(client=client, actor=asker.actor)  # type: ignore[arg-type]
    return state, client


@pytest.mark.spec("BT-24-007")
def test_the_newcomer_is_suggested_once_in_both_its_roles() -> None:
    state, _ = _state_with_replica(_OWNER, _ASKER)
    assert ask_who_else_belongs(state, _ASKER, _TABLE) == (
        SuggestedActor(
            _NEWCOMER,
            state.actor_id(_NEWCOMER.name),
            (CVDRole.VENDOR, CVDRole.DEPLOYER),
        ),
    )


@pytest.mark.spec("BT-24-008")
def test_the_answer_is_projected_from_the_askers_replica() -> None:
    """The case, its participants and its report are read off the replica."""
    state, client = _state_with_replica(_OWNER, _ASKER)
    ask_who_else_belongs(state, _ASKER, _TABLE)
    assert unquote(client.paths[0]) == _CASE
    assert len(client.paths) == 1 + 2 + 1  # case, two participants, report


def test_a_newcomer_already_in_the_case_is_not_suggested() -> None:
    state, _ = _state_with_replica(_OWNER, _ASKER, _NEWCOMER)
    assert ask_who_else_belongs(state, _ASKER, _TABLE) == ()


@pytest.mark.spec("BT-24-004")
def test_an_empty_table_suggests_no_one() -> None:
    state, _ = _state_with_replica(_OWNER, _ASKER)
    assert ask_who_else_belongs(state, _ASKER, ()) == ()


def test_a_replica_without_the_case_fails_the_ask() -> None:
    state = story_state(_ASKER.name, _NEWCOMER.name, case=mock_case(_CASE))
    empty = SqliteDataLayer(
        "sqlite:///:memory:", actor_id=state.actor_id(_ASKER.name)
    )
    asker = state.actor(_ASKER.name)
    state.cast[_ASKER.name] = ActorSession(
        client=StoreClient(empty),  # type: ignore[arg-type]
        actor=asker.actor,
    )
    with pytest.raises(httpx.HTTPStatusError):
        ask_who_else_belongs(state, _ASKER, _TABLE)


def test_an_answer_naming_an_actor_off_the_table_is_a_story_error() -> None:
    state = story_state(_NEWCOMER.name, _OWNER.name)
    stray = ParticipantSuggestion(
        actor_id=state.actor_id(_OWNER.name),
        role=CVDRole.VENDOR,
        rationale="not a row of the table",
    )
    with pytest.raises(DemoStoryError, match="no row of the scenario"):
        _grouped(state, _TABLE, [stray])


def test_the_copy_is_a_fresh_store_disposed_on_exit() -> None:
    """The copy shares no engine with the asker's own store, and goes away."""
    _, client = _state_with_replica(_OWNER, _ASKER)
    before = set(sqlite_engine._ENGINES)
    with replica_copy(client, _CASE) as copy:  # type: ignore[arg-type]
        assert copy.actor_id == client.actor_id
        assert copy.read_case(_CASE) is not None
        opened = set(sqlite_engine._ENGINES) - before
        assert len(opened) == 1
        assert all("suggest-" in key for key in opened)
    assert set(sqlite_engine._ENGINES) == before


def test_the_copy_needs_a_client_that_names_its_actor() -> None:
    client = StoreClient(SqliteDataLayer("sqlite:///:memory:", actor_id="a"))
    client.actor_id = None  # type: ignore[assignment]
    with pytest.raises(ValueError, match="must name the actor"):
        with replica_copy(client, _CASE):  # type: ignore[arg-type]
            pass


def test_a_failed_copy_is_disposed_too() -> None:
    """A replica read that raises part-way still leaves no copy behind."""
    empty = SqliteDataLayer("sqlite:///:memory:", actor_id="urn:test:asker")
    before = set(sqlite_engine._ENGINES)
    with pytest.raises(httpx.HTTPStatusError):
        with replica_copy(StoreClient(empty), _CASE):  # type: ignore[arg-type]
            pass  # pragma: no cover - the copy never opens
    assert set(sqlite_engine._ENGINES) == before


def test_an_object_the_replica_holds_inline_is_copied_without_a_read() -> None:
    """Only a reference is fetched; an inline participant is the record."""
    participant = make(
        CaseParticipant,
        attributed_to="urn:test:owner",
        context=_CASE,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case = make(
        VulnerabilityCase,
        id_=_CASE,
        attributed_to="urn:test:owner",
        case_participants=[participant],
    )
    served = json.loads(bytes(AS2JSONResponse(case).body))
    client = MagicMock()
    client.actor_id = "urn:test:asker"
    client.dl_path.side_effect = lambda key: key
    client.get.return_value = served

    with replica_copy(client, _CASE) as copy:
        assert copy.read(participant.id_) is not None

    client.get.assert_called_once()


def test_a_role_named_twice_for_one_actor_is_kept_once() -> None:
    state = story_state(_NEWCOMER.name)
    newcomer = state.actor_id(_NEWCOMER.name)
    twice = [
        ParticipantSuggestion(
            actor_id=newcomer, role=CVDRole.VENDOR, rationale=reason
        )
        for reason in ("ships it", "ships it again")
    ]
    assert _grouped(state, _TABLE, twice) == (
        SuggestedActor(_NEWCOMER, newcomer, (CVDRole.VENDOR,)),
    )
