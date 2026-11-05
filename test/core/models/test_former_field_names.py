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

"""A former stored field name is an unknown key, refused by ``extra="forbid"``.

Before 1.0 Vultron supports one storage version (ADR-0175), so no model keeps
a list of the field names it once used.  A row that still carries one is
refused like any other unknown key (MV-11-004, ARCH-12-003), with Pydantic's
generic ``extra_forbidden`` error, and is never read through an alias.
"""

import importlib.util
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
from pydantic.alias_generators import to_camel

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import CaseProposalDeclineRecord
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.report_case_link import VultronReportCaseLink

_URI = "https://example.org/x"
PROPOSAL_ID = "https://example.org/proposals/p-1"
CASE_ACTOR_ID = "https://example.org/actors/vendor/case-actor"
OWNER_ID = "https://example.org/actors/vendor"
_PROPOSAL = {"proposal_id": PROPOSAL_ID, "case_actor_id": CASE_ACTOR_ID}


def _case_data() -> dict[str, Any]:
    case = VulnerabilityCase(
        id_="https://example.org/cases/c-1", attributed_to=OWNER_ID, name="c"
    )
    return case.model_dump(mode="json", by_alias=True)


def _entry_data() -> dict[str, Any]:
    return {
        "caseId": "https://example.org/cases/c-1",
        "logIndex": 0,
        "logObjectId": "https://example.org/activities/act-1",
        "semanticType": "invite_actor_to_case",
    }


#: (model, valid data, a field name the model once stored and no longer does)
_FORMER: list[tuple[type[BaseModel], dict[str, Any], str]] = [
    (VulnerabilityCase, _case_data(), "recommendation_recommender_index"),
    (CaseLedgerEntry, _entry_data(), "event_type"),
    (
        ReceivedActivityRecord,
        {"activity_id": f"{_URI}/a-1", "received_body": "{}"},
        "activity",
    ),
    # ``DeferredInboxActivity`` was retired into ``ReceivedActivityRecord``
    # (ADR-0154), so the fields it carried under its own names are former
    # names of the record that absorbed it, ``rows_json`` among them.
    (
        ReceivedActivityRecord,
        {"activity_id": f"{_URI}/a-1", "received_body": "{}"},
        "rows_json",
    ),
    (
        ReceivedActivityRecord,
        {"activity_id": f"{_URI}/a-1", "received_body": "{}"},
        "activity_row_json",
    ),
    # The per-message wait replaced the per-case list (ADR-0154).
    (
        VultronPendingCaseInbox,
        {"case_id": f"{_URI}/case"},
        "activity_ids",
    ),
    (
        CaseProposalAdmissionRecord,
        {**_PROPOSAL, "proposer_uri": OWNER_ID},
        "vendor_uri",
    ),
    (
        CaseProposalDeclineRecord,
        {**_PROPOSAL, "proposer_uri": OWNER_ID},
        "vendor_uri",
    ),
    (
        VultronReportCaseLink,
        {"report_id": f"{_URI}/report"},
        "trusted_case_creator_id",
    ),
    (
        VultronReportCaseLink,
        {"report_id": f"{_URI}/report"},
        "trusted_case_actor_id",
    ),
    *(
        (
            VultronReplicationState,
            {"case_id": f"{_URI}/case", "peer_id": f"{_URI}/peer"},
            name,
        )
        for name in (
            "join_backfill_target_index",
            "join_backfill_last_sent_index",
            "join_backfill_complete",
        )
    ),
]
#: Both spellings of each former name: the field name, and the camelCase form
#: an aliased dump would have written.
_CASES = [
    (cls, data, key)
    for cls, data, name in _FORMER
    for key in dict.fromkeys((name, to_camel(name)))
]
_IDS = [f"{cls.__name__}.{key}" for cls, _, key in _CASES]


def test_no_retired_field_tracking_module_exists() -> None:
    """The tracking module #5573 removed is gone (ADR-0175).

    This checks one removal by its old module path only; a named refusal
    reintroduced elsewhere is caught by
    :func:`test_a_former_field_name_is_refused_as_an_unknown_key`, which
    requires exactly one generic ``extra_forbidden`` error per former name.
    """
    assert (
        importlib.util.find_spec("vultron.core.models.retired_stored_fields")
        is None
    )


@pytest.mark.spec("ARCH-12-003", "MV-11-004")
@pytest.mark.parametrize(("cls", "data", "key"), _CASES, ids=_IDS)
def test_the_valid_data_validates(
    cls: type[BaseModel], data: dict[str, Any], key: str
) -> None:
    """The sample is valid, so only the former key can cause a refusal."""
    assert key not in cls.model_fields
    cls.model_validate(data)


@pytest.mark.spec("ARCH-12-003", "MV-11-004", "MV-11-012")
@pytest.mark.parametrize(("cls", "data", "key"), _CASES, ids=_IDS)
def test_a_former_field_name_is_refused_as_an_unknown_key(
    cls: type[BaseModel], data: dict[str, Any], key: str
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        cls.model_validate({**data, key: "stale"})

    errors = excinfo.value.errors()
    assert [(e["type"], e["loc"]) for e in errors] == [
        ("extra_forbidden", (key,))
    ]


_RenamedRecord = (
    type[CaseProposalAdmissionRecord] | type[CaseProposalDeclineRecord]
)


@pytest.mark.spec("CS-12-001")
@pytest.mark.parametrize(
    "cls", [CaseProposalAdmissionRecord, CaseProposalDeclineRecord]
)
def test_the_record_stores_the_uri_under_its_role_name(
    cls: _RenamedRecord,
) -> None:
    record = cls.model_validate({**_PROPOSAL, "proposer_uri": OWNER_ID})

    assert record.proposer_uri == OWNER_ID
    dumped = record.model_dump()
    assert dumped["proposer_uri"] == OWNER_ID
    assert "vendor_uri" not in dumped
    assert cls.model_validate(dumped) == record
