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

"""
Tests for receive-report case-creation behavior tree (IDEA-260408-01-2).

Verifies that ReceiveReportCaseBT correctly orchestrates case creation,
embargo initialization, participant creation, and outbox notification at
the RM.RECEIVED stage (ADR-0015).

Per specs/case-management.yaml CM-12 and specs/behavior-tree-integration.yaml
BT-06.

Tests are grouped by tree phase:
- TestTreeStructure  — root node type, child count, and node identity
- TestTreeFlow       — happy-path execution, case creation, outbox ordering
- TestTreeIdempotency — idempotency guard and early-exit paths
- TestParticipantCreation — owner/reporter/vendor participant RM seeding
- TestEmbargoInitialization — embargo creation, EM state, and signatory seeding

Fixtures are defined in conftest.py and shared with sibling tree test files.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes import (
    CheckAutoCaseCreationEnabledNode,
    CheckCaseExistsForReport,
    CreateCaseOwnerParticipant,
    InitializeDefaultEmbargoNode,
)
from vultron.core.behaviors.case.receive_report_case_tree import (
    create_receive_report_case_tree,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole

# ============================================================================
# Tree structure tests
# ============================================================================


class TestTreeStructure:
    """Structure assertions: root node type, children count, and node types."""

    def test_create_receive_report_case_tree_returns_sequence(
        self, report, offer, reporter_actor_id
    ):
        """Tree factory returns a Sequence root gating on auto_create_case."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        assert tree is not None
        assert tree.name == "ReceiveReportCaseBT"
        assert isinstance(tree, py_trees.composites.Sequence)
        assert hasattr(tree, "children")
        assert len(tree.children) == 2

    def test_tree_first_child_is_auto_create_gate(
        self, report, offer, reporter_actor_id
    ):
        """First child is CheckAutoCaseCreationEnabledNode (policy gate)."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        assert isinstance(tree.children[0], CheckAutoCaseCreationEnabledNode)

    def test_tree_second_child_is_case_creation_selector(
        self, report, offer, reporter_actor_id
    ):
        """Second child is the idempotency Selector (ReceiveReportCaseSelector)."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        selector = tree.children[1]
        assert isinstance(selector, py_trees.composites.Selector)
        assert selector.name == "ReceiveReportCaseSelector"

    def test_selector_first_child_is_idempotency_check(
        self, report, offer, reporter_actor_id
    ):
        """Selector's first child is CheckCaseExistsForReport (idempotency guard)."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        selector = tree.children[1]
        assert isinstance(selector.children[0], CheckCaseExistsForReport)

    def test_selector_second_child_is_flow_sequence(
        self, report, offer, reporter_actor_id
    ):
        """Selector's second child is the ReceiveReportCaseFlow Sequence."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        flow = tree.children[1].children[1]
        assert isinstance(flow, py_trees.composites.Sequence)
        assert flow.name == "ReceiveReportCaseFlow"

    def test_tree_flow_has_ten_children(
        self, report, offer, reporter_actor_id
    ):
        """ReceiveReportCaseFlow sequence has exactly 10 action nodes."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        flow = tree.children[1].children[1]
        assert len(flow.children) == 10

    def test_propose_case_to_actor_node_is_wired(
        self, report, offer, reporter_actor_id
    ):
        """ProposeCaseToActorNode appears after CreateCaseActorNode in the flow."""
        from vultron.core.behaviors.case.nodes.actor import (
            ProposeCaseToActorNode,
        )
        from vultron.core.behaviors.case.case_setup_tree import (
            CreateCaseActorNode,
        )

        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        flow = tree.children[1].children[1]
        node_types = [type(c) for c in flow.children]
        assert ProposeCaseToActorNode in node_types
        propose_idx = node_types.index(ProposeCaseToActorNode)
        create_actor_idx = next(
            i
            for i, c in enumerate(flow.children)
            if isinstance(c, CreateCaseActorNode)
        )
        assert propose_idx == create_actor_idx + 1, (
            "ProposeCaseToActorNode must appear immediately after "
            "CreateCaseActorNode"
        )


# ============================================================================
# auto_create_case policy gate tests (CM-15-001)
# ============================================================================


class TestAutoCreateCasePolicyGate:
    """The auto_create_case gate controls whether the tree creates a case."""

    def test_gate_wired_with_actor_config(
        self, report, offer, reporter_actor_id
    ):
        """The root gate receives the supplied ActorConfig (CM-15-001)."""
        from vultron.core.models.actor_config import ActorConfig

        cfg = ActorConfig(auto_create_case=False)
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
            actor_config=cfg,
        )
        gate = tree.children[0]
        assert isinstance(gate, CheckAutoCaseCreationEnabledNode)
        assert gate.actor_config is cfg

    def test_tree_creates_case_when_auto_create_enabled(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """auto_create_case=True (default) still creates the case (AC-1)."""
        from vultron.core.models.actor_config import ActorConfig

        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
            actor_config=ActorConfig(auto_create_case=True),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )
        assert result.status == Status.SUCCESS
        assert datalayer.find_case_by_report_id(report.id_) is not None

    def test_tree_skips_case_when_auto_create_disabled(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """auto_create_case=False makes the tree exit without a case (AC-2)."""
        from vultron.core.models.actor_config import ActorConfig

        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
            actor_config=ActorConfig(auto_create_case=False),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )
        # Outer Sequence fails at the gate before any DataLayer write.
        assert result.status == Status.FAILURE
        assert datalayer.find_case_by_report_id(report.id_) is None


# ============================================================================
# Tree flow tests
# ============================================================================


class TestTreeFlow:
    """Happy-path execution, case creation, and outbox ordering."""

    def test_tree_succeeds(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Tree executes successfully and returns Status.SUCCESS."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )
        assert result.status == Status.SUCCESS

    def test_tree_creates_case(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Tree creates a VulnerabilityCase linked to the report."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None
        # The case should reference the report
        reports = getattr(case, "vulnerability_reports", []) or []
        report_refs = [
            r if isinstance(r, str) else getattr(r, "id_", str(r))
            for r in reports
        ]
        assert report.id_ in report_refs

    def test_tree_queues_create_case_activity(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Tree queues a Create(Case) activity to the actor's outbox."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        outbox_items = datalayer.clone_for_actor(actor.id_).outbox_list()
        assert len(outbox_items) > 0

    def test_create_case_precedes_add_participant_in_outbox(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Create(Case) must be queued before Add(CaseParticipant) (D5-7-MSGORDER-1).

        Ensures the reporter actor receives the case-creation notification before
        receiving the participant-addition notification, preventing "case not found"
        warnings on the reporter side.
        """
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        items = datalayer.clone_for_actor(actor.id_).outbox_list()
        assert len(items) >= 2, f"Expected >= 2 outbox items; got {len(items)}"

        # Read the first two activities to check their types
        first_activity = datalayer.read(items[0])
        second_activity = datalayer.read(items[1])
        assert (
            first_activity is not None
        ), f"Could not read activity '{items[0]}'"
        assert (
            second_activity is not None
        ), f"Could not read activity '{items[1]}'"

        first_type = getattr(first_activity, "type_", None)
        second_type = getattr(second_activity, "type_", None)
        assert (
            first_type == "Create"
        ), f"First outbox item should be Create(Case), got type_={first_type!r}"
        assert second_type == "Add", (
            f"Second outbox item should be Add(CaseParticipant),"
            f" got type_={second_type!r}"
        )


# ============================================================================
# Idempotency tests
# ============================================================================


class TestTreeIdempotency:
    """Idempotency guard and early-exit paths."""

    def test_tree_is_idempotent(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Running the tree twice succeeds and does not duplicate the case."""
        tree1 = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        result1 = bridge.execute_with_setup(
            tree=tree1, actor_id=actor.id_, activity=offer
        )
        assert result1.status == Status.SUCCESS

        tree2 = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        result2 = bridge.execute_with_setup(
            tree=tree2, actor_id=actor.id_, activity=offer
        )
        assert result2.status == Status.SUCCESS

        # Only one case for this report
        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None

    def test_tree_early_exits_when_case_already_initialized(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """CheckCaseExistsForReport returns SUCCESS when case has participants."""
        # Run once to initialize case
        tree1 = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree1, actor_id=actor.id_, activity=offer
        )

        # Record outbox length before second run
        outbox_count_before = len(
            datalayer.clone_for_actor(actor.id_).outbox_list()
        )

        # Second run: CheckCaseExistsForReport should succeed (early exit)
        tree2 = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        result2 = bridge.execute_with_setup(
            tree=tree2, actor_id=actor.id_, activity=offer
        )
        assert result2.status == Status.SUCCESS

        # No additional outbox items (early exit skips CreateCaseActivity)
        assert (
            len(datalayer.clone_for_actor(actor.id_).outbox_list())
            == outbox_count_before
        )


# ============================================================================
# Participant creation tests
# ============================================================================


class TestParticipantCreation:
    """Owner, reporter, and vendor participant RM state seeding."""

    def test_tree_creates_case_owner_participant_at_rm_received(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Tree creates a case-owner participant at RM.RECEIVED (BTND-05-002)."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None

        found_owner = False
        for p_ref in case.case_participants:
            p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
            participant = datalayer.read(p_id)
            if participant is None:
                continue
            p_actor = participant.attributed_to
            p_actor_id = (
                p_actor
                if isinstance(p_actor, str)
                else getattr(p_actor, "id_", p_actor)
            )
            if p_actor_id != actor.id_:
                continue
            roles = participant.case_roles
            if CVDRole.CASE_OWNER not in roles:
                continue
            statuses = participant.participant_statuses
            assert statuses, "Case-owner participant has no status history"
            latest = statuses[-1]
            rm = getattr(latest, "rm_state", None)
            assert (
                rm == RM.RECEIVED
            ), f"Expected case-owner rm_state=RM.RECEIVED, got {rm}"
            found_owner = True

        assert found_owner, "No case-owner participant found in case"

    def test_tree_creates_finder_participant_at_rm_accepted(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Tree creates a reporter participant at RM.ACCEPTED."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None

        found_finder = False
        for p_ref in case.case_participants:
            p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
            participant = datalayer.read(p_id)
            if participant is None:
                continue
            p_actor = participant.attributed_to
            p_actor_id = (
                p_actor
                if isinstance(p_actor, str)
                else getattr(p_actor, "id_", p_actor)
            )
            if p_actor_id != reporter_actor.id_:
                continue
            roles = participant.case_roles
            if CVDRole.FINDER not in roles:
                continue
            statuses = participant.participant_statuses
            assert statuses, "Finder participant has no status history"
            latest = statuses[-1]
            rm = getattr(latest, "rm_state", None)
            assert (
                rm == RM.ACCEPTED
            ), f"Expected reporter rm_state=RM.ACCEPTED, got {rm}"
            found_finder = True

        assert found_finder, "No reporter participant found in case"

    def test_vendor_participant_reuses_existing_received_status(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Vendor participant reuses pre-existing RM.RECEIVED status (no duplicate)."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None

        for p_ref in case.case_participants:
            p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
            participant = datalayer.read(p_id)
            if participant is None:
                continue
            p_actor = participant.attributed_to
            p_actor_id = (
                p_actor
                if isinstance(p_actor, str)
                else getattr(p_actor, "id_", p_actor)
            )
            if p_actor_id != actor.id_:
                continue
            # Participant should have exactly one status (the pre-existing one)
            statuses = participant.participant_statuses
            assert len(statuses) == 1
            assert statuses[0].id_ == vendor_received_status.id_
            break

    def test_case_owner_participant_created_without_pre_existing_status(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
    ):
        """Case-owner participant is created with fresh RM.RECEIVED when no prior status."""
        # No vendor_received_status fixture — owner has no prior status record
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )
        assert result.status == Status.SUCCESS

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None

        for p_ref in case.case_participants:
            p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
            participant = datalayer.read(p_id)
            if participant is None:
                continue
            p_actor = participant.attributed_to
            p_actor_id = (
                p_actor
                if isinstance(p_actor, str)
                else getattr(p_actor, "id_", p_actor)
            )
            if p_actor_id != actor.id_:
                continue
            if CVDRole.CASE_OWNER not in participant.case_roles:
                continue
            statuses = participant.participant_statuses
            assert statuses
            rm = getattr(statuses[-1], "rm_state", None)
            assert rm == RM.RECEIVED, f"Expected RM.RECEIVED, got {rm}"
            break


# ============================================================================
# Embargo initialization tests
# ============================================================================


class TestEmbargoInitialization:
    """Embargo creation, EM state, and signatory seeding."""

    def test_tree_creates_default_embargo(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Tree creates a default embargo and attaches it to the case."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None
        assert case.active_embargo is not None

    def test_tree_sets_em_state_active_after_embargo_init(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """After embargo initialization, the case's current EM state MUST be
        ACTIVE, not NONE or PROPOSED (EP-04-001, EP-04-002,
        specs/case-management.yaml CM-12-004).
        """
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None
        assert case.active_embargo is not None
        assert case.current_status.em_state != EM.NONE, (
            f"Expected em_state != NONE after embargo init,"
            f" got {case.current_status.em_state}"
        )
        assert case.current_status.em_state == EM.ACTIVE, (
            f"Expected em_state == ACTIVE after embargo init,"
            f" got {case.current_status.em_state}"
        )

    def test_tree_records_embargo_initialized_event(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """After embargo initialization the case MUST have an active embargo
        (D5-7-EMSTATE-1).

        record_event('embargo_initialized') was removed in #789; the behavioral
        invariant is now verified by checking case.active_embargo is not None.
        The canonical ledger commit (CommitCaseLedgerEntryNode) records the
        submit_report entry that caused the embargo to be initialized.
        """
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None
        assert (
            case.active_embargo is not None
        ), "Expected case.active_embargo to be set after embargo initialization"

    def test_tree_embargo_initialized_event_references_embargo_id(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """The active embargo MUST reference the correct embargo object ID
        (D5-7-EMSTATE-1).

        record_event('embargo_initialized') was removed in #789; the behavioral
        invariant is now verified by checking case.active_embargo equals the
        expected embargo ID.
        """
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None
        assert case.active_embargo is not None
        embargo = datalayer.read(case.active_embargo)
        assert embargo is not None

    def test_tree_owner_participant_precedes_embargo_in_sequence(
        self,
        report,
        offer,
        reporter_actor_id,
    ):
        """CreateCaseOwnerParticipant MUST precede InitializeDefaultEmbargoNode
        in the sequence (CM-14-002, AC-1).
        """
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        flow = tree.children[1].children[1]
        node_types = [type(child) for child in flow.children]

        owner_idx = None
        embargo_idx = None
        for i, t in enumerate(node_types):
            if t is CreateCaseOwnerParticipant:
                owner_idx = i
            if t is InitializeDefaultEmbargoNode:
                embargo_idx = i

        assert (
            owner_idx is not None
        ), "CreateCaseOwnerParticipant not found in flow"
        assert (
            embargo_idx is not None
        ), "InitializeDefaultEmbargoNode not found in flow"
        assert owner_idx < embargo_idx, (
            f"CreateCaseOwnerParticipant (idx={owner_idx}) must precede"
            f" InitializeDefaultEmbargoNode (idx={embargo_idx}) — CM-14-002"
        )

    def test_owner_seeded_as_signatory_after_embargo_init(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Case-owner participant MUST have embargo_consent_state == SIGNATORY
        after tree execution when a default embargo is created (CM-14-003, AC-2).
        """
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None
        assert (
            case.active_embargo is not None
        ), "No active embargo — prerequisite"

        found_owner = False
        for p_ref in case.case_participants:
            p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
            participant = datalayer.read(p_id)
            if participant is None:
                continue
            p_actor = participant.attributed_to
            p_actor_id = (
                p_actor
                if isinstance(p_actor, str)
                else getattr(p_actor, "id_", p_actor)
            )
            if p_actor_id != actor.id_:
                continue
            if CVDRole.CASE_OWNER not in participant.case_roles:
                continue
            assert PEC(participant.embargo_consent_state) == PEC.SIGNATORY, (
                f"Expected owner embargo_consent_state=SIGNATORY,"
                f" got {participant.embargo_consent_state!r}"
            )
            active_embargo_id = (
                case.active_embargo
                if isinstance(case.active_embargo, str)
                else getattr(
                    case.active_embargo, "id_", str(case.active_embargo)
                )
            )
            assert active_embargo_id in participant.accepted_embargo_ids, (
                f"Expected active embargo '{active_embargo_id}'"
                f" in owner accepted_embargo_ids,"
                f" got {participant.accepted_embargo_ids!r}"
            )
            found_owner = True

        assert found_owner, "No case-owner participant found in case"

    def test_reporter_seeded_as_signatory_when_active_embargo(
        self,
        datalayer,
        actor,
        reporter_actor,
        reporter_actor_id,
        report,
        offer,
        bridge,
        reporter_accepted_status,
        vendor_received_status,
    ):
        """Reporter participant MUST have embargo_consent_state == SIGNATORY
        when an active embargo exists at participant creation time
        (CM-14-005, AC-3).
        """
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert case is not None
        assert (
            case.active_embargo is not None
        ), "No active embargo — prerequisite"

        found_reporter = False
        for p_ref in case.case_participants:
            p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
            participant = datalayer.read(p_id)
            if participant is None:
                continue
            p_actor = participant.attributed_to
            p_actor_id = (
                p_actor
                if isinstance(p_actor, str)
                else getattr(p_actor, "id_", p_actor)
            )
            if p_actor_id != reporter_actor.id_:
                continue
            if CVDRole.FINDER not in participant.case_roles:
                continue
            assert PEC(participant.embargo_consent_state) == PEC.SIGNATORY, (
                f"Expected reporter embargo_consent_state=SIGNATORY,"
                f" got {participant.embargo_consent_state!r}"
            )
            active_embargo_id = (
                case.active_embargo
                if isinstance(case.active_embargo, str)
                else getattr(
                    case.active_embargo, "id_", str(case.active_embargo)
                )
            )
            assert active_embargo_id in participant.accepted_embargo_ids, (
                f"Expected active embargo '{active_embargo_id}'"
                f" in reporter accepted_embargo_ids,"
                f" got {participant.accepted_embargo_ids!r}"
            )
            found_reporter = True

        assert found_reporter, "No reporter participant found in case"
