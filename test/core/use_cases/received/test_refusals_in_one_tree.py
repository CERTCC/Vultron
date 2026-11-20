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
"""Turn-aways of the participant-move and note handlers run in one tree (#4643).

A received delivery runs exactly one tree (CLP-10-005, ADR-0135).  An
activity too incomplete to build its handler's tree, or one naming a case this
store does not hold, is refused by a guard of that tree.  A precondition
guard's refusal leaves intake's record for the outcome stage to reduce to a
receipt stub; a door's (the path stage) leaves nothing, and the outcome stage
writes the stub from the delivery's own body (CLP-10-018).
"""

from typing import Any

import pytest

from test.support.act_runner import run_in_act
from test.support.objects import authored_at
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render import As2WireRenderAdapter
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.case_participant import (
    ReinstateParticipantInCaseReceivedUseCase,
    RemoveParticipantFromCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    reinstate_participant_activity,
    remove_participant_activity,
)

_OWNER = "https://example.org/users/owner"
_CASE_ID = "https://example.org/cases/no-such-case"
_STORE_ACTOR = "https://test.example/api/v2/actors/test-actor"
_COORDINATOR = "https://example.org/users/coordinator"

_MOVES: dict[str, tuple[Any, ...]] = {
    "add": (
        ReinstateParticipantInCaseReceivedUseCase,
        "Add(<Actor>, target=VulnerabilityCase)",
        reinstate_participant_activity,
        "target",
    ),
    "remove": (
        RemoveParticipantFromCaseReceivedUseCase,
        "Remove(<Actor>, origin=VulnerabilityCase)",
        remove_participant_activity,
        "origin",
    ),
}


@pytest.fixture()
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_ACTOR)


def _move_event(make_payload, verb: str):
    """The move, addressed to the store's actor so it passes the addressee
    door (HP-01-005) and reaches the refusal under test."""
    build = _MOVES[verb][2]
    return make_payload(
        build(
            _COORDINATOR,
            _CASE_ID,
            actor=_OWNER,
            to=[_STORE_ACTOR],
            at=authored_at(),
        )
    )


def _run_move(verb: str, dl: SqliteDataLayer, event):
    use_case = _MOVES[verb][0]
    return run_in_act(
        use_case(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        )
    )


def _only_the_archive(
    dl: SqliteDataLayer, activity_id: str, *, recorded: bool = True
) -> None:
    """The refused activity is kept only if intake ran, and nothing about
    the case is: a door's refusal precedes intake (CLP-10-010)."""
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    assert (record is not None) is recorded
    assert dl.read(_CASE_ID) is None
    assert dl.read(f"{_CASE_ID}/participants/coord") is None


@pytest.mark.spec("CLP-10-005")
@pytest.mark.spec("CLP-10-018")
@pytest.mark.parametrize("verb", sorted(_MOVES))
@pytest.mark.parametrize("missing", ["case", "object_"])
def test_move_missing_an_id_is_refused_in_one_tree(
    dl, make_payload, tree_runs, verb, missing
):
    slot = _MOVES[verb][3] if missing == "case" else missing
    event = _move_event(make_payload, verb).model_copy(update={slot: None})

    result = _run_move(verb, dl, event)

    assert result.disposition == HandlerDisposition.REFUSED
    assert result.reason == (
        f"{_MOVES[verb][1]} is missing the actor it names or its case"
    )
    assert len(tree_runs) == 1
    _only_the_archive(dl, event.activity_id)


@pytest.mark.spec("CLP-10-005")
@pytest.mark.spec("HP-01-005")
@pytest.mark.parametrize("verb", sorted(_MOVES))
def test_move_for_an_unknown_case_is_refused_in_one_tree(
    dl, make_payload, tree_runs, verb
):
    """The path stage finds no replica of the case (HP-01-005, HP-01-039)."""
    event = _move_event(make_payload, verb)

    result = _run_move(verb, dl, event)

    assert result.disposition == HandlerDisposition.REFUSED
    assert result.reason == f"holds no replica of case '{_CASE_ID}'"
    assert len(tree_runs) == 1
    _only_the_archive(dl, event.activity_id, recorded=False)
