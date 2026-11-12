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

"""The replica slots for a case's vulnerability items and case references.

The CASE_MANAGER records each one as an ``Add`` carrying it in full with the
case as its target (CLP-07-021).  The replica stores the record and lists it
on its case, as the entry states (CM-23-016).
"""

from typing import Any, cast

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from test.support.act_clock import ACT_AT
from test.support.act_runner import run_tree
from test.support.objects import make
from vultron.core.behaviors.sync.nodes import (
    ApplyCaseReferenceFromLedgerNode,
    ApplyVulnerabilityItemFromLedgerNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.vulnerability_item import VulnerabilityItem

MANAGER_ACTOR_ID = "https://example.org/actors/case-manager"
ITEM_ID = f"{CASE_ID}/items/1"
REFERENCE_ID = f"{CASE_ID}/references/1"

_STAMP = {"published": ACT_AT.isoformat(), "updated": ACT_AT.isoformat()}
_ITEM = {
    "type": "VulnerabilityItem",
    "id": ITEM_ID,
    "cve": "CVE-2026-0001",
    **_STAMP,
}
_REFERENCE = {
    "type": "CaseReference",
    "id": REFERENCE_ID,
    **_STAMP,
    "url": {"type": "Link", "href": "https://example.org/a"},
    "name": "Advisory",
}

_SLOTS = [
    pytest.param(
        ApplyVulnerabilityItemFromLedgerNode,
        "add_vulnerability_item_to_case",
        _ITEM,
        VulnerabilityItem,
        "vulnerability_items",
        id="item",
    ),
    pytest.param(
        ApplyCaseReferenceFromLedgerNode,
        "add_case_reference_to_case",
        _REFERENCE,
        CaseReference,
        "case_references",
        id="reference",
    ),
]


def _entry(semantic_type: str, record: Any) -> CaseLedgerEntry:
    object_id = record["id"] if isinstance(record, dict) else str(record)
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=1,
            object_id=object_id,
            semantic_type=semantic_type,
            payload_snapshot={
                "type": "Add",
                "id": f"{object_id}/add",
                "actor": MANAGER_ACTOR_ID,
                "context": CASE_ID,
                "target": CASE_ID,
                "object": record,
            },
            prev_log_hash="0" * 64,
            received_at=ACT_AT,
        )
    )


@pytest.fixture
def replica(datalayer) -> VulnerabilityCase:
    case = make(VulnerabilityCase, id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    datalayer.save(case)
    return case


def _run(bridge, node_class, entry: CaseLedgerEntry):
    return run_tree(
        bridge,
        tree=node_class(name="CaseContent"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=MANAGER_ACTOR_ID),
    )


def _listed(datalayer, field: str) -> list[Any]:
    case = cast(VulnerabilityCase, datalayer.read(CASE_ID))
    return list(getattr(case, field))


@pytest.mark.spec("CLP-07-021", "CM-23-016")
@pytest.mark.parametrize(("node", "kind", "record", "cls", "field"), _SLOTS)
def test_the_record_is_stored_and_listed_on_the_case(
    datalayer, bridge, replica, node, kind, record, cls, field
):
    result = _run(bridge, node, _entry(kind, record))

    assert result.status == Status.SUCCESS, result.feedback_message
    assert isinstance(datalayer.read(record["id"]), cls)
    assert _listed(datalayer, field) == [record["id"]]


@pytest.mark.spec("CLP-07-021")
@pytest.mark.parametrize(("node", "kind", "record", "cls", "field"), _SLOTS)
def test_a_replayed_entry_lists_the_record_once(
    datalayer, bridge, replica, node, kind, record, cls, field
):
    _run(bridge, node, _entry(kind, record))

    result = _run(bridge, node, _entry(kind, record))

    assert result.status == Status.SUCCESS, result.feedback_message
    assert _listed(datalayer, field) == [record["id"]]


@pytest.mark.spec("CLP-07-021")
@pytest.mark.parametrize(("node", "kind", "record", "cls", "field"), _SLOTS)
def test_a_record_already_listed_inline_is_not_listed_again(
    datalayer, bridge, replica, node, kind, record, cls, field
):
    """The owner's case seeded from the Create already holds it inline."""
    held = cls.model_validate({k: v for k, v in record.items() if k != "type"})
    setattr(replica, field, [held])
    datalayer.save(replica)

    result = _run(bridge, node, _entry(kind, record))

    assert result.status == Status.SUCCESS, result.feedback_message
    assert [getattr(r, "id_", r) for r in _listed(datalayer, field)] == [
        record["id"]
    ]


@pytest.mark.spec("SYNC-12-004")
@pytest.mark.parametrize(("node", "kind", "record", "cls", "field"), _SLOTS)
def test_an_entry_naming_its_record_by_id_only_fails(
    datalayer, bridge, replica, node, kind, record, cls, field
):
    result = _run(bridge, node, _entry(kind, record["id"]))

    assert result.status == Status.FAILURE
    assert _listed(datalayer, field) == []


@pytest.mark.spec("SYNC-12-004")
def test_an_invalid_record_fails(datalayer, bridge, replica):
    bad = {**_ITEM, "cve": "not a CVE ID"}

    result = _run(
        bridge,
        ApplyVulnerabilityItemFromLedgerNode,
        _entry("add_vulnerability_item_to_case", bad),
    )

    assert result.status == Status.FAILURE
    assert datalayer.read(ITEM_ID) is None


@pytest.mark.spec("CLP-07-021")
def test_a_replica_without_the_case_skips(datalayer, bridge):
    result = _run(
        bridge,
        ApplyVulnerabilityItemFromLedgerNode,
        _entry("add_vulnerability_item_to_case", _ITEM),
    )

    assert result.status == Status.SUCCESS
    assert datalayer.read(ITEM_ID) is None
