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
"""The SuggestParticipants Retriever wraps the core service (BT-24, ADR-0186).

- Its REAL backend reads the case id, asks the service and writes the
  suggestions to its typed output port (BT-18-012, BT-24-008).
- A failure to find out is *error*, never *no* (ADR-0183).
- Its DETERMINISTIC default writes an empty list (BT-23-013, BT-23-014).
- It sits behind the time-bounded seam and answers within the budget
  (BT-18-015).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

import py_trees
import pytest
from py_trees.common import Access, Status
from py_trees.ports import NoDataAvailable

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.call_out.bundles.participant_suggestion import (
    PARTICIPANT_SUGGESTION_DETERMINISTIC,
    ParticipantSuggestionCallOutBundle,
    SuggestParticipantsRetriever,
    suggest_participants_with,
)
from vultron.core.behaviors.call_out.capabilities.participant_suggestion import (
    PARTICIPANT_SUGGESTIONS_KEY,
    SUGGESTION_CASE_ID_KEY,
    SuggestParticipantsCapability,
)
from vultron.core.behaviors.call_out.errors import (
    CallOutBackendError,
    CallOutBudgetExceededError,
)
from vultron.core.behaviors.call_out.guard import (
    TimeBoundedCallOut,
    unwrap_call_out,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.participant_suggestion import (
    ParticipantSuggestion,
    SuggestionContext,
)
from vultron.enums import CVDRole
from vultron.errors import VultronError

_OWNER = "https://example.org/actors/owner"
_CASE = "https://example.org/cases/c-1"
_SUGGESTION = ParticipantSuggestion(
    actor_id="https://example.org/actors/other-inc",
    role=CVDRole.VENDOR,
    rationale="bundles the affected library",
)


class _Port:
    def __init__(
        self, answer: Sequence[ParticipantSuggestion] = (_SUGGESTION,)
    ) -> None:
        self._answer = answer
        self.asked: list[SuggestionContext] = []

    def suggest_participants(
        self, context: SuggestionContext
    ) -> Sequence[ParticipantSuggestion]:
        self.asked.append(context)
        return self._answer


class _UnreachablePort:
    def suggest_participants(
        self, context: SuggestionContext
    ) -> Sequence[ParticipantSuggestion]:
        raise VultronError("suggestion service unreachable")


class _Stopwatch:
    def __init__(self) -> None:
        self.now = 100.0

    def seconds(self) -> float:
        return self.now


class _SlowPort(_Port):
    """Answers after moving *stopwatch* on by *took*."""

    def __init__(self, stopwatch: _Stopwatch, took: timedelta) -> None:
        super().__init__()
        self._stopwatch = stopwatch
        self._took = took

    def suggest_participants(
        self, context: SuggestionContext
    ) -> Sequence[ParticipantSuggestion]:
        self._stopwatch.now += self._took.total_seconds()
        return super().suggest_participants(context)


@pytest.fixture(autouse=True)
def _clean_blackboard():
    py_trees.blackboard.Blackboard.clear()
    yield
    py_trees.blackboard.Blackboard.clear()


@pytest.fixture
def dl() -> SqliteDataLayer:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_OWNER)
    store.create(make(VulnerabilityCase, id_=_CASE, attributed_to=_OWNER))
    return store


def _place_case_id(case_id: str = _CASE) -> None:
    writer = py_trees.blackboard.Client(name="suggestion_test_writer")
    writer.register_key(SUGGESTION_CASE_ID_KEY, Access.WRITE)
    writer.set(SUGGESTION_CASE_ID_KEY, case_id)


def _written() -> object:
    return py_trees.blackboard.Blackboard.storage.get(
        f"/{PARTICIPANT_SUGGESTIONS_KEY}"
    )


def _node(
    bundle: ParticipantSuggestionCallOutBundle,
) -> py_trees.behaviour.Behaviour:
    node = bundle.suggest_participants_factory("SuggestParticipants")
    node.setup()
    return node


@pytest.mark.spec("BT-18-012")
@pytest.mark.spec("BT-24-008")
def test_the_retriever_writes_the_services_suggestions(
    dl: SqliteDataLayer,
) -> None:
    port = _Port()
    node = _node(
        ParticipantSuggestionCallOutBundle(
            suggest_participants_factory=suggest_participants_with(port, dl)
        )
    )
    _place_case_id()

    node.tick_once()

    assert node.status == Status.SUCCESS
    assert _written() == [_SUGGESTION]
    [asked] = port.asked
    assert asked.id_ == _CASE
    backend = unwrap_call_out(node)
    assert isinstance(backend, SuggestParticipantsRetriever)
    assert type(backend).declaration() is SuggestParticipantsCapability


@pytest.mark.spec("BT-24-004")
def test_an_empty_answer_is_a_yes_with_an_empty_list(
    dl: SqliteDataLayer,
) -> None:
    node = _node(
        ParticipantSuggestionCallOutBundle(
            suggest_participants_factory=suggest_participants_with(
                _Port(()), dl
            )
        )
    )
    _place_case_id()
    node.tick_once()
    assert node.status == Status.SUCCESS
    assert _written() == []


@pytest.mark.parametrize(
    ("port", "case_id", "diagnostic"),
    [
        (_UnreachablePort(), _CASE, "suggestion service unreachable"),
        (_Port(), "https://example.org/cases/missing", "not found"),
    ],
    ids=["adapter-unreachable", "case-missing"],
)
def test_a_failure_to_find_out_is_an_error_not_a_no(
    dl: SqliteDataLayer, port: object, case_id: str, diagnostic: str
) -> None:
    node = _node(
        ParticipantSuggestionCallOutBundle(
            suggest_participants_factory=suggest_participants_with(
                port,  # type: ignore[arg-type]
                dl,
            )
        )
    )
    _place_case_id(case_id)
    with pytest.raises(CallOutBackendError, match=diagnostic):
        node.tick_once()
    assert _written() is None


def test_no_case_id_on_the_blackboard_is_a_wiring_error(
    dl: SqliteDataLayer,
) -> None:
    """A tree that places the Retriever without its input fails whole."""
    port = _Port()
    node = _node(
        ParticipantSuggestionCallOutBundle(
            suggest_participants_factory=suggest_participants_with(port, dl)
        )
    )
    with pytest.raises(NoDataAvailable, match=SUGGESTION_CASE_ID_KEY):
        node.tick_once()
    assert port.asked == []


@pytest.mark.spec("BT-23-013")
@pytest.mark.spec("BT-23-014")
def test_the_deterministic_default_writes_an_empty_list() -> None:
    node = _node(PARTICIPANT_SUGGESTION_DETERMINISTIC)
    node.tick_once()
    assert node.status == Status.SUCCESS
    assert _written() == []
    backend = unwrap_call_out(node)
    assert isinstance(backend, SuggestParticipantsCapability)
    assert type(backend).declaration() is SuggestParticipantsCapability


@pytest.mark.spec("BT-18-015")
def test_every_product_of_the_bundle_is_time_bounded(
    dl: SqliteDataLayer,
) -> None:
    for bundle in (
        PARTICIPANT_SUGGESTION_DETERMINISTIC,
        ParticipantSuggestionCallOutBundle(
            suggest_participants_factory=suggest_participants_with(_Port(), dl)
        ),
    ):
        assert isinstance(_node(bundle), TimeBoundedCallOut)


@pytest.mark.spec("BT-18-015")
@pytest.mark.parametrize(
    ("took", "overran"),
    [(timedelta(milliseconds=40), False), (timedelta(milliseconds=250), True)],
    ids=["within", "over"],
)
def test_the_retriever_answers_within_the_budget(
    dl: SqliteDataLayer, took: timedelta, overran: bool
) -> None:
    stopwatch = _Stopwatch()
    seam = TimeBoundedCallOut(
        SuggestParticipantsRetriever(
            "SuggestParticipants", port=_SlowPort(stopwatch, took), dl=dl
        ),
        budget=timedelta(milliseconds=100),
        stopwatch=stopwatch,
    )
    seam.setup()
    _place_case_id()
    if overran:
        with pytest.raises(
            CallOutBudgetExceededError, match="SuggestParticipants"
        ):
            seam.tick_once()
        assert _written() is None
    else:
        seam.tick_once()
        assert seam.status == Status.SUCCESS
        assert _written() == [_SUGGESTION]


@pytest.mark.spec("BT-24-001")
def test_the_call_out_and_a_sentinel_reach_the_same_port_method(
    dl: SqliteDataLayer,
) -> None:
    """One adapter serves the tree's call-out and an outside caller alike."""
    from vultron.core.services.participant_suggestion import (
        suggest_case_participants,
    )

    port = _Port()
    node = _node(
        ParticipantSuggestionCallOutBundle(
            suggest_participants_factory=suggest_participants_with(port, dl)
        )
    )
    _place_case_id()
    node.tick_once()
    case = dl.read_case(_CASE)
    assert case is not None
    # A Sentinel, outside any tree, calls the service directly.
    assert suggest_case_participants(case, port, dl) == [_SUGGESTION]

    assert len(port.asked) == 2
    assert port.asked[0] == port.asked[1]
