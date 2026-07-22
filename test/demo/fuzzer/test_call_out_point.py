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
"""Tests for vultron.demo.fuzzer.call_out_point and related exemplars.

Verifies:
- CallOutBackendFactory type alias is importable and callable (BT-18-004)
- Five shape mixin classes are importable
- Each exemplar node subclasses the correct shape mixin (BT-18-001)
- Exemplar nodes that declare output_keys write to the blackboard on SUCCESS
  (BT-18-002, BT-18-003)
- NewValidationInfoSentinel is a valid Behaviour with correct success_rate
"""

import pytest
import py_trees
from py_trees.common import Status

from vultron.core.behaviors.call_out_point import CallOutBackendFactory
from vultron.demo.fuzzer.call_out_point import (
    ActuatorCallOutPoint,
    ComposerCallOutPoint,
    EvaluatorCallOutPoint,
    NewDeploymentInfoSentinel,
    NewPrioritizationInfoSentinel,
    NewValidationInfoSentinel,
    RetrieverCallOutPoint,
    SentinelCallOutPoint,
)
from vultron.demo.fuzzer.report_management.prioritize import OnAccept, OnDefer
from vultron.demo.fuzzer.report_management.publication import PrepareReport
from vultron.demo.fuzzer.embargo import (
    CurrentEmbargoAcceptable,
    EmbargoTimerExpired,
    EvaluateEmbargoProposal,
    ExitEmbargoForOtherReason,
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    OnEmbargoAccept,
    OnEmbargoExit,
    OnEmbargoReject,
    ReasonToProposeEmbargoWhenDeployed,
    SelectEmbargoOfferTerms,
    StopProposingEmbargo,
    WantToProposeEmbargo,
    WillingToCounterEmbargoProposal,
)
from vultron.demo.fuzzer.messaging import FollowUpOnErrorMessage
from vultron.demo.fuzzer.report_management.acquire_exploit import (
    DevelopExploit,
    EvaluateExploitPriority,
    FindExploit,
    HaveExploit,
    PurchaseExploit,
)
from vultron.demo.fuzzer.report_management.assign_vul_id import (
    AssignId,
    IdAssignable,
    IdAssigned,
    InScope,
    RequestId,
)
from vultron.demo.fuzzer.report_management.close_report import (
    OtherCloseCriteriaMet,
    PreCloseAction,
)
from vultron.demo.fuzzer.report_management.deploy_fix import (
    DeployFix,
    DeployMitigation,
    MitigationAvailable,
    MitigationDeployed,
    MonitorDeployment,
    MonitoringRequirement,
    PrioritizeDeployment,
)
from vultron.demo.fuzzer.report_management.develop_fix import CreateFix
from vultron.demo.fuzzer.report_management.monitor_threats import (
    MonitorAttacks,
    MonitorExploits,
    MonitorPublicReports,
)
from vultron.demo.fuzzer.report_management.prioritize import (
    EnoughPrioritizationInfo,
    GatherPrioritizationInfo,
)
from vultron.demo.fuzzer.report_management.publication import (
    PrepareExploit,
    PrepareFix,
    Publish,
    ReprioritizeExploit,
    ReprioritizeFix,
    ReprioritizeReport,
)
from vultron.demo.fuzzer.report_management.report_to_others import (
    AllPartiesKnown,
    ChooseRecipient,
    IdentifyCoordinators,
    IdentifyVendors,
    InjectCoordinator,
    InjectOther,
    InjectParticipant,
    InjectVendor,
    PolicyCompatible,
    RecipientEffortExceeded,
    RemoveRecipient,
    SetRcptQrmR,
    TotalEffortLimitMet,
)
from vultron.demo.fuzzer.report_management.validate import (
    EvaluateReportCredibility,
    EvaluateReportValidity,
    GatherValidationInfo,
)


@pytest.fixture(autouse=True)
def clear_blackboard():
    """Clear py_trees global blackboard state between tests."""
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


# ---------------------------------------------------------------------------
# CallOutBackendFactory type alias
# ---------------------------------------------------------------------------


def test_call_out_backend_factory_importable():
    assert CallOutBackendFactory is not None


def test_call_out_backend_factory_is_callable_type():
    """A factory matching the signature satisfies the type alias."""

    def factory(n):
        return EvaluateReportCredibility(n)

    node = factory("TestNode")
    assert isinstance(node, py_trees.behaviour.Behaviour)
    assert node.name == "TestNode"


# ---------------------------------------------------------------------------
# Shape mixin imports
# ---------------------------------------------------------------------------


def test_evaluator_mixin_importable():
    assert EvaluatorCallOutPoint is not None


def test_retriever_mixin_importable():
    assert RetrieverCallOutPoint is not None


def test_composer_mixin_importable():
    assert ComposerCallOutPoint is not None


def test_actuator_mixin_importable():
    assert ActuatorCallOutPoint is not None


def test_sentinel_mixin_importable():
    assert SentinelCallOutPoint is not None


# ---------------------------------------------------------------------------
# Shape hierarchy — exemplar nodes subclass correct mixin
# ---------------------------------------------------------------------------


def test_evaluate_report_credibility_is_evaluator():
    assert issubclass(EvaluateReportCredibility, EvaluatorCallOutPoint)


def test_evaluate_report_validity_is_evaluator():
    assert issubclass(EvaluateReportValidity, EvaluatorCallOutPoint)


def test_gather_validation_info_is_retriever():
    assert issubclass(GatherValidationInfo, RetrieverCallOutPoint)


def test_on_accept_is_actuator():
    assert issubclass(OnAccept, ActuatorCallOutPoint)


def test_on_defer_is_actuator():
    assert issubclass(OnDefer, ActuatorCallOutPoint)


def test_prepare_report_is_composer():
    assert issubclass(PrepareReport, ComposerCallOutPoint)


def test_new_validation_info_sentinel_is_sentinel():
    assert issubclass(NewValidationInfoSentinel, SentinelCallOutPoint)


def test_new_prioritization_info_sentinel_is_sentinel():
    assert issubclass(NewPrioritizationInfoSentinel, SentinelCallOutPoint)


def test_new_deployment_info_sentinel_is_sentinel():
    assert issubclass(NewDeploymentInfoSentinel, SentinelCallOutPoint)


# ---------------------------------------------------------------------------
# All exemplar nodes are py_trees Behaviours
# ---------------------------------------------------------------------------


_ALL_EXEMPLARS = [
    EvaluateReportCredibility,
    EvaluateReportValidity,
    GatherValidationInfo,
    OnAccept,
    OnDefer,
    PrepareReport,
    NewValidationInfoSentinel,
    NewPrioritizationInfoSentinel,
    NewDeploymentInfoSentinel,
]


@pytest.mark.parametrize("node_cls", _ALL_EXEMPLARS)
def test_exemplar_is_behaviour(node_cls):
    node = node_cls()
    assert isinstance(node, py_trees.behaviour.Behaviour)


@pytest.mark.parametrize("node_cls", _ALL_EXEMPLARS)
def test_exemplar_has_blackboard_contract_docstring(node_cls):
    """Exemplar docstring must contain the BT-18-001 blackboard contract."""
    assert node_cls.__doc__ and "Blackboard contract" in node_cls.__doc__


# ---------------------------------------------------------------------------
# Sentinel — success_rate and no output_keys
# ---------------------------------------------------------------------------


def test_new_validation_info_sentinel_success_rate():
    assert NewValidationInfoSentinel.success_rate == pytest.approx(0.10)


def test_new_validation_info_sentinel_output_keys_empty():
    assert NewValidationInfoSentinel.output_keys == {}


def test_new_prioritization_info_sentinel_success_rate():
    assert NewPrioritizationInfoSentinel.success_rate == pytest.approx(0.10)


def test_new_prioritization_info_sentinel_output_keys_empty():
    assert NewPrioritizationInfoSentinel.output_keys == {}


def test_new_deployment_info_sentinel_success_rate():
    assert NewDeploymentInfoSentinel.success_rate == pytest.approx(0.10)


def test_new_deployment_info_sentinel_output_keys_empty():
    assert NewDeploymentInfoSentinel.output_keys == {}


# ---------------------------------------------------------------------------
# Actuator — no output_keys
# ---------------------------------------------------------------------------


def test_on_accept_output_keys_empty():
    assert OnAccept.output_keys == {}


def test_on_defer_output_keys_empty():
    assert OnDefer.output_keys == {}


# ---------------------------------------------------------------------------
# Evaluator exemplar — writes output key on SUCCESS (BT-18-002, BT-18-003)
# ---------------------------------------------------------------------------


def test_evaluate_report_credibility_output_keys_declared():
    assert (
        "report_credibility_verdict" in EvaluateReportCredibility.output_keys
    )


def test_evaluate_report_credibility_writes_blackboard_on_success():
    """EvaluateReportCredibility writes report_credibility_verdict on SUCCESS."""
    from vultron.demo.fuzzer.base import AlwaysSucceed
    from vultron.demo.fuzzer.call_out_point import EvaluatorCallOutPoint

    class _AlwaysSucceedEvaluator(EvaluatorCallOutPoint, AlwaysSucceed):
        output_keys = {"report_credibility_verdict": str}

    node = _AlwaysSucceedEvaluator("TestCredibility")
    node.setup()
    status = node.update()

    assert status == Status.SUCCESS
    assert (
        "/report_credibility_verdict" in py_trees.blackboard.Blackboard.storage
    )
    val = py_trees.blackboard.Blackboard.storage["/report_credibility_verdict"]
    assert isinstance(val, str)


def test_evaluate_report_validity_output_keys_declared():
    assert "report_validity_verdict" in EvaluateReportValidity.output_keys


# ---------------------------------------------------------------------------
# Retriever exemplar — writes output key on SUCCESS
# ---------------------------------------------------------------------------


def test_gather_validation_info_output_keys_declared():
    assert "validation_info_gathered" in GatherValidationInfo.output_keys


def test_gather_validation_info_writes_blackboard_on_success():
    """GatherValidationInfo writes validation_info_gathered on SUCCESS."""
    from vultron.demo.fuzzer.base import AlwaysSucceed
    from vultron.demo.fuzzer.call_out_point import RetrieverCallOutPoint

    class _AlwaysSucceedRetriever(RetrieverCallOutPoint, AlwaysSucceed):
        output_keys = {"validation_info_gathered": str}

    node = _AlwaysSucceedRetriever("TestGather")
    node.setup()
    status = node.update()

    assert status == Status.SUCCESS
    assert (
        "/validation_info_gathered" in py_trees.blackboard.Blackboard.storage
    )
    val = py_trees.blackboard.Blackboard.storage["/validation_info_gathered"]
    assert isinstance(val, str)


# ---------------------------------------------------------------------------
# Composer exemplar — writes output key on SUCCESS
# ---------------------------------------------------------------------------


def test_prepare_report_output_keys_declared():
    assert "prepared_report_artifact" in PrepareReport.output_keys


def test_prepare_report_writes_blackboard_on_success():
    """PrepareReport writes prepared_report_artifact on SUCCESS."""
    from vultron.demo.fuzzer.base import AlwaysSucceed
    from vultron.demo.fuzzer.call_out_point import ComposerCallOutPoint

    class _AlwaysSucceedComposer(ComposerCallOutPoint, AlwaysSucceed):
        output_keys = {"prepared_report_artifact": str}

    node = _AlwaysSucceedComposer("TestPrepare")
    node.setup()
    status = node.update()

    assert status == Status.SUCCESS
    assert (
        "/prepared_report_artifact" in py_trees.blackboard.Blackboard.storage
    )
    val = py_trees.blackboard.Blackboard.storage["/prepared_report_artifact"]
    assert isinstance(val, str)


# ---------------------------------------------------------------------------
# AC5 — Blackboard contract for all 29 FUZZ-08d call-out-point nodes
# (BT-18-001): each subclasses the correct shape mixin and declares its
# output key with the right type annotation.
# ---------------------------------------------------------------------------

_EMBARGO_EVALUATOR_NODES = [
    (ExitEmbargoWhenDeployed, "exit_embargo_when_deployed_verdict"),
    (ExitEmbargoWhenFixReady, "exit_embargo_when_fix_ready_verdict"),
    (ExitEmbargoForOtherReason, "exit_embargo_other_reason_verdict"),
    (StopProposingEmbargo, "stop_proposing_embargo_verdict"),
    (SelectEmbargoOfferTerms, "selected_embargo_terms_verdict"),
    (WantToProposeEmbargo, "want_to_propose_embargo_verdict"),
    (WillingToCounterEmbargoProposal, "willing_to_counter_verdict"),
    (
        ReasonToProposeEmbargoWhenDeployed,
        "reason_to_propose_when_deployed_verdict",
    ),
    (EvaluateEmbargoProposal, "evaluate_embargo_proposal_verdict"),
    (CurrentEmbargoAcceptable, "current_embargo_acceptable_verdict"),
]

_RM_EVALUATOR_NODES = [
    (EnoughPrioritizationInfo, "enough_prioritization_info_verdict"),
    (EvaluateExploitPriority, "exploit_priority_verdict"),
    (PurchaseExploit, "purchase_exploit_verdict"),
    (IdAssignable, "id_assignable_verdict"),
    (InScope, "in_scope_verdict"),
    (OtherCloseCriteriaMet, "other_close_criteria_met_verdict"),
    (PrioritizeDeployment, "deployment_priority_verdict"),
    (DeployMitigation, "deploy_mitigation_verdict"),
    (MonitoringRequirement, "monitoring_requirement_verdict"),
    (DeployFix, "deploy_fix_verdict"),
    # NOTE: PrioritizePublicationIntents is intentionally absent here — its
    # output is a structured PublicationIntentDecision (not a str verdict) as
    # of Production Collapse 2 (ADR-0028). Its structured output is covered by
    # test/core/behaviors/report/test_publication_tree.py, mirroring how
    # EvaluateExploitStrategy (Collapse 1) is covered by its own tree test.
    (ReprioritizeExploit, "reprioritize_exploit_verdict"),
    (ReprioritizeFix, "reprioritize_fix_verdict"),
    (ReprioritizeReport, "reprioritize_report_verdict"),
    (AllPartiesKnown, "all_parties_known_verdict"),
    (RecipientEffortExceeded, "recipient_effort_exceeded_verdict"),
    (PolicyCompatible, "policy_compatible_verdict"),
    (TotalEffortLimitMet, "total_effort_limit_met_verdict"),
]

_RM_RETRIEVER_NODES = [
    (GatherPrioritizationInfo, "prioritization_info_gathered"),
    (RequestId, "assigned_id"),
    (IdentifyVendors, "identified_vendors"),
    (IdentifyCoordinators, "identified_coordinators"),
    (ChooseRecipient, "chosen_recipient"),
]

# Nodes whose output_keys declare str values
_RM_RETRIEVER_STR_NODES = [
    (GatherPrioritizationInfo, "prioritization_info_gathered"),
    (RequestId, "assigned_id"),
    (ChooseRecipient, "chosen_recipient"),
]

# Nodes whose output_keys declare list values (multi-actor ID collections)
_RM_RETRIEVER_LIST_NODES = [
    (IdentifyVendors, "identified_vendors"),
    (IdentifyCoordinators, "identified_coordinators"),
]

_RM_BINARY_RETRIEVER_NODES = [
    IdAssigned,
    MitigationDeployed,
    MitigationAvailable,
    HaveExploit,
    FindExploit,
    MonitorAttacks,
    MonitorExploits,
    MonitorPublicReports,
]

_EMBARGO_BINARY_RETRIEVER_NODES = [
    EmbargoTimerExpired,
]


@pytest.mark.parametrize("node_cls, output_key", _EMBARGO_EVALUATOR_NODES)
def test_embargo_node_subclasses_evaluator(node_cls, output_key):
    assert issubclass(node_cls, EvaluatorCallOutPoint)


@pytest.mark.parametrize("node_cls, output_key", _EMBARGO_EVALUATOR_NODES)
def test_embargo_node_output_key_declared(node_cls, output_key):
    assert output_key in node_cls.output_keys


@pytest.mark.parametrize("node_cls, output_key", _EMBARGO_EVALUATOR_NODES)
def test_embargo_node_output_key_type_is_str(node_cls, output_key):
    assert node_cls.output_keys[output_key] is str


@pytest.mark.parametrize("node_cls, output_key", _RM_EVALUATOR_NODES)
def test_rm_evaluator_node_subclasses_evaluator(node_cls, output_key):
    assert issubclass(node_cls, EvaluatorCallOutPoint)


@pytest.mark.parametrize("node_cls, output_key", _RM_EVALUATOR_NODES)
def test_rm_evaluator_node_output_key_declared(node_cls, output_key):
    assert output_key in node_cls.output_keys


@pytest.mark.parametrize("node_cls, output_key", _RM_EVALUATOR_NODES)
def test_rm_evaluator_node_output_key_type_is_str(node_cls, output_key):
    assert node_cls.output_keys[output_key] is str


@pytest.mark.parametrize("node_cls, output_key", _RM_RETRIEVER_NODES)
def test_rm_retriever_node_subclasses_retriever(node_cls, output_key):
    assert issubclass(node_cls, RetrieverCallOutPoint)


@pytest.mark.parametrize("node_cls, output_key", _RM_RETRIEVER_NODES)
def test_rm_retriever_node_output_key_declared(node_cls, output_key):
    assert output_key in node_cls.output_keys


@pytest.mark.parametrize("node_cls, output_key", _RM_RETRIEVER_STR_NODES)
def test_rm_retriever_node_output_key_type_is_str(node_cls, output_key):
    assert node_cls.output_keys[output_key] is str


@pytest.mark.parametrize("node_cls, output_key", _RM_RETRIEVER_LIST_NODES)
def test_rm_retriever_node_output_key_type_is_list(node_cls, output_key):
    assert node_cls.output_keys[output_key] is list


@pytest.mark.parametrize("node_cls, output_key", _RM_RETRIEVER_NODES)
def test_rm_retriever_node_has_blackboard_contract_docstring(
    node_cls, output_key
):
    assert node_cls.__doc__ and "Blackboard contract" in node_cls.__doc__


# ---------------------------------------------------------------------------
# Binary Retriever nodes — subclass RetrieverCallOutPoint, empty output_keys
# (BT-18-006)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("node_cls", _RM_BINARY_RETRIEVER_NODES)
def test_rm_binary_retriever_node_subclasses_retriever(node_cls):
    assert issubclass(node_cls, RetrieverCallOutPoint)


@pytest.mark.parametrize("node_cls", _RM_BINARY_RETRIEVER_NODES)
def test_rm_binary_retriever_node_output_keys_empty(node_cls):
    assert node_cls.output_keys == {}


@pytest.mark.parametrize("node_cls", _RM_BINARY_RETRIEVER_NODES)
def test_rm_binary_retriever_node_has_blackboard_contract_docstring(node_cls):
    assert node_cls.__doc__ and "Blackboard contract" in node_cls.__doc__


@pytest.mark.parametrize("node_cls", _EMBARGO_BINARY_RETRIEVER_NODES)
def test_embargo_binary_retriever_node_subclasses_retriever(node_cls):
    assert issubclass(node_cls, RetrieverCallOutPoint)


@pytest.mark.parametrize("node_cls", _EMBARGO_BINARY_RETRIEVER_NODES)
def test_embargo_binary_retriever_node_output_keys_empty(node_cls):
    assert node_cls.output_keys == {}


@pytest.mark.parametrize("node_cls", _EMBARGO_BINARY_RETRIEVER_NODES)
def test_embargo_binary_retriever_node_has_blackboard_contract_docstring(
    node_cls,
):
    assert node_cls.__doc__ and "Blackboard contract" in node_cls.__doc__


# ---------------------------------------------------------------------------
# Composer nodes (FUZZ-08g) — subclass ComposerCallOutPoint, declare
# output_keys, and write artifact to blackboard on SUCCESS (BT-18-001/02/03)
# ---------------------------------------------------------------------------

_RM_COMPOSER_NODES = [
    (AssignId, "assigned_vul_id"),
    (CreateFix, "fix_artifact"),
    (DevelopExploit, "developed_exploit_artifact"),
    (PrepareExploit, "prepared_exploit_artifact"),
    (PrepareFix, "prepared_fix_artifact"),
    (PrepareReport, "prepared_report_artifact"),
    (FollowUpOnErrorMessage, "followup_message_artifact"),
]


@pytest.mark.parametrize("node_cls, output_key", _RM_COMPOSER_NODES)
def test_rm_composer_node_subclasses_composer(node_cls, output_key):
    assert issubclass(node_cls, ComposerCallOutPoint)


@pytest.mark.parametrize("node_cls, output_key", _RM_COMPOSER_NODES)
def test_rm_composer_node_output_key_declared(node_cls, output_key):
    assert output_key in node_cls.output_keys


@pytest.mark.parametrize("node_cls, output_key", _RM_COMPOSER_NODES)
def test_rm_composer_node_output_key_type_is_str(node_cls, output_key):
    assert node_cls.output_keys[output_key] is str


@pytest.mark.parametrize("node_cls, output_key", _RM_COMPOSER_NODES)
def test_rm_composer_node_has_blackboard_contract_docstring(
    node_cls, output_key
):
    assert node_cls.__doc__ and "Blackboard contract" in node_cls.__doc__


def test_rm_composer_node_writes_blackboard_on_success():
    """A Composer node writes its output key to the blackboard on SUCCESS."""
    from vultron.demo.fuzzer.base import AlwaysSucceed

    class _AlwaysSucceedComposer(ComposerCallOutPoint, AlwaysSucceed):
        output_keys = {"assigned_vul_id": str}

    node = _AlwaysSucceedComposer("TestAssignId")
    node.setup()
    status = node.update()

    assert status == Status.SUCCESS
    assert "/assigned_vul_id" in py_trees.blackboard.Blackboard.storage
    val = py_trees.blackboard.Blackboard.storage["/assigned_vul_id"]
    assert isinstance(val, str)


# ---------------------------------------------------------------------------
# Actuator nodes (FUZZ-08h) — subclass ActuatorCallOutPoint, no output_keys,
# blackboard contract documented (BT-18-001/02/03)
# ---------------------------------------------------------------------------

_EMBARGO_ACTUATOR_NODES = [
    OnEmbargoExit,
    OnEmbargoAccept,
    OnEmbargoReject,
]

_RM_ACTUATOR_NODES = [
    OnAccept,
    OnDefer,
    PreCloseAction,
    MonitorDeployment,
    Publish,
    RemoveRecipient,
    SetRcptQrmR,
    InjectParticipant,
    InjectVendor,
    InjectCoordinator,
    InjectOther,
]

_ALL_ACTUATOR_NODES = _EMBARGO_ACTUATOR_NODES + _RM_ACTUATOR_NODES


@pytest.mark.parametrize("node_cls", _ALL_ACTUATOR_NODES)
def test_actuator_node_subclasses_actuator(node_cls):
    assert issubclass(node_cls, ActuatorCallOutPoint)


@pytest.mark.parametrize("node_cls", _ALL_ACTUATOR_NODES)
def test_actuator_node_output_keys_empty(node_cls):
    assert node_cls.output_keys == {}


@pytest.mark.parametrize("node_cls", _ALL_ACTUATOR_NODES)
def test_actuator_node_has_blackboard_contract_docstring(node_cls):
    assert node_cls.__doc__ and "Blackboard contract" in node_cls.__doc__


@pytest.mark.parametrize("node_cls", _ALL_ACTUATOR_NODES)
def test_actuator_node_is_behaviour(node_cls):
    node = node_cls()
    assert isinstance(node, py_trees.behaviour.Behaviour)


def test_actuator_node_does_not_write_blackboard_on_success():
    """An Actuator node does not write output_keys to the blackboard on SUCCESS.

    Uses a fixture that declares an output_key but inherits ActuatorCallOutPoint
    (which does not write keys) to confirm the key is absent after update().
    Contrast with Composer/Evaluator/Retriever nodes, which DO write their keys.
    """
    from vultron.demo.fuzzer.base import AlwaysSucceed

    class _AlwaysSucceedActuator(ActuatorCallOutPoint, AlwaysSucceed):
        output_keys = {"actuator_test_key": str}

    py_trees.blackboard.Blackboard.storage.clear()
    node = _AlwaysSucceedActuator("TestActuator")
    node.setup()
    status = node.update()

    assert status == Status.SUCCESS
    assert "/actuator_test_key" not in py_trees.blackboard.Blackboard.storage
