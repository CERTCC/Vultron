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

"""A renamed stored field is refused under its old key, never aliased (#4128).

The CaseProposal admission, decline and pending-Create records named the
proposer or case owner ``vendor_uri``; the field is now ``proposer_uri`` on
the two decision records and ``owner_uri`` on the pending-Create marker
(CS-12-001).  There is no read alias and no conversion.
"""

from collections.abc import Mapping
from typing import Any, ClassVar

import pytest
from pydantic import ValidationError

from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import CaseProposalDeclineRecord
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.retired_stored_fields import (
    RetiredFieldsRecord,
    RetiredStoredField,
)

PROPOSAL_ID = "https://example.org/proposals/p-1"
CASE_ACTOR_ID = "https://example.org/actors/vendor/case-actor"
OWNER_ID = "https://example.org/actors/vendor"

_RenamedRecord = (
    type[CaseProposalAdmissionRecord]
    | type[CaseProposalDeclineRecord]
    | type[PendingCreateCaseActivity]
)

_RENAMED: list[tuple[_RenamedRecord, str]] = [
    (CaseProposalAdmissionRecord, "proposer_uri"),
    (CaseProposalDeclineRecord, "proposer_uri"),
    (PendingCreateCaseActivity, "owner_uri"),
]
_IDS = [cls.__name__ for cls, _ in _RENAMED]


def _data(**uri: str) -> dict[str, Any]:
    return {"proposal_id": PROPOSAL_ID, "case_actor_id": CASE_ACTOR_ID, **uri}


@pytest.mark.spec("CS-12-001")
@pytest.mark.parametrize(("cls", "new"), _RENAMED, ids=_IDS)
def test_the_record_stores_the_uri_under_its_role_name(
    cls: _RenamedRecord, new: str
) -> None:
    record = cls.model_validate(_data(**{new: OWNER_ID}))

    assert getattr(record, new) == OWNER_ID
    dumped = record.model_dump()
    assert dumped[new] == OWNER_ID
    assert "vendor_uri" not in dumped
    assert cls.model_validate(dumped) == record


@pytest.mark.spec("CP-05-005")
@pytest.mark.parametrize("old", ["vendor_uri", "vendorUri"])
@pytest.mark.parametrize(("cls", "new"), _RENAMED, ids=_IDS)
def test_the_retired_key_is_refused_naming_the_reset(
    cls: _RenamedRecord, new: str, old: str
) -> None:
    with pytest.raises(ValidationError, match="must be reset") as excinfo:
        cls.model_validate(_data(**{old: OWNER_ID}))

    message = str(excinfo.value)
    assert cls.__name__ in message
    assert repr(old) in message
    assert repr(new) in message
    assert "#4128" in message


@pytest.mark.spec("CP-05-005")
@pytest.mark.parametrize(("cls", "new"), _RENAMED, ids=_IDS)
def test_the_retired_key_is_refused_beside_its_replacement(
    cls: _RenamedRecord, new: str
) -> None:
    with pytest.raises(ValidationError, match="must be reset"):
        cls.model_validate(_data(**{new: OWNER_ID, "vendor_uri": OWNER_ID}))


@pytest.mark.usefixtures("isolated_core_registries")
def test_a_model_declaring_no_retired_keys_is_unaffected() -> None:
    class _Plain(RetiredFieldsRecord):
        vendor_uri: str

    assert _Plain(vendor_uri=OWNER_ID).vendor_uri == OWNER_ID


@pytest.mark.usefixtures("isolated_core_registries")
def test_non_dict_input_passes_through_to_normal_validation() -> None:
    class _Renamed(RetiredFieldsRecord):
        new_name: str
        retired_stored_fields: ClassVar[Mapping[str, RetiredStoredField]] = {
            "old_name": RetiredStoredField("new_name", "#0")
        }

    record = _Renamed(new_name="x")

    assert _Renamed.model_validate(record) == record


@pytest.mark.spec("EH-07-001")
@pytest.mark.usefixtures("isolated_core_registries")
def test_every_retired_key_present_is_reported_not_only_the_first() -> None:
    class _TwiceRenamed(RetiredFieldsRecord):
        first: str | None = None
        second: str | None = None
        retired_stored_fields: ClassVar[Mapping[str, RetiredStoredField]] = {
            "old_first": RetiredStoredField("first", "#1"),
            "old_second": RetiredStoredField("second", "#2"),
        }

    with pytest.raises(ValidationError, match="must be reset") as excinfo:
        _TwiceRenamed.model_validate({"old_first": "a", "oldSecond": "b"})

    message = str(excinfo.value)
    assert "2 violation(s)" in message
    assert "'old_first'" in message and "'first'" in message
    assert "'oldSecond'" in message and "'second'" in message


@pytest.mark.usefixtures("isolated_core_registries")
def test_a_replacement_the_model_does_not_declare_is_refused_at_definition() -> (
    None
):
    with pytest.raises(TypeError, match="does not declare"):

        class _Typo(RetiredFieldsRecord):
            new_name: str
            retired_stored_fields: ClassVar[
                Mapping[str, RetiredStoredField]
            ] = {"old_name": RetiredStoredField("new_nmae", "#0")}


@pytest.mark.usefixtures("isolated_core_registries")
def test_a_retired_key_the_model_still_declares_is_refused_at_definition() -> (
    None
):
    with pytest.raises(TypeError, match="still declares"):

        class _StillThere(RetiredFieldsRecord):
            old_name: str
            new_name: str
            retired_stored_fields: ClassVar[
                Mapping[str, RetiredStoredField]
            ] = {"old_name": RetiredStoredField("new_name", "#0")}
