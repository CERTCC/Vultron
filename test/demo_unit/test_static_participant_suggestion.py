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
"""Tests of :mod:`vultron.demo.static_participant_suggestion` (BT-24-007).

The demos' participant-suggestion adapter answers from a declared table:
its rows in order, less any actor the case already holds, and nothing for an
empty table.  The last tests ask it through the core service, as every
caller must (BT-24-008).
"""

import pytest

from test.support.replica_client import seed_case_replica
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.participant_suggestion import (
    ParticipantSuggestion,
    SuggestionContext,
)
from vultron.core.ports.participant_suggestion import (
    ParticipantSuggestionPort,
)
from vultron.core.services.participant_suggestion import (
    suggest_case_participants,
    suggestion_context,
)
from vultron.demo.static_participant_suggestion import (
    StaticParticipantSuggester,
)
from vultron.enums import CVDRole

_OWNER = "https://example.org/actors/owner"
_VENDOR = "https://example.org/actors/vendor"
_SECOND = "https://example.org/actors/second-vendor"
_CASE = "https://example.org/cases/c-1"


def _row(actor_id: str, role: CVDRole) -> ParticipantSuggestion:
    return ParticipantSuggestion(
        actor_id=actor_id, role=role, rationale=f"{actor_id} as {role}"
    )


@pytest.fixture
def store() -> SqliteDataLayer:
    """The owner's store, holding the case with the owner and one vendor."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_OWNER)
    seed_case_replica(
        dl,
        _CASE,
        {_OWNER: [CVDRole.CASE_OWNER], _VENDOR: [CVDRole.VENDOR]},
    )
    return dl


@pytest.fixture
def context(store: SqliteDataLayer) -> SuggestionContext:
    case = store.read_case(_CASE)
    assert case is not None
    return suggestion_context(case, store)


def test_the_adapter_conforms_to_the_port() -> None:
    assert isinstance(
        StaticParticipantSuggester(()), ParticipantSuggestionPort
    )


@pytest.mark.spec("BT-24-007")
def test_it_answers_with_the_table_in_its_order(
    context: SuggestionContext,
) -> None:
    table = (_row(_SECOND, CVDRole.VENDOR), _row(_SECOND, CVDRole.DEPLOYER))
    assert StaticParticipantSuggester(table).suggest_participants(context) == (
        table[0],
        table[1],
    )


@pytest.mark.spec("BT-24-004")
def test_an_empty_table_answers_with_no_one(
    context: SuggestionContext,
) -> None:
    assert StaticParticipantSuggester(()).suggest_participants(context) == ()


def test_an_actor_already_in_the_case_is_left_out(
    context: SuggestionContext,
) -> None:
    table = (_row(_VENDOR, CVDRole.VENDOR), _row(_SECOND, CVDRole.VENDOR))
    assert StaticParticipantSuggester(table).suggest_participants(context) == (
        table[1],
    )


def test_the_table_is_kept_as_declared() -> None:
    table = [_row(_SECOND, CVDRole.VENDOR)]
    assert StaticParticipantSuggester(table).table == tuple(table)


def test_a_row_that_is_not_a_suggestion_is_refused_at_construction() -> None:
    with pytest.raises(TypeError, match=r"not \['dict'\]"):
        StaticParticipantSuggester([{"actor_id": _SECOND}])  # type: ignore[list-item]


@pytest.mark.spec("BT-24-007")
@pytest.mark.spec("BT-24-008")
def test_the_core_service_asks_it_about_the_stored_case(
    store: SqliteDataLayer,
) -> None:
    """Through the service, the case's references resolved from the store."""
    case = store.read_case(_CASE)
    assert case is not None
    table = (_row(_VENDOR, CVDRole.VENDOR), _row(_SECOND, CVDRole.VENDOR))
    assert suggest_case_participants(
        case, StaticParticipantSuggester(table), store
    ) == [table[1]]
