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

"""Unit tests for embargo teardown nodes (teardown.py)."""

import logging
from typing import cast
from unittest.mock import MagicMock, patch

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.teardown import (
    ApplyEmbargoTeardownNode,
    ClearActiveEmbargoNode,
    HasEmbargoActiveNode,
    RemoveFromProposedEmbargoesNode,
    ResetParticipantConsentNode,
    SendAnnounceEmbargoEventNode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.models.case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    make_case_and_embargo,
    make_case_with_manager,
    setup_blackboard,
)

ACTOR_ID = "https://example.org/actors/vendor"


def _setup_blackboard_with_factory(
    dl: SqliteDataLayer,
    factory: MagicMock,
    actor_id: str = ACTOR_ID,
) -> None:
    """Write datalayer, actor_id, and trigger_activity_factory to blackboard."""
    py_trees.blackboard.Blackboard.enable_activity_stream()
    bb = py_trees.blackboard.Client(name="test-factory-setup")
    for key in ("datalayer", "actor_id", "trigger_activity_factory"):
        bb.register_key(key=key, access=py_trees.common.Access.WRITE)
    bb.datalayer = dl
    bb.actor_id = actor_id
    bb.trigger_activity_factory = factory


class TestHasEmbargoActiveNode:
    """Tests for HasEmbargoActiveNode."""

    def test_returns_success_when_em_active(self):
        """Returns SUCCESS when EM state is ACTIVE."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("hea1", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = HasEmbargoActiveNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_success_when_em_revise(self):
        """Returns SUCCESS when EM state is REVISE (also an active embargo)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("hea2", em_state=EM.REVISE)
        dl.create(case)

        setup_blackboard(dl)
        node = HasEmbargoActiveNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_em_exited(self):
        """Returns FAILURE when EM state is EXITED (teardown already done)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("hea3", em_state=EM.EXITED)
        case.active_embargo = None
        dl.create(case)

        setup_blackboard(dl)
        node = HasEmbargoActiveNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_failure_when_case_missing(self):
        """Returns FAILURE when case is not found in the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        setup_blackboard(dl)

        node = HasEmbargoActiveNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE


class TestClearActiveEmbargoNode:
    """Tests for ClearActiveEmbargoNode."""

    @pytest.mark.spec("EMB-07-001")
    def test_transitions_em_active_to_exited_and_clears_pointer(self):
        """Transitions EM.ACTIVE → EXITED and sets active_embargo = None."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen1", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED
        assert updated.active_embargo is None

    def test_teardown_logged_in_narrative_form(self, caplog):
        """EM ACTIVE → EXITED is logged at INFO (SL-04-001, AC-16)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen-narr", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl, actor_id=ACTOR_ID)
        node = ClearActiveEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.INFO):
            bt.tick()

        narrative = [
            r
            for r in caplog.records
            if "embargo ACTIVE → EXITED" in r.getMessage()
            and r.levelno == logging.INFO
        ]
        assert narrative, "Expected a narrative embargo-teardown line"
        assert (
            narrative[0].getMessage()
            == f"Actor '{ACTOR_ID}' embargo ACTIVE → EXITED"
            f" for case '{case.id_}'"
        )

    def test_cleared_embargo_detail_line_is_debug(self, caplog):
        """The verbose "Cleared active embargo" detail line is DEBUG."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen-detail", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.DEBUG):
            bt.tick()

        detail = [
            r
            for r in caplog.records
            if "Cleared active embargo" in r.getMessage()
        ]
        assert detail, "Expected the 'Cleared active embargo' detail line"
        assert all(r.levelno == logging.DEBUG for r in detail)

    @pytest.mark.spec("EMB-07-002")
    def test_transitions_em_revise_to_exited(self):
        """Transitions EM.REVISE → EXITED."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen2", em_state=EM.REVISE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED

    @pytest.mark.spec("EMB-07-003")
    def test_idempotent_when_already_exited(self):
        """Returns SUCCESS without modifying state when EM already EXITED."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen3", em_state=EM.EXITED)
        case.active_embargo = None
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED

    def test_state_sync_override_for_unexpected_em_state(self, caplog):
        """Logs WARNING and applies state-sync override for non-standard EM state."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen4", em_state=EM.NONE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.WARNING):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert any("state-sync override" in r.message for r in caplog.records)
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED

    def test_returns_failure_when_case_missing(self):
        """Returns FAILURE when the case is not found in the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        setup_blackboard(dl)

        node = ClearActiveEmbargoNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_single_save_call(self):
        """Both em_state and active_embargo are committed in a single datalayer.save()."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen5", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        original_save = dl.save
        save_calls = []

        def recording_save(obj):
            save_calls.append(obj)
            return original_save(obj)

        dl.save = recording_save
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert (
            len(save_calls) == 1
        ), f"Expected exactly 1 datalayer.save() call, got {len(save_calls)}"


class TestResetParticipantConsentNode:
    """Tests for ResetParticipantConsentNode."""

    @pytest.mark.spec("EMB-13-001")
    def test_resets_participant_pec_to_no_embargo(self):
        """Resets all participant PEC states to NO_EMBARGO."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("rpcn1", em_state=EM.ACTIVE)
        participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/p1",
            attributed_to="https://example.org/users/finder",
        )
        participant.embargo_consent_state = PEC.SIGNATORY.value
        case.case_participants.append(participant.id_)
        dl.create(case)
        dl.create(participant)

        setup_blackboard(dl)
        node = ResetParticipantConsentNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated_p = cast(as_CaseParticipant, dl.read(participant.id_))
        assert updated_p.embargo_consent_state == PEC.NO_EMBARGO.value

    def test_returns_success_with_no_participants(self):
        """Returns SUCCESS when case has no participants."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("rpcn2", em_state=EM.ACTIVE)
        case.case_participants = []
        dl.create(case)

        setup_blackboard(dl)
        node = ResetParticipantConsentNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_case_missing(self):
        """Returns FAILURE when the case is not found in the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        setup_blackboard(dl)

        node = ResetParticipantConsentNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE


class TestApplyEmbargoTeardownNode:
    """Tests for ApplyEmbargoTeardownNode."""

    @pytest.mark.spec("EMB-07-001")
    def test_transitions_em_active_to_exited(self):
        """Node transitions EM.ACTIVE → EM.EXITED and saves the case."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("atn1", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED
        assert updated.active_embargo is None

    def test_teardown_logged_in_narrative_form(self, caplog):
        """ApplyEmbargoTeardownNode logs EM ACTIVE → EXITED at INFO."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("atn-narr", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.INFO):
            bt.tick()

        narrative = [
            r
            for r in caplog.records
            if "embargo ACTIVE → EXITED" in r.getMessage()
            and r.levelno == logging.INFO
        ]
        assert narrative, "Expected a narrative embargo-teardown line"
        assert f"for case '{case.id_}'" in narrative[0].getMessage()

    def test_teardown_applied_detail_line_is_debug(self, caplog):
        """The verbose "Embargo teardown applied" detail line is DEBUG."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("atn-detail", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.DEBUG):
            bt.tick()

        detail = [
            r
            for r in caplog.records
            if "Embargo teardown applied" in r.getMessage()
        ]
        assert detail, "Expected the 'Embargo teardown applied' detail line"
        assert all(r.levelno == logging.DEBUG for r in detail)

    @pytest.mark.spec("EMB-07-002")
    def test_transitions_em_revise_to_exited(self):
        """Node transitions EM.REVISE → EM.EXITED (also a valid terminate path)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("atn2", em_state=EM.REVISE)
        dl.create(case)

        setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED

    @pytest.mark.spec("EMB-07-003")
    def test_idempotent_when_already_exited(self):
        """Node returns SUCCESS without modifying state when already EXITED."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("atn3", em_state=EM.EXITED)
        case.active_embargo = None
        dl.create(case)

        setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED

    def test_state_sync_override_for_unexpected_em_state(self, caplog):
        """Node logs WARNING and applies override for non-standard EM state."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("atn4", em_state=EM.NONE)
        dl.create(case)

        setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.WARNING):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert any("state-sync override" in r.message for r in caplog.records)
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED

    @pytest.mark.spec("EMB-13-001")
    def test_resets_participant_embargo_consent(self):
        """Node resets participant PEC state to NO_EMBARGO."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("atn5", em_state=EM.ACTIVE)
        participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/p1",
            attributed_to="https://example.org/users/finder",
        )
        participant.embargo_consent_state = PEC.SIGNATORY.value
        case.case_participants.append(participant.id_)
        dl.create(case)
        dl.create(participant)

        setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated_p = cast(as_CaseParticipant, dl.read(participant.id_))
        assert updated_p.embargo_consent_state == PEC.NO_EMBARGO.value

    def test_returns_success_when_case_missing(self):
        """Node returns SUCCESS when the case ID is not in the DataLayer.

        In the sync context (Announce log entry fan-out), a missing case is
        not an error — the entry may reference a case the participant does
        not know about yet.  The Sequence should not fail in this situation.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        setup_blackboard(dl)

        node = ApplyEmbargoTeardownNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    @pytest.mark.spec("EMB-18-001")
    def test_delegates_em_write_to_clear_active_embargo_node(self):
        """AC-1 (issue #2583): EM write is delegated to ClearActiveEmbargoNode.

        When ClearActiveEmbargoNode.update() is patched to return FAILURE the
        EM state is not mutated and the node still returns SUCCESS (sync
        context graceful fallback).  This proves the inline write was
        replaced by delegation.
        """
        from py_trees.common import Status as BtStatus

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("ac1-del", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with patch.object(
            ClearActiveEmbargoNode, "update", return_value=BtStatus.FAILURE
        ):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        unchanged = cast(VulnerabilityCase, dl.read(case.id_))
        assert unchanged.current_status.em.state == EM.ACTIVE


class TestRemoveFromProposedEmbargoesNode:
    """Tests for RemoveFromProposedEmbargoesNode."""

    def test_removes_embargo_from_proposed_list(self):
        """Node removes embargo_id from proposed_embargoes and returns SUCCESS."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, embargo = make_case_and_embargo("rfp1", em_state=EM.PROPOSED)
        case.proposed_embargoes.append(embargo.id_)
        dl.create(case)

        setup_blackboard(dl)
        node = RemoveFromProposedEmbargoesNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert embargo.id_ not in [
            e if isinstance(e, str) else getattr(e, "id_", None)
            for e in updated.proposed_embargoes
        ]

    def test_idempotent_when_not_in_proposed(self):
        """Node returns SUCCESS even if embargo_id is not in proposed_embargoes."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, embargo = make_case_and_embargo("rfp2", em_state=EM.ACTIVE)
        # embargo NOT in proposed_embargoes
        dl.create(case)

        setup_blackboard(dl)
        node = RemoveFromProposedEmbargoesNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_case_missing(self):
        """Node returns FAILURE when the case ID is not in the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        setup_blackboard(dl)

        node = RemoveFromProposedEmbargoesNode(
            case_id="https://example.org/cases/nonexistent",
            embargo_id=(
                "https://example.org/cases/nonexistent/embargo_events/e1"
            ),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE


# ---------------------------------------------------------------------------
# SendAnnounceEmbargoEventNode
# ---------------------------------------------------------------------------


class TestSendAnnounceEmbargoEventNode:
    """Tests for SendAnnounceEmbargoEventNode."""

    def _make_factory(self) -> MagicMock:
        factory = MagicMock()
        factory.announce_embargo.return_value = (
            "https://example.org/activities/announce1",
            {},
        )
        return factory

    def test_emits_announce_activity_and_queues_to_outbox(self):
        """Node calls announce_embargo and queues the activity to outbox."""
        case, _, dl = make_case_with_manager("saee1", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("saee1")
        factory = self._make_factory()

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        factory.announce_embargo.assert_called_once_with(
            embargo_id=embargo.id_,
            case_id=case.id_,
            actor=ACTOR_ID,
            to=[CASE_MANAGER_ACTOR],
        )
        outbox = dl.outbox_list()
        assert "https://example.org/activities/announce1" in outbox

    def test_returns_success_when_factory_unavailable(self):
        """Node returns SUCCESS (skips gracefully) when no factory is set."""
        case, _, dl = make_case_with_manager("saee2", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("saee2")

        setup_blackboard(dl, actor_id=ACTOR_ID)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_case_not_found(self):
        """Node returns FAILURE when the case cannot be read from the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        factory = self._make_factory()

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id="https://example.org/cases/missing",
            embargo_id="https://example.org/cases/missing/embargo_events/e1",
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
        factory.announce_embargo.assert_not_called()

    def test_returns_success_when_no_case_manager(self):
        """Node returns SUCCESS (skips gracefully) when no CASE_MANAGER is found."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, embargo = make_case_and_embargo("saee4", em_state=EM.ACTIVE)
        dl.create(case)  # no CASE_MANAGER participant
        factory = self._make_factory()

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        factory.announce_embargo.assert_not_called()

    def test_returns_failure_when_factory_raises(self):
        """Node returns FAILURE when the factory call raises an exception."""
        case, _, dl = make_case_with_manager("saee5", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("saee5")
        factory = self._make_factory()
        factory.announce_embargo.side_effect = RuntimeError("boom")

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_success_when_outbox_write_fails(self):
        """Node returns SUCCESS (best-effort) when factory succeeds but outbox write raises."""
        case, _, dl = make_case_with_manager("saee6", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("saee6")
        factory = self._make_factory()

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        patch_target = (
            "vultron.core.behaviors.embargo.nodes.emit.add_activity_to_outbox"
        )
        with patch(patch_target, side_effect=RuntimeError("outbox error")):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        factory.announce_embargo.assert_called_once()
