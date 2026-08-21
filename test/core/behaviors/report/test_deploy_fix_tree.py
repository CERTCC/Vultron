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
"""Tests for the deploy-fix behavior tree and its production nodes.

Covers all acceptance criteria from issue #1825:

- AC-1: DeployFixBT Fallback with four arms (early-exit, stay-deferred,
  deploy-if-ready, monitor-if-desired)
- AC-2: DeployFixCallOutBundle reduced to 4 fields (deploy_mitigation removed)
- AC-3: CheckDeployerRoleNode reused; CheckRMStateAccepted reused;
  CheckCSFixNotYetDeployed new guard node
- AC-4: CheckNoNewDeploymentInfoNode reads blackboard flag; defaults SUCCESS
- AC-5: TransitionCStoFixDeployed + EmitCDActivity
- AC-7: Bundle injection, tree structure, guard presence, factory seams,
  early-exit short-circuit
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.call_out.bundles.deploy_fix import (
    DEPLOY_FIX_DETERMINISTIC,
    DeployFixCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckDeployerRoleNode,
)
from vultron.core.behaviors.report.deploy_fix_tree import (
    create_deploy_fix_tree,
)
from vultron.core.behaviors.report.nodes.deploy_fix import (
    NEW_DEPLOYMENT_INFO_KEY,
    CheckCSFixNotYetDeployed,
    CheckNoNewDeploymentInfoNode,
    CSinStateFixDeployed,
    EmitCDActivity,
    RMinStateDeferred,
    TransitionCStoFixDeployed,
)
from vultron.core.behaviors.report.nodes.develop_fix import (
    CheckRMStateAccepted,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfdDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/test-deploy-001"
DEPLOYER_ACTOR_ID = "https://example.org/actors/deployer-001"
VENDOR_ACTOR_ID = "https://example.org/actors/vendor-001"
CASE_MANAGER_ACTOR_ID = "https://example.org/actors/case-manager-001"


@pytest.fixture
def bt_scenario():
    """Scenario scoped to DEPLOYER_ACTOR_ID — the deployer, who deploys the fix.

    Shadows the harness default so the store belongs to the actor these trees
    execute as: a BT's store follows its executing actor (ADR-0070).
    """
    return BTTestScenario(DEPLOYER_ACTOR_ID)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def deployer_participant() -> VultronParticipant:
    return VultronParticipant(
        id_="https://example.org/participants/deployer-cp-001",
        attributed_to=DEPLOYER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.DEPLOYER],
    )


@pytest.fixture
def case_manager_participant() -> VultronParticipant:
    return VultronParticipant(
        id_="https://example.org/participants/cm-cp-001",
        attributed_to=CASE_MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )


@pytest.fixture
def case_with_deployer(
    bt_scenario: BTTestScenario,
    deployer_participant: VultronParticipant,
) -> VultronCase:
    case = VultronCase(
        id_=CASE_ID,
        name="Test Case",
        case_participants=[deployer_participant.id_],
        actor_participant_index={DEPLOYER_ACTOR_ID: deployer_participant.id_},
    )
    bt_scenario.seed(deployer_participant, case)
    return case


@pytest.fixture
def case_with_deployer_and_case_manager(
    bt_scenario: BTTestScenario,
    deployer_participant: VultronParticipant,
    case_manager_participant: VultronParticipant,
) -> VultronCase:
    case = VultronCase(
        id_=CASE_ID,
        name="Test Case",
        case_participants=[
            deployer_participant.id_,
            case_manager_participant.id_,
        ],
        actor_participant_index={
            DEPLOYER_ACTOR_ID: deployer_participant.id_,
            CASE_MANAGER_ACTOR_ID: case_manager_participant.id_,
        },
    )
    bt_scenario.seed(deployer_participant, case_manager_participant, case)
    return case


def _seed_status(
    bt_scenario: BTTestScenario,
    case_id: str,
    actor_id: str,
    rm: RM = RM.ACCEPTED,
    vfd: CS_vfd = CS_vfd.VFd,
) -> None:
    """Seed a ParticipantStatus record with the given RM and VFD states."""
    status = ParticipantStatus(
        context=case_id,
        attributed_to=actor_id,
        rm=RmDimension(state=rm),
        vfd=VfdDimension(state=vfd),
    )
    bt_scenario.dl.create(status)

    case = bt_scenario.dl.read(case_id)
    if not isinstance(case, VultronCase):
        return
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id:
        participant = bt_scenario.dl.read(participant_id)
        if isinstance(participant, CaseParticipant):
            participant.participant_statuses.append(status)
            bt_scenario.dl.save(participant)


# ---------------------------------------------------------------------------
# AC-1: create_deploy_fix_tree factory + tree structure
# ---------------------------------------------------------------------------


def test_create_deploy_fix_tree_returns_behaviour():
    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_deploy_fix_tree_root_name():
    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    assert tree.name == "DeployFixBT"


def test_tree_root_is_fallback():
    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    assert isinstance(tree, py_trees.composites.Selector)


def test_tree_has_four_arms():
    """DeployFixBT Fallback has exactly 4 arms (AC-1)."""
    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    assert len(tree.children) == 4
    assert isinstance(tree.children[0], CSinStateFixDeployed)
    assert tree.children[1].name == "_ShouldStayInRmDeferred"
    assert tree.children[2].name == "_DeployFixIfReady"
    assert tree.children[3].name == "_MonitorDeploymentIfDesired"


def test_should_stay_deferred_arm_composition():
    """_ShouldStayInRmDeferred = RMinStateDeferred + CheckNoNewDeploymentInfo."""
    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    arm = tree.children[1]
    assert isinstance(arm, py_trees.composites.Sequence)
    assert len(arm.children) == 2
    assert isinstance(arm.children[0], RMinStateDeferred)
    assert isinstance(arm.children[1], CheckNoNewDeploymentInfoNode)


def test_deploy_if_ready_arm_composition():
    """_DeployFixIfReady arm: 3 guards + 2 call-outs + transition + emit."""
    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    arm = tree.children[2]
    assert isinstance(arm, py_trees.composites.Sequence)
    assert len(arm.children) == 7
    assert isinstance(arm.children[0], CheckDeployerRoleNode)
    assert isinstance(arm.children[1], CheckRMStateAccepted)
    assert isinstance(arm.children[2], CheckCSFixNotYetDeployed)
    assert arm.children[3].name == "PrioritizeDeployment"
    assert arm.children[4].name == "DeployFix"
    assert isinstance(arm.children[5], TransitionCStoFixDeployed)
    assert isinstance(arm.children[6], EmitCDActivity)


def test_monitor_arm_composition():
    """_MonitorDeploymentIfDesired arm: MonitoringRequirement + MonitorDeployment."""
    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    arm = tree.children[3]
    assert isinstance(arm, py_trees.composites.Sequence)
    assert len(arm.children) == 2
    assert arm.children[0].name == "MonitoringRequirement"
    assert arm.children[1].name == "MonitorDeployment"


# ---------------------------------------------------------------------------
# AC-2 / AC-7: DeployFixCallOutBundle has exactly 4 fields
# ---------------------------------------------------------------------------


def test_bundle_has_four_fields():
    """DeployFixCallOutBundle reduced to 4 fields (deploy_mitigation removed)."""
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(DeployFixCallOutBundle)}
    assert field_names == {
        "prioritize_deployment_factory",
        "deploy_fix_factory",
        "monitoring_requirement_factory",
        "monitor_deployment_factory",
    }
    assert "deploy_mitigation_factory" not in field_names


def test_default_call_out_children_are_deterministic():
    """DETERMINISTIC: ceiling/floor of each node's stochastic p (BT-23-002)."""
    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    deploy_arm = tree.children[2]
    monitor_arm = tree.children[3]
    # PrioritizeDeployment p=0.90 → AlwaysSucceed
    assert isinstance(deploy_arm.children[3], AlwaysSucceed)
    # DeployFix p=0.10 → AlwaysFail
    assert isinstance(deploy_arm.children[4], AlwaysFail)
    # MonitoringRequirement p=0.70 → AlwaysSucceed
    assert isinstance(monitor_arm.children[0], AlwaysSucceed)
    # MonitorDeployment p=1.0 → AlwaysSucceed
    assert isinstance(monitor_arm.children[1], AlwaysSucceed)


def test_bundle_parameter_accepted():
    tree = create_deploy_fix_tree(
        case_id=CASE_ID,
        actor_id=DEPLOYER_ACTOR_ID,
        call_out=DEPLOY_FIX_DETERMINISTIC,
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_deterministic_deploy_fix_is_instance_of_bundle():
    assert isinstance(DEPLOY_FIX_DETERMINISTIC, DeployFixCallOutBundle)


# ---------------------------------------------------------------------------
# AC-7: Each call-out factory seam is individually replaceable
# ---------------------------------------------------------------------------


def _marker_factory(label: str):
    def factory(name: str) -> py_trees.behaviour.Behaviour:
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self) -> Status:
                return Status.SUCCESS

        return _Marker(name=label)

    return factory


# (field, label, arm_index, child_index within arm)
_CALL_OUT_SEAMS = [
    ("prioritize_deployment_factory", "PD", 2, 3),
    ("deploy_fix_factory", "DF", 2, 4),
    ("monitoring_requirement_factory", "MR", 3, 0),
    ("monitor_deployment_factory", "MD", 3, 1),
]


@pytest.mark.parametrize("field,label,arm_idx,child_idx", _CALL_OUT_SEAMS)
def test_each_factory_is_wired(field, label, arm_idx, child_idx):
    """Each of the 4 factory fields is individually wired into the tree."""
    sentinel = {"called": False}

    def custom_factory(name: str) -> py_trees.behaviour.Behaviour:
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self) -> Status:
                return Status.SUCCESS

        return _Marker(name=label)

    bundle = DeployFixCallOutBundle(**{field: custom_factory})  # type: ignore[arg-type]
    tree = create_deploy_fix_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, call_out=bundle
    )
    assert sentinel["called"]
    assert tree.children[arm_idx].children[child_idx].name == label


def test_all_factories_replaceable():
    bundle = DeployFixCallOutBundle(
        prioritize_deployment_factory=_marker_factory("PD"),  # type: ignore[arg-type]
        monitoring_requirement_factory=_marker_factory("MR"),  # type: ignore[arg-type]
        deploy_fix_factory=_marker_factory("DF"),  # type: ignore[arg-type]
        monitor_deployment_factory=_marker_factory("MD"),  # type: ignore[arg-type]
    )
    tree = create_deploy_fix_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, call_out=bundle
    )
    tree_str = py_trees.display.ascii_tree(tree)
    for label in ("PD", "MR", "DF", "MD"):
        assert label in tree_str


def test_stochastic_bundle_children_are_fuzzer_nodes():
    """STOCHASTIC bundle produces the correct fuzzer-class nodes."""
    from vultron.demo.fuzzer.bundles.deploy_fix import DEPLOY_FIX_STOCHASTIC
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        DeployFix,
        MonitorDeployment,
        MonitoringRequirement,
        PrioritizeDeployment,
    )

    tree = create_deploy_fix_tree(
        case_id=CASE_ID,
        actor_id=DEPLOYER_ACTOR_ID,
        call_out=DEPLOY_FIX_STOCHASTIC,
    )
    deploy_arm = tree.children[2]
    monitor_arm = tree.children[3]
    assert isinstance(deploy_arm.children[3], PrioritizeDeployment)
    assert isinstance(deploy_arm.children[4], DeployFix)
    assert isinstance(monitor_arm.children[0], MonitoringRequirement)
    assert isinstance(monitor_arm.children[1], MonitorDeployment)


# ---------------------------------------------------------------------------
# AC-3 / AC-1: CSinStateFixDeployed early-exit guard
# ---------------------------------------------------------------------------


class TestCSinStateFixDeployed:
    def test_success_when_fix_deployed(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFD)
        result = bt_scenario.run(
            CSinStateFixDeployed(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS

    def test_failure_when_not_deployed(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFd)
        result = bt_scenario.run(
            CSinStateFixDeployed(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE

    def test_failure_when_case_missing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            CSinStateFixDeployed(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE

    def test_failure_when_actor_not_participant(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        result = bt_scenario.run(
            CSinStateFixDeployed(case_id=CASE_ID, actor_id=VENDOR_ACTOR_ID),
            actor_id=VENDOR_ACTOR_ID,
        )
        assert result.status == Status.FAILURE


class TestCheckCSFixNotYetDeployed:
    def test_success_when_fix_ready_not_deployed(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        """SUCCESS only for VFd (fix ready, not yet deployed)."""
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFd)
        result = bt_scenario.run(
            CheckCSFixNotYetDeployed(
                case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
            ),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS

    @pytest.mark.parametrize("vfd", [CS_vfd.vfd, CS_vfd.Vfd])
    def test_failure_when_fix_not_ready(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
        vfd: CS_vfd,
    ) -> None:
        """FAILURE when fix is not yet ready — d→D requires VFd source.

        Guards against an invalid vfd/Vfd → VFD state-machine jump.
        """
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=vfd)
        result = bt_scenario.run(
            CheckCSFixNotYetDeployed(
                case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
            ),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE

    def test_failure_when_already_deployed(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFD)
        result = bt_scenario.run(
            CheckCSFixNotYetDeployed(
                case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
            ),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE

    def test_failure_when_case_missing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            CheckCSFixNotYetDeployed(
                case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
            ),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE


class TestRMinStateDeferred:
    def test_success_when_deferred(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, rm=RM.DEFERRED)
        result = bt_scenario.run(
            RMinStateDeferred(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS

    def test_failure_when_accepted(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, rm=RM.ACCEPTED)
        result = bt_scenario.run(
            RMinStateDeferred(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE

    def test_failure_when_case_missing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            RMinStateDeferred(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# AC-4: CheckNoNewDeploymentInfoNode blackboard flag
# ---------------------------------------------------------------------------


class TestCheckNoNewDeploymentInfoNode:
    def test_success_when_flag_absent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Defaults SUCCESS when the blackboard key is absent (AC-4)."""
        result = bt_scenario.run(
            CheckNoNewDeploymentInfoNode(), actor_id=DEPLOYER_ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_success_when_flag_falsy(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            CheckNoNewDeploymentInfoNode(),
            actor_id=DEPLOYER_ACTOR_ID,
            **{NEW_DEPLOYMENT_INFO_KEY: False},
        )
        assert result.status == Status.SUCCESS

    def test_failure_when_flag_truthy(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """FAILURE when the sentinel wrote a truthy new-info flag."""
        result = bt_scenario.run(
            CheckNoNewDeploymentInfoNode(),
            actor_id=DEPLOYER_ACTOR_ID,
            **{NEW_DEPLOYMENT_INFO_KEY: True},
        )
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# AC-5: TransitionCStoFixDeployed + EmitCDActivity
# ---------------------------------------------------------------------------


class TestTransitionCStoFixDeployed:
    def test_success_and_creates_vfd_status(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFd)
        result_out: dict = {}
        node = TransitionCStoFixDeployed(
            case_id=CASE_ID,
            actor_id=DEPLOYER_ACTOR_ID,
            result_out=result_out,
        )
        result = bt_scenario.run(node, actor_id=DEPLOYER_ACTOR_ID)
        assert result.status == Status.SUCCESS
        assert "status_id" in result_out
        assert "participant_id" in result_out

    def test_failure_when_case_missing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            TransitionCStoFixDeployed(
                case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
            ),
            actor_id=DEPLOYER_ACTOR_ID,
        )
        assert result.status == Status.FAILURE

    def test_fix_deployed_logged_in_narrative_form(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
        caplog,
    ) -> None:
        """AC-13: the d→D transition reads as a CVD milestone at INFO.

        The narrative line comes from ``CreateParticipantStatusNode``, which is
        the only place that knows the VFd before-state; this node's own
        message is DEBUG detail (SL-04-007).
        """
        import logging

        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFd)
        node = TransitionCStoFixDeployed(
            case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, result_out={}
        )

        with caplog.at_level(logging.DEBUG):
            assert (
                bt_scenario.run(node, actor_id=DEPLOYER_ACTOR_ID).status
                == Status.SUCCESS
            )

        narrative = [
            r
            for r in caplog.records
            if " CS: " in r.getMessage() and r.levelno == logging.INFO
        ]
        assert narrative, "Expected a CS narrative line at INFO"
        message = narrative[0].getMessage()
        assert f"Actor '{DEPLOYER_ACTOR_ID}' CS: VFd → VFD" in message
        assert "(fix deployed)" in message

        detail = [
            r
            for r in caplog.records
            if "VFd → VFD (fix deployed)" in r.getMessage()
            and r.name.endswith("TransitionCStoFixDeployed")
        ]
        assert detail, "Expected the node's own detail line"
        assert all(r.levelno == logging.DEBUG for r in detail)


class TestEmitCDActivity:
    def test_success_emits_cd_activity(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer_and_case_manager: VultronCase,
    ) -> None:
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFd)
        result_out: dict = {}
        transition_node = TransitionCStoFixDeployed(
            case_id=CASE_ID,
            actor_id=DEPLOYER_ACTOR_ID,
            result_out=result_out,
        )
        tr = bt_scenario.run(transition_node, actor_id=DEPLOYER_ACTOR_ID)
        assert tr.status == Status.SUCCESS
        assert "status_id" in result_out

        emit_node = EmitCDActivity(
            case_id=CASE_ID,
            actor_id=DEPLOYER_ACTOR_ID,
            result_out=result_out,
        )
        result = bt_scenario.run(emit_node, actor_id=DEPLOYER_ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_failure_when_result_out_empty(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        node = EmitCDActivity(
            case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, result_out={}
        )
        result = bt_scenario.run(node, actor_id=DEPLOYER_ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_failure_when_no_case_manager(
        self,
        bt_scenario: BTTestScenario,
        case_with_deployer: VultronCase,
    ) -> None:
        _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFd)
        result_out: dict = {}
        transition_node = TransitionCStoFixDeployed(
            case_id=CASE_ID,
            actor_id=DEPLOYER_ACTOR_ID,
            result_out=result_out,
        )
        bt_scenario.run(transition_node, actor_id=DEPLOYER_ACTOR_ID)

        emit_node = EmitCDActivity(
            case_id=CASE_ID,
            actor_id=DEPLOYER_ACTOR_ID,
            result_out=result_out,
        )
        result = bt_scenario.run(emit_node, actor_id=DEPLOYER_ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# AC-7: Early-exit arm short-circuits the deploy/monitor arms
# ---------------------------------------------------------------------------


def test_early_exit_when_fix_already_deployed(
    bt_scenario: BTTestScenario,
    case_with_deployer_and_case_manager: VultronCase,
) -> None:
    """Fix already deployed → CSinStateFixDeployed SUCCESS → Fallback succeeds.

    The deploy arm's TransitionCStoFixDeployed must NOT run (no duplicate
    status). We assert SUCCESS and that no new VFD status was appended.
    """
    _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFD)
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VultronCase)
    participant_id = case.actor_participant_index[DEPLOYER_ACTOR_ID]
    participant = bt_scenario.dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    before = len(participant.participant_statuses)

    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    result = bt_scenario.run(tree, actor_id=DEPLOYER_ACTOR_ID)
    assert result.status == Status.SUCCESS

    participant = bt_scenario.dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    assert len(participant.participant_statuses) == before


def test_stay_deferred_short_circuits(
    bt_scenario: BTTestScenario,
    case_with_deployer: VultronCase,
) -> None:
    """Deferred deployer, no new info → _ShouldStayInRmDeferred SUCCESS.

    Asserts SUCCESS *and* that no VFD status was appended — proving arm 2
    (stay-deferred) produced the SUCCESS, not the always-succeeding monitor
    arm masking a broken deploy arm.
    """
    _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, rm=RM.DEFERRED)
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VultronCase)
    participant_id = case.actor_participant_index[DEPLOYER_ACTOR_ID]
    participant = bt_scenario.dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    before = len(participant.participant_statuses)

    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    result = bt_scenario.run(tree, actor_id=DEPLOYER_ACTOR_ID)
    assert result.status == Status.SUCCESS

    # No deployment side effects: the deploy arm must not have run.
    participant = bt_scenario.dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    assert len(participant.participant_statuses) == before
    assert bt_scenario.dl.outbox_list() == []


def test_full_deploy_arm_completes_and_emits_cd(
    bt_scenario: BTTestScenario,
    case_with_deployer_and_case_manager: VultronCase,
) -> None:
    """Deployer, RM ACCEPTED, fix ready-not-deployed, DeployFix SUCCEEDS.

    Injects ``deploy_fix_factory=AlwaysSucceed`` so the ``_DeployFixIfReady``
    Sequence runs to completion (guards pass → PrioritizeDeployment → DeployFix
    → TransitionCStoFixDeployed → EmitCDActivity).  Asserts the deploy arm's
    two production action nodes actually fired: a new VFD ``ParticipantStatus``
    was appended and a CD activity was queued to the deployer's outbox.

    This is the integration coverage the DETERMINISTIC default cannot provide
    (its ``deploy_fix_factory`` is AlwaysFail, so the arm never reaches the
    transition/emit nodes).
    """
    _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFd)
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VultronCase)
    participant_id = case.actor_participant_index[DEPLOYER_ACTOR_ID]
    participant = bt_scenario.dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    before = len(participant.participant_statuses)

    bundle = DeployFixCallOutBundle(
        deploy_fix_factory=lambda n: AlwaysSucceed(n),  # type: ignore[arg-type]
    )
    tree = create_deploy_fix_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, call_out=bundle
    )
    result = bt_scenario.run(tree, actor_id=DEPLOYER_ACTOR_ID)
    assert result.status == Status.SUCCESS

    # TransitionCStoFixDeployed appended a new VFD (fix-deployed) status.
    participant = bt_scenario.dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    assert len(participant.participant_statuses) == before + 1
    assert participant.participant_statuses[-1].vfd.state == CS_vfd.VFD

    # EmitCDActivity queued a CD activity to the deployer's outbox.
    outbox = bt_scenario.dl.outbox_list()
    assert len(outbox) == 1


def test_deploy_arm_falls_through_to_monitor_when_deployfix_fails(
    bt_scenario: BTTestScenario,
    case_with_deployer_and_case_manager: VultronCase,
) -> None:
    """DETERMINISTIC DeployFix=AlwaysFail → deploy arm fails, monitor arm wins.

    Documents the default-bundle behavior: the deploy arm fails at DeployFix
    (before the transition/emit nodes), so no VFD status is written, and the
    overall SUCCESS comes from the always-succeeding monitor arm.
    """
    _seed_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, vfd=CS_vfd.VFd)
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VultronCase)
    participant_id = case.actor_participant_index[DEPLOYER_ACTOR_ID]
    participant = bt_scenario.dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    before = len(participant.participant_statuses)

    tree = create_deploy_fix_tree(case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID)
    result = bt_scenario.run(tree, actor_id=DEPLOYER_ACTOR_ID)
    assert result.status == Status.SUCCESS

    # DeployFix (AlwaysFail) short-circuited the arm before the transition node.
    participant = bt_scenario.dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    assert len(participant.participant_statuses) == before
    assert bt_scenario.dl.outbox_list() == []
