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

"""Which ``AnnounceLogEntryReceivedBT`` effect slot replays a ledger entry.

Shared by the replay ratchets (RSH-08-004): each evaluates an entry against
the positive event condition of every effect slot in
``create_announce_log_entry_tree`` — whatever module under
``vultron/core/behaviors/`` defines it — rather than matching slots by name.
"""

from typing import Any

import py_trees
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    _make_event,
    _to_persistable_entry,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole

MANAGER = "https://example.org/actors/case-manager"
PROPOSER = "https://example.org/actors/proposer"
REPLICA = "https://example.org/actors/replica"
CASE_ID = "https://example.org/cases/replay-ratchet"


def effect_slot_conditions() -> list[py_trees.behaviour.Behaviour]:
    """The positive event conditions of the announce tree's effect slots.

    Found by position, not by class: each slot is
    ``Selector(Sequence(IsX, ApplyX), Inverter(IsX))`` under
    ``LogEntryEventEffects``, and ``IsX`` may be any condition class in any
    module (``IsOfferOwnershipTransferEventNode`` is not an
    ``_ActivityEventNode``).  The condition under the ``Inverter`` is the
    slot's skip arm, not its match.
    """
    (effects,) = [
        node
        for node in create_announce_log_entry_tree().iterate()
        if node.name == "LogEntryEventEffects"
    ]
    conditions = []
    for slot in effects.children:
        match_arm = slot.children[0]
        assert isinstance(match_arm, py_trees.composites.Sequence), slot.name
        assert isinstance(slot.children[-1], py_trees.decorators.Inverter), (
            slot.name
        )
        conditions.append(match_arm.children[0])
    return conditions


def _replica_store() -> SqliteDataLayer:
    """A replica holding the case, so the relay classifier sees the manager."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=REPLICA)
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=PROPOSER)
    manager = CaseParticipant(
        attributed_to=MANAGER,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(manager)
    case.actor_participant_index[MANAGER] = manager.id_
    dl.create(case)
    return dl


def matching_slots(event_type: str, snapshot: dict[str, Any]) -> list[str]:
    """Names of the slot conditions an *event_type* entry satisfies."""
    dl = _replica_store()
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=f"urn:{event_type}",
            event_type=event_type,
            payload_snapshot={"context": CASE_ID, **snapshot},
            prev_log_hash="0" * 64,
        )
    )
    matched = []
    for condition in effect_slot_conditions():
        py_trees.blackboard.Blackboard.storage.clear()
        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=condition,
            actor_id=REPLICA,
            activity=_make_event(entry, actor_id=MANAGER),
        )
        if result.status == Status.SUCCESS:
            matched.append(condition.name)
    return matched
