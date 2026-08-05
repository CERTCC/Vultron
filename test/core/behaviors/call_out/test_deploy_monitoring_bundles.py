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
"""Unit tests for DeploymentMonitoringBundle, DeployFixCallOutBundle,
and DeployMitigationCallOutBundle (AC-1 through AC-5, BT-23-002).

Covers:
- AC-1: DeploymentMonitoringBundle has the three shared fields with correct defaults.
- AC-2: DeployFixCallOutBundle inherits DeploymentMonitoringBundle; existing tests green.
- AC-3: DeployMitigationCallOutBundle(DeploymentMonitoringBundle) has the three
  additional fields; DEPLOY_MITIGATION_DETERMINISTIC singleton exists.
- AC-4: DEPLOY_MITIGATION_STOCHASTIC wires the three fuzzer nodes.
- AC-5: Unit tests for field defaults, DETERMINISTIC singleton, inheritance chain.
"""

import dataclasses

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.call_out import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.call_out.bundles.deploy_fix import (
    DEPLOY_FIX_DETERMINISTIC,
    DeployFixCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.deploy_mitigation import (
    DEPLOY_MITIGATION_DETERMINISTIC,
    DeployMitigationCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.deploy_monitoring import (
    DeploymentMonitoringBundle,
)

# ---------------------------------------------------------------------------
# AC-1: DeploymentMonitoringBundle — three shared fields, correct defaults
# ---------------------------------------------------------------------------


class TestDeploymentMonitoringBundle:
    def test_is_frozen_dataclass(self):
        bundle = DeploymentMonitoringBundle()
        assert dataclasses.is_dataclass(bundle)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            bundle.prioritize_deployment_factory = None  # type: ignore[misc]

    def test_has_three_fields(self):
        fields = {
            f.name for f in dataclasses.fields(DeploymentMonitoringBundle)
        }
        assert fields == {
            "prioritize_deployment_factory",
            "monitoring_requirement_factory",
            "monitor_deployment_factory",
        }

    def test_prioritize_deployment_defaults_to_always_succeed(self):
        b = DeploymentMonitoringBundle()
        node = b.prioritize_deployment_factory("probe")
        assert isinstance(node, AlwaysSucceed)

    def test_monitoring_requirement_defaults_to_always_succeed(self):
        b = DeploymentMonitoringBundle()
        node = b.monitoring_requirement_factory("probe")
        assert isinstance(node, AlwaysSucceed)

    def test_monitor_deployment_defaults_to_always_succeed(self):
        b = DeploymentMonitoringBundle()
        node = b.monitor_deployment_factory("probe")
        assert isinstance(node, AlwaysSucceed)

    def test_all_default_nodes_tick_to_success(self):
        b = DeploymentMonitoringBundle()
        for factory in [
            b.prioritize_deployment_factory,
            b.monitoring_requirement_factory,
            b.monitor_deployment_factory,
        ]:
            node = factory("probe")
            node.tick_once()
            assert node.status == Status.SUCCESS

    def test_all_default_nodes_are_py_trees_behaviours(self):
        b = DeploymentMonitoringBundle()
        for factory in [
            b.prioritize_deployment_factory,
            b.monitoring_requirement_factory,
            b.monitor_deployment_factory,
        ]:
            assert isinstance(factory("probe"), py_trees.behaviour.Behaviour)


# ---------------------------------------------------------------------------
# AC-2: DeployFixCallOutBundle inherits DeploymentMonitoringBundle
# ---------------------------------------------------------------------------


class TestDeployFixCallOutBundleInheritance:
    def test_inherits_deployment_monitoring_bundle(self):
        assert issubclass(DeployFixCallOutBundle, DeploymentMonitoringBundle)

    def test_has_deploy_fix_factory_field(self):
        fields = {f.name for f in dataclasses.fields(DeployFixCallOutBundle)}
        assert "deploy_fix_factory" in fields

    def test_inherited_fields_still_present(self):
        fields = {f.name for f in dataclasses.fields(DeployFixCallOutBundle)}
        assert {
            "prioritize_deployment_factory",
            "monitoring_requirement_factory",
            "monitor_deployment_factory",
        }.issubset(fields)

    def test_deploy_fix_defaults_to_always_fail(self):
        node = DEPLOY_FIX_DETERMINISTIC.deploy_fix_factory("probe")
        assert isinstance(node, AlwaysFail)
        node.tick_once()
        assert node.status == Status.FAILURE

    def test_deterministic_singleton_is_instance_of_bundle(self):
        assert isinstance(DEPLOY_FIX_DETERMINISTIC, DeployFixCallOutBundle)

    def test_deterministic_singleton_is_instance_of_base(self):
        assert isinstance(DEPLOY_FIX_DETERMINISTIC, DeploymentMonitoringBundle)

    def test_deterministic_singleton_is_frozen(self):
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            DEPLOY_FIX_DETERMINISTIC.deploy_fix_factory = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AC-3: DeployMitigationCallOutBundle — three additional fields
# ---------------------------------------------------------------------------


class TestDeployMitigationCallOutBundle:
    def test_inherits_deployment_monitoring_bundle(self):
        assert issubclass(
            DeployMitigationCallOutBundle, DeploymentMonitoringBundle
        )

    def test_is_frozen_dataclass(self):
        bundle = DeployMitigationCallOutBundle()
        assert dataclasses.is_dataclass(bundle)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            bundle.mitigation_deployed_factory = None  # type: ignore[misc]

    def test_has_six_fields(self):
        fields = {
            f.name for f in dataclasses.fields(DeployMitigationCallOutBundle)
        }
        assert fields == {
            "prioritize_deployment_factory",
            "monitoring_requirement_factory",
            "monitor_deployment_factory",
            "mitigation_deployed_factory",
            "mitigation_available_factory",
            "deploy_mitigation_factory",
        }

    def test_mitigation_deployed_defaults_to_always_fail(self):
        node = DEPLOY_MITIGATION_DETERMINISTIC.mitigation_deployed_factory(
            "probe"
        )
        assert isinstance(node, AlwaysFail)
        node.tick_once()
        assert node.status == Status.FAILURE

    def test_mitigation_available_defaults_to_always_succeed(self):
        node = DEPLOY_MITIGATION_DETERMINISTIC.mitigation_available_factory(
            "probe"
        )
        assert isinstance(node, AlwaysSucceed)
        node.tick_once()
        assert node.status == Status.SUCCESS

    def test_deploy_mitigation_defaults_to_always_succeed(self):
        node = DEPLOY_MITIGATION_DETERMINISTIC.deploy_mitigation_factory(
            "probe"
        )
        assert isinstance(node, AlwaysSucceed)
        node.tick_once()
        assert node.status == Status.SUCCESS

    def test_inherited_fields_use_always_succeed(self):
        for factory in [
            DEPLOY_MITIGATION_DETERMINISTIC.prioritize_deployment_factory,
            DEPLOY_MITIGATION_DETERMINISTIC.monitoring_requirement_factory,
            DEPLOY_MITIGATION_DETERMINISTIC.monitor_deployment_factory,
        ]:
            node = factory("probe")
            assert isinstance(node, AlwaysSucceed)

    def test_deterministic_singleton_is_instance_of_bundle(self):
        assert isinstance(
            DEPLOY_MITIGATION_DETERMINISTIC, DeployMitigationCallOutBundle
        )

    def test_deterministic_singleton_is_instance_of_base(self):
        assert isinstance(
            DEPLOY_MITIGATION_DETERMINISTIC, DeploymentMonitoringBundle
        )

    def test_deterministic_singleton_is_frozen(self):
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            DEPLOY_MITIGATION_DETERMINISTIC.deploy_mitigation_factory = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AC-4: DEPLOY_MITIGATION_STOCHASTIC wires the three fuzzer nodes
# ---------------------------------------------------------------------------


class TestDeployMitigationStochasticBundle:
    @pytest.fixture
    def stochastic(self):
        from vultron.demo.fuzzer.bundles.deploy_mitigation import (
            DEPLOY_MITIGATION_STOCHASTIC,
        )

        return DEPLOY_MITIGATION_STOCHASTIC

    def test_stochastic_is_instance_of_bundle(self, stochastic):
        assert isinstance(stochastic, DeployMitigationCallOutBundle)

    def test_mitigation_deployed_is_fuzzer_node(self, stochastic):
        from vultron.demo.fuzzer.report_management.deploy_fix import (
            MitigationDeployed,
        )

        node = stochastic.mitigation_deployed_factory("probe")
        assert isinstance(node, MitigationDeployed)

    def test_mitigation_available_is_fuzzer_node(self, stochastic):
        from vultron.demo.fuzzer.report_management.deploy_fix import (
            MitigationAvailable,
        )

        node = stochastic.mitigation_available_factory("probe")
        assert isinstance(node, MitigationAvailable)

    def test_deploy_mitigation_is_fuzzer_node(self, stochastic):
        from vultron.demo.fuzzer.report_management.deploy_fix import (
            DeployMitigation,
        )

        node = stochastic.deploy_mitigation_factory("probe")
        assert isinstance(node, DeployMitigation)

    def test_prioritize_deployment_is_fuzzer_node(self, stochastic):
        from vultron.demo.fuzzer.report_management.deploy_fix import (
            PrioritizeDeployment,
        )

        node = stochastic.prioritize_deployment_factory("probe")
        assert isinstance(node, PrioritizeDeployment)

    def test_monitoring_requirement_is_fuzzer_node(self, stochastic):
        from vultron.demo.fuzzer.report_management.deploy_fix import (
            MonitoringRequirement,
        )

        node = stochastic.monitoring_requirement_factory("probe")
        assert isinstance(node, MonitoringRequirement)

    def test_monitor_deployment_is_fuzzer_node(self, stochastic):
        from vultron.demo.fuzzer.report_management.deploy_fix import (
            MonitorDeployment,
        )

        node = stochastic.monitor_deployment_factory("probe")
        assert isinstance(node, MonitorDeployment)

    def test_stochastic_is_frozen(self, stochastic):
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            stochastic.mitigation_deployed_factory = None  # type: ignore[misc]
