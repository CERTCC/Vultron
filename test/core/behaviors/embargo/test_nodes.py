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
"""Unit tests for vultron/core/behaviors/embargo/nodes.py."""

from typing import cast

import py_trees

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoTeardownNode,
    IsActiveEmbargoNode,
    RemoveFromProposedEmbargoesNode,
    ValidateCaseExistsNode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# Populate the vocabulary registry as a side-effect.
_ = VulnerabilityCase


def _setup_blackboard(
    dl: SqliteDataLayer, actor_id: str = "https://example.org/users/vendor"
) -> None:
    """Populate the py_trees blackboard with the DataLayer and actor_id."""
    py_trees.blackboard.Blackboard.enable_activity_stream()
    blackboard = py_trees.blackboard.Client(name="test-setup")
    blackboard.register_key(
        key="datalayer", access=py_trees.common.Access.WRITE
    )
    blackboard.register_key(
        key="actor_id", access=py_trees.common.Access.WRITE
    )
    blackboard.datalayer = dl
    blackboard.actor_id = actor_id


def _make_case_and_embargo(
    case_suffix: str,
    em_state: EM = EM.ACTIVE,
) -> tuple[VulnerabilityCase, EmbargoEvent]:
    case = VulnerabilityCase(
        id_=f"https://example.org/cases/case_{case_suffix}",
        name=f"Test Case {case_suffix}",
    )
    embargo = EmbargoEvent(
        id_=f"https://example.org/cases/case_{case_suffix}/embargo_events/e1",
        context=case.id_,
    )
    case.active_embargo = embargo.id_
    case.current_status.em_state = em_state
    return case, embargo


class TestValidateCaseExistsNode:
    """Tests for ValidateCaseExistsNode."""

    def test_returns_success_when_case_found(self):
        """Node returns SUCCESS when case exists in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = _make_case_and_embargo("vcn1")
        dl.create(case)

        _setup_blackboard(dl)
        node = ValidateCaseExistsNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_case_missing(self):
        """Node returns FAILURE when the case ID is not in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        _setup_blackboard(dl)

        node = ValidateCaseExistsNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE


class TestApplyEmbargoTeardownNode:
    """Tests for ApplyEmbargoTeardownNode."""

    def test_transitions_em_active_to_exited(self):
        """Node transitions EM.ACTIVE → EM.EXITED and saves the case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = _make_case_and_embargo("atn1", em_state=EM.ACTIVE)
        dl.create(case)

        _setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.EXITED
        assert updated.active_embargo is None

    def test_transitions_em_revise_to_exited(self):
        """Node transitions EM.REVISE → EM.EXITED (also a valid terminate path)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = _make_case_and_embargo("atn2", em_state=EM.REVISE)
        dl.create(case)

        _setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.EXITED

    def test_idempotent_when_already_exited(self):
        """Node returns SUCCESS without modifying state when already EXITED."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = _make_case_and_embargo("atn3", em_state=EM.EXITED)
        case.active_embargo = None
        dl.create(case)

        _setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.EXITED

    def test_state_sync_override_for_unexpected_em_state(self, caplog):
        """Node logs WARNING and applies override for non-standard EM state."""
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = _make_case_and_embargo("atn4", em_state=EM.NONE)
        dl.create(case)

        _setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.WARNING):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert any("state-sync override" in r.message for r in caplog.records)
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.EXITED

    def test_resets_participant_embargo_consent(self):
        """Node resets participant PEC state to NO_EMBARGO."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = _make_case_and_embargo("atn5", em_state=EM.ACTIVE)
        participant = CaseParticipant(
            id_=f"{case.id_}/participants/p1",
            attributed_to="https://example.org/users/finder",
        )
        participant.embargo_consent_state = PEC.SIGNATORY.value
        case.case_participants.append(participant.id_)
        dl.create(case)
        dl.create(participant)

        _setup_blackboard(dl)
        node = ApplyEmbargoTeardownNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated_p = cast(CaseParticipant, dl.read(participant.id_))
        assert updated_p.embargo_consent_state == PEC.NO_EMBARGO.value

    def test_returns_success_when_case_missing(self):
        """Node returns SUCCESS when the case ID is not in the DataLayer.

        In the sync context (Announce log entry fan-out), a missing case is
        not an error — the entry may reference a case the participant does not
        know about yet.  The Sequence should not fail in this situation.
        """
        dl = SqliteDataLayer("sqlite:///:memory:")
        _setup_blackboard(dl)

        node = ApplyEmbargoTeardownNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS


class TestIsActiveEmbargoNode:
    """Tests for IsActiveEmbargoNode."""

    def test_returns_success_when_embargo_is_active(self):
        """Node returns SUCCESS when case.active_embargo matches embargo_id."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = _make_case_and_embargo("ian1", em_state=EM.ACTIVE)
        dl.create(case)

        _setup_blackboard(dl)
        node = IsActiveEmbargoNode(case_id=case.id_, embargo_id=embargo.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_embargo_not_active(self):
        """Node returns FAILURE when active_embargo does not match."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = _make_case_and_embargo("ian2", em_state=EM.PROPOSED)
        case.active_embargo = None
        dl.create(case)

        _setup_blackboard(dl)
        node = IsActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=embargo.id_,
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_failure_when_case_missing(self):
        """Node returns FAILURE when the case ID is not in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        _setup_blackboard(dl)

        node = IsActiveEmbargoNode(
            case_id="https://example.org/cases/nonexistent",
            embargo_id="https://example.org/cases/nonexistent/embargo_events/e1",
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE


class TestRemoveFromProposedEmbargoesNode:
    """Tests for RemoveFromProposedEmbargoesNode."""

    def test_removes_embargo_from_proposed_list(self):
        """Node removes embargo_id from proposed_embargoes and returns SUCCESS."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = _make_case_and_embargo("rfp1", em_state=EM.PROPOSED)
        case.proposed_embargoes.append(embargo.id_)
        dl.create(case)

        _setup_blackboard(dl)
        node = RemoveFromProposedEmbargoesNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert embargo.id_ not in [
            e if isinstance(e, str) else getattr(e, "id_", None)
            for e in updated.proposed_embargoes
        ]

    def test_idempotent_when_not_in_proposed(self):
        """Node returns SUCCESS even if embargo_id is not in proposed_embargoes."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = _make_case_and_embargo("rfp2", em_state=EM.ACTIVE)
        # embargo NOT in proposed_embargoes
        dl.create(case)

        _setup_blackboard(dl)
        node = RemoveFromProposedEmbargoesNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_case_missing(self):
        """Node returns FAILURE when the case ID is not in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        _setup_blackboard(dl)

        node = RemoveFromProposedEmbargoesNode(
            case_id="https://example.org/cases/nonexistent",
            embargo_id="https://example.org/cases/nonexistent/embargo_events/e1",
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
