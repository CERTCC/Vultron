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
"""The replica slot for the ``create_embargo_event`` entry (#5122).

The CASE_MANAGER commits one right after a case's genesis entry for each
embargo the creation wrote, carrying it in full (CLP-07-013, VAM-05-016).
The replica stores the embargo and moves nothing else (CM-23-016).
"""

from datetime import UTC, datetime
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
from test.support.embargo_register import activate
from vultron.core.behaviors.embargo.nodes import (
    ApplyCreatedEmbargoFromLedgerNode,
)
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
)

MANAGER_ACTOR_ID = "https://example.org/actors/case-manager"
EMBARGO_ID = f"{CASE_ID}/embargo_events/default"
_END = datetime(2026, 12, 1, tzinfo=UTC)


def _embargo_snapshot(context: str = CASE_ID) -> dict[str, Any]:
    return {
        "type": "EmbargoEvent",
        "id": EMBARGO_ID,
        "context": context,
        "startTime": "2026-09-01T00:00:00+00:00",
        "endTime": _END.isoformat(),
    }


def _entry(embargo: dict[str, Any]) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=1,
            object_id=EMBARGO_ID,
            semantic_type="create_embargo_event",
            payload_snapshot={
                "type": "Create",
                "id": f"{EMBARGO_ID}/create",
                "actor": MANAGER_ACTOR_ID,
                "context": CASE_ID,
                "object": embargo,
            },
            prev_log_hash="0" * 64,
        )
    )


@pytest.fixture
def created_case(datalayer) -> VulnerabilityCase:
    """A replica seeded from a genesis entry naming its embargo by id."""
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    activate(case, EMBARGO_ID)
    datalayer.save(case)
    return case


def _run(bridge, entry: CaseLedgerEntry):
    return bridge.execute_with_setup(
        tree=ApplyCreatedEmbargoFromLedgerNode(name="CreatedEmbargo"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=MANAGER_ACTOR_ID),
    )


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("VAM-05-016")
def test_the_carried_embargo_is_stored_and_nothing_else_moves(
    datalayer, bridge, created_case
):
    register = list(created_case.embargo_register)

    result = _run(bridge, _entry(_embargo_snapshot()))

    assert result.status == Status.SUCCESS, result.feedback_message
    stored = datalayer.read(EMBARGO_ID)
    assert isinstance(stored, EmbargoEvent)
    assert stored.end_time == _END
    case = cast(VulnerabilityCase, datalayer.read(CASE_ID))
    assert case.embargo_register == register


@pytest.mark.spec("CM-23-016")
def test_a_held_embargo_is_a_no_op(datalayer, bridge, created_case):
    _run(bridge, _entry(_embargo_snapshot()))
    first = datalayer.read(EMBARGO_ID)

    result = _run(bridge, _entry(_embargo_snapshot()))

    assert result.status == Status.SUCCESS, result.feedback_message
    assert datalayer.read(EMBARGO_ID) == first


@pytest.mark.spec("EMB-18-004")
def test_an_embargo_of_another_case_is_refused(
    datalayer, bridge, created_case
):
    result = _run(
        bridge, _entry(_embargo_snapshot("https://example.org/cases/other"))
    )

    assert result.status == Status.FAILURE
    assert datalayer.read(EMBARGO_ID) is None


def test_a_replica_without_the_case_skips(datalayer, bridge):
    """Regime 2 (ADR-0087): a partial replica has nothing to store into."""
    result = _run(bridge, _entry(_embargo_snapshot()))

    assert result.status == Status.SUCCESS
    assert datalayer.read(EMBARGO_ID) is None


@pytest.mark.spec("RSH-08-004")
def test_the_announce_tree_carries_the_slot():
    names = {
        node.name
        for node in create_announce_log_entry_tree(
            sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
        ).iterate()
    }

    assert any("CreatedEmbargo" in name for name in names)
