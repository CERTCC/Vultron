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
"""Ledger fan-out and replay apply the CM-10-004 embargo content gate (CM-10-005).

The gate markers are strict ``xfail`` until the gate lands. Today the fan-out
collectors filter on RM-closed only, and the replay path filters nothing, so a
participant that has not accepted the active embargo receives every committed
entry. The no-embargo control passes today and must keep passing.
"""

from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.sync.nodes import SendMissingEntriesNode
from vultron.core.behaviors.sync.nodes.fanout import (
    CollectLogEntryRecipientsNode,
    CollectNonClosedLogEntryRecipientsNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.enums.roles import CVDRole

MANAGER_ID = OWNER_ACTOR_ID
SIGNATORY_ID = "https://example.org/actors/signatory"
NON_SIGNATORY_ID = PARTICIPANT_ACTOR_ID
EMBARGO_ID = f"{CASE_ID}/embargoes/fanout-gate"

_GATE_XFAIL = pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-10-005: ledger fan-out and replay do not yet apply the CM-10-004"
        " embargo content gate. Tracked in #4042; source #3917."
    ),
)
_COLLECTORS = pytest.mark.parametrize(
    "node_cls",
    [CollectLogEntryRecipientsNode, CollectNonClosedLogEntryRecipientsNode],
)


@pytest.fixture
def datalayer():
    """The CASE_MANAGER's store: fan-out and replay run as the manager.

    Shadows the package fixture, which is the participant's store.
    """
    return SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER_ID)


def _seed_case(datalayer, *, embargo_active: bool) -> None:
    """A case in which one participant has not accepted the embargo.

    With *embargo_active* false the embargo exists but is not the case's
    active embargo, so the gate has nothing to withhold.
    """
    embargo = EmbargoEvent(
        id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(45)
    )
    datalayer.create(embargo)
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=MANAGER_ID)
    if embargo_active:
        case.set_embargo(embargo)
    for actor_id, accepted, roles in (
        (MANAGER_ID, [EMBARGO_ID], [CVDRole.CASE_MANAGER]),
        (SIGNATORY_ID, [EMBARGO_ID], []),
        (NON_SIGNATORY_ID, [], []),
    ):
        participant = CaseParticipant(
            id_=f"{actor_id}/participant",
            attributed_to=actor_id,
            context=CASE_ID,
            case_roles=roles,
            accepted_embargo_ids=accepted,
        )
        datalayer.create(participant)
        case.add_participant(participant)
    datalayer.save(case)


def _collect_recipients(bridge, node_cls: type) -> list[str]:
    result = bridge.execute_with_setup(
        tree=node_cls(case_id=CASE_ID),
        actor_id=MANAGER_ID,
        log_entry=_make_entry(0),
    )
    assert result.status == Status.SUCCESS
    return list(py_trees.blackboard.Blackboard.storage["/fanout_recipients"])


@pytest.mark.spec("CM-10-005")
@_COLLECTORS
def test_fanout_includes_non_signatory_without_active_embargo(
    bridge, datalayer, node_cls: type
) -> None:
    """Control: with no active embargo, the gate withholds nothing."""
    _seed_case(datalayer, embargo_active=False)

    recipients = _collect_recipients(bridge, node_cls)

    assert SIGNATORY_ID in recipients
    assert NON_SIGNATORY_ID in recipients


@_GATE_XFAIL
@pytest.mark.spec("CM-10-005")
@_COLLECTORS
def test_fanout_withholds_entries_from_non_signatory(
    bridge, datalayer, node_cls: type
) -> None:
    _seed_case(datalayer, embargo_active=True)

    recipients = _collect_recipients(bridge, node_cls)

    assert SIGNATORY_ID in recipients
    assert NON_SIGNATORY_ID not in recipients


@_GATE_XFAIL
@pytest.mark.spec("CM-10-005")
def test_replay_sends_nothing_to_non_signatory(bridge, datalayer) -> None:
    """A paused participant's Reject must not replay the withheld entries."""
    _seed_case(datalayer, embargo_active=True)
    first = _make_entry(0)
    second = _make_entry(1, first.entry_hash)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=SendMissingEntriesNode(name="SendMissingEntries"),
        actor_id=MANAGER_ID,
        sync_port=sync_port,
        case_actor_id=MANAGER_ID,
        replay_entry=second,
        replay_peer_id=NON_SIGNATORY_ID,
        replay_case_ledger_entries=[first, second],
        replay_from_index=0,
    )

    assert result.status == Status.SUCCESS
    sync_port.send_announce_log_entry.assert_not_called()
