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

The CASE_MANAGER abandons each open proposal with its ``Reject`` of the
proposal it received, or its ``Undo`` of one it sent itself, then an ``Undo``
of each Invite it relayed for it (EMB-16-001, ADR-0152).  The replica drops
each proposal it still holds open and reaches EM ``NONE`` with the last
(EP-09-007, RSH-08-004); a ``Reject`` is the abandonment only when the
CASE_MANAGER sent it.  Runs in the participant's own store (``datalayer``,
ADR-0073).
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
from test.support.embargo_register import propose
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoAbandonmentFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    IsEmbargoAbandonmentEventNode,
    IsRejectEmbargoInviteEventNode,
    IsUndoEmbargoInviteEventNode,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole

_REJECT = MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value
_UNDO = MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE.value
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
    propose(case, FIRST_ID, SECOND_ID)
    _participant(
        datalayer,
        case,
        MANAGER_ACTOR_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    datalayer.save(case)
    return case


def _abandonment(
    embargo: Any, *, verb: str = "Reject", actor: str = MANAGER_ACTOR_ID
) -> dict[str, Any]:
    """The manager's ``Reject`` or ``Undo`` of an embargo Invite, as committed."""
    return {
        "type": verb,
        "actor": actor,
        "context": CASE_ID,
        "object": {
            "type": "Invite",
            "id": f"https://example.org/activities/invite-{id(embargo)}",
            "context": CASE_ID,
            "object": embargo,
        },
    }


def _replay(bridge, embargo: Any, *, verb: str = "Reject"):
    return _run(
        bridge,
        ApplyEmbargoAbandonmentFromLedgerNode(name="Abandonment"),
        _entry(
            _REJECT if verb == "Reject" else _UNDO,
            _abandonment(embargo, verb=verb),
        ),
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
        _entry(_REJECT, snapshot),
    )

    assert result.status == Status.FAILURE
    assert _case(datalayer).proposed_embargo_ids == [FIRST_ID, SECOND_ID]


@pytest.mark.spec("EMB-16-001")
def test_an_undo_after_the_reject_changes_nothing_more(
    bridge, datalayer, proposed_case
):
    """The Reject cancels; each Undo of a relayed Invite finds it in place,
    so the CANCEL is applied once (ADR-0152)."""
    assert _replay(bridge, _embargo_snapshot(FIRST_ID)).status == (
        Status.SUCCESS
    )
    before = _case(datalayer).model_dump(mode="json")

    for _ in range(2):
        result = _replay(bridge, _embargo_snapshot(FIRST_ID), verb="Undo")
        assert result.status == Status.SUCCESS

    assert _case(datalayer).model_dump(mode="json") == before
    assert _case(datalayer).proposed_embargo_ids == [SECOND_ID]


@pytest.mark.spec("EMB-16-001")
def test_the_undo_of_the_managers_own_proposal_cancels_it(
    bridge, datalayer, proposed_case
):
    """When the CASE_MANAGER made the proposal itself, its Undo of that
    proposal is the cancel (ADR-0152)."""
    result = _replay(bridge, _embargo_snapshot(FIRST_ID), verb="Undo")

    assert result.status == Status.SUCCESS
    assert _case(datalayer).proposed_embargo_ids == [SECOND_ID]


def _matches(bridge, node, semantic_type: str, actor: str) -> Status:
    snapshot = _abandonment(_embargo_snapshot(FIRST_ID), actor=actor)
    if semantic_type == _UNDO:
        snapshot["type"] = "Undo"
    status: Status = _run(bridge, node, _entry(semantic_type, snapshot)).status
    return status


@pytest.mark.spec("EMB-16-001")
@pytest.mark.spec("SE-03-004")
@pytest.mark.parametrize(
    ("actor", "abandonment", "participant_reject"),
    [
        (MANAGER_ACTOR_ID, Status.SUCCESS, Status.FAILURE),
        (OWNER_ACTOR_ID, Status.FAILURE, Status.SUCCESS),
    ],
    ids=["case-manager", "participant"],
)
@pytest.mark.spec("MSM-07-016")
def test_a_reject_is_the_abandonment_only_from_the_case_manager(
    bridge, datalayer, proposed_case, actor, abandonment, participant_reject
):
    """One semantic type, told apart after routing by the payload's
    ``actor`` (ADR-0152): the CASE_MANAGER's Reject goes to the abandonment
    slot, which cancels, and a participant's to the rejection slot, which
    records DECLINED."""
    assert (
        _matches(
            bridge,
            IsEmbargoAbandonmentEventNode(name="IsAbandonment"),
            _REJECT,
            actor,
        )
        is abandonment
    )
    assert (
        _matches(
            bridge,
            IsRejectEmbargoInviteEventNode(name="IsRejection"),
            _REJECT,
            actor,
        )
        is participant_reject
    )


def test_the_undo_slot_matches_only_an_undo(bridge, datalayer, proposed_case):
    node = IsUndoEmbargoInviteEventNode
    assert _matches(bridge, node(name="a"), _UNDO, MANAGER_ACTOR_ID) is (
        Status.SUCCESS
    )
    assert _matches(bridge, node(name="b"), _REJECT, MANAGER_ACTOR_ID) is (
        Status.FAILURE
    )
