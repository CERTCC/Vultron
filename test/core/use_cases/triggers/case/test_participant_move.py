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
"""The Case Owner's remove-participant and reinstate-participant triggers.

Each sends the Owner's own act naming the actor, ``Remove(<Actor>,
origin=<case>)`` or ``Add(<Actor>, target=<case>)``, to the case's
CASE_MANAGER only (CM-31-004, CM-31-011, ADR-0199).  The sender writes
nothing on its own replica: every replica applies the move from the ledger
entry.
"""

import json
from typing import Any

import pytest

from test.core.use_cases.received.actor.test_case_joining_replies import (
    route_received,
)
from test.core.use_cases.received.test_participant_removal_planned import (
    CASE_ID,
    MANAGER,
    OWNER,
    VENDOR,
    _RemovalCase,
    _seed,
)
from test.support.act_runner import run_in_act
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.triggers.case import (
    ReinstateParticipantTriggerRequest,
    RemoveParticipantTriggerRequest,
    SvcReinstateParticipantUseCase,
    SvcRemoveParticipantUseCase,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.parser import parse_activity

_MOVES = {
    "remove": (
        SvcRemoveParticipantUseCase,
        RemoveParticipantTriggerRequest,
        "Remove",
        "origin",
    ),
    "reinstate": (
        SvcReinstateParticipantUseCase,
        ReinstateParticipantTriggerRequest,
        "Add",
        "target",
    ),
}


def _store(actor_id: str) -> SqliteDataLayer:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    _seed(dl)
    return dl


def _trigger(dl: SqliteDataLayer, verb: str, actor_id: str, **body: Any):
    use_case, request, _, _ = _MOVES[verb]
    return run_in_act(
        use_case(
            dl,
            request(
                actor_id=actor_id,
                case_id=body.pop("case_id", CASE_ID),
                participant_actor_id=body.pop("named", VENDOR),
            ),
            trigger_activity=TriggerActivityAdapter(dl),
            clock=SystemClock(),
        )
    )


def _queued_body(dl: SqliteDataLayer, before: set[str]) -> dict[str, Any]:
    (queued,) = set(dl.outbox_list()) - before
    body = read_sealed_body_dict(dl, queued)
    assert body is not None
    return body


@pytest.mark.spec("CM-31-004")
@pytest.mark.spec("CM-31-011")
@pytest.mark.parametrize("verb", sorted(_MOVES))
def test_the_owners_act_names_the_actor_and_goes_to_the_case_manager_only(
    verb: str,
) -> None:
    dl = _store(OWNER)
    before = set(dl.outbox_list())

    result = _trigger(dl, verb, OWNER)

    _, _, activity_type, slot = _MOVES[verb]
    body = _queued_body(dl, before)
    assert body["type"] == activity_type
    assert body["actor"] == OWNER
    assert body["to"] == [MANAGER]
    # The actor as a typed reference, never its participant record.
    assert body["object"]["id"] == VENDOR
    assert set(body["object"]) <= {"id", "type"}
    assert body[slot] == CASE_ID
    assert "attributedTo" not in body
    assert result.activity is not None
    assert result.activity["id"] == body["id"]


@pytest.mark.spec("CM-31-007")
@pytest.mark.parametrize("verb", sorted(_MOVES))
def test_the_trigger_changes_nothing_on_the_senders_replica(
    verb: str,
) -> None:
    """The sender applies the move from the entry, like every replica."""
    dl = _store(OWNER)
    record = dl.read(f"{CASE_ID}/participants/vendor-removal")
    assert isinstance(record, CaseParticipant)

    _trigger(dl, verb, OWNER)

    assert dl.read(record.id_) == record


@pytest.mark.spec("TRIG-03-001")
@pytest.mark.parametrize("verb", sorted(_MOVES))
def test_an_unknown_case_is_refused_before_anything_is_queued(
    verb: str,
) -> None:
    dl = _store(OWNER)
    before = set(dl.outbox_list())

    with pytest.raises(VultronNotFoundError):
        _trigger(dl, verb, OWNER, case_id="https://example.org/cases/none")

    assert set(dl.outbox_list()) == before


@pytest.mark.spec("CM-31-005")
@pytest.mark.spec("CM-31-044")
def test_the_case_manager_admits_the_queued_acts_as_their_entries() -> None:
    """Round trip: the CASE_MANAGER ledgers each act the trigger sent."""
    owner = _store(OWNER)
    manager_dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
    manager = _RemovalCase(dl=manager_dl, case=_seed(manager_dl))

    for verb in ("remove", "reinstate"):
        before = set(owner.outbox_list())
        _trigger(owner, verb, OWNER)
        body = _queued_body(owner, before)
        result = route_received(
            manager.dl,
            parse_activity(json.loads(json.dumps(body))),
            receiving_actor_id=MANAGER,
            sync_port=SyncActivityAdapter(manager.dl),
            trigger_activity=TriggerActivityAdapter(manager.dl),
        )
        assert result.disposition is HandlerDisposition.APPLIED, result.reason
        assert manager.ledger()[-1].log_object_id == body["id"]

    assert not manager.participant(VENDOR).removed


@pytest.mark.spec("OX-12-001")
def test_an_owner_that_is_the_case_manager_addresses_itself() -> None:
    """An Owner that also holds the CASE_MANAGER role sends the same act to
    its own inbox, which admits it under the same rules."""
    dl = _store(MANAGER)
    before = set(dl.outbox_list())

    _trigger(dl, "remove", MANAGER)

    assert _queued_body(dl, before)["to"] == [MANAGER]
