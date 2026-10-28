#!/usr/bin/env python
#
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
"""The received-tree stage that answers a stamped ledger position (SYNC-18).

:func:`create_ledger_position_stage` builds the CASE_MANAGER's answer to the
``ledgerPosition`` a received case activity states (ADR-0155, ADR-0156).
``create_receive_activity_tree`` places it in every received tree that names
its case and has a sender guard, after the door guards and before the
clock decisions and precondition guards, so it runs once per delivery
whatever the act's merits (CLP-10-005)::

    LedgerPositionIfCaseManager (CaseManagerGate)
    └─ LedgerPositionAnswer (never fails the tree)
       └─ AnswerLedgerPosition (Sequence)
          ├─ ClassifyLedgerPosition            # DEBUG lag, ERROR split
          └─ AnswerByStanding (Selector)
             ├─ LedgerPositionIs[none]         # nothing to answer
             ├─ AnswerHeldPosition (Sequence)
             │  ├─ LedgerPositionIs[lag|tail]
             │  └─ RecordAndReplayIfActive (Selector)
             │     ├─ PeerNotActiveParticipant # inert: nothing written
             │     └─ RecordAndReplay (Sequence)
             │        ├─ UpdateReplicationState            # SYNC-17-003
             │        └─ ReplayIfLagging (Selector)
             │           ├─ LedgerPositionIs[tail]         # nothing to send
             │           └─ Replay: FindCaseActor, ReplayMissingEntries
             └─ RepairSplitPosition (Sequence)
                ├─ LedgerPositionIs[split]
                └─ ReseedPeer                  # SYNC-16-003/004

The record and the replay are the nodes ``Read(CaseLedgerEntry)`` answers
with (SYNC-18-007), and the re-seed is the one rate-bounded re-seed send
(SYNC-18-005).  The stage commits no ledger entry: a position statement
changes nothing in the case file (SYNC-17-006).
"""

import py_trees

from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.sync.nodes.chain import UpdateReplicationStateNode
from vultron.core.behaviors.sync.nodes.ledger_position import (
    HELD,
    ClassifyLedgerPositionNode,
    LedgerPositionAnswer,
    LedgerPositionIsNode,
    PeerNotActiveParticipantNode,
    PositionStanding,
)
from vultron.core.behaviors.sync.nodes.replay import (
    FindCaseActorNode,
    ReplayMissingEntriesNode,
)
from vultron.core.behaviors.sync.nodes.reseed import ReseedPeerNode

__all__ = ["LEDGER_POSITION_GATE_NAME", "create_ledger_position_stage"]

#: Name of the CASE_MANAGER gate around the ledger-position answer.
LEDGER_POSITION_GATE_NAME = "LedgerPositionIfCaseManager"


def _is(*expect: PositionStanding) -> LedgerPositionIsNode:
    return LedgerPositionIsNode(expect=frozenset(expect))


def create_ledger_position_stage(
    case_id: str, sender_id: str
) -> CaseManagerGate:
    """The CASE_MANAGER's answer to *sender_id*'s stamped position in *case_id*.

    Runs only at the case's CASE_MANAGER; a store that does not hold the case
    skips it at ``debug`` level.  A held position from an active participant
    is recorded, and a lagging one also has the entries after it replayed
    under the replay rate bound and outbox de-duplication; at the tail
    nothing is sent (SYNC-18-007).  A split position is logged at ERROR and
    an active participant re-seeded under the SYNC-16-004 bound
    (SYNC-18-005).  An inert sender's position is neither recorded nor
    answered.  Whatever the answer does, the received activity is judged as
    it would be without it.
    """
    replay_a_lag = py_trees.composites.Selector(
        name="ReplayIfLagging",
        memory=False,
        children=[
            _is(PositionStanding.TAIL),
            py_trees.composites.Sequence(
                name="Replay",
                memory=False,
                children=[
                    FindCaseActorNode(name="FindCaseActor", case_id=case_id),
                    ReplayMissingEntriesNode(
                        name="ReplayMissingEntries", case_id=case_id
                    ),
                ],
            ),
        ],
    )
    record_and_replay = py_trees.composites.Sequence(
        name="RecordAndReplay",
        memory=False,
        children=[
            UpdateReplicationStateNode(
                name="UpdateReplicationState", case_id=case_id
            ),
            replay_a_lag,
        ],
    )
    by_standing = py_trees.composites.Selector(
        name="AnswerByStanding",
        memory=False,
        children=[
            _is(PositionStanding.NONE),
            py_trees.composites.Sequence(
                name="AnswerHeldPosition",
                memory=False,
                children=[
                    LedgerPositionIsNode(expect=HELD),
                    py_trees.composites.Selector(
                        name="RecordAndReplayIfActive",
                        memory=False,
                        children=[
                            PeerNotActiveParticipantNode(
                                case_id=case_id, sender_id=sender_id
                            ),
                            record_and_replay,
                        ],
                    ),
                ],
            ),
            py_trees.composites.Sequence(
                name="RepairSplitPosition",
                memory=False,
                children=[
                    _is(PositionStanding.SPLIT),
                    ReseedPeerNode(
                        case_id=case_id, peer_id=sender_id, name="ReseedPeer"
                    ),
                ],
            ),
        ],
    )
    answer = py_trees.composites.Sequence(
        name="AnswerLedgerPosition",
        memory=False,
        children=[
            ClassifyLedgerPositionNode(
                case_id=case_id,
                sender_id=sender_id,
                name="ClassifyLedgerPosition",
            ),
            by_standing,
        ],
    )
    return create_case_manager_gated_tree(
        name=LEDGER_POSITION_GATE_NAME,
        case_id=case_id,
        children=[
            LedgerPositionAnswer(name="LedgerPositionAnswer", child=answer)
        ],
        case_may_be_absent=True,
    )
