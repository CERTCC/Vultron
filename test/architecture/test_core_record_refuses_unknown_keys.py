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

"""A stored record refuses an unknown key, like every ``CoreObject`` (#4186).

``CoreRecord`` once ignored unknown keys, so a row written before a field
rename read back with the renamed field silently ``None`` (ARCH-12-003).  The
subject set is discovered, so a new record type is covered the day it lands.
"""

from typing import Any

import pytest
from pydantic import ValidationError

import vultron.adapters.outbox_dead_letter
import vultron.adapters.outbox_sealed_body  # noqa: F401
from test.support.core_vocab import import_all_core_models
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import CoreObject, CoreRecord, with_record_id
from vultron.core.models.retired_stored_fields import RetiredFieldsRecord

import_all_core_models()

_URI = "https://example.org/x"
_PROPOSAL = {
    "proposal_id": f"{_URI}/p-1",
    "case_actor_id": f"{_URI}/manager",
}

#: Minimal valid data for each concrete record.  The abstract
#: ``RetiredFieldsRecord`` base has no fields of its own to build from.
_SAMPLES: dict[str, dict[str, Any]] = {
    "CaseProposalAdmissionRecord": {**_PROPOSAL, "proposer_uri": _URI},
    "CaseProposalDeclineRecord": {**_PROPOSAL, "proposer_uri": _URI},
    "PendingCreateCaseActivity": {**_PROPOSAL, "owner_uri": _URI},
    "DeadLetterRecord": {
        "unresolvable_uri": _URI,
        "actor_id": _URI,
        "activity_id": _URI,
    },
    "OutboxDeadLetterEntry": {
        "activity_id": _URI,
        "actor_id": _URI,
        "reason": "unreachable",
        "total_attempts": 3,
    },
    "PendingCreationTimeRevisionRelay": {
        "case_id": f"{_URI}/case",
        "embargo_id": f"{_URI}/embargo",
        "proposal_id": f"{_URI}/p-1",
        "losing_source": "actor_default",
        "report_id": f"{_URI}/report",
        "case_actor_id": f"{_URI}/manager",
    },
    "ReceivedActivityRecord": {
        "activity_id": f"{_URI}/a-1",
        "activity": VultronActivity(
            id_=f"{_URI}/a-1", type_="Create", actor=_URI
        ),
    },
    "SealedOutboundBody": {"activity_id": _URI, "body": "{}"},
    "VultronOfferRecord": {
        "offer_id": f"{_URI}/offer",
        "report_id": f"{_URI}/report",
        "offer_actor_id": _URI,
    },
    "VultronPendingCaseInbox": {"case_id": f"{_URI}/case"},
    "VultronReplicationState": {
        "case_id": f"{_URI}/case",
        "peer_id": f"{_URI}/peer",
    },
    "VultronReportCaseLink": {"report_id": f"{_URI}/report"},
}


def _record_types() -> list[type[CoreRecord]]:
    found: set[type[CoreRecord]] = set()
    stack = [CoreRecord]
    while stack:
        for sub in stack.pop().__subclasses__():
            if sub not in found:
                found.add(sub)
                stack.append(sub)
    return sorted(
        (
            cls
            for cls in found
            if not issubclass(cls, CoreObject)
            and not cls.__module__.startswith("test")
            and cls is not RetiredFieldsRecord
        ),
        key=lambda cls: cls.__name__,
    )


_RECORDS = _record_types()
_IDS = [cls.__name__ for cls in _RECORDS]


def test_every_record_has_a_sample() -> None:
    """A new record type must add its sample here, or this fails first."""
    assert sorted(_SAMPLES) == _IDS


@pytest.mark.spec("ARCH-12-003")
@pytest.mark.parametrize("cls", _RECORDS, ids=_IDS)
def test_record_refuses_an_unknown_key(cls: type[CoreRecord]) -> None:
    assert cls.model_config.get("extra") == "forbid"
    with pytest.raises(ValidationError) as exc:
        cls.model_validate({**_SAMPLES[cls.__name__], "retiredKey": "x"})
    assert any(
        e["type"] == "extra_forbidden" and e["loc"] == ("retiredKey",)
        for e in exc.value.errors()
    )


@pytest.mark.spec("ARCH-12-003")
@pytest.mark.parametrize("cls", _RECORDS, ids=_IDS)
def test_record_dump_round_trips(cls: type[CoreRecord]) -> None:
    """One spelling of ``id_``: a dump validates back to an equal record."""
    record = cls.model_validate(_SAMPLES[cls.__name__])
    assert cls.model_validate(record.model_dump()) == record


@pytest.mark.spec("ARCH-12-003")
@pytest.mark.parametrize("cls", _RECORDS, ids=_IDS)
def test_record_assignment_revalidates_without_an_unknown_key(
    cls: type[CoreRecord],
) -> None:
    """Assignment validates by field name: ``id_`` must not read as extra."""
    record = cls.model_validate(_SAMPLES[cls.__name__])
    record.id_ = record.id_
    assert cls.model_validate(record.model_dump()) == record


def test_with_record_id_states_one_spelling() -> None:
    assert with_record_id({"id_": "a", "x": 1}, "b") == {"id_": "b", "x": 1}
    assert with_record_id({"id_": "a", "id": "c"}, "b") == {"id": "b"}
    assert with_record_id({"x": 1}, "b") == {"x": 1, "id": "b"}
