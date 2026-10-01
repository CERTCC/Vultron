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

import logging
from typing import cast

import py_trees
import pytest

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.proposal import (
    ALREADY_DECLINED_PREFIX,
    RecordParticipantAcceptanceNode,
    RecordParticipantRejectionNode,
    UpdateParticipantEmbargoPecNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.note import VultronNote
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

REJECTER = "https://example.org/actors/rejecter"
OWNER = "https://example.org/actors/owner"


def _tick(node: py_trees.behaviour.Behaviour) -> py_trees.common.Status:
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
        """The handler reads this FAILURE's prefix as SKIPPED, not REFUSED."""
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
        assert node.feedback_message.startswith(ALREADY_DECLINED_PREFIX)

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


class TestRecordParticipantAcceptanceNodeFailsClosed:
    """The EP-05-001 comparison needs both embargo records; a gap is a FAILURE."""

    def _revise_case(
        self, dl: SqliteDataLayer, *, active_replicated: bool
    ) -> tuple[VulnerabilityCase, str, str, str]:
        """A REVISE case owned by OWNER: active A (maybe unheld), proposed B."""
        case, active = make_case_and_embargo(
            "rpa1", em_state=EM.REVISE, attributed_to=OWNER
        )
        revision = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/e2",
            context=case.id_,
            end_time=days_from_now_utc(90),
        )
        case.proposed_embargoes = [revision.id_]
        owner_p = as_CaseParticipant(
            attributed_to=OWNER,
            context=case.id_,
            embargo_consent_state=PEC.SIGNATORY,
            accepted_embargo_ids=[active.id_],
        )
        case.actor_participant_index[OWNER] = owner_p.id_
        case.case_participants = [owner_p.id_]
        dl.create(case)
        dl.create(revision)
        dl.create(owner_p)
        if active_replicated:
            dl.create(active)
        return case, active.id_, revision.id_, owner_p.id_

    @pytest.mark.spec("EMB-18-003")
    @pytest.mark.spec("EP-05-001")
    def test_unreadable_replaced_embargo_fails_as_an_invariant_violation(
        self, dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
    ):
        """A is missing here: FAILURE, an ERROR naming case and A, no write."""
        case, active_id, revision_id, owner_p_id = self._revise_case(
            dl, active_replicated=False
        )
        setup_blackboard(dl)
        node = RecordParticipantAcceptanceNode(
            case_id=case.id_, embargo_id=revision_id, accepting_actor_id=OWNER
        )

        with caplog.at_level(logging.ERROR):
            assert _tick(node) == py_trees.common.Status.FAILURE
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        message = errors[0].getMessage()
        assert "Invariant violation" in message
        assert case.id_ in message
        assert active_id in message
        untouched = cast(VulnerabilityCase, dl.read(case.id_))
        assert untouched.current_status.em.state == EM.REVISE
        assert untouched.active_embargo_id == active_id
        assert untouched.proposed_embargoes == [revision_id]
        owner_p = cast(CaseParticipant, dl.read(owner_p_id))
        assert owner_p.accepted_embargo_ids == [active_id]

    @pytest.mark.spec("EMB-18-003")
    @pytest.mark.spec("EP-05-001")
    def test_replaced_embargo_of_another_type_fails_as_an_invariant_violation(
        self, dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
    ):
        """A resolves to a non-embargo record: the same ERROR, no write."""
        case, active_id, revision_id, owner_p_id = self._revise_case(
            dl, active_replicated=False
        )
        dl.create(VultronNote(id_=active_id, content="not an embargo"))
        setup_blackboard(dl)
        node = RecordParticipantAcceptanceNode(
            case_id=case.id_, embargo_id=revision_id, accepting_actor_id=OWNER
        )

        with caplog.at_level(logging.WARNING):
            assert _tick(node) == py_trees.common.Status.FAILURE
        errors = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert [r.levelno for r in errors] == [logging.ERROR]
        message = errors[0].getMessage()
        assert "Invariant violation" in message
        assert case.id_ in message
        assert active_id in message
        untouched = cast(VulnerabilityCase, dl.read(case.id_))
        assert untouched.current_status.em.state == EM.REVISE
        assert untouched.active_embargo_id == active_id
        assert untouched.proposed_embargoes == [revision_id]
        owner_p = cast(CaseParticipant, dl.read(owner_p_id))
        assert owner_p.accepted_embargo_ids == [active_id]

    @pytest.mark.spec("EMB-18-003")
    def test_unknown_accepted_embargo_fails_without_an_invariant_error(
        self, dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
    ):
        """The *accepted* embargo is the one missing: a plain refusal."""
        case, active_id, revision_id, owner_p_id = self._revise_case(
            dl, active_replicated=True
        )
        setup_blackboard(dl)
        stranger = f"{case.id_}/embargo_events/stranger"
        node = RecordParticipantAcceptanceNode(
            case_id=case.id_,
            embargo_id=stranger,
            accepting_actor_id=OWNER,
        )

        with caplog.at_level(logging.WARNING):
            assert _tick(node) == py_trees.common.Status.FAILURE
        assert stranger in node.feedback_message
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
        untouched = cast(VulnerabilityCase, dl.read(case.id_))
        assert untouched.current_status.em.state == EM.REVISE
        assert untouched.active_embargo_id == active_id
        assert untouched.proposed_embargoes == [revision_id]
        owner_p = cast(CaseParticipant, dl.read(owner_p_id))
        assert owner_p.accepted_embargo_ids == [active_id]


def _participant_on_blackboard(
    dl: SqliteDataLayer, pec: PEC
) -> CaseParticipant:
    """Seed a participant and place it on the ``participant`` key."""
    participant = CaseParticipant(
        attributed_to=REJECTER,
        context="https://example.org/cases/pec-node",
        embargo_consent_state=pec,
    )
    dl.create(participant)
    setup_blackboard(dl)
    bb = py_trees.blackboard.Client(name="participant-seed")
    bb.register_key(key="participant", access=py_trees.common.Access.WRITE)
    bb.participant = participant
    return participant


class TestUpdateParticipantEmbargoPecNodeWhereLegal:
    """``where_legal=True`` turns an illegal trigger into a recorded no-op."""

    @pytest.mark.spec("EP-09-004")
    @pytest.mark.spec("CM-18-003")
    def test_a_signatory_keeps_its_state_and_the_node_succeeds(
        self, dl: SqliteDataLayer
    ):
        participant = _participant_on_blackboard(dl, PEC.SIGNATORY)
        out: dict[str, object] = {}
        node = UpdateParticipantEmbargoPecNode(
            PEC_Trigger.INVITE, where_legal=True, result_out=out
        )
        assert _tick(node) is py_trees.common.Status.SUCCESS
        stored = cast(CaseParticipant, dl.read(participant.id_))
        assert stored.embargo_consent_state == PEC.SIGNATORY
        assert out == {
            "pec_before": PEC.SIGNATORY,
            "pec_after": PEC.SIGNATORY,
            "pec_changed": False,
        }

    def test_a_legal_trigger_applies_and_reports_the_change(
        self, dl: SqliteDataLayer
    ):
        participant = _participant_on_blackboard(dl, PEC.UNBOUND)
        out: dict[str, object] = {}
        node = UpdateParticipantEmbargoPecNode(
            PEC_Trigger.INVITE, where_legal=True, result_out=out
        )
        assert _tick(node) is py_trees.common.Status.SUCCESS
        stored = cast(CaseParticipant, dl.read(participant.id_))
        assert stored.embargo_consent_state == PEC.INVITED
        assert out["pec_changed"] is True
        assert (out["pec_before"], out["pec_after"]) == (
            PEC.UNBOUND,
            PEC.INVITED,
        )

    def test_without_where_legal_an_illegal_trigger_still_raises(
        self, dl: SqliteDataLayer
    ):
        """The default stays fail-closed for every caller that did not opt in."""
        _participant_on_blackboard(dl, PEC.SIGNATORY)
        node = UpdateParticipantEmbargoPecNode(PEC_Trigger.INVITE)
        with pytest.raises(VultronInvalidStateTransitionError):
            _tick(node)

    def test_no_participant_records_nothing(self, dl: SqliteDataLayer):
        setup_blackboard(dl)
        bb = py_trees.blackboard.Client(name="participant-seed")
        bb.register_key(key="participant", access=py_trees.common.Access.WRITE)
        bb.participant = None
        out: dict[str, object] = {}
        node = UpdateParticipantEmbargoPecNode(
            PEC_Trigger.INVITE, where_legal=True, result_out=out
        )
        assert _tick(node) is py_trees.common.Status.SUCCESS
        assert out == {}
