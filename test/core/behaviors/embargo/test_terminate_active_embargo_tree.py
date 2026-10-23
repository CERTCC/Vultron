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
"""Tests for create_terminate_active_embargo_tree (EMB-14).

Verifies:
- Tree structure: Sequence root with correct sub-tree shape.
- Call-out injection: bundle factories are wired at each call-out slot.
- Deterministic defaults: ceiling/floor rule applied per BT-23-002.
- Stochastic bundle: produces the expected fuzzer classes.
- terminate_embargo_bt delegation: final child is the existing mechanism.
- The chosen reason is the cause the TERMINATED entry records (EMB-14-001).
"""

import py_trees
import pytest
from py_trees.common import Status

from test.support.embargo_register import (
    activate,
    agree_to_active_embargo,
    write_consent_rows,
)
from test.support.ledger import ledger_entries
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out import unwrap_call_out
from vultron.core.behaviors.call_out.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EmbargoCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_TEARDOWN_SEMANTIC_TYPE,
    ChooseTerminationCauseNode,
    ChosenTermination,
    HasActiveEmbargoNode,
)
from vultron.core.behaviors.embargo.nodes.chosen_cause import (
    fix_ready_vendors,
)
from vultron.core.behaviors.embargo.terminate_active_embargo_tree import (
    create_terminate_active_embargo_tree,
)
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import (
    ReporterParticipant,
    VendorParticipant,
)
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    FixDeployedCause,
    FixReadyCause,
    OtherCause,
    TerminationCause,
    TerminationCauseKind,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_vf
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
)
from vultron.core.states.rm import RM
from vultron.demo.fuzzer.bundles.embargo import EMBARGO_STOCHASTIC
from vultron.demo.fuzzer.embargo import (
    EmbargoExitOverride,
    EmbargoExitPolicyGuard,
    ExitEmbargoForOtherReason,
    ExitEmbargoWhenDeployed,
    ExitEmbargoWhenFixReady,
    OnEmbargoExit,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

CASE_ID = "https://example.org/cases/test-terminate-001"


def _make_result_out() -> dict:
    return {}


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


def test_returns_behaviour():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_root_name():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert tree.name == "TerminateActiveEmbargoBT"


def test_root_is_sequence():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree, py_trees.composites.Sequence)


def test_root_has_five_children():
    """Root Sequence: HasActiveEmbargo, ReasonSelector, AuthorizeSelector, OnEmbargoExit, terminate_embargo_bt."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert len(tree.children) == 5


def test_root_sequence_memory_false():
    """memory=False on root ensures stateless restart every tick."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree, py_trees.composites.Sequence)
    assert tree.memory is False


def test_reason_selector_memory_false():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    reason = tree.children[1]
    assert isinstance(reason, py_trees.composites.Selector)
    assert reason.memory is False


def test_authorize_selector_memory_false():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    auth = tree.children[2]
    assert isinstance(auth, py_trees.composites.Selector)
    assert auth.memory is False


# ---------------------------------------------------------------------------
# Child 0 — HasActiveEmbargoNode precondition guard
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-14-001")
def test_child_0_is_has_active_embargo():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(tree.children[0], HasActiveEmbargoNode)


# ---------------------------------------------------------------------------
# Child 1 — ReasonSelector (EMB-14-001)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-14-001")
@pytest.mark.spec("EMB-14-004")
def test_child_1_is_reason_selector():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    reason = tree.children[1]
    assert isinstance(reason, py_trees.composites.Selector)
    assert reason.name == "ReasonSelector"


@pytest.mark.spec("EMB-14-001")
@pytest.mark.spec("EMB-14-004")
def test_reason_selector_has_three_children():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert len(tree.children[1].children) == 3


@pytest.mark.spec("EMB-14-001")
@pytest.mark.parametrize(
    "index,cls",
    [
        (0, AlwaysFail),  # ExitEmbargoWhenDeployed (p=0.33)
        (1, AlwaysFail),  # ExitEmbargoWhenFixReady (p=0.25)
        (2, AlwaysFail),  # ExitEmbargoForOtherReason (p=0.005)
    ],
)
def test_reason_selector_deterministic_defaults(index, cls):
    """DETERMINISTIC: all reason nodes are AlwaysFail (p < 0.5 for all three)."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    branch = tree.children[1].children[index]
    assert isinstance(unwrap_call_out(branch.children[0]), cls)


@pytest.mark.spec("EMB-14-001")
@pytest.mark.parametrize(
    "index,cls",
    [
        (0, ExitEmbargoWhenDeployed),
        (1, ExitEmbargoWhenFixReady),
        (2, ExitEmbargoForOtherReason),
    ],
)
def test_reason_selector_stochastic_classes(index, cls):
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_STOCHASTIC,
    )
    branch = tree.children[1].children[index]
    assert isinstance(unwrap_call_out(branch.children[0]), cls)


@pytest.mark.spec("EMB-14-001")
@pytest.mark.parametrize(
    "index,kind",
    [
        (0, TerminationCauseKind.FIX_DEPLOYED),
        (1, TerminationCauseKind.FIX_READY),
        (2, TerminationCauseKind.OTHER),
    ],
)
def test_each_reason_call_out_is_followed_by_its_cause(index, kind):
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    branch = tree.children[1].children[index]
    assert isinstance(branch, py_trees.composites.Sequence)
    choose = branch.children[1]
    assert isinstance(choose, ChooseTerminationCauseNode)
    assert choose._kind is kind


# ---------------------------------------------------------------------------
# Child 2 — AuthorizeEmbargoExit Selector (EMB-14-002, EMB-14-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-14-002")
@pytest.mark.spec("EMB-14-004")
def test_child_2_is_authorize_selector():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    auth = tree.children[2]
    assert isinstance(auth, py_trees.composites.Selector)
    assert auth.name == "AuthorizeEmbargoExit"


@pytest.mark.spec("EMB-14-002")
@pytest.mark.spec("EMB-14-003")
def test_authorize_selector_has_two_children():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert len(tree.children[2].children) == 2


@pytest.mark.spec("EMB-14-002")
def test_authorize_first_child_deterministic_is_always_succeed():
    """EmbargoExitPolicyGuard (p=1.0) → AlwaysSucceed."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(
        unwrap_call_out(tree.children[2].children[0]), AlwaysSucceed
    )


@pytest.mark.spec("EMB-14-003")
def test_authorize_second_child_deterministic_is_always_fail():
    """EmbargoExitOverride (p=0.0) → AlwaysFail."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(
        unwrap_call_out(tree.children[2].children[1]), AlwaysFail
    )


@pytest.mark.spec("EMB-14-002")
@pytest.mark.spec("EMB-14-004")
def test_authorize_first_child_stochastic_is_policy_guard():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_STOCHASTIC,
    )
    assert isinstance(
        unwrap_call_out(tree.children[2].children[0]), EmbargoExitPolicyGuard
    )


@pytest.mark.spec("EMB-14-003")
@pytest.mark.spec("EMB-14-004")
def test_authorize_second_child_stochastic_is_override():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_STOCHASTIC,
    )
    assert isinstance(
        unwrap_call_out(tree.children[2].children[1]), EmbargoExitOverride
    )


# ---------------------------------------------------------------------------
# Child 3 — OnEmbargoExit Actuator
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-14-004")
def test_child_3_on_embargo_exit_deterministic_is_always_succeed():
    """OnEmbargoExit (p=1.0) → AlwaysSucceed in DETERMINISTIC bundle."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    assert isinstance(unwrap_call_out(tree.children[3]), AlwaysSucceed)


def test_child_3_on_embargo_exit_stochastic_class():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_STOCHASTIC,
    )
    assert isinstance(unwrap_call_out(tree.children[3]), OnEmbargoExit)


# ---------------------------------------------------------------------------
# Child 4 — terminate_embargo_bt delegation
# ---------------------------------------------------------------------------


def test_child_4_is_terminate_embargo_bt_sequence():
    """The final child must be the TerminateEmbargoBT Sequence (BT-19-001)."""
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out()
    )
    term = tree.children[4]
    assert isinstance(term, py_trees.composites.Sequence)
    assert term.name == "TerminateEmbargoBT"


# ---------------------------------------------------------------------------
# Factory injection — each call-out slot accepts a custom factory
# ---------------------------------------------------------------------------


_TERMINATE_FACTORY_FIELDS = [
    ("exit_embargo_when_deployed_factory", 1, 0),
    ("exit_embargo_when_fix_ready_factory", 1, 1),
    ("exit_embargo_for_other_reason_factory", 1, 2),
    ("embargo_exit_policy_guard_factory", 2, 0),
    ("embargo_exit_override_factory", 2, 1),
    ("on_embargo_exit_factory", None, None),  # direct child 3
]


@pytest.mark.parametrize(
    "field,parent_idx,child_idx", _TERMINATE_FACTORY_FIELDS
)
def test_factory_field_is_wired(field, parent_idx, child_idx):
    sentinel = {"called": False}

    def custom_factory(name: str) -> py_trees.behaviour.Behaviour:
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            IS_CUSTOM_MARKER = True

            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=name)

    bundle = EmbargoCallOutBundle(**{field: custom_factory})  # type: ignore[arg-type]
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=_make_result_out(), call_out=bundle
    )
    assert sentinel["called"], f"factory {field!r} was not called"

    if parent_idx is None:
        # on_embargo_exit is child 3 directly
        assert getattr(
            unwrap_call_out(tree.children[3]), "IS_CUSTOM_MARKER", False
        )
    else:
        node = tree.children[parent_idx].children[child_idx]
        if parent_idx == 1:
            # A reason branch: its call-out, then the cause it chooses.
            node = node.children[0]
        assert getattr(unwrap_call_out(node), "IS_CUSTOM_MARKER", False)


# ---------------------------------------------------------------------------
# result_out propagation
# ---------------------------------------------------------------------------


def test_result_out_passed_through():
    """result_out dict is the same object passed to HasActiveEmbargoNode."""
    result = _make_result_out()
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID, result_out=result
    )
    guard = tree.children[0]
    assert isinstance(guard, HasActiveEmbargoNode)
    # HasActiveEmbargoNode stores result_out as an instance attribute
    assert guard._result_out is result


# ---------------------------------------------------------------------------
# Deterministic singleton accepted
# ---------------------------------------------------------------------------


def test_deterministic_singleton_accepted():
    tree = create_terminate_active_embargo_tree(
        case_id=CASE_ID,
        result_out=_make_result_out(),
        call_out=EMBARGO_DETERMINISTIC,
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)


# ---------------------------------------------------------------------------
# The chosen reason is the recorded cause (EMB-14-001)
# ---------------------------------------------------------------------------


class _World:
    """A CASE_MANAGER vendor's store holding a case with an embargo in force.

    The manager is a fix-ready vendor; a second vendor is not fix-ready, so
    a ``FIX_READY`` cause names the manager alone.  Every party has agreed
    to the embargo in force.  A finder is the other
    party the teardown reaches.
    """

    def __init__(
        self,
        *,
        manager_fix_ready: bool = True,
        vendor_fix_ready: bool = False,
        vendor_agrees: bool = True,
    ) -> None:
        self.manager = as_Service(name="Vendor Co")
        self.vendor = as_Service(name="Other Vendor")
        self.finder = as_Service(name="Finder Co")
        self.dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=self.manager.id_
        )
        for actor in (self.manager, self.vendor, self.finder):
            self.dl.create(actor)
        case = VulnerabilityCase(
            name="Voluntary termination", attributed_to=self.manager.id_
        )
        self.embargo = as_EmbargoEvent(
            context=case.id_, end_time=days_from_now_utc(10)
        )
        owner = self._vendor(
            self.manager.id_, case.id_, fix_ready=manager_fix_ready
        )
        owner.add_role(CVDRole.CASE_MANAGER)
        vendor = self._vendor(
            self.vendor.id_, case.id_, fix_ready=vendor_fix_ready
        )
        finder = ReporterParticipant(
            attributed_to=self.finder.id_, context=case.id_
        )
        participants = (
            (self.manager.id_, owner),
            (self.vendor.id_, vendor),
            (self.finder.id_, finder),
        )
        for actor_id, participant in participants:
            case.case_participants.append(participant.id_)
            case.actor_participant_index[actor_id] = participant.id_
        activate(case, self.embargo.id_)
        self.case_id = case.id_
        for obj in (case, self.embargo, owner, vendor, finder):
            self.dl.create(obj)
        write_consent_rows(self.dl, case)
        # Every party is a signatory, so each is an active participant
        # (CM-10-004).
        signatories = [self.manager.id_, self.finder.id_]
        if vendor_agrees:
            signatories.append(self.vendor.id_)
        agree_to_active_embargo(self.dl, case, *signatories)

    @staticmethod
    def _vendor(
        actor_id: str, case_id: str, *, fix_ready: bool
    ) -> VendorParticipant:
        return VendorParticipant(
            attributed_to=actor_id,
            context=case_id,
            participant_statuses=[
                ParticipantStatus(
                    attributed_to=actor_id,
                    context=case_id,
                    rm=RmDimension(state=RM.ACCEPTED),
                    vf=VfDimension(state=CS_vf.VF if fix_ready else CS_vf.Vf),
                    cvd_role=[CVDRole.VENDOR],
                )
            ],
        )

    def run(self, bundle: EmbargoCallOutBundle):
        tree = create_terminate_active_embargo_tree(
            case_id=self.case_id, result_out={}, call_out=bundle
        )
        return BTBridge(
            datalayer=self.dl,
            trigger_activity=TriggerActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute_with_setup(
            tree=tree,
            actor_id=self.manager.id_,
            sync_port=SyncActivityAdapter(self.dl),
        )

    def case(self) -> VulnerabilityCase:
        case = self.dl.read(self.case_id)
        assert isinstance(case, VulnerabilityCase)
        return case

    def teardown_snapshot(self) -> dict:
        (entry,) = [
            e
            for e in ledger_entries(self.dl, self.case_id)
            if e.semantic_type == EMBARGO_TEARDOWN_SEMANTIC_TYPE
        ]
        return entry.payload_snapshot or {}

    def termination(self) -> EmbargoTermination | None:
        case = self.dl.read(self.case_id)
        assert isinstance(case, VulnerabilityCase)
        entry = case.embargo_register_entry(self.embargo.id_)
        assert entry is not None
        assert entry.status is EmbargoRegisterStatus.TERMINATED
        return entry.termination


def _succeeding(field: str) -> EmbargoCallOutBundle:
    """The deterministic bundle with the reason call-out *field* succeeding."""
    return EmbargoCallOutBundle(**{field: AlwaysSucceed})


@pytest.mark.spec("EMB-14-001")
@pytest.mark.spec("EMB-13-004")
@pytest.mark.parametrize(
    "field,expected",
    [
        ("exit_embargo_when_deployed_factory", lambda w: FixDeployedCause()),
        (
            "exit_embargo_when_fix_ready_factory",
            lambda w: FixReadyCause(vendors=[w.manager.id_]),
        ),
        ("exit_embargo_for_other_reason_factory", lambda w: OtherCause()),
    ],
)
def test_the_chosen_reason_is_recorded_as_the_cause(field, expected):
    world = _World()

    result = world.run(_succeeding(field))

    assert result.status == Status.SUCCESS, result.feedback_message
    cause: TerminationCause = expected(world)
    assert world.termination() == EmbargoTermination(
        reason=TerminationReason.EARLY, cause=cause
    )
    # The committed Remove carries the same cause (EMB-13-005).
    snapshot = world.teardown_snapshot()
    assert snapshot["content"] == "EARLY"
    assert snapshot["terminationCause"] == cause.model_dump(
        mode="json", by_alias=True
    )


@pytest.mark.spec("EMB-14-001")
def test_fix_ready_with_no_fix_ready_vendor_tries_the_next_reason():
    world = _World(manager_fix_ready=False)
    bundle = EmbargoCallOutBundle(
        exit_embargo_when_fix_ready_factory=AlwaysSucceed,
        exit_embargo_for_other_reason_factory=AlwaysSucceed,
    )

    result = world.run(bundle)

    assert result.status == Status.SUCCESS, result.feedback_message
    assert world.termination() == EmbargoTermination(
        reason=TerminationReason.EARLY, cause=OtherCause()
    )


@pytest.mark.spec("EMB-14-001")
@pytest.mark.spec("EMB-14-004")
def test_no_reason_ends_nothing():
    world = _World()

    result = world.run(EMBARGO_DETERMINISTIC)

    assert result.status == Status.FAILURE
    case = world.dl.read(world.case_id)
    assert isinstance(case, VulnerabilityCase)
    assert case.active_embargo_id == world.embargo.id_


def test_a_termination_read_before_a_cause_is_chosen_is_a_wiring_fault():
    with pytest.raises(VultronWiringError):
        _ = ChosenTermination().termination


def test_a_voluntary_termination_cannot_choose_a_threat_signal():
    with pytest.raises(VultronWiringError):
        ChooseTerminationCauseNode(
            case_id=CASE_ID,
            kind=TerminationCauseKind.THREAT_SIGNAL,
            chosen=ChosenTermination(),
        )


@pytest.mark.spec("VP-09-007")
def test_fix_ready_vendors_are_the_active_fix_ready_vendors_sorted():
    world = _World(vendor_fix_ready=True)

    vendors = fix_ready_vendors(world.dl, world.case())

    assert vendors == sorted([world.manager.id_, world.vendor.id_])


@pytest.mark.spec("VP-09-007")
def test_an_inert_fix_ready_vendor_is_not_in_the_quorum():
    world = _World(vendor_fix_ready=True, vendor_agrees=False)

    assert fix_ready_vendors(world.dl, world.case()) == [world.manager.id_]


def test_an_unchosen_cause_at_the_commit_is_a_wiring_fault():
    """The commit reads the cause outside its refusal handler, so a missing
    choice is reported as an internal error, not a refusal."""
    world = _World()

    result = BTBridge(
        datalayer=world.dl,
        trigger_activity=TriggerActivityAdapter(world.dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute_with_setup(
        tree=terminate_embargo_bt(
            case_id=world.case_id,
            result_out={},
            termination=ChosenTermination(),
        ),
        actor_id=world.manager.id_,
        sync_port=SyncActivityAdapter(world.dl),
    )

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert world.case().active_embargo_id == world.embargo.id_


@pytest.mark.parametrize(
    "kind,name",
    [
        (TerminationCauseKind.FIX_DEPLOYED, "ChooseFixDeployedCause"),
        (TerminationCauseKind.FIX_READY, "ChooseFixReadyCause"),
        (TerminationCauseKind.OTHER, "ChooseOtherCause"),
    ],
)
def test_choose_node_names(kind, name):
    node = ChooseTerminationCauseNode(
        case_id=CASE_ID, kind=kind, chosen=ChosenTermination()
    )
    assert node.name == name
