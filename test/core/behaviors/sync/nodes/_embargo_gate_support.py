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
"""Shared scaffolding for the CM-10-005/006 embargo-gate node tests.

Imported by ``test_fanout_embargo_gate.py`` and ``test_embargo_backfill.py``,
which test the fan-out/replay gate and the admission backfill node.
"""

import py_trees
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
)
from test.support.embargo_register import activate
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.sync.nodes import SendMissingEntriesNode
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    embargo_paused_from_index,
)
from vultron.core.behaviors.sync.nodes.fanout import (
    FanOutLogEntryExcludingClosedNode,
    FanOutLogEntryNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

MANAGER_ID = OWNER_ACTOR_ID
SIGNATORY_ID = "https://example.org/actors/signatory"
NON_SIGNATORY_ID = PARTICIPANT_ACTOR_ID
EMBARGO_ID = f"{CASE_ID}/embargoes/fanout-gate"


def manager_datalayer() -> SqliteDataLayer:
    """The CASE_MANAGER's store: fan-out, replay and backfill run as the manager.

    Each test module wraps this in a ``datalayer`` fixture that shadows the
    package fixture, which is the participant's store.
    """
    return SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER_ID)


def seed_case(datalayer, *, embargo_active: bool) -> None:
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
        activate(case, embargo)
    for actor_id, consent, roles in (
        (MANAGER_ID, EmbargoConsentState.AGREED, [CVDRole.CASE_MANAGER]),
        (SIGNATORY_ID, EmbargoConsentState.AGREED, []),
        (NON_SIGNATORY_ID, EmbargoConsentState.INVITED, []),
    ):
        participant = CaseParticipant(
            id_=f"{actor_id}/participant",
            attributed_to=actor_id,
            context=CASE_ID,
            case_roles=roles,
            embargo_consents=[
                EmbargoConsent(embargo_id=EMBARGO_ID, state=consent)
            ],
        )
        datalayer.create(participant)
        case.add_participant(participant)
    datalayer.save(case)


def collect_recipients(bridge, node_cls: type) -> list[str]:
    result = bridge.execute_with_setup(
        tree=node_cls(case_id=CASE_ID),
        actor_id=MANAGER_ID,
        log_entry=_make_entry(0),
    )
    assert result.status == Status.SUCCESS
    return list(py_trees.blackboard.Blackboard.storage["/fanout_recipients"])


def accept_embargo(datalayer, actor_id: str) -> None:
    """Record that *actor_id* accepted the active embargo (CM-10-006 admission).

    Marks the participant's row for the embargo ``AGREED``, which is what
    the active-participant check reads (CM-10-004).
    """
    participant = datalayer.read(f"{actor_id}/participant")
    assert isinstance(participant, CaseParticipant)
    participant.apply_pec_transition(
        EMBARGO_ID,
        PEC_Trigger.AGREE,
        entry_status=EmbargoRegisterStatus.ACTIVE,
    )
    datalayer.save(participant)


def seed_ledger(datalayer, count: int) -> list:
    entries = [_make_entry(0)]
    for index in range(1, count):
        entries.append(_make_entry(index, entries[-1].entry_hash))
    for entry in entries:
        datalayer.save(entry)
    return entries


def close(datalayer, actor_id: str) -> None:
    """Move *actor_id*'s participant to RM.CLOSED."""
    participant = datalayer.read(f"{actor_id}/participant")
    assert isinstance(participant, CaseParticipant)
    participant.participant_statuses = [
        ParticipantStatus(
            context=CASE_ID,
            attributed_to=actor_id,
            rm=RmDimension(state=RM.CLOSED),
        )
    ]
    datalayer.save(participant)


def replay(bridge, entries, *, peer_id: str, from_index: int, sync_port):
    return bridge.execute_with_setup(
        tree=SendMissingEntriesNode(name="SendMissingEntries"),
        actor_id=MANAGER_ID,
        sync_port=sync_port,
        case_actor_id=MANAGER_ID,
        replay_entry=entries[-1],
        replay_peer_id=peer_id,
        replay_case_ledger_entries=entries,
        replay_from_index=from_index,
    )


def paused_from(datalayer, peer_id: str = NON_SIGNATORY_ID) -> int | None:
    return embargo_paused_from_index(
        datalayer, case_id=CASE_ID, peer_id=peer_id
    )


def fan_out(
    bridge,
    entry,
    sync_port,
    *,
    tree_cls: type[FanOutLogEntryNode]
    | type[FanOutLogEntryExcludingClosedNode] = FanOutLogEntryNode,
) -> None:
    result = bridge.execute_with_setup(
        tree=tree_cls(case_id=CASE_ID),
        actor_id=MANAGER_ID,
        log_entry=entry,
        sync_port=sync_port,
    )
    assert result.status == Status.SUCCESS


def sends(sync_port) -> list[tuple[int, list[str]]]:
    """``(log_index, recipients)`` per ``send_announce_log_entry`` call, in order."""
    return [
        (call.kwargs["entry"].log_index, list(call.kwargs["to"]))
        for call in sync_port.send_announce_log_entry.call_args_list
    ]
