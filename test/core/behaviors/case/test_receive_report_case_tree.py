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
Tests for the slimmed vendor receive-report case-proposal tree (ADR-0041).

The tree no longer creates a VulnerabilityCase.  Instead it:
1. Writes a pending VultronReportCaseLink (WritePendingReportCaseLinkNode).
2. Sends Create(as_CaseProposal) to the CaseActor service
   (ProposeReportCaseToActorNode).

Tests are grouped by concern:
- TestTreeStructure       — root shape, child count, node types
- TestPolicyGate          — auto_create_case=False skips the flow
- TestHappyPath           — link written + proposal queued
- TestIdempotency         — second run is a no-op (CP-04-001)
- TestConcurrentExecution — two parallel invocations don't corrupt each other
                            (BTND-03-004)

Fixtures defined in conftest.py and shared with sibling tree test files.
"""

import threading

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes import (
    CheckAutoCaseCreationEnabledNode,
    CheckPendingProposalExistsForReport,
    ProposeReportCaseToActorNode,
    EnsureCaseActorHostedNode,
    WritePendingReportCaseLinkNode,
)
from vultron.core.behaviors.case.receive_report_case_tree import (
    create_receive_report_case_tree,
)
from vultron.core.models.report_case_link import VultronReportCaseLink

_CASE_ACTOR_SERVICE_URL = "http://case-actor:7999/api/v2"


@pytest.fixture(autouse=True)
def configure_case_actor_url(monkeypatch):
    """Configure VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL for all tests."""
    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _CASE_ACTOR_SERVICE_URL
    )
    from vultron.config.app import reload_config

    reload_config()
    yield
    # Undo the env patch BEFORE reloading: monkeypatch's own undo runs after
    # this teardown, so reloading first would re-cache this fixture's URL into
    # the module-level config for the rest of the session (#2086).
    monkeypatch.undo()
    reload_config()


# ============================================================================
# Tree structure tests
# ============================================================================


@pytest.mark.spec("CM-12-001")
class TestTreeStructure:
    """Root shape, child count, and node identity assertions (ADR-0041)."""

    def test_factory_returns_sequence(self, report, offer, reporter_actor_id):
        """Tree factory returns a Sequence root named ReceiveReportCaseBT."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        assert tree is not None
        assert tree.name == "ReceiveReportCaseBT"
        assert isinstance(tree, py_trees.composites.Sequence)
        assert len(tree.children) == 2

    def test_first_child_is_policy_gate(
        self, report, offer, reporter_actor_id
    ):
        """First child is CheckAutoCaseCreationEnabledNode."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        assert isinstance(tree.children[0], CheckAutoCaseCreationEnabledNode)

    def test_second_child_is_selector(self, report, offer, reporter_actor_id):
        """Second child is ReceiveReportCaseSelector (Selector)."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        sel = tree.children[1]
        assert isinstance(sel, py_trees.composites.Selector)
        assert sel.name == "ReceiveReportCaseSelector"

    def test_selector_first_child_is_idempotency_check(
        self, report, offer, reporter_actor_id
    ):
        """Selector's first child is CheckPendingProposalExistsForReport."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        sel = tree.children[1]
        assert isinstance(sel.children[0], CheckPendingProposalExistsForReport)

    def test_selector_second_child_is_flow_sequence(
        self, report, offer, reporter_actor_id
    ):
        """Selector's second child is the ReceiveReportProposalFlow Sequence."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        flow = tree.children[1].children[1]
        assert isinstance(flow, py_trees.composites.Sequence)
        assert flow.name == "ReceiveReportProposalFlow"

    def test_flow_has_three_children(self, report, offer, reporter_actor_id):
        """ReceiveReportProposalFlow has exactly 3 children."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        flow = tree.children[1].children[1]
        assert len(flow.children) == 3

    def test_flow_first_child_ensures_case_actor_hosted(
        self, report, offer, reporter_actor_id
    ):
        """Provisioning runs before the link write, as its own leaf.

        ``EnsureCaseActorHostedNode`` was extracted from
        ``WritePendingReportCaseLinkNode.update()``, which had grown to two jobs
        (BTND-02-001).  Ordering matters: the CaseActor record must be in its own
        store before ``ProposeReportCaseToActorNode`` delivers to its inbox.
        """
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        flow = tree.children[1].children[1]
        assert isinstance(flow.children[0], EnsureCaseActorHostedNode)

    def test_flow_second_child_is_write_link(
        self, report, offer, reporter_actor_id
    ):
        """Flow's second child is WritePendingReportCaseLinkNode (AC-2)."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        flow = tree.children[1].children[1]
        assert isinstance(flow.children[1], WritePendingReportCaseLinkNode)

    def test_flow_third_child_is_propose(
        self, report, offer, reporter_actor_id
    ):
        """Flow's third child is ProposeReportCaseToActorNode."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        flow = tree.children[1].children[1]
        assert isinstance(flow.children[2], ProposeReportCaseToActorNode)

    def test_no_create_case_node(self, report, offer, reporter_actor_id):
        """Tree does NOT contain CreateCaseNode (AC-1)."""
        from vultron.core.behaviors.report.nodes import CreateCaseNode

        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )

        def _collect(node):
            yield node
            for child in getattr(node, "children", []):
                yield from _collect(child)

        node_types = [type(n) for n in _collect(tree)]
        assert (
            CreateCaseNode not in node_types
        ), "CreateCaseNode must not appear in the slimmed vendor tree (AC-1)"

    def test_no_embargo_node(self, report, offer, reporter_actor_id):
        """Tree does NOT contain InitializeDefaultEmbargoNode (AC-1)."""
        from vultron.core.behaviors.case.embargo_tree import (
            InitializeDefaultEmbargoNode,
        )

        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )

        def _collect(node):
            yield node
            for child in getattr(node, "children", []):
                yield from _collect(child)

        node_types = [type(n) for n in _collect(tree)]
        assert (
            InitializeDefaultEmbargoNode not in node_types
        ), "InitializeDefaultEmbargoNode must not appear in the vendor tree (AC-1)"


# ============================================================================
# Policy gate tests
# ============================================================================


@pytest.mark.spec("CM-15-001")
@pytest.mark.spec("CM-15-002")
@pytest.mark.spec("CM-15-003")
@pytest.mark.spec("CM-15-004")
class TestPolicyGate:
    """auto_create_case=False prevents any DataLayer writes."""

    def test_gate_wired_with_actor_config(
        self, report, offer, reporter_actor_id
    ):
        """CheckAutoCaseCreationEnabledNode receives the supplied ActorConfig."""
        from vultron.config.actor import ActorConfig

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

    def test_disabled_gate_returns_failure_and_writes_nothing(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """auto_create_case=False → tree returns FAILURE, no link written."""
        from vultron.config.actor import ActorConfig

        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
            actor_config=ActorConfig(auto_create_case=False),
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )
        assert result.status == Status.FAILURE

        link = datalayer.read(VultronReportCaseLink.build_id(report.id_))
        assert (
            link is None
        ), "No ReportCaseLink should be written when gate disabled"

    def test_enabled_gate_succeeds(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """auto_create_case=True (default) allows the flow to run."""
        from vultron.config.actor import ActorConfig

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


# ============================================================================
# Happy-path tests
# ============================================================================


class TestHappyPath:
    """Proposal flow: link written + Create(as_CaseProposal) queued."""

    def test_tree_succeeds(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """Tree returns Status.SUCCESS on first run."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )
        assert result.status == Status.SUCCESS

    def test_pending_link_written(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """WritePendingReportCaseLinkNode creates a pending VultronReportCaseLink (AC-2)."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        link_id = VultronReportCaseLink.build_id(report.id_)
        link = datalayer.read(link_id)
        assert isinstance(
            link, VultronReportCaseLink
        ), "VultronReportCaseLink must exist after tree execution (AC-2)"
        assert link.report_id == report.id_
        assert link.case_id is None, "Link must be pending (case_id=None)"
        assert not link.proposal_rejected

    def test_trusted_case_creator_id_is_the_case_actor_container(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """Link.trusted_case_creator_id is the CaseActor *container* identity.

        #1872 AC-5. It used to be ``.../actors/case-actor-{slug}``, derived from
        the report id. That identity was a phantom — the sender computed it and no
        container hosted it — so the proposal's delivery 404'd and the round-trip
        never began. The bootstrap match (CP-06-003) works on the container
        identity because the case a message concerns travels in
        ``activity.context``, not in the actor URI.
        """
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        link = datalayer.read(VultronReportCaseLink.build_id(report.id_))
        assert isinstance(link, VultronReportCaseLink)

        assert link.trusted_case_creator_id == (
            f"{_CASE_ACTOR_SERVICE_URL}/actors/case-actor"
        ), "the CaseActor identity is the container's, and carries no case"
        assert "case-actor-" not in (link.trusted_case_creator_id or ""), (
            "a per-case slug is the retired form; it is unhostable by"
            " construction (#1872)"
        )

    def test_proposal_queued_to_outbox(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """ProposeReportCaseToActorNode enqueues Create(as_CaseProposal) to outbox."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        outbox = datalayer.clone_for_actor(actor.id_).outbox_list()
        assert (
            len(outbox) >= 1
        ), "At least one outbox item expected (the proposal)"

    def test_no_vulnerability_case_created(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """Tree must NOT create a VulnerabilityCase (AC-1, ADR-0041)."""
        tree = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree, actor_id=actor.id_, activity=offer
        )

        case = datalayer.find_case_by_report_id(report.id_)
        assert (
            case is None
        ), "Vendor tree must NOT create a VulnerabilityCase (ADR-0041 AC-1)"


# ============================================================================
# Idempotency tests
# ============================================================================


class TestIdempotency:
    """Running the tree twice is a no-op after the first proposal (CP-04-001)."""

    def test_second_run_returns_success(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """Both runs return SUCCESS."""
        for _ in range(2):
            tree = create_receive_report_case_tree(
                report_id=report.id_,
                offer_id=offer.id_,
                reporter_actor_id=reporter_actor_id,
            )
            result = bridge.execute_with_setup(
                tree=tree, actor_id=actor.id_, activity=offer
            )
            assert result.status == Status.SUCCESS

    def test_second_run_does_not_duplicate_link(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """Only one VultronReportCaseLink is created even when run twice."""
        for _ in range(2):
            tree = create_receive_report_case_tree(
                report_id=report.id_,
                offer_id=offer.id_,
                reporter_actor_id=reporter_actor_id,
            )
            bridge.execute_with_setup(
                tree=tree, actor_id=actor.id_, activity=offer
            )

        links = [
            obj
            for obj in datalayer.list_objects("ReportCaseLink")
            if isinstance(obj, VultronReportCaseLink)
            and obj.report_id == report.id_
        ]
        assert len(links) == 1

    def test_second_run_does_not_add_outbox_items(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """CheckPendingProposalExistsForReport short-circuits; no extra activities queued."""
        tree1 = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree1, actor_id=actor.id_, activity=offer
        )

        count_after_first = len(
            datalayer.clone_for_actor(actor.id_).outbox_list()
        )

        tree2 = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree2, actor_id=actor.id_, activity=offer
        )

        count_after_second = len(
            datalayer.clone_for_actor(actor.id_).outbox_list()
        )
        assert (
            count_after_second == count_after_first
        ), "Second run must not enqueue additional outbox items"

    def test_retry_after_proposal_rejected_sends_new_proposal(
        self,
        datalayer,
        actor,
        offer,
        reporter_actor_id,
        report,
        bridge,
    ):
        """When proposal_rejected=True, a second tree run enqueues a new proposal.

        The Selector falls through (CheckPendingProposalExistsForReport returns
        FAILURE because proposal_rejected=True), WritePendingReportCaseLinkNode
        returns SUCCESS (link exists — skips write), and ProposeReportCaseToActorNode
        enqueues another Create(as_CaseProposal).  This is the correct retry
        behavior after the CaseActor rejects the first proposal.
        """
        tree1 = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        bridge.execute_with_setup(
            tree=tree1, actor_id=actor.id_, activity=offer
        )

        link_id = VultronReportCaseLink.build_id(report.id_)
        link = datalayer.read(link_id)
        assert isinstance(link, VultronReportCaseLink)
        link.proposal_rejected = True
        datalayer.save(link)

        count_before_retry = len(
            datalayer.clone_for_actor(actor.id_).outbox_list()
        )

        tree2 = create_receive_report_case_tree(
            report_id=report.id_,
            offer_id=offer.id_,
            reporter_actor_id=reporter_actor_id,
        )
        result = bridge.execute_with_setup(
            tree=tree2, actor_id=actor.id_, activity=offer
        )
        assert result.status == Status.SUCCESS

        count_after_retry = len(
            datalayer.clone_for_actor(actor.id_).outbox_list()
        )
        assert (
            count_after_retry > count_before_retry
        ), "Re-triggering after proposal_rejected=True must enqueue a new proposal"


# ============================================================================
# Concurrent execution tests (BTND-03-004)
# ============================================================================


class TestConcurrentExecution:
    """Two parallel invocations with distinct report_ids don't corrupt each other.

    The py_trees blackboard is process-global (BTND-03-004).  The slimmed
    tree uses only constructor-injected ``report_id`` values (not inter-node
    handoff blackboard keys), so concurrent executions for distinct reports
    MUST NOT corrupt each other's DataLayer state.

    This class exercises the ``_BT_GLOBAL_LOCK`` serialisation in
    ``BTBridge.execute_with_setup`` and verifies that per-report isolation
    holds even when two bridge instances race on the global lock.
    """

    @staticmethod
    def _make_report_offer(
        datalayer, reporter_actor_id, actor_id, report_id, name, content
    ):
        from vultron.wire.as2.factories import rm_submit_report_activity
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        report = as_VulnerabilityReport(
            id_=report_id, name=name, content=content
        )
        datalayer.create(report)
        offer = rm_submit_report_activity(
            report=report, actor=reporter_actor_id, to=actor_id
        )
        datalayer.create(offer)
        return report, offer

    @staticmethod
    def _spawn_and_join(datalayer, actor_id, reporter_actor_id, pairs):
        """Spawn one thread per (report, offer, key) pair; join all; return results dict.

        ``pairs`` is a list of ``(report_obj, offer_obj, key_str)`` tuples.
        Returns ``{key: Status}`` for each thread that completed successfully.
        Asserts no deadlock (``is_alive()`` after join) and no thread errors.
        Both ``results`` and ``errors`` are written under the same lock so
        all inter-thread writes are consistently protected.
        """
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )

        results: dict[str, Status] = {}
        errors: list[str] = []
        _lock = threading.Lock()

        def _run(
            report_id: str, offer_id: str, offer: object, key: str
        ) -> None:
            try:
                bridge = BTBridge(
                    datalayer=datalayer,
                    trigger_activity=TriggerActivityAdapter(datalayer),
                )
                tree = create_receive_report_case_tree(
                    report_id=report_id,
                    offer_id=offer_id,
                    reporter_actor_id=reporter_actor_id,
                )
                result = bridge.execute_with_setup(
                    tree=tree, actor_id=actor_id, activity=offer
                )
                with _lock:
                    results[key] = result.status
            except Exception as exc:
                with _lock:
                    errors.append(f"{key}: {exc}")

        threads = [
            threading.Thread(target=_run, args=(r.id_, o.id_, o, k))
            for r, o, k in pairs
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        for i, t in enumerate(threads):
            assert (
                not t.is_alive()
            ), f"Thread {i} timed out — possible deadlock"
        assert not errors, f"Thread errors: {errors}"
        return results

    def test_two_threads_both_succeed(
        self,
        datalayer,
        actor,
        reporter_actor_id,
    ):
        """Both threads complete with Status.SUCCESS (BTND-03-004)."""
        report_a, offer_a = self._make_report_offer(
            datalayer,
            reporter_actor_id,
            actor.id_,
            "https://example.org/reports/CONCURRENT-A",
            "Concurrent Report A",
            "Test content A",
        )
        report_b, offer_b = self._make_report_offer(
            datalayer,
            reporter_actor_id,
            actor.id_,
            "https://example.org/reports/CONCURRENT-B",
            "Concurrent Report B",
            "Test content B",
        )
        results = self._spawn_and_join(
            datalayer,
            actor.id_,
            reporter_actor_id,
            [(report_a, offer_a, "a"), (report_b, offer_b, "b")],
        )
        assert (
            results.get("a") == Status.SUCCESS
        ), f"Thread A status: {results.get('a')}"
        assert (
            results.get("b") == Status.SUCCESS
        ), f"Thread B status: {results.get('b')}"

    def test_two_threads_produce_distinct_links(
        self,
        datalayer,
        actor,
        reporter_actor_id,
    ):
        """Each thread writes its own VultronReportCaseLink; two distinct records exist."""
        report_a, offer_a = self._make_report_offer(
            datalayer,
            reporter_actor_id,
            actor.id_,
            "https://example.org/reports/LINK-A",
            "Link Report A",
            "Content A",
        )
        report_b, offer_b = self._make_report_offer(
            datalayer,
            reporter_actor_id,
            actor.id_,
            "https://example.org/reports/LINK-B",
            "Link Report B",
            "Content B",
        )
        self._spawn_and_join(
            datalayer,
            actor.id_,
            reporter_actor_id,
            [(report_a, offer_a, "a"), (report_b, offer_b, "b")],
        )

        link_a = datalayer.read(VultronReportCaseLink.build_id(report_a.id_))
        link_b = datalayer.read(VultronReportCaseLink.build_id(report_b.id_))

        assert isinstance(
            link_a, VultronReportCaseLink
        ), "VultronReportCaseLink for report A must exist"
        assert isinstance(
            link_b, VultronReportCaseLink
        ), "VultronReportCaseLink for report B must exist"
        assert link_a.report_id == report_a.id_
        assert link_b.report_id == report_b.id_
        assert link_a.id_ != link_b.id_, "Links must be distinct records"
