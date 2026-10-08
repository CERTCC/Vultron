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
"""Replay of ``add_embargo_event_to_case`` on a participant replica (#3814 AC-4).

The activation counterpart of the teardown replay: the register activates
the embargo, so EM derives ACTIVE, through ``EmbargoLifecycle`` (EMB-18-001).
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
from test.support.embargo_register import activate, propose
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoActivationFromLedgerNode,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import EM

MANAGER = "https://example.org/actors/case-manager"
EMBARGO_ID = f"{CASE_ID}/embargo_events/e1"
PRIOR_EMBARGO_ID = f"{CASE_ID}/embargo_events/e0"


def _embargo_snapshot() -> dict[str, Any]:
    return {
        "type": "EmbargoEvent",
        "id": EMBARGO_ID,
        "context": CASE_ID,
        "endTime": (now_utc() + timedelta(days=60)).isoformat(),
    }


def _seed(datalayer, em: EM) -> VulnerabilityCase:
    """A replica whose register has the entry's embargo open as a proposal.

    ``REVISE`` adds an earlier embargo in force, which the activation
    supersedes.  EM is derived from the register (ADR-0122).
    """
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    if em is EM.REVISE:
        # The activation reads the embargo it replaces (EMB-18-003).
        datalayer.save(
            EmbargoEvent(
                id_=PRIOR_EMBARGO_ID,
                context=CASE_ID,
                end_time=now_utc() + timedelta(days=90),
            )
        )
        activate(case, PRIOR_EMBARGO_ID)
    propose(case, EMBARGO_ID)
    assert case.em_state == em
    datalayer.save(case)
    return case


def _apply(bridge, embargo: Any):
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/add-embargo",
            event_type="add_embargo_event_to_case",
            payload_snapshot={
                "type": "Add",
                "actor": OWNER_ACTOR_ID,
                "context": CASE_ID,
                "object": embargo,
                "target": CASE_ID,
            },
            prev_log_hash="0" * 64,
        )
    )
    return bridge.execute_with_setup(
        tree=ApplyEmbargoActivationFromLedgerNode(name="ApplyActivation"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=MANAGER),
    )


def _case(datalayer) -> VulnerabilityCase:
    case = datalayer.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return case


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("EMB-18-001")
@pytest.mark.parametrize("em_before", [EM.PROPOSED, EM.REVISE])
def test_the_entry_activates_the_embargo_on_the_replica(
    bridge, datalayer, em_before
):
    _seed(datalayer, em_before)

    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS

    case = _case(datalayer)
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == EMBARGO_ID
    # Stored from the inline copy the entry carries (EMB-18-003).
    assert isinstance(datalayer.read(EMBARGO_ID), EmbargoEvent)


@pytest.mark.spec("SYNC-12-003")
def test_an_embargo_already_in_force_is_a_no_op(bridge, datalayer):
    _seed(datalayer, EM.PROPOSED)
    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS
    before = _case(datalayer).model_dump()

    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS
    assert _case(datalayer).model_dump() == before


@pytest.mark.spec("SYNC-12-001")
def test_a_replica_without_the_case_skips(bridge, datalayer):
    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS
    assert datalayer.read(EMBARGO_ID) is None


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("EMB-18-003")
def test_an_embargo_the_replica_cannot_reconstruct_fails(bridge, datalayer):
    """A bare id the replica does not hold blocks persisting the entry."""
    _seed(datalayer, EM.PROPOSED)

    assert _apply(bridge, EMBARGO_ID).status == Status.FAILURE
    assert _case(datalayer).current_status.em.state == EM.PROPOSED
