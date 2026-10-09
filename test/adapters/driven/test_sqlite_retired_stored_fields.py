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

"""A record stored under a renamed field's old key is refused, never converted.

Each row is inserted as a verbatim ``Record`` (no model serialization), so
this exercises the read path a database written before the rename takes.
The project carries no backwards compatibility for stored data: the row
reads back absent, and the logged reason tells an operator the store must
be reset rather than leaving a bare "not found" (#4128, #4020).
"""

from typing import Any

import pytest

from vultron.adapters.driven.db_record import Record
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import CaseProposalDeclineRecord
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.report_case_link import VultronReportCaseLink

PROPOSAL_ID = "https://example.org/proposals/p-legacy"
REPORT_ID = "https://example.org/reports/r-legacy"
CASE_ACTOR_ID = "https://example.org/actors/vendor/case-actor"
OWNER_ID = "https://example.org/actors/vendor"

_RenamedRecord = (
    type[CaseProposalAdmissionRecord]
    | type[CaseProposalDeclineRecord]
    | type[PendingCreateCaseActivity]
    | type[VultronReportCaseLink]
)

_PROPOSAL_FIELDS: dict[str, Any] = {
    "proposal_id": PROPOSAL_ID,
    "case_actor_id": CASE_ACTOR_ID,
}
_LINK_FIELDS: dict[str, Any] = {"report_id": REPORT_ID, "rm_state": "RECEIVED"}

# (record class, build_id key, other stored fields, retired key, new key)
_CASES: list[tuple[_RenamedRecord, str, dict[str, Any], str, str]] = [
    (
        CaseProposalAdmissionRecord,
        PROPOSAL_ID,
        _PROPOSAL_FIELDS,
        "vendor_uri",
        "proposer_uri",
    ),
    (
        CaseProposalDeclineRecord,
        PROPOSAL_ID,
        _PROPOSAL_FIELDS,
        "vendor_uri",
        "proposer_uri",
    ),
    (
        PendingCreateCaseActivity,
        PROPOSAL_ID,
        _PROPOSAL_FIELDS,
        "vendor_uri",
        "owner_uri",
    ),
    (
        VultronReportCaseLink,
        REPORT_ID,
        _LINK_FIELDS,
        "trusted_case_creator_id",
        "case_creator_id",
    ),
    (
        VultronReportCaseLink,
        REPORT_ID,
        _LINK_FIELDS,
        "trusted_case_actor_id",
        "case_manager_id",
    ),
]
_IDS = [f"{case[0].__name__}.{case[3]}" for case in _CASES]


def _row(
    cls: _RenamedRecord, key: str, fields: dict[str, Any], uri_key: str
) -> Record:
    type_name = cls.model_fields["type_"].default
    record_id = cls.build_id(key)
    return Record(
        id_=record_id,
        type_=type_name,
        data_={
            "id": record_id,
            "type": type_name,
            **fields,
            uri_key: OWNER_ID,
        },
    )


@pytest.mark.spec("CP-05-005")
@pytest.mark.parametrize(
    ("cls", "key", "fields", "old", "new"), _CASES, ids=_IDS
)
def test_a_pre_rename_row_reads_absent_naming_the_reset(
    dl, caplog, cls, key, fields, old, new
) -> None:
    row = _row(cls, key, fields, old)
    dl.create(row)

    with caplog.at_level("WARNING"):
        assert dl.read(row.id_) is None

    assert "must be reset" in caplog.text
    assert repr(old) in caplog.text
    assert repr(new) in caplog.text


@pytest.mark.spec("CP-05-005")
@pytest.mark.parametrize(
    ("cls", "key", "fields", "old", "new"), _CASES, ids=_IDS
)
def test_a_row_under_the_new_name_reads_back(
    dl, cls, key, fields, old, new
) -> None:
    row = _row(cls, key, fields, new)
    dl.create(row)

    record = dl.read(row.id_)

    assert isinstance(record, cls)
    assert getattr(record, new) == OWNER_ID
