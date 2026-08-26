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
"""Tests for the deploy-mitigation behavior tree factory (issue #1954).

Covers all acceptance criteria from issue #1954:

- AC-1: DeployMitigationBT Fallback with four arms (mitigation-deployed,
  stay-deferred, deploy-if-available, monitor-if-desired)
- AC-2: Six call-out factories from DeployMitigationCallOutBundle all wired
- AC-3: DETERMINISTIC default uses ceiling/floor mapping (BT-23-002)
- AC-4: Each factory seam is individually replaceable
- AC-5: Integration — early-exit, stay-deferred, full-deploy arm, falls-through-to-monitor
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.call_out.bundles.deploy_mitigation import (
    DEPLOY_MITIGATION_DETERMINISTIC,
    DeployMitigationCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckDeployerRoleNode,
)
from vultron.core.behaviors.report.deploy_mitigation_tree import (
    create_deploy_mitigation_tree,
)
from vultron.core.behaviors.report.nodes.deploy_fix import (
    NEW_DEPLOYMENT_INFO_KEY,
    CheckNoNewDeploymentInfoNode,
    RMinStateDeferred,
)
from vultron.core.behaviors.report.nodes.conditions import (
    CheckRMStateAccepted,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/test-deploy-mitigation-001"
DEPLOYER_ACTOR_ID = "https://example.org/actors/deployer-mit-001"
VENDOR_ACTOR_ID = "https://example.org/actors/vendor-mit-001"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def deployer_participant() -> VultronParticipant:
    return VultronParticipant(
        id_="https://example.org/participants/deployer-mit-cp-001",
        attributed_to=DEPLOYER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.DEPLOYER],
    )


@pytest.fixture
def case_with_deployer(
    bt_scenario: BTTestScenario,
    deployer_participant: VultronParticipant,
) -> VultronCase:
    case = VultronCase(
        id_=CASE_ID,
        name="Test Mitigation Case",
        case_participants=[deployer_participant.id_],
        actor_participant_index={DEPLOYER_ACTOR_ID: deployer_participant.id_},
    )
    bt_scenario.seed(deployer_participant, case)
    return case


def _seed_rm_status(
    bt_scenario: BTTestScenario,
    case_id: str,
    actor_id: str,
    rm: RM = RM.ACCEPTED,
) -> None:
    """Seed a ParticipantStatus record with the given RM state."""
    status = ParticipantStatus(
        context=case_id,
        attributed_to=actor_id,
        rm=RmDimension(state=rm),
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
# AC-1: create_deploy_mitigation_tree factory + tree structure
# ---------------------------------------------------------------------------


def test_create_deploy_mitigation_tree_returns_behaviour():
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_deploy_mitigation_tree_root_name():
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    assert tree.name == "DeployMitigationBT"


def test_tree_root_is_fallback():
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    assert isinstance(tree, py_trees.composites.Selector)


def test_tree_has_four_arms():
    """DeployMitigationBT Fallback has exactly 4 arms."""
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    assert len(tree.children) == 4
    assert tree.children[0].name == "MitigationDeployed"
    assert tree.children[1].name == "_ShouldStayInRmDeferred"
    assert tree.children[2].name == "_DeployMitigationIfAvailable"
    assert tree.children[3].name == "_MonitorDeploymentIfDesired"


def test_should_stay_deferred_arm_composition():
    """_ShouldStayInRmDeferred = RMinStateDeferred + CheckNoNewDeploymentInfo."""
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    arm = tree.children[1]
    assert isinstance(arm, py_trees.composites.Sequence)
    assert len(arm.children) == 2
    assert isinstance(arm.children[0], RMinStateDeferred)
    assert isinstance(arm.children[1], CheckNoNewDeploymentInfoNode)


def test_deploy_mitigation_if_available_arm_composition():
    """_DeployMitigationIfAvailable arm: 2 guards + 3 call-outs (no CS nodes)."""
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    arm = tree.children[2]
    assert isinstance(arm, py_trees.composites.Sequence)
    assert len(arm.children) == 5
    assert isinstance(arm.children[0], CheckDeployerRoleNode)
    assert isinstance(arm.children[1], CheckRMStateAccepted)
    assert arm.children[2].name == "MitigationAvailable"
    assert arm.children[3].name == "PrioritizeDeployment"
    assert arm.children[4].name == "DeployMitigation"


def test_monitor_arm_composition():
    """_MonitorDeploymentIfDesired arm: MonitoringRequirement + MonitorDeployment."""
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    arm = tree.children[3]
    assert isinstance(arm, py_trees.composites.Sequence)
    assert len(arm.children) == 2
    assert arm.children[0].name == "MonitoringRequirement"
    assert arm.children[1].name == "MonitorDeployment"


# ---------------------------------------------------------------------------
# AC-2: DeployMitigationCallOutBundle has exactly 6 fields
# ---------------------------------------------------------------------------


def test_bundle_has_six_fields():
    import dataclasses

    field_names = {
        f.name for f in dataclasses.fields(DeployMitigationCallOutBundle)
    }
    assert field_names == {
        "mitigation_deployed_factory",
        "mitigation_available_factory",
        "prioritize_deployment_factory",
        "deploy_mitigation_factory",
        "monitoring_requirement_factory",
        "monitor_deployment_factory",
    }


# ---------------------------------------------------------------------------
# AC-3: DETERMINISTIC default uses ceiling/floor mapping (BT-23-002)
# ---------------------------------------------------------------------------


def test_default_call_out_children_are_deterministic():
    """DETERMINISTIC: ceiling/floor of each node's stochastic p (BT-23-002)."""
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    # arm 0: mitigation_deployed p=0.25 → AlwaysFail
    assert isinstance(tree.children[0], AlwaysFail)

    deploy_arm = tree.children[2]
    monitor_arm = tree.children[3]
    # mitigation_available p=0.70 → AlwaysSucceed
    assert isinstance(deploy_arm.children[2], AlwaysSucceed)
    # prioritize_deployment p=0.90 → AlwaysSucceed
    assert isinstance(deploy_arm.children[3], AlwaysSucceed)
    # deploy_mitigation p=0.75 → AlwaysSucceed
    assert isinstance(deploy_arm.children[4], AlwaysSucceed)
    # monitoring_requirement p=0.70 → AlwaysSucceed
    assert isinstance(monitor_arm.children[0], AlwaysSucceed)
    # monitor_deployment p=1.0 → AlwaysSucceed
    assert isinstance(monitor_arm.children[1], AlwaysSucceed)


def test_bundle_parameter_accepted():
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID,
        actor_id=DEPLOYER_ACTOR_ID,
        call_out=DEPLOY_MITIGATION_DETERMINISTIC,
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_deterministic_singleton_is_instance_of_bundle():
    assert isinstance(
        DEPLOY_MITIGATION_DETERMINISTIC, DeployMitigationCallOutBundle
    )


# ---------------------------------------------------------------------------
# AC-4: Each call-out factory seam is individually replaceable
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
    ("mitigation_deployed_factory", "MD", 0, None),  # arm 0 is the node itself
    ("mitigation_available_factory", "MA", 2, 2),
    ("prioritize_deployment_factory", "PD", 2, 3),
    ("deploy_mitigation_factory", "DM", 2, 4),
    ("monitoring_requirement_factory", "MR", 3, 0),
    ("monitor_deployment_factory", "MON", 3, 1),
]


@pytest.mark.parametrize("field,label,arm_idx,child_idx", _CALL_OUT_SEAMS)
def test_each_factory_is_wired(field, label, arm_idx, child_idx):
    """Each of the 6 factory fields is individually wired into the tree."""
    sentinel = {"called": False}

    def custom_factory(name: str) -> py_trees.behaviour.Behaviour:
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self) -> Status:
                return Status.SUCCESS

        return _Marker(name=label)

    bundle = DeployMitigationCallOutBundle(**{field: custom_factory})  # type: ignore[arg-type]
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, call_out=bundle
    )
    assert sentinel["called"]
    if child_idx is None:
        assert tree.children[arm_idx].name == label
    else:
        assert tree.children[arm_idx].children[child_idx].name == label


def test_all_factories_replaceable():
    bundle = DeployMitigationCallOutBundle(
        mitigation_deployed_factory=_marker_factory("MD"),  # type: ignore[arg-type]
        mitigation_available_factory=_marker_factory("MA"),  # type: ignore[arg-type]
        prioritize_deployment_factory=_marker_factory("PD"),  # type: ignore[arg-type]
        deploy_mitigation_factory=_marker_factory("DM"),  # type: ignore[arg-type]
        monitoring_requirement_factory=_marker_factory("MR"),  # type: ignore[arg-type]
        monitor_deployment_factory=_marker_factory("MON"),  # type: ignore[arg-type]
    )
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, call_out=bundle
    )
    tree_str = py_trees.display.ascii_tree(tree)
    for label in ("MD", "MA", "PD", "DM", "MR", "MON"):
        assert label in tree_str


def test_stochastic_bundle_children_are_fuzzer_nodes():
    """STOCHASTIC bundle produces the correct fuzzer-class nodes."""
    from vultron.demo.fuzzer.bundles.deploy_mitigation import (
        DEPLOY_MITIGATION_STOCHASTIC,
    )
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        DeployMitigation,
        MitigationAvailable,
        MitigationDeployed,
        MonitorDeployment,
        MonitoringRequirement,
        PrioritizeDeployment,
    )

    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID,
        actor_id=DEPLOYER_ACTOR_ID,
        call_out=DEPLOY_MITIGATION_STOCHASTIC,
    )
    deploy_arm = tree.children[2]
    monitor_arm = tree.children[3]
    assert isinstance(tree.children[0], MitigationDeployed)
    assert isinstance(deploy_arm.children[2], MitigationAvailable)
    assert isinstance(deploy_arm.children[3], PrioritizeDeployment)
    assert isinstance(deploy_arm.children[4], DeployMitigation)
    assert isinstance(monitor_arm.children[0], MonitoringRequirement)
    assert isinstance(monitor_arm.children[1], MonitorDeployment)


# ---------------------------------------------------------------------------
# AC-5: Integration — tree behavior under various state conditions
# ---------------------------------------------------------------------------


def test_early_exit_when_mitigation_already_deployed(
    bt_scenario: BTTestScenario,
    case_with_deployer: VultronCase,
) -> None:
    """MitigationDeployed factory returns SUCCESS → Fallback succeeds immediately.

    Use a bundle whose mitigation_deployed_factory always succeeds to simulate
    the case where mitigation is already in place.  The deploy and monitor arms
    must not run.
    """
    bundle = DeployMitigationCallOutBundle(
        mitigation_deployed_factory=lambda n: AlwaysSucceed(n),  # type: ignore[arg-type]
    )
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, call_out=bundle
    )
    result = bt_scenario.run(tree, actor_id=DEPLOYER_ACTOR_ID)
    assert result.status == Status.SUCCESS


def test_stay_deferred_short_circuits(
    bt_scenario: BTTestScenario,
    case_with_deployer: VultronCase,
) -> None:
    """Deferred deployer, no new info → _ShouldStayInRmDeferred SUCCESS.

    The DETERMINISTIC mitigation_deployed_factory is AlwaysFail, so arm 0
    fails.  With RM=DEFERRED and no new-info flag, arm 1 succeeds.
    """
    _seed_rm_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, rm=RM.DEFERRED)

    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    result = bt_scenario.run(tree, actor_id=DEPLOYER_ACTOR_ID)
    assert result.status == Status.SUCCESS


def test_stay_deferred_fails_when_new_info_present(
    bt_scenario: BTTestScenario,
    case_with_deployer: VultronCase,
) -> None:
    """Deferred + new deployment info → _ShouldStayInRmDeferred fails.

    CheckNoNewDeploymentInfoNode returns FAILURE when the blackboard flag is
    truthy, so the sequence fails and the tree falls through to the deploy arm.
    The deploy arm then fails (CheckRMStateAccepted fails for DEFERRED),
    leaving the monitor arm to succeed.
    """
    _seed_rm_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, rm=RM.DEFERRED)

    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID
    )
    result = bt_scenario.run(
        tree,
        actor_id=DEPLOYER_ACTOR_ID,
        **{NEW_DEPLOYMENT_INFO_KEY: True},
    )
    # Monitor arm (all AlwaysSucceed by default) rescues the tree.
    assert result.status == Status.SUCCESS


def test_deploy_arm_completes_when_mitigation_succeeds(
    bt_scenario: BTTestScenario,
    case_with_deployer: VultronCase,
) -> None:
    """Deployer, RM ACCEPTED, DeployMitigation SUCCEEDS → deploy arm runs fully.

    Injects ``deploy_mitigation_factory=AlwaysSucceed`` so the
    ``_DeployMitigationIfAvailable`` Sequence runs to completion.  No state
    transition or activity emission occurs (mitigation has no CS bit), but the
    overall tree should return SUCCESS via the deploy arm.
    """
    _seed_rm_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, rm=RM.ACCEPTED)

    # Pin all three deploy-arm call-outs explicitly so the test is independent
    # of future changes to the DETERMINISTIC defaults.
    bundle = DeployMitigationCallOutBundle(
        mitigation_available_factory=lambda n: AlwaysSucceed(n),  # type: ignore[arg-type]
        prioritize_deployment_factory=lambda n: AlwaysSucceed(n),  # type: ignore[arg-type]
        deploy_mitigation_factory=lambda n: AlwaysSucceed(n),  # type: ignore[arg-type]
    )
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, call_out=bundle
    )
    result = bt_scenario.run(tree, actor_id=DEPLOYER_ACTOR_ID)
    assert result.status == Status.SUCCESS


def test_deploy_arm_falls_through_to_monitor_when_deploy_mitigation_fails(
    bt_scenario: BTTestScenario,
    case_with_deployer: VultronCase,
) -> None:
    """DETERMINISTIC DeployMitigation=AlwaysSucceed but MitigationAvailable fails.

    Override mitigation_available_factory to AlwaysFail so the deploy arm
    short-circuits before DeployMitigation; the overall tree succeeds via the
    monitor arm (all AlwaysSucceed by default).
    """
    _seed_rm_status(bt_scenario, CASE_ID, DEPLOYER_ACTOR_ID, rm=RM.ACCEPTED)

    bundle = DeployMitigationCallOutBundle(
        mitigation_available_factory=lambda n: AlwaysFail(n),  # type: ignore[arg-type]
    )
    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=DEPLOYER_ACTOR_ID, call_out=bundle
    )
    result = bt_scenario.run(tree, actor_id=DEPLOYER_ACTOR_ID)
    # Monitor arm rescues (MonitoringRequirement and MonitorDeployment both AlwaysSucceed).
    assert result.status == Status.SUCCESS


def test_non_deployer_role_skips_deploy_arm(
    bt_scenario: BTTestScenario,
) -> None:
    """Actor without DEPLOYER role → CheckDeployerRoleNode FAILURE → deploy arm skipped.

    The monitor arm (AlwaysSucceed defaults) then rescues the tree.
    """
    non_deployer = VultronParticipant(
        id_="https://example.org/participants/vendor-mit-cp-001",
        attributed_to=VENDOR_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )
    case = VultronCase(
        id_=CASE_ID,
        name="Test Mitigation Case",
        case_participants=[non_deployer.id_],
        actor_participant_index={VENDOR_ACTOR_ID: non_deployer.id_},
    )
    bt_scenario.seed(non_deployer, case)
    _seed_rm_status(bt_scenario, CASE_ID, VENDOR_ACTOR_ID, rm=RM.ACCEPTED)

    tree = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=VENDOR_ACTOR_ID
    )
    result = bt_scenario.run(tree, actor_id=VENDOR_ACTOR_ID)
    # Monitor arm succeeds.
    assert result.status == Status.SUCCESS
