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

import py_trees

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.teardown import (
    ApplyEmbargoTeardownNode,
    RemoveFromProposedEmbargoesNode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.core.models.case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)


class TestApplyEmbargoTeardownNode:
    """Tests for ApplyEmbargoTeardownNode."""

    def test_transitions_em_active_to_exited(self):
        """Node transitions EM.ACTIVE → EM.EXITED and saves the case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
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

    def test_transitions_em_revise_to_exited(self):
        """Node transitions EM.REVISE → EM.EXITED (also a valid terminate path)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
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

    def test_idempotent_when_already_exited(self):
        """Node returns SUCCESS without modifying state when already EXITED."""
        dl = SqliteDataLayer("sqlite:///:memory:")
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
        dl = SqliteDataLayer("sqlite:///:memory:")
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

    def test_resets_participant_embargo_consent(self):
        """Node resets participant PEC state to NO_EMBARGO."""
        dl = SqliteDataLayer("sqlite:///:memory:")
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
        dl = SqliteDataLayer("sqlite:///:memory:")
        setup_blackboard(dl)

        node = ApplyEmbargoTeardownNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS


class TestRemoveFromProposedEmbargoesNode:
    """Tests for RemoveFromProposedEmbargoesNode."""

    def test_removes_embargo_from_proposed_list(self):
        """Node removes embargo_id from proposed_embargoes and returns SUCCESS."""
        dl = SqliteDataLayer("sqlite:///:memory:")
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
        dl = SqliteDataLayer("sqlite:///:memory:")
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
        dl = SqliteDataLayer("sqlite:///:memory:")
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
