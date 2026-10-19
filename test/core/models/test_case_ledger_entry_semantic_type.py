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
"""A ledger entry carries its semantic type as ``semanticType`` (CLP-02-014).

Spec: CLP-02-014
"""

import pytest

from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry

CASE_ID = "https://example.org/cases/case-1"
OBJECT_ID = "https://example.org/activities/act-1"
SEMANTIC_TYPE = "invite_actor_to_case"


@pytest.mark.spec("CLP-02-014")
def test_entry_serializes_semantic_type_under_semantic_type_key() -> None:
    entry = CaseLedgerEntry(
        case_id=CASE_ID,
        log_index=0,
        log_object_id=OBJECT_ID,
        semantic_type=SEMANTIC_TYPE,
    )

    dumped = entry.model_dump(by_alias=True)

    assert dumped["semanticType"] == SEMANTIC_TYPE
    assert "eventType" not in dumped


@pytest.mark.spec("CLP-02-014")
def test_entry_carrying_retired_event_type_key_is_refused() -> None:
    # semanticType is present, so only the retired key can cause the refusal,
    # and the match requires the message to name the rename, not merely
    # reject an unknown or missing field.
    with pytest.raises(ValueError, match=r"'eventType'.*renamed"):
        CaseLedgerEntry.model_validate(
            {
                "caseId": CASE_ID,
                "logIndex": 0,
                "logObjectId": OBJECT_ID,
                "semanticType": SEMANTIC_TYPE,
                "eventType": SEMANTIC_TYPE,
            }
        )


@pytest.mark.spec("CLP-02-014")
def test_stored_row_carrying_retired_event_type_field_is_refused() -> None:
    # A row dumped by field name, not alias, spells the old key event_type.
    with pytest.raises(ValueError, match=r"'event_type'.*renamed"):
        CaseLedgerEntry.model_validate(
            {
                "case_id": CASE_ID,
                "log_index": 0,
                "log_object_id": OBJECT_ID,
                "semantic_type": SEMANTIC_TYPE,
                "event_type": SEMANTIC_TYPE,
            }
        )


@pytest.mark.spec("CLP-02-014")
def test_chain_record_hashes_semantic_type_under_field_name() -> None:
    record = HashChainLedgerRecord(
        case_id=CASE_ID,
        object_id=OBJECT_ID,
        semantic_type=SEMANTIC_TYPE,
    )

    hashed = record._hashable_dict()

    assert hashed["semantic_type"] == SEMANTIC_TYPE
    assert "event_type" not in hashed
    # The stamped hash and the recomputed one read the same key.
    assert record.verify_hash()
