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

"""``ApplyEmbargoAbandonmentFromLedgerNode`` on a participant's replica.

The CASE_MANAGER commits one ER per abandoned proposal (EMB-16-001, #4131).
The replica drops each proposal it still holds open and reaches EM ``NONE``
with the last (EP-09-007, RSH-08-004).  Runs in the participant's own store
(``datalayer``, ADR-0073).
"""

from datetime import timedelta
from typing import Any, cast

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import CASE_ID, OWNER_ACTOR_ID
from test.core.behaviors.sync.nodes.test_embargo_relay_effect import (
    MANAGER_ACTOR_ID,
    _embargo_snapshot,
    _entry,
    _participant,
    _run,
)
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoAbandonmentFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    EMBARGO_ABANDONMENT_EVENT_TYPE,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole

FIRST_ID = f"{CASE_ID}/embargo_events/p1"
SECOND_ID = f"{CASE_ID}/embargo_events/p2"


@pytest.fixture
def proposed_case(datalayer) -> VulnerabilityCase:
    """A replica case at EM ``PROPOSED`` with two open proposals."""
    for embargo_id in (FIRST_ID, SECOND_ID):
        datalayer.create(
            EmbargoEvent(
                id_=embargo_id,
                context=CASE_ID,
                end_time=now_utc() + timedelta(days=30),
            )
        )
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    case.append_case_status(em_state=EM.PROPOSED)
    case.proposed_embargoes = [FIRST_ID, SECOND_ID]
    _participant(
        datalayer,
        case,
        MANAGER_ACTOR_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    datalayer.save(case)
    return case


def _abandonment(embargo: Any) -> dict[str, Any]:
    """The manager's ``Reject(Invite(EmbargoEvent))``, as committed."""
    return {
        "type": "Reject",
        "actor": MANAGER_ACTOR_ID,
        "context": CASE_ID,
        "object": {
            "type": "Invite",
            "id": f"https://example.org/activities/invite-{id(embargo)}",
            "context": CASE_ID,
            "object": embargo,
        },
    }


def _replay(bridge, embargo: Any):
    return _run(
        bridge,
        ApplyEmbargoAbandonmentFromLedgerNode(name="Abandonment"),
        _entry(EMBARGO_ABANDONMENT_EVENT_TYPE, _abandonment(embargo)),
    )


def _case(datalayer) -> VulnerabilityCase:
    return cast(VulnerabilityCase, datalayer.read(CASE_ID))


@pytest.mark.spec("EMB-16-001")
@pytest.mark.spec("EP-09-007")
def test_each_entry_drops_its_proposal_and_the_last_reaches_none(
    bridge, datalayer, proposed_case
):
    assert _replay(bridge, _embargo_snapshot(FIRST_ID)).status == (
        Status.SUCCESS
    )
    case = _case(datalayer)
    assert case.current_status.em.state == EM.PROPOSED
    assert case.proposed_embargo_ids == [SECOND_ID]

    assert _replay(bridge, _embargo_snapshot(SECOND_ID)).status == (
        Status.SUCCESS
    )
    case = _case(datalayer)
    assert case.current_status.em.state == EM.NONE
    assert case.proposed_embargo_ids == []


@pytest.mark.spec("SYNC-12-001")
def test_an_entry_for_a_proposal_not_held_open_is_a_no_op(
    bridge, datalayer, proposed_case
):
    """A repeated or late entry never blocks the persist."""
    assert _replay(bridge, FIRST_ID).status == Status.SUCCESS
    assert _replay(bridge, FIRST_ID).status == Status.SUCCESS

    case = _case(datalayer)
    assert case.current_status.em.state == EM.PROPOSED
    assert case.proposed_embargo_ids == [SECOND_ID]


def test_a_partial_replica_without_the_case_skips(bridge, datalayer):
    assert _replay(bridge, _embargo_snapshot(FIRST_ID)).status == (
        Status.SUCCESS
    )
    assert datalayer.read(CASE_ID) is None


def test_an_entry_naming_no_embargo_fails(bridge, datalayer, proposed_case):
    snapshot = _abandonment(None)
    snapshot["object"] = "https://example.org/activities/bare-invite"
    result = _run(
        bridge,
        ApplyEmbargoAbandonmentFromLedgerNode(name="Abandonment"),
        _entry(EMBARGO_ABANDONMENT_EVENT_TYPE, snapshot),
    )

    assert result.status == Status.FAILURE
    assert _case(datalayer).proposed_embargo_ids == [FIRST_ID, SECOND_ID]
