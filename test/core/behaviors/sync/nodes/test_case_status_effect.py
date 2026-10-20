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
"""Replay of ``add_case_status_to_case`` on a participant replica (#3814 AC-2).

The replica copies the committed CaseStatus as carried (CM-23-016, ADR-0124).
The CASE_MANAGER adjudicated it (RSH-09-005, RSH-09-005); the replica does not
adjudicate again.  EM is derived from the replica's embargo register, so a
status never moves it (ADR-0122).
"""

from datetime import timedelta
from typing import Any

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from test.support.embargo_register import activate, terminate
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.sync.nodes.case_status_effect import (
    ApplyCaseStatusFromLedgerNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM

MANAGER = "https://example.org/actors/case-manager"
EMBARGO_ID = f"{CASE_ID}/embargo_events/e1"


def _case_status(em: EM, pxa: CS_pxa, **fields: Any) -> CaseStatus:
    return CaseStatus(
        context=CASE_ID,
        attributed_to=MANAGER,
        em=EmDimension(state=em),
        pxa=PxaDimension(state=pxa),
        **fields,
    )


def _register_at(case: VulnerabilityCase, em: EM) -> None:
    """Drive *case*'s embargo register to *em* (EM is derived, ADR-0122)."""
    if em in (EM.ACTIVE, EM.EXITED):
        activate(case, EMBARGO_ID)
    if em is EM.EXITED:
        terminate(case)
    assert case.em_state == em


def _seed(datalayer, em: EM = EM.ACTIVE, pxa: CS_pxa = CS_pxa.pxa):
    current = _case_status(em, pxa)
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    _register_at(case, em)
    case.case_statuses = []
    case.add_case_status(current)
    datalayer.save(current)
    datalayer.save(case)
    return current


def _replay_teardown(datalayer) -> None:
    """The teardown's own ledger entry, replayed ahead of the status snapshot."""
    case = _case(datalayer)
    terminate(case)
    datalayer.save(case)


def _later(current: CaseStatus, em: EM, pxa: CS_pxa) -> CaseStatus:
    """A status committed after *current*, so it becomes the current one."""
    assert current.updated is not None
    stamp = current.updated + timedelta(seconds=1)
    return _case_status(em, pxa, published=stamp, updated=stamp)


def _apply(bridge, status_object: Any):
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/add-case-status",
            semantic_type="add_case_status_to_case",
            payload_snapshot={
                "type": "Add",
                "actor": MANAGER,
                "context": CASE_ID,
                "object": status_object,
            },
            prev_log_hash="0" * 64,
        )
    )
    return bridge.execute_with_setup(
        tree=ApplyCaseStatusFromLedgerNode(name="ApplyCaseStatus"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=MANAGER),
    )


def _wire(status: CaseStatus) -> dict[str, Any]:
    return As2WireRenderAdapter().render(status)


def _case(datalayer) -> VulnerabilityCase:
    case = datalayer.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return case


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("SYNC-12-001")
def test_the_committed_status_becomes_the_replicas_current_status(
    bridge, datalayer
):
    """In ledger order the EM a snapshot carries is already the replica's.

    The teardown's entry precedes the CASE_MANAGER's status snapshot, so the
    replica's register derives ``EXITED`` before the status arrives.
    """
    current = _seed(datalayer, EM.ACTIVE, CS_pxa.pxa)
    committed = _later(current, EM.EXITED, CS_pxa.Pxa)
    _replay_teardown(datalayer)

    assert _apply(bridge, _wire(committed)).status == Status.SUCCESS

    case = _case(datalayer)
    assert case.current_status.id_ == committed.id_
    assert case.current_status.em.state == EM.EXITED
    assert case.current_status.pxa.state == CS_pxa.Pxa


@pytest.mark.spec("RSH-09-005")
def test_a_status_never_moves_the_replicas_em(bridge, datalayer):
    """A snapshot EM the register does not derive is carried forward."""
    current = _seed(datalayer, EM.ACTIVE, CS_pxa.pxa)
    committed = _later(current, EM.EXITED, CS_pxa.Pxa)

    assert _apply(bridge, _wire(committed)).status == Status.SUCCESS

    case = _case(datalayer)
    assert case.current_status.id_ == committed.id_
    assert case.em_state == EM.ACTIVE
    assert case.current_status.em.state == EM.ACTIVE
    assert case.current_status.pxa.state == CS_pxa.Pxa


@pytest.mark.spec("CM-23-016")
def test_the_pxa_the_entry_carries_is_copied(bridge, datalayer):
    """The replica keeps no P/X/A of its own over the entry's.

    A replica that refused the entry's value and carried its own forward
    would hold a status no entry records.
    """
    current = _seed(datalayer, EM.ACTIVE, CS_pxa.PXa)
    committed = _later(current, EM.ACTIVE, CS_pxa.Pxa)

    assert _apply(bridge, _wire(committed)).status == Status.SUCCESS

    case = _case(datalayer)
    assert [_as_id(s) for s in case.case_statuses] == [
        current.id_,
        committed.id_,
    ]
    assert case.current_status.pxa.state == CS_pxa.Pxa


@pytest.mark.spec("CM-23-016")
def test_a_multi_step_pxa_advance_is_copied(bridge, datalayer):
    """A replica copies the move; it checks no adjacency."""
    current = _seed(datalayer, EM.ACTIVE, CS_pxa.pxa)
    committed = _later(current, EM.ACTIVE, CS_pxa.PXA)

    assert _apply(bridge, _wire(committed)).status == Status.SUCCESS
    assert _case(datalayer).current_status.pxa.state == CS_pxa.PXA


@pytest.mark.spec("RSH-09-005")
def test_an_invalid_em_move_keeps_the_replicas_em(bridge, datalayer):
    """EXITED → ACTIVE is not an EM transition; the P/X/A advance still lands."""
    current = _seed(datalayer, EM.EXITED, CS_pxa.pxa)
    committed = _later(current, EM.ACTIVE, CS_pxa.Pxa)

    assert _apply(bridge, _wire(committed)).status == Status.SUCCESS

    case = _case(datalayer)
    assert case.current_status.id_ == committed.id_
    assert case.current_status.em.state == EM.EXITED
    assert case.current_status.pxa.state == CS_pxa.Pxa


@pytest.mark.spec("SYNC-12-003")
def test_a_status_the_replica_holds_is_not_appended_twice(bridge, datalayer):
    current = _seed(datalayer)

    assert _apply(bridge, _wire(current)).status == Status.SUCCESS
    assert [_as_id(s) for s in _case(datalayer).case_statuses] == [current.id_]


@pytest.mark.spec("SYNC-12-003")
@pytest.mark.spec("RSH-09-005")
def test_a_status_with_a_stale_em_is_not_appended_twice(bridge, datalayer):
    """Re-delivery is a no-op: the id is already held."""
    current = _seed(datalayer, EM.EXITED, CS_pxa.pxa)
    committed = _later(current, EM.ACTIVE, CS_pxa.Pxa)

    assert _apply(bridge, _wire(committed)).status == Status.SUCCESS
    assert _apply(bridge, _wire(committed)).status == Status.SUCCESS

    case = _case(datalayer)
    assert [_as_id(s) for s in case.case_statuses] == [
        current.id_,
        committed.id_,
    ]
    assert case.current_status.em.state == EM.EXITED


@pytest.mark.spec("RSH-08-004")
def test_a_status_with_no_materialized_one_to_compare_is_appended(
    bridge, datalayer
):
    """No readable current status: the committed status still lands.

    The replica's only status is a reference it cannot resolve; the entry's
    status is appended as recorded.
    """
    unresolved = "urn:uuid:unresolved-status"
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    _register_at(case, EM.ACTIVE)
    case.case_statuses = [unresolved]
    datalayer.save(case)
    committed = _case_status(EM.ACTIVE, CS_pxa.Pxa)

    assert _apply(bridge, _wire(committed)).status == Status.SUCCESS

    case = _case(datalayer)
    assert [_as_id(s) for s in case.case_statuses] == [
        unresolved,
        committed.id_,
    ]
    assert case.current_status.em.state == EM.ACTIVE


@pytest.mark.spec("SYNC-12-001")
def test_a_replica_without_the_case_skips(bridge, datalayer):
    status = _case_status(EM.ACTIVE, CS_pxa.pxa)
    assert _apply(bridge, _wire(status)).status == Status.SUCCESS


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("SYNC-12-002")
@pytest.mark.parametrize(
    "status_object",
    [
        "urn:uuid:bare-id",
        {"id": "urn:uuid:bad", "type": "CaseStatus", "emState": "NOPE"},
    ],
    ids=["bare id", "malformed"],
)
def test_an_unreadable_status_fails_so_the_entry_is_not_persisted(
    bridge, datalayer, status_object
):
    current = _seed(datalayer)

    assert _apply(bridge, status_object).status == Status.FAILURE
    assert [_as_id(s) for s in _case(datalayer).case_statuses] == [current.id_]
