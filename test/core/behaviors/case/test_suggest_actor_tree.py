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

"""Tests for the CaseActor-routed suggest-actor BT factories (ADR-0026/CM-16).

Covers:
- create_recommend_actor_to_case_received_tree
- create_accept_actor_recommendation_received_tree
- create_reject_actor_recommendation_received_tree
- EvaluateDefaultRolesNode (AC-1 through AC-4, CM-16-003)

Per specs/behavior-tree-integration.yaml BT-15-001, BTND-02-001 (memory=False),
ADR-0026/CM-16.
"""

import json
import logging
from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from test.support.clock_decisions import clock_decision_node_ids
from test.support.refusal_effects import refusal_effect_node_ids
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
    EvaluateDefaultRolesNode,
)
from vultron.core.behaviors.case.nodes.invite_actor_emit import (
    INVITE_ID_KIND,
)
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    CreateInertInviteeParticipantNode,
    validated_invitee_roles,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.case.nodes.stub_invite_lifetime import (
    ReinviteAwaitingNode,
    ReinviteNotToClosedParticipantNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor import (
    AcceptedInviteeIsNotRemovedNode,
    EmitAcceptRecordedRecommendationNode,
    EmitRecordedInviteNode,
    RecordedOfferAnswer,
    RequireRecordedOfferAnswerNode,
    SeatRecordedInviteeNode,
    SuggestedActorIsInvitableNode,
)
from vultron.core.behaviors.case.suggest_actor_tree import (
    ActorAlreadyParticipantNode,
    EmitAcceptActorRecommendationNode,
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
    EmitRejectActorRecommendationNode,
    InviteInFlightNode,
    PendingOfferCaseParticipantNode,
    create_accept_actor_recommendation_received_tree,
    create_receive_offer_case_participant_tree,
    create_recommend_actor_to_case_received_tree,
    create_reject_actor_recommendation_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderIsCaseManagerNode,
    SenderIsCaseOwnerNode,
    SenderIsParticipantNode,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.protocol_pair import (
    ProtocolPair,
)
from vultron.core.use_cases.received.actor.offer_case_participant import (
    AcceptOfferCaseParticipantReceivedUseCase,
    OfferCaseParticipantReceivedUseCase,
    RejectOfferCaseParticipantReceivedUseCase,
)
from vultron.core.use_cases.received.actor.suggest import (
    OfferActorToCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole

_REC_ID = "https://example.org/recommendations/rec-1"
_RECOMMENDER = "https://example.org/actors/recommender"
_RECOMMENDED = "https://example.org/actors/recommended"
_CASE_ID = "https://example.org/cases/case-1"
_SENDER = "https://example.org/actors/sender"
_OFFER_RULE = OfferCaseParticipantReceivedUseCase.sender_entitlement
_RECOMMEND_RULE = OfferActorToCaseReceivedUseCase.sender_entitlement
_ACCEPT_RULE = AcceptOfferCaseParticipantReceivedUseCase.sender_entitlement
_REJECT_RULE = RejectOfferCaseParticipantReceivedUseCase.sender_entitlement
_MANAGER = "https://example.org/actors/case-manager"


def _invite_id_as_manager(
    node: EmitInviteActorToCaseNode | EmitRecordedInviteNode,
) -> str | None:
    """The id *node* gives its Invite when the CASE_MANAGER runs it."""
    node.actor_id = _MANAGER
    return node._invite_id()


def _derived_invite_id(recommendation_id: str) -> str:
    return derived_activity_id(
        INVITE_ID_KIND, _MANAGER, _CASE_ID, recommendation_id
    )


class TestEvaluateDefaultRolesNode:
    """Unit tests for EvaluateDefaultRolesNode (AC-1, AC-2, AC-3, CM-16-003)."""

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()
        # Inject explicit roles so the default path does not interfere with
        # tests that only check the node's structural properties. Tests that
        # cover the no-roles failure path create their own node without roles.
        self.node = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=_REC_ID,
            injected_roles=["vendor"],
        )
        self.node.setup()
        self.node.initialise()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def test_node_exists(self):
        """AC-1: EvaluateDefaultRolesNode exists in the BT node library."""
        assert self.node is not None

    def test_node_name_defaults_to_class_name(self):
        assert self.node.name == "EvaluateDefaultRolesNode"

    def test_node_stores_suggested_actor_id(self):
        assert self.node.suggested_actor_id == _RECOMMENDED

    def test_node_stores_case_id(self):
        assert self.node.case_id == _CASE_ID

    def test_node_stores_recommendation_id(self):
        """AC-1: EvaluateDefaultRolesNode accepts recommendation_id."""
        assert self.node.recommendation_id == _REC_ID

    def test_returns_success_when_roles_injected(self):
        """Returns SUCCESS when injected roles are provided."""
        result = self.node.update()
        assert result == Status.SUCCESS

    def test_writes_vendor_role_to_namespaced_blackboard_key(self):
        """AC-2: writes suggested_roles_{segment} = [CVDRole.VENDOR] to blackboard."""
        self.node.update()
        expected_key = (
            f"/suggested_roles_{_REC_ID.rsplit('/', maxsplit=1)[-1]}"
        )
        raw = py_trees.blackboard.Blackboard.storage.get(expected_key)
        assert raw == [CVDRole.VENDOR], (
            f"Expected [CVDRole.VENDOR] at '{expected_key}', got {raw!r}"
        )

    def test_does_not_write_global_suggested_roles_key(self):
        """AC-4: raw /suggested_roles key must not be written."""
        self.node.update()
        raw = py_trees.blackboard.Blackboard.storage.get("/suggested_roles")
        assert raw is None, (
            f"Expected no /suggested_roles key, but found {raw!r}"
        )

    def test_custom_name_accepted(self):
        node = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=_REC_ID,
            name="MyCustomName",
        )
        assert node.name == "MyCustomName"

    def test_two_instances_write_different_keys(self):
        """AC-3: two tree instances with different recommendation_ids write to different keys."""
        rec_id_2 = "https://example.org/recommendations/rec-2"
        node2 = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=rec_id_2,
            injected_roles=["vendor"],
        )
        node2.setup()
        node2.initialise()

        self.node.update()
        node2.update()

        key1 = f"/suggested_roles_{_REC_ID.rsplit('/', maxsplit=1)[-1]}"
        key2 = f"/suggested_roles_{rec_id_2.rsplit('/', maxsplit=1)[-1]}"

        assert key1 != key2, (
            "Keys must differ for different recommendation_ids"
        )
        assert py_trees.blackboard.Blackboard.storage.get(key1) == [
            CVDRole.VENDOR
        ]
        assert py_trees.blackboard.Blackboard.storage.get(key2) == [
            CVDRole.VENDOR
        ]

    def test_injected_retired_finder_role_is_dropped(self, caplog):
        """An injected 'finder' is not a role (ADR-0078); only live roles stay.

        The warning carries the retirement reason, not just "unrecognized".
        """
        caplog.set_level(logging.WARNING)
        node = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=_REC_ID,
            injected_roles=["finder", "vendor"],
        )
        node.setup()
        node.initialise()
        node.update()
        key = f"/suggested_roles_{_REC_ID.rsplit('/', maxsplit=1)[-1]}"
        assert py_trees.blackboard.Blackboard.storage.get(key) == [
            CVDRole.VENDOR
        ]
        assert any(
            "ADR-0078" in record.getMessage() for record in caplog.records
        )

    def test_returns_failure_when_compute_roles_returns_empty(self):
        """AC-4: returns FAILURE when _compute_roles() returns empty list (CM-16-003).

        Guards future Evaluator overrides that substitute a custom evaluator
        returning [] — the empty list must be rejected at write time per
        ADR-0032 / BT-HELPER-01, not silently overridden by the consumer.
        """

        class _EmptyRolesNode(EvaluateDefaultRolesNode):
            def _compute_roles(self):
                return []

        node = _EmptyRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=_REC_ID,
        )
        node.setup()
        node.initialise()
        result = node.update()
        assert result == Status.FAILURE
        assert node.feedback_message, "feedback_message must be set on FAILURE"
        # blackboard key must not be written
        expected_key = (
            f"/suggested_roles_{_REC_ID.rsplit('/', maxsplit=1)[-1]}"
        )
        raw = py_trees.blackboard.Blackboard.storage.get(expected_key)
        assert raw is None, (
            f"Blackboard key '{expected_key}' must not be written when "
            f"_compute_roles() returns empty list, got {raw!r}"
        )

    @pytest.mark.spec("CM-16-003")
    def test_defaults_to_vendor_when_no_roles_given(self):
        """CM-16-003: when no injected roles, _compute_roles() returns VENDOR.

        The default _compute_roles() applies the protocol default (VENDOR) so
        the suggest-actor path works without explicit roles from the recommender.
        CM-11-019 (no-roles Invite refused) is enforced downstream by
        CreateInertInviteeParticipantNode, not here.
        """
        node = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=_REC_ID,
        )
        node.setup()
        node.initialise()
        result = node.update()
        assert result == Status.SUCCESS
        # Blackboard key must be written with the VENDOR default
        expected_key = (
            f"/suggested_roles_{_REC_ID.rsplit('/', maxsplit=1)[-1]}"
        )
        raw = py_trees.blackboard.Blackboard.storage.get(expected_key)
        assert raw == [CVDRole.VENDOR], (
            f"Expected VENDOR default at '{expected_key}', got {raw!r}"
        )

    @pytest.mark.spec("CM-11-019")
    def test_require_explicit_roles_fails_when_no_roles_given(self):
        """CM-11-019: require_explicit_roles=True → FAILURE when no roles.

        The owner-direct invite path sets require_explicit_roles=True so the
        Case Owner must supply roles explicitly; no VENDOR default is applied.
        """
        node = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=_REC_ID,
            require_explicit_roles=True,
        )
        node.setup()
        node.initialise()
        result = node.update()
        assert result == Status.FAILURE
        assert node.feedback_message, "feedback_message must be set on FAILURE"
        assert "inviter must give" in node.feedback_message, (
            f"Expected CM-11-019 message, got: {node.feedback_message!r}"
        )
        expected_key = (
            f"/suggested_roles_{_REC_ID.rsplit('/', maxsplit=1)[-1]}"
        )
        raw = py_trees.blackboard.Blackboard.storage.get(expected_key)
        assert raw is None, (
            f"Blackboard key must not be written when FAILURE, got {raw!r}"
        )


class TestRecommendActorToCaseReceivedTree:
    """Structural tests for create_recommend_actor_to_case_received_tree."""

    def setup_method(self):
        self.tree = create_recommend_actor_to_case_received_tree(
            sender_rule=_RECOMMEND_RULE,
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )

    def test_root_is_sequence(self):
        assert isinstance(self.tree, py_trees.composites.Sequence)

    def test_root_name(self):
        assert self.tree.name == "RecommendActorToCaseBT"

    def test_memory_false(self):
        assert self.tree.memory is False, (
            "RecommendActorToCaseBT root Sequence must use memory=False "
            "(BTND-02-001 stateless-ticking invariant)"
        )

    def _flatten_tree_types(self):
        """Collect all node types via depth-first walk."""
        types = []
        for node in self.tree.iterate():
            types.append(type(node))
        return types

    def test_has_evaluate_default_roles_node(self):
        """AC-4 (tree wiring): EvaluateDefaultRolesNode appears in the tree."""
        all_types = self._flatten_tree_types()
        assert EvaluateDefaultRolesNode in all_types, (
            "RecommendActorToCaseBT must contain EvaluateDefaultRolesNode"
        )

    def test_evaluate_roles_node_before_emit_node(self):
        """EvaluateDefaultRolesNode must precede EmitOfferCaseParticipantToOwnerNode."""
        nodes = list(self.tree.iterate())
        types = [type(n) for n in nodes]
        eval_idx = next(
            (i for i, t in enumerate(types) if t is EvaluateDefaultRolesNode),
            None,
        )
        emit_idx = next(
            (
                i
                for i, t in enumerate(types)
                if t is EmitOfferCaseParticipantToOwnerNode
            ),
            None,
        )
        assert eval_idx is not None, "EvaluateDefaultRolesNode not found"
        assert emit_idx is not None, (
            "EmitOfferCaseParticipantToOwnerNode not found"
        )
        assert eval_idx < emit_idx, (
            "EvaluateDefaultRolesNode must appear before "
            "EmitOfferCaseParticipantToOwnerNode in tree ordering"
        )

    def test_evaluate_node_carries_recommended_id(self):
        nodes = [
            n
            for n in self.tree.iterate()
            if isinstance(n, EvaluateDefaultRolesNode)
        ]
        assert nodes, "Expected EvaluateDefaultRolesNode in tree"
        node = nodes[0]
        assert node.suggested_actor_id == _RECOMMENDED
        assert node.case_id == _CASE_ID

    def test_has_emit_offer_case_participant_node(self):
        """Effect nodes must include EmitOfferCaseParticipantToOwnerNode."""
        all_types = self._flatten_tree_types()
        assert EmitOfferCaseParticipantToOwnerNode in all_types, (
            "RecommendActorToCaseBT must contain EmitOfferCaseParticipantToOwnerNode"
        )

    def test_emit_node_carries_recommendation_id(self):
        """The emit node must carry the original recommendation ID as origin."""
        emit_nodes = [
            n
            for n in self.tree.iterate()
            if isinstance(n, EmitOfferCaseParticipantToOwnerNode)
        ]
        assert emit_nodes, (
            "Expected EmitOfferCaseParticipantToOwnerNode in tree"
        )
        node = emit_nodes[0]
        assert node.recommendation_id == _REC_ID
        assert node.recommender_id == _RECOMMENDER
        assert node.recommended_id == _RECOMMENDED
        assert node.case_id == _CASE_ID


class TestEmitOfferCaseParticipantToOwnerNodeEmptyRoles:
    """Unit tests for the empty-roles guard in EmitOfferCaseParticipantToOwnerNode."""

    def _node(self):
        dl = MagicMock()
        factory = MagicMock()
        node = EmitOfferCaseParticipantToOwnerNode(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        # Wire datalayer and actor_id via the standard helper.
        writer = py_trees.blackboard.Client(name="test-emit-setup-writer")
        writer.register_key(
            key="datalayer", access=py_trees.common.Access.WRITE
        )
        writer.register_key(
            key="actor_id", access=py_trees.common.Access.WRITE
        )
        writer.register_key(
            key="trigger_activity_factory",
            access=py_trees.common.Access.WRITE,
        )
        writer.datalayer = dl
        writer.actor_id = _ACTOR_ID
        writer.trigger_activity_factory = factory
        node.setup()
        # Simulate a pathological writer that bypasses EvaluateDefaultRolesNode's
        # non-empty invariant by writing [] to the namespaced blackboard key.
        # Must be written before initialise() so the ports cache sees the value.
        id_segment = _REC_ID.rsplit("/", maxsplit=1)[-1]
        py_trees.blackboard.Blackboard.storage[
            f"/suggested_roles_{id_segment}"
        ] = []
        node.initialise()
        return node, factory

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def test_returns_failure_when_roles_empty(self):
        """update() must return FAILURE when suggested_roles is [] (CM-16-003)."""
        node, _ = self._node()
        result = node.update()
        assert result == Status.FAILURE
        assert node.feedback_message, "feedback_message must be set on FAILURE"

    def test_factory_not_called_when_roles_empty(self):
        """factory.offer_actor_to_case must not be called with empty roles."""
        node, factory = self._node()
        node.update()
        factory.offer_actor_to_case.assert_not_called()


class TestEmitInviteActorToCaseNodeEmptyRoles:
    """Unit tests for the empty-roles guard in EmitInviteActorToCaseNode (CM-17-003)."""

    _CASE_ID_INVITE = "https://example.org/cases/case-invite-1"
    _INVITEE_ID = "https://example.org/actors/invitee"
    _RECOMMENDATION_ID = "https://example.org/activities/offer-invite-1"

    def _node(self):
        dl = MagicMock()
        factory = MagicMock()
        node = EmitInviteActorToCaseNode(
            invitee_id=self._INVITEE_ID,
            case_id=self._CASE_ID_INVITE,
            recommendation_id=self._RECOMMENDATION_ID,
        )
        writer = py_trees.blackboard.Client(
            name="test-invite-empty-roles-writer"
        )
        writer.register_key(
            key="datalayer", access=py_trees.common.Access.WRITE
        )
        writer.register_key(
            key="actor_id", access=py_trees.common.Access.WRITE
        )
        writer.register_key(
            key="trigger_activity_factory",
            access=py_trees.common.Access.WRITE,
        )
        writer.datalayer = dl
        writer.actor_id = _ACTOR_ID
        writer.trigger_activity_factory = factory
        node.setup()
        # An empty list where EvaluateDefaultRolesNode writes the roles for
        # this recommendation. Must be written before initialise() so the
        # ports cache sees the value.
        py_trees.blackboard.Blackboard.storage[
            "/suggested_roles_offer-invite-1"
        ] = []
        node.initialise()
        return node, factory

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def test_returns_failure_when_roles_empty(self):
        """update() must return FAILURE when suggested_roles is [] (CM-17-003)."""
        node, _ = self._node()
        result = node.update()
        assert result == Status.FAILURE
        assert node.feedback_message, "feedback_message must be set on FAILURE"

    def test_factory_not_called_when_roles_empty(self):
        """factory.invite_actor_to_case must not be called with empty roles."""
        node, factory = self._node()
        node.update()
        factory.invite_actor_to_case.assert_not_called()


#: The id of the Case Owner's answer the trees under test are built for.
_ANSWER_ID = "https://example.org/activities/owner-answer-1"

#: What the recorded-Offer guard publishes for the answer under test.
_RECORDED = RecordedOfferAnswer(
    recommendation_id=_REC_ID,
    recommender_id=_RECOMMENDER,
    invitee_id=_RECOMMENDED,
    roles=("vendor",),
)


def _as_published(node):
    """*node*, reading :data:`_RECORDED` as if the guard had published it."""
    node._recorded = _RECORDED
    return node


class TestAcceptActorRecommendationReceivedTree:
    """Structural tests for create_accept_actor_recommendation_received_tree."""

    def setup_method(self):
        self.tree = create_accept_actor_recommendation_received_tree(
            answer_id=_ANSWER_ID,
            case_id=_CASE_ID,
            sender_id=_SENDER,
            sender_rule=_ACCEPT_RULE,
        )

    def test_root_is_sequence(self):
        assert isinstance(self.tree, py_trees.composites.Sequence)

    def test_root_name(self):
        assert self.tree.name == "AcceptActorRecommendationBT"

    def test_memory_false(self):
        assert self.tree.memory is False, (
            "AcceptActorRecommendationBT root Sequence must use memory=False"
        )

    @pytest.mark.spec("CM-16-019")
    def test_the_accept_recommendation_node_answers_the_recorded_offer(self):
        nodes = [
            c
            for c in self.tree.iterate()
            if isinstance(c, EmitAcceptRecordedRecommendationNode)
        ]
        assert nodes, "Expected EmitAcceptRecordedRecommendationNode in tree"
        node = _as_published(nodes[0])
        assert node._subject() == (_RECOMMENDER, _REC_ID, _RECOMMENDED)
        assert node.case_id == _CASE_ID

    @pytest.mark.spec("CM-16-019")
    def test_the_invite_goes_to_the_recorded_invitee(self):
        nodes = [
            c
            for c in self.tree.iterate()
            if isinstance(c, EmitRecordedInviteNode)
        ]
        assert nodes, (
            "Expected EmitRecordedInviteNode in tree (CM-16-006 step 4)"
        )
        node = _as_published(nodes[0])
        assert node._invitee() == _RECOMMENDED
        assert node._read_suggested_roles() == ["vendor"]
        assert node.case_id == _CASE_ID

    @pytest.mark.spec("OX-06-002")
    def test_the_invite_id_derives_from_the_accepted_recommendation(self):
        """A retry of this tree for one recommendation rebuilds one Invite."""
        node = _as_published(
            next(
                c
                for c in self.tree.iterate()
                if isinstance(c, EmitRecordedInviteNode)
            )
        )
        assert _invite_id_as_manager(node) == _derived_invite_id(_REC_ID)

    @pytest.mark.spec("CM-11-015")
    @pytest.mark.spec("CM-16-006")
    @pytest.mark.spec("CLP-10-010")
    def test_the_guards_run_before_the_commit_and_either_emit(self):
        """The recorded-Offer lookup, then the closed/joined refusal, then the rest."""
        order = list(self.tree.iterate())
        lookup = next(
            i
            for i, n in enumerate(order)
            if isinstance(n, RequireRecordedOfferAnswerNode)
        )
        guard = next(
            i
            for i, n in enumerate(order)
            if isinstance(n, SuggestedActorIsInvitableNode)
        )
        later = [
            i
            for i, n in enumerate(order)
            if isinstance(
                n,
                (
                    CommitCaseLedgerEntryNode,
                    EmitAcceptRecordedRecommendationNode,
                    EmitRecordedInviteNode,
                ),
            )
        ]
        assert later, "the tree has a commit and both emits"
        assert lookup < guard
        assert all(guard < i for i in later), (
            "the closed/joined refusal must precede the receipt commit and"
            " both emits (CM-11-015, CM-16-006)"
        )


@pytest.mark.parametrize(
    "node_class",
    [
        AcceptedInviteeIsNotRemovedNode,
        EmitAcceptRecordedRecommendationNode,
        EmitRecordedInviteNode,
        EmitRejectActorRecommendationNode,
        SeatRecordedInviteeNode,
        SuggestedActorIsInvitableNode,
    ],
)
def test_an_answer_node_without_the_published_offer_is_an_internal_error(
    node_class,
):
    """A tree that omits the lookup guard is a composition error, not a refusal.

    Every node that reads the published answer checks for it before its own
    work, so the bridge reports an internal error (#2255).  The store holds
    no case, so a node that ran its case read first would report an ordinary
    refusal instead and fail this test.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
    try:
        result = BTBridge(
            datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
        ).execute_with_setup(
            node_class(answer_id=_ANSWER_ID, case_id=_CASE_ID),
            actor_id=_MANAGER,
        )
    finally:
        dl.close()
    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "must run first" in result.feedback_message


@pytest.mark.spec("CM-11-019")
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ((), []),
        (None, []),
        (("vendor",), [CVDRole.VENDOR]),
        ([CVDRole.COORDINATOR], [CVDRole.COORDINATOR]),
        (("no-such-role",), []),
    ],
)
def test_validated_invitee_roles_never_defaults(raw, expected):
    """No valid role seats nothing: there is no VENDOR default (CM-11-019)."""
    assert validated_invitee_roles(raw) == expected


class TestRejectActorRecommendationReceivedTree:
    """Structural tests for create_reject_actor_recommendation_received_tree."""

    def setup_method(self):
        self.tree = create_reject_actor_recommendation_received_tree(
            answer_id=_ANSWER_ID,
            case_id=_CASE_ID,
            sender_id=_SENDER,
            sender_rule=_REJECT_RULE,
        )

    def test_root_is_sequence(self):
        assert isinstance(self.tree, py_trees.composites.Sequence)

    def test_root_name(self):
        assert self.tree.name == "RejectActorRecommendationBT"

    def test_memory_false(self):
        assert self.tree.memory is False, (
            "RejectActorRecommendationBT root Sequence must use memory=False"
        )

    @pytest.mark.spec("CM-16-019")
    def test_the_reject_recommendation_node_answers_the_recorded_offer(self):
        nodes = [
            c
            for c in self.tree.iterate()
            if isinstance(c, EmitRejectActorRecommendationNode)
        ]
        assert nodes, "Expected EmitRejectActorRecommendationNode in tree"
        node = _as_published(nodes[0])
        assert node._subject() == (_RECOMMENDER, _REC_ID, _RECOMMENDED)
        assert node.case_id == _CASE_ID

    @pytest.mark.spec("CLP-10-010")
    def test_the_recorded_offer_lookup_precedes_the_commit_and_the_emit(self):
        order = list(self.tree.iterate())
        lookup = next(
            i
            for i, n in enumerate(order)
            if isinstance(n, RequireRecordedOfferAnswerNode)
        )
        later = [
            i
            for i, n in enumerate(order)
            if isinstance(
                n,
                (CommitCaseLedgerEntryNode, EmitRejectActorRecommendationNode),
            )
        ]
        assert later, "the tree has a commit and the emit"
        assert all(lookup < i for i in later)


# ---------------------------------------------------------------------------
# Duplicate-detection precondition node tests (CM-16-008, CM-16-009)
# ---------------------------------------------------------------------------


_ACTOR_ID = "https://example.org/actors/case-actor"


def _make_node_with_datalayer(node, dl, actor_id=_ACTOR_ID):
    """Wire a datalayer mock onto a DataLayerAction node via the blackboard."""
    # Populate the blackboard storage so initialise() can read datalayer/actor_id.
    writer = py_trees.blackboard.Client(name="test-setup-writer")
    writer.register_key(key="datalayer", access=py_trees.common.Access.WRITE)
    writer.register_key(key="actor_id", access=py_trees.common.Access.WRITE)
    writer.datalayer = dl
    writer.actor_id = actor_id
    node.setup()
    node.initialise()
    return node


class TestActorAlreadyParticipantNode:
    """Unit tests for ActorAlreadyParticipantNode (AC-7b, CM-16-009)."""

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def _node(self, participant_index=None):
        dl = MagicMock()
        case_obj = MagicMock()
        object.__setattr__(
            case_obj, "actor_participant_index", participant_index or {}
        )
        dl.read_case.return_value = case_obj
        node = ActorAlreadyParticipantNode(
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        return _make_node_with_datalayer(node, dl)

    def test_returns_success_when_actor_in_index(self):
        node = self._node(
            participant_index={
                _RECOMMENDED: "https://example.org/participants/p1"
            }
        )
        assert node.update() == Status.SUCCESS

    def test_returns_failure_when_actor_not_in_index(self):
        node = self._node(participant_index={})
        assert node.update() == Status.FAILURE

    def test_returns_failure_when_datalayer_not_available(self):
        node = ActorAlreadyParticipantNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID
        )
        # node.datalayer is None by default — no setup/initialise needed
        assert node.update() == Status.FAILURE

    def test_name_defaults_to_class_name(self):
        node = ActorAlreadyParticipantNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID
        )
        assert node.name == "ActorAlreadyParticipantNode"

    def test_custom_name_accepted(self):
        node = ActorAlreadyParticipantNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID, name="MyName"
        )
        assert node.name == "MyName"


_ZERO_HASH = "0" * 64
_INVITE_SNAPSHOT = {"type": "Invite", "object": {"id": _RECOMMENDED}}
_OFFER_SNAPSHOT = {
    "type": "Offer",
    "object": {"type": "CaseParticipant", "attributedTo": _RECOMMENDED},
}


def _ledger(*rows: tuple[str, dict]) -> SqliteDataLayer:
    """A store whose ledger holds *rows* of (semantic_type, snapshot), in order.

    Each entry is keyed by its own activity id, as the CASE_MANAGER commits a
    request it sends (ADR-0119), never by the actor the request concerns.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR_ID)
    prev = _ZERO_HASH
    for index, (semantic_type, snapshot) in enumerate(rows):
        entry = _to_persistable_entry(
            HashChainLedgerRecord(
                case_id=_CASE_ID,
                log_index=index,
                object_id=f"https://example.org/activities/a-{index}",
                semantic_type=semantic_type,
                payload_snapshot=snapshot,
                prev_log_hash=prev,
            )
        )
        dl.save(entry)
        prev = entry.entry_hash
    return dl


def _answer(request_index: int, link: str = "object") -> dict:
    """A reply snapshot answering the request at *request_index* via *link*."""
    return {
        "type": "Accept",
        link: f"https://example.org/activities/a-{request_index}",
    }


_LOOKUPS = [
    pytest.param(
        InviteInFlightNode,
        "invite_actor_to_case",
        _INVITE_SNAPSHOT,
        "accept_invite_actor_to_case",
        id="invite-in-flight",
    ),
    pytest.param(
        PendingOfferCaseParticipantNode,
        "offer_case_participant",
        _OFFER_SNAPSHOT,
        "accept_offer_case_participant",
        id="pending-offer",
    ),
]


@pytest.mark.parametrize(
    ("node_type", "request_type", "snapshot", "reply"), _LOOKUPS
)
class TestPendingRequestLookup:
    """InviteInFlightNode (AC-7a, CM-16-009) and PendingOfferCaseParticipantNode
    (AC-6, CM-16-008) find the request by the actor its snapshot names (#4903).
    """

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def _run(self, node_type, dl) -> Status:
        node = node_type(recommended_id=_RECOMMENDED, case_id=_CASE_ID)
        _make_node_with_datalayer(node, dl)
        status = cast(Status, node.update())
        dl.close()
        return status

    @pytest.mark.spec("CM-16-008", "CM-16-009")
    def test_success_when_a_request_for_the_actor_is_unanswered(
        self, node_type, request_type, snapshot, reply
    ):
        assert self._run(node_type, _ledger((request_type, snapshot))) == (
            Status.SUCCESS
        )

    def test_failure_when_no_request_was_sent(
        self, node_type, request_type, snapshot, reply
    ):
        assert self._run(node_type, _ledger()) == Status.FAILURE

    def test_failure_when_the_request_names_another_actor(
        self, node_type, request_type, snapshot, reply
    ):
        other = json.loads(
            json.dumps(snapshot).replace(_RECOMMENDED, _RECOMMENDER)
        )
        assert self._run(node_type, _ledger((request_type, other))) == (
            Status.FAILURE
        )

    @pytest.mark.parametrize("link", ["object", "inReplyTo"])
    def test_failure_when_the_request_was_answered(
        self, node_type, request_type, snapshot, reply, link
    ):
        dl = _ledger((request_type, snapshot), (reply, _answer(0, link)))
        assert self._run(node_type, dl) == Status.FAILURE

    def test_success_when_a_later_request_is_unanswered(
        self, node_type, request_type, snapshot, reply
    ):
        dl = _ledger(
            (request_type, snapshot),
            (reply, _answer(0)),
            (request_type, snapshot),
        )
        assert self._run(node_type, dl) == Status.SUCCESS

    def test_success_when_only_another_actors_request_was_answered(
        self, node_type, request_type, snapshot, reply
    ):
        other = json.loads(
            json.dumps(snapshot).replace(_RECOMMENDED, _RECOMMENDER)
        )
        dl = _ledger(
            (request_type, snapshot),
            (request_type, other),
            (reply, _answer(1)),
        )
        assert self._run(node_type, dl) == Status.SUCCESS

    def test_failure_when_datalayer_not_available(
        self, node_type, request_type, snapshot, reply
    ):
        node = node_type(recommended_id=_RECOMMENDED, case_id=_CASE_ID)
        assert node.update() == Status.FAILURE


class TestDuplicateDetectionTreeStructure:
    """Structural tests for duplicate-detection arms in create_recommend_actor_to_case_received_tree.

    CM-16-008, CM-16-009, ADR-0026 Duplicate Recommendation Handling table.
    """

    def setup_method(self):
        self.tree = create_recommend_actor_to_case_received_tree(
            sender_rule=_RECOMMEND_RULE,
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        self.all_nodes = list(self.tree.iterate())
        self.all_types = [type(n) for n in self.all_nodes]

    def test_has_actor_already_participant_node(self):
        assert ActorAlreadyParticipantNode in self.all_types

    def test_has_invite_in_flight_node(self):
        assert InviteInFlightNode in self.all_types

    def test_has_pending_offer_case_participant_node(self):
        assert PendingOfferCaseParticipantNode in self.all_types

    def test_has_emit_note_duplicate_node(self):
        assert EmitNoteDuplicateRecommendationToOwnerNode in self.all_types

    def test_has_emit_accept_actor_recommendation_node(self):
        assert EmitAcceptActorRecommendationNode in self.all_types

    def _duplicate_selector(self):
        """Find the DuplicateOrFreshSelector by name."""
        return next(
            n
            for n in self.all_nodes
            if isinstance(n, py_trees.composites.Selector)
            and n.name == "DuplicateOrFreshSelector"
        )

    def test_has_selector_for_duplicate_or_fresh(self):
        assert self._duplicate_selector() is not None, (
            "DuplicateOrFreshSelector must exist in the tree"
        )

    def test_selector_has_six_children(self):
        assert len(self._duplicate_selector().children) == 6

    @pytest.mark.spec("OX-06-002")
    def test_every_invite_id_derives_from_the_offer_it_answers(self):
        """Owner-direct and re-invite Invites alike take the Offer's id."""
        invites = [
            n
            for n in self.all_nodes
            if isinstance(n, EmitInviteActorToCaseNode)
        ]
        assert len(invites) >= 2, (
            "expected the reinvite and owner-direct emits"
        )
        assert {_invite_id_as_manager(n) for n in invites} == {
            _derived_invite_id(_REC_ID)
        }

    @pytest.mark.spec("OX-06-002")
    @pytest.mark.spec("CM-11-015")
    def test_a_reinvite_from_a_new_offer_is_a_fresh_invite(self):
        """A re-invite answers a new Offer, so its Invite gets a new id."""
        later = create_recommend_actor_to_case_received_tree(
            sender_rule=_RECOMMEND_RULE,
            recommendation_id=f"{_REC_ID}-later",
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        reinvite = next(
            n
            for n in later.iterate()
            if isinstance(n, py_trees.composites.Sequence)
            and n.name == "OwnerReinvite"
        )
        node = next(
            c
            for c in reinvite.children
            if isinstance(c, EmitInviteActorToCaseNode)
        )
        assert _invite_id_as_manager(node) == _derived_invite_id(
            f"{_REC_ID}-later"
        )
        assert _invite_id_as_manager(node) != _derived_invite_id(_REC_ID)

    @pytest.mark.spec("CM-11-015")
    def test_reinvite_arm_is_first_and_emits_without_creating_a_record(self):
        """Re-invite arm: owner, unanswered record, roles, Invite — and no new record."""
        reinvite = self._duplicate_selector().children[0]
        assert isinstance(reinvite, py_trees.composites.Sequence)
        assert reinvite.name == "OwnerReinvite"
        assert [type(c) for c in reinvite.children] == [
            SenderIsCaseOwnerNode,
            ReinviteAwaitingNode,
            EvaluateDefaultRolesNode,
            EmitInviteActorToCaseNode,
        ]

    @pytest.mark.spec("CM-11-015")
    def test_closed_participant_guard_runs_before_the_recommender_is_recorded(
        self,
    ):
        guard = next(
            n
            for n in self.all_nodes
            if n.name == "ReinviteIsNotToClosedParticipant"
        )
        assert any(
            isinstance(c, ReinviteNotToClosedParticipantNode)
            for c in guard.children
        )
        order = [n.name for n in self.all_nodes]
        assert order.index("ReinviteIsNotToClosedParticipant") < order.index(
            "RecordRecommendationRecommenderNode"
        )

    def test_ac7b_sequence_structure(self):
        """AC-7b arm: Sequence(ActorAlreadyParticipantNode, EmitAcceptActorRecommendationNode)."""
        ac7b = self._duplicate_selector().children[1]
        assert isinstance(ac7b, py_trees.composites.Sequence)
        child_types = [type(c) for c in ac7b.children]
        assert ActorAlreadyParticipantNode in child_types
        assert EmitAcceptActorRecommendationNode in child_types

    def test_ac7a_sequence_structure(self):
        """AC-7a arm: Sequence(InviteInFlightNode, EmitAcceptActorRecommendationNode)."""
        ac7a = self._duplicate_selector().children[2]
        assert isinstance(ac7a, py_trees.composites.Sequence)
        child_types = [type(c) for c in ac7a.children]
        assert InviteInFlightNode in child_types
        assert EmitAcceptActorRecommendationNode in child_types

    def test_ac6_sequence_structure(self):
        """AC-6 arm: Sequence(PendingOfferCaseParticipantNode, EmitNoteDuplicateRecommendationToOwnerNode)."""
        ac6 = self._duplicate_selector().children[3]
        assert isinstance(ac6, py_trees.composites.Sequence)
        child_types = [type(c) for c in ac6.children]
        assert PendingOfferCaseParticipantNode in child_types
        assert EmitNoteDuplicateRecommendationToOwnerNode in child_types

    @pytest.mark.spec("CM-17-007")
    def test_owner_direct_invite_structure(self):
        """CASE_OWNER arm: owner check, roles, Invite, inert participant.

        No ``Add(CaseParticipant)`` follows the inert record: that message
        means reinstatement only (CM-31-011, CM-31-012).
        """
        owner = self._duplicate_selector().children[4]
        assert isinstance(owner, py_trees.composites.Sequence)
        assert owner.name == "OwnerDirectInvite"
        assert [type(c) for c in owner.children] == [
            SenderIsCaseOwnerNode,
            EvaluateDefaultRolesNode,
            EmitInviteActorToCaseNode,
            CreateInertInviteeParticipantNode,
        ]
        check = owner.children[0]
        assert isinstance(check, SenderIsCaseOwnerNode)
        assert check._sender_actor_id == _RECOMMENDER
        emit = owner.children[2]
        assert isinstance(emit, EmitInviteActorToCaseNode)
        assert emit.invitee_id == _RECOMMENDED
        assert emit.attributed_to == _RECOMMENDER

    def test_fresh_path_structure(self):
        """Fresh path arm: not the owner, then roles, then the Offer to the owner."""
        fresh = self._duplicate_selector().children[5]
        assert isinstance(fresh, py_trees.composites.Sequence)
        child_types = [type(c) for c in fresh.children]
        guard = fresh.children[0]
        assert isinstance(guard, py_trees.decorators.Inverter)
        assert isinstance(guard.decorated, SenderIsCaseOwnerNode)
        assert EvaluateDefaultRolesNode in child_types
        assert EmitOfferCaseParticipantToOwnerNode in child_types

    def test_selector_memory_false(self):
        assert self._duplicate_selector().memory is False


class TestProtocolPairIsPending:
    """Unit tests for ProtocolPair.is_pending() (added for AC-6/AC-7)."""

    def test_is_pending_true_when_request_found_and_no_reply(self):
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_semantic_type="offer_case_participant",
            object_id=_RECOMMENDED,
            request_found=True,
        )
        assert pair.is_pending() is True

    def test_is_pending_false_when_request_not_found(self):
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_semantic_type="offer_case_participant",
            object_id=_RECOMMENDED,
            request_found=False,
        )
        assert pair.is_pending() is False

    def test_is_pending_false_when_reply_found(self):
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_semantic_type="offer_case_participant",
            object_id=_RECOMMENDED,
            request_found=True,
            reply_object_id="https://example.org/activities/reply",
            reply_semantic_type="accept_offer_case_participant",
        )
        assert pair.is_pending() is False

    def test_is_open_still_true_for_fresh_pair(self):
        """is_open() returns True for fresh pair (no request found). is_pending() should not."""
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_semantic_type="offer_case_participant",
            object_id=_RECOMMENDED,
            request_found=False,
        )
        assert pair.is_open() is True
        assert pair.is_pending() is False

    def test_request_found_defaults_to_false(self):
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_semantic_type="offer_case_participant",
            object_id=_RECOMMENDED,
        )
        assert pair.request_found is False


class TestEmitNoteDuplicateRecommendationToOwnerNodeContent:
    """Unit tests for the note text, offer_content forwarding (CM-16-016).

    The text is the node's ``_compose()``; committing and announcing the
    note is covered against a real store in
    ``nodes/test_suggest_actor_owner_recipient.py`` (#4829).
    """

    _OWNER_ID = "https://example.org/actors/owner"

    def _content(self, offer_content=None) -> str:
        node = EmitNoteDuplicateRecommendationToOwnerNode(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
            offer_content=offer_content,
        )
        # Resolved by ``update()`` before it composes the note.
        node._owner_id = self._OWNER_ID
        note = node._compose()
        assert note.in_reply_to == _REC_ID
        return note.content

    @pytest.mark.spec("CM-16-016")
    def test_note_names_the_owner_and_the_second_recommender(self):
        content = self._content()
        assert self._OWNER_ID in content
        assert _RECOMMENDER in content

    def test_note_body_excludes_content_when_absent(self):
        """Note body must not contain 'Recommender note:' when offer_content is None."""
        assert "Recommender note:" not in self._content(offer_content=None)

    @pytest.mark.spec("CM-16-016")
    def test_note_body_includes_offer_content(self):
        """CM-16-016: Note body must include offer_content when provided."""
        offer_text = "Please add this vendor urgently."
        content = self._content(offer_content=offer_text)
        assert "Recommender note:" in content
        assert offer_text in content

    def test_offer_content_stored_on_node(self):
        """offer_content is stored as an attribute for introspection."""
        node = EmitNoteDuplicateRecommendationToOwnerNode(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
            offer_content="Some notes.",
        )
        assert node.offer_content == "Some notes."

    def test_offer_content_none_by_default(self):
        """offer_content defaults to None (backward-compatible constructor)."""
        node = EmitNoteDuplicateRecommendationToOwnerNode(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        assert node.offer_content is None

    def test_whitespace_only_offer_content_normalized_to_none(self):
        """Whitespace-only offer_content is normalized to None at construction."""
        node = EmitNoteDuplicateRecommendationToOwnerNode(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
            offer_content="   ",
        )
        assert node.offer_content is None

    def test_note_body_excludes_content_for_whitespace_only_input(self):
        """Note body must not contain 'Recommender note:' for whitespace-only offer_content."""
        assert "Recommender note:" not in self._content(offer_content="   ")


# ---------------------------------------------------------------------------
# #3752: every effect sits behind the CASE_MANAGER role gate (BT-17-001)
# ---------------------------------------------------------------------------


def _descendants(node: py_trees.behaviour.Behaviour) -> set[int]:
    return {id(n) for n in node.iterate()} - {id(node)}


def _gate(tree: py_trees.behaviour.Behaviour, name: str):
    gates = [
        n
        for n in tree.iterate()
        if isinstance(n, py_trees.composites.Selector) and n.name == name
    ]
    assert len(gates) == 1, f"expected exactly one gate named {name!r}"
    return gates[0]


def _effect_nodes(tree: py_trees.behaviour.Behaviour) -> list:
    """Leaves that write or emit: everything after the receipt commit.

    The CASE_MANAGER's clock decisions sit in their own gated stage before
    the guards and are not effects of the received activity (CLP-10-025),
    nor is the refusal notice, which answers only a refusal (CLP-10-022).
    """
    decisions = clock_decision_node_ids(tree) | refusal_effect_node_ids(tree)
    return [
        n
        for n in tree.iterate()
        if (
            type(n).__name__.startswith("Emit")
            or type(n).__name__.startswith("Record")
        )
        and id(n) not in decisions
    ]


@pytest.mark.spec("BT-17-001")
@pytest.mark.parametrize(
    ("factory", "kwargs", "gate_name"),
    [
        (
            create_recommend_actor_to_case_received_tree,
            dict(
                recommendation_id=_REC_ID,
                recommender_id=_RECOMMENDER,
                recommended_id=_RECOMMENDED,
                case_id=_CASE_ID,
                sender_rule=_RECOMMEND_RULE,
            ),
            "RecommendActorToCaseIfCaseManager",
        ),
        (
            create_accept_actor_recommendation_received_tree,
            dict(
                answer_id=_ANSWER_ID,
                case_id=_CASE_ID,
                sender_id=_SENDER,
                sender_rule=_ACCEPT_RULE,
            ),
            "AcceptActorRecommendationIfCaseManager",
        ),
        (
            create_reject_actor_recommendation_received_tree,
            dict(
                answer_id=_ANSWER_ID,
                case_id=_CASE_ID,
                sender_id=_SENDER,
                sender_rule=_REJECT_RULE,
            ),
            "RejectActorRecommendationIfCaseManager",
        ),
    ],
    ids=["recommend", "accept", "reject"],
)
def test_every_effect_is_inside_the_case_manager_gate(
    factory, kwargs, gate_name
):
    """No emit or index write is reachable without passing the role gate.

    The gate is the sanctioned composite (BTND-07-005) and sits after the
    receipt commit (CLP-10-006), so a receiver that is not the CASE_MANAGER
    skips every effect (#3752).
    """
    from vultron.core.behaviors.case.nodes.conditions import (
        CheckIsCaseManagerNode,
    )

    tree = factory(**kwargs)
    gate = _gate(tree, gate_name)
    inside = _descendants(gate)

    effects = _effect_nodes(tree)
    assert effects, "the tree must have effect nodes to gate"
    outside = [type(n).__name__ for n in effects if id(n) not in inside]
    assert outside == [], f"effect nodes outside the gate: {outside}"

    # The gate follows the receipt commit: commit first, effects second.
    children = list(tree.children)
    commit_index = next(
        i
        for i, c in enumerate(children)
        if c.name == "GuardedCommitCaseLedgerEntryBT"
    )
    assert children.index(gate) > commit_index
    # And it is the role check that guards it.
    assert any(isinstance(n, CheckIsCaseManagerNode) for n in gate.iterate())


@pytest.mark.spec("HP-01-006")
@pytest.mark.parametrize(
    ("factory", "kwargs", "guard_type"),
    [
        (
            create_recommend_actor_to_case_received_tree,
            dict(
                recommendation_id=_REC_ID,
                recommender_id=_RECOMMENDER,
                recommended_id=_RECOMMENDED,
                case_id=_CASE_ID,
                sender_rule=_RECOMMEND_RULE,
            ),
            SenderIsParticipantNode,
        ),
        (
            create_receive_offer_case_participant_tree,
            dict(case_id=_CASE_ID, sender_id=_SENDER, sender_rule=_OFFER_RULE),
            SenderIsCaseManagerNode,
        ),
        (
            create_accept_actor_recommendation_received_tree,
            dict(
                answer_id=_ANSWER_ID,
                case_id=_CASE_ID,
                sender_id=_SENDER,
                sender_rule=_ACCEPT_RULE,
            ),
            SenderIsCaseOwnerNode,
        ),
        (
            create_reject_actor_recommendation_received_tree,
            dict(
                answer_id=_ANSWER_ID,
                case_id=_CASE_ID,
                sender_id=_SENDER,
                sender_rule=_REJECT_RULE,
            ),
            SenderIsCaseOwnerNode,
        ),
    ],
    ids=["recommend", "offer", "accept", "reject"],
)
def test_sender_guard_follows_intake_and_precedes_the_commit(
    factory, kwargs, guard_type
):
    """The sender guard sits between intake and the receipt commit.

    A refused sender therefore writes and sends nothing (ADR-0115).
    """
    children = list(factory(**kwargs).children)
    names = [c.name for c in children]
    # The check may sit inside a child: a rule whose two sides differ composes
    # a SenderRuleGuard holding the side checks (HP-01-008), and a CASE_OWNER
    # guard puts the closure check ahead of the role check (CM-23-018).
    guard_index = next(
        i
        for i, c in enumerate(children)
        if any(isinstance(n, guard_type) for n in c.iterate())
    )
    commit_index = names.index("GuardedCommitCaseLedgerEntryBT")
    assert guard_index == 3, (
        "the sender guard must come right after intake, the post-close"
        " guard (CM-23-013) and the addressee door (HP-01-005)"
    )
    assert guard_index < commit_index
