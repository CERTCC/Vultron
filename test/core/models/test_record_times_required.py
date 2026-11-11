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
"""A record's own time is stated by the act that builds it (ADR-0176).

No record below defaults its time to a clock read: built without one, it is
refused at construction (ARCH-10-001), and built with one, it keeps exactly
that instant and reads no clock.
"""

import json
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from test.support.act_clock import ACT_AT, no_clock
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.dead_letter import DeadLetterRecord
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.replication_state import VultronReplicationState

_CASE = "https://example.org/cases/c1"
_ACTIVITY = "https://example.org/activities/a1"
_ACTOR = "https://example.org/actors/a"
_BODY = json.dumps(
    {"type": "Create", "id": _ACTIVITY, "actor": _ACTOR, "object": "x"}
)

#: ``(model, the fields it needs besides its time, the time fields)``.
_RECORDS: list[tuple[type[BaseModel], dict[str, Any], tuple[str, ...]]] = [
    (
        ReceivedActivityRecord,
        {"activity_id": _ACTIVITY, "received_body": _BODY},
        ("received_at",),
    ),
    (
        DeadLetterRecord,
        {
            "unresolvable_uri": "https://example.org/missing",
            "actor_id": _ACTOR,
            "activity_id": _ACTIVITY,
        },
        ("received_at",),
    ),
    (VultronPendingCaseInbox, {"case_id": _CASE}, ("queued_at",)),
    (
        CaseLedgerEntry,
        # ``updated`` is the object time CoreObject still defaults (Part C).
        {
            "case_id": _CASE,
            "log_object_id": _ACTIVITY,
            "semantic_type": "t",
            "updated": ACT_AT,
        },
        ("published", "received_at"),
    ),
    (
        HashChainLedgerRecord,
        {
            "case_id": _CASE,
            "log_index": 0,
            "object_id": _ACTIVITY,
            "semantic_type": "t",
        },
        ("received_at",),
    ),
    (
        VultronReplicationState,
        {"case_id": _CASE, "peer_id": _ACTOR},
        ("updated_at",),
    ),
]
_IDS = [model.__name__ for model, _, _ in _RECORDS]


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize(("model", "fields", "times"), _RECORDS, ids=_IDS)
def test_a_record_without_its_time_is_refused(
    model: type[BaseModel], fields: dict[str, Any], times: tuple[str, ...]
) -> None:
    for omitted in times:
        given = {**fields, **{t: ACT_AT for t in times if t != omitted}}
        with no_clock(), pytest.raises(ValidationError) as caught:
            model(**given)
        field = model.model_fields[omitted]
        names = {omitted, field.alias, field.validation_alias}
        [error] = caught.value.errors()
        assert error["loc"][0] in names
        assert error["type"] == "missing"


@pytest.mark.spec("CS-13-002")
@pytest.mark.parametrize(("model", "fields", "times"), _RECORDS, ids=_IDS)
def test_a_record_keeps_the_time_it_is_given(
    model: type[BaseModel], fields: dict[str, Any], times: tuple[str, ...]
) -> None:
    with no_clock():
        record = model(**fields, **{t: ACT_AT for t in times})
    for t in times:
        assert getattr(record, t) == ACT_AT


@pytest.mark.spec("SYNC-01-003")
def test_a_ledger_record_without_its_time_is_not_hashed() -> None:
    """The hash covers ``received_at``, so none is stamped to hash over.

    The record is refused for the missing field, not for a hash computed
    over a time the clock supplied.
    """
    with no_clock(), pytest.raises(ValidationError) as caught:
        HashChainLedgerRecord.model_validate(
            {
                "case_id": _CASE,
                "log_index": 0,
                "object_id": _ACTIVITY,
                "semantic_type": "t",
            }
        )
    errors = caught.value.errors()
    assert [e["loc"] for e in errors] == [("received_at",)]
    assert errors[0]["type"] == "missing"
