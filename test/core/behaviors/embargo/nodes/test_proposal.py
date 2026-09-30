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

"""``RecordParticipantRejectionNode`` (nodes/proposal.py).

The received-side twin of ``RecordParticipantAcceptanceNode``: it records a
participant's Reject through ``EmbargoLifecycle.record_embargo_rejection`` and
reports the outcomes the handler maps to dispositions — SUCCESS on a recorded
or no-op answer, FAILURE plus an already-``DECLINED`` record for a repeat
(→ SKIPPED, HP-01-003), FAILURE for an unknown embargo or a missing case
(→ REFUSED).  The consent rule itself is pinned in
``test/core/services/embargo_lifecycle/test_consent.py``.
"""

from typing import cast

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.proposal import (
    RecordParticipantRejectionNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)

REJECTER = "https://example.org/actors/rejecter"


def _tick(node: RecordParticipantRejectionNode) -> py_trees.common.Status:
    bt = py_trees.trees.BehaviourTree(root=node)
    bt.setup()
    bt.tick()
    return node.status


def _case_with_rejecter(
    dl: SqliteDataLayer, *, pec: PEC
) -> tuple[VulnerabilityCase, str, str]:
    """An ACTIVE case whose embargo is in force, plus a rejecter at *pec*."""
    case, embargo = make_case_and_embargo("rpr1", em_state=EM.ACTIVE)
    participant = as_CaseParticipant(
        attributed_to=REJECTER,
        context=case.id_,
        embargo_consent_state=pec,
        accepted_embargo_ids=[embargo.id_] if pec is PEC.SIGNATORY else [],
    )
    case.actor_participant_index[REJECTER] = participant.id_
    case.case_participants = [*case.case_participants, participant.id_]
    dl.create(case)
    dl.create(embargo)
    dl.create(participant)
    return case, embargo.id_, participant.id_


class TestRecordParticipantRejectionNode:
    def test_records_a_withdrawal_and_succeeds(self, dl: SqliteDataLayer):
        case, embargo_id, participant_id = _case_with_rejecter(
            dl, pec=PEC.SIGNATORY
        )
        setup_blackboard(dl)
        node = RecordParticipantRejectionNode(
            case_id=case.id_,
            embargo_id=embargo_id,
            rejecting_actor_id=REJECTER,
        )

        assert _tick(node) == py_trees.common.Status.SUCCESS
        participant = cast(CaseParticipant, dl.read(participant_id))
        assert participant.embargo_consent_state == PEC.DECLINED.value
        assert participant.accepted_embargo_ids == []

    def test_partial_replica_without_the_participant_succeeds(
        self, dl: SqliteDataLayer
    ):
        """No record for the rejecter here: nothing to write, tree continues."""
        case, embargo = make_case_and_embargo("rpr2", em_state=EM.ACTIVE)
        dl.create(case)
        dl.create(embargo)
        setup_blackboard(dl)
        node = RecordParticipantRejectionNode(
            case_id=case.id_,
            embargo_id=embargo.id_,
            rejecting_actor_id=REJECTER,
        )

        assert _tick(node) == py_trees.common.Status.SUCCESS

    @pytest.mark.spec("HP-01-003")
    def test_repeat_from_declined_fails_naming_the_repeat(
        self, dl: SqliteDataLayer
    ):
        """The handler reads FAILURE + DECLINED as SKIPPED, not REFUSED."""
        case, embargo_id, _participant_id = _case_with_rejecter(
            dl, pec=PEC.DECLINED
        )
        setup_blackboard(dl)
        node = RecordParticipantRejectionNode(
            case_id=case.id_,
            embargo_id=embargo_id,
            rejecting_actor_id=REJECTER,
        )

        assert _tick(node) == py_trees.common.Status.FAILURE
        assert "already declined" in node.feedback_message

    def test_unknown_embargo_fails(self, dl: SqliteDataLayer):
        case, _embargo_id, participant_id = _case_with_rejecter(
            dl, pec=PEC.INVITED
        )
        setup_blackboard(dl)
        node = RecordParticipantRejectionNode(
            case_id=case.id_,
            embargo_id=f"{case.id_}/embargo_events/stranger",
            rejecting_actor_id=REJECTER,
        )

        assert _tick(node) == py_trees.common.Status.FAILURE
        assert "neither the active" in node.feedback_message
        participant = cast(CaseParticipant, dl.read(participant_id))
        assert participant.embargo_consent_state == PEC.INVITED.value

    def test_missing_case_fails(self, dl: SqliteDataLayer):
        setup_blackboard(dl)
        node = RecordParticipantRejectionNode(
            case_id="https://example.org/cases/missing",
            embargo_id="https://example.org/cases/missing/embargo_events/e",
            rejecting_actor_id=REJECTER,
        )

        assert _tick(node) == py_trees.common.Status.FAILURE
