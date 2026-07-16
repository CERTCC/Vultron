"""Tests for vultron.demo.fuzzer.report_management.report_to_others."""

import pytest
import py_trees

from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlmostCertainlyFail,
    AlwaysSucceed,
    ProbablySucceed,
    SuccessOrRunning,
    UniformSucceedFail,
    UsuallyFail,
    UsuallySucceed,
)
from vultron.demo.fuzzer.report_management.report_to_others import (
    AllPartiesKnown,
    ChooseRecipient,
    HaveReportToOthersCapability,
    IdentifyCoordinators,
    IdentifyOthers,
    IdentifyVendors,
    InjectCoordinator,
    InjectOther,
    InjectParticipant,
    InjectVendor,
    MoreCoordinators,
    MoreOthers,
    MoreVendors,
    NotificationsComplete,
    PolicyCompatible,
    RcptNotInQrmS,
    RecipientEffortExceeded,
    RemoveRecipient,
    SetRcptQrmR,
    TotalEffortLimitMet,
)

_ALL_NODES = [
    HaveReportToOthersCapability,
    AllPartiesKnown,
    IdentifyVendors,
    IdentifyCoordinators,
    IdentifyOthers,
    NotificationsComplete,
    ChooseRecipient,
    RemoveRecipient,
    RecipientEffortExceeded,
    PolicyCompatible,
    RcptNotInQrmS,
    SetRcptQrmR,
    TotalEffortLimitMet,
    MoreVendors,
    MoreCoordinators,
    MoreOthers,
    InjectParticipant,
    InjectVendor,
    InjectCoordinator,
    InjectOther,
]


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_is_behaviour(node_cls):
    """Each node must be a py_trees Behaviour."""
    node = node_cls()
    assert isinstance(node, py_trees.behaviour.Behaviour)


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_has_docstring(node_cls):
    """Each node must have a non-empty docstring (BT-16-003)."""
    assert node_cls.__doc__ and node_cls.__doc__.strip()


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_name_defaults_to_class_name(node_cls):
    """Default name must be the class name."""
    node = node_cls()
    assert node.name == node_cls.__name__


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_name_custom(node_cls):
    """Custom name must be respected."""
    node = node_cls(name="custom")
    assert node.name == "custom"


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_update_returns_status(node_cls):
    """update() must return a valid py_trees Status."""
    node = node_cls()
    node.setup()
    status = node.update()
    assert status in (
        py_trees.common.Status.SUCCESS,
        py_trees.common.Status.FAILURE,
        py_trees.common.Status.RUNNING,
    )


# --- Base-type tests ---


def test_have_report_to_others_capability_base_type():
    assert issubclass(HaveReportToOthersCapability, UsuallySucceed)


def test_all_parties_known_base_type():
    assert issubclass(AllPartiesKnown, UniformSucceedFail)


def test_identify_vendors_base_type():
    assert issubclass(IdentifyVendors, SuccessOrRunning)


def test_identify_coordinators_base_type():
    assert issubclass(IdentifyCoordinators, SuccessOrRunning)


def test_identify_others_base_type():
    assert issubclass(IdentifyOthers, AlwaysSucceed)


def test_notifications_complete_base_type():
    assert issubclass(NotificationsComplete, UniformSucceedFail)


def test_choose_recipient_base_type():
    assert issubclass(ChooseRecipient, AlwaysSucceed)


def test_remove_recipient_base_type():
    assert issubclass(RemoveRecipient, AlwaysSucceed)


def test_recipient_effort_exceeded_base_type():
    assert issubclass(RecipientEffortExceeded, AlmostCertainlyFail)


def test_policy_compatible_base_type():
    assert issubclass(PolicyCompatible, ProbablySucceed)


def test_rcpt_not_in_qrm_s_base_type():
    assert issubclass(RcptNotInQrmS, AlmostAlwaysSucceed)


def test_set_rcpt_qrm_r_base_type():
    assert issubclass(SetRcptQrmR, AlwaysSucceed)


def test_total_effort_limit_met_base_type():
    assert issubclass(TotalEffortLimitMet, AlmostAlwaysFail)


def test_more_vendors_base_type():
    assert issubclass(MoreVendors, UsuallyFail)


def test_more_coordinators_base_type():
    assert issubclass(MoreCoordinators, AlmostAlwaysFail)


def test_more_others_base_type():
    assert issubclass(MoreOthers, AlmostAlwaysFail)


def test_inject_participant_base_type():
    assert issubclass(InjectParticipant, AlwaysSucceed)


def test_inject_vendor_base_type():
    assert issubclass(InjectVendor, InjectParticipant)


def test_inject_coordinator_base_type():
    assert issubclass(InjectCoordinator, InjectParticipant)


def test_inject_other_base_type():
    assert issubclass(InjectOther, InjectParticipant)


# --- Success-rate tests (WeightedBehavior subclasses only) ---


def test_have_report_to_others_capability_success_rate():
    assert HaveReportToOthersCapability.success_rate == pytest.approx(0.75)


def test_all_parties_known_success_rate():
    assert AllPartiesKnown.success_rate == pytest.approx(0.5)


def test_identify_others_success_rate():
    assert IdentifyOthers.success_rate == pytest.approx(1.0)


def test_notifications_complete_success_rate():
    assert NotificationsComplete.success_rate == pytest.approx(0.5)


def test_choose_recipient_success_rate():
    assert ChooseRecipient.success_rate == pytest.approx(1.0)


def test_remove_recipient_success_rate():
    assert RemoveRecipient.success_rate == pytest.approx(1.0)


def test_recipient_effort_exceeded_success_rate():
    assert RecipientEffortExceeded.success_rate == pytest.approx(7 / 100)


def test_policy_compatible_success_rate():
    assert PolicyCompatible.success_rate == pytest.approx(2 / 3)


def test_rcpt_not_in_qrm_s_success_rate():
    assert RcptNotInQrmS.success_rate == pytest.approx(0.9)


def test_set_rcpt_qrm_r_success_rate():
    assert SetRcptQrmR.success_rate == pytest.approx(1.0)


def test_total_effort_limit_met_success_rate():
    assert TotalEffortLimitMet.success_rate == pytest.approx(0.1)


def test_more_vendors_success_rate():
    assert MoreVendors.success_rate == pytest.approx(0.25)


def test_more_coordinators_success_rate():
    assert MoreCoordinators.success_rate == pytest.approx(0.1)


def test_more_others_success_rate():
    assert MoreOthers.success_rate == pytest.approx(0.1)


def test_inject_participant_success_rate():
    assert InjectParticipant.success_rate == pytest.approx(1.0)


def test_inject_vendor_success_rate():
    assert InjectVendor.success_rate == pytest.approx(1.0)


def test_inject_coordinator_success_rate():
    assert InjectCoordinator.success_rate == pytest.approx(1.0)


def test_inject_other_success_rate():
    assert InjectOther.success_rate == pytest.approx(1.0)


# --- SuccessOrRunning nodes never return FAILURE ---


def test_identify_vendors_never_fails():
    """IdentifyVendors (SuccessOrRunning) must never return FAILURE."""
    node = IdentifyVendors()
    node.setup()
    for _ in range(50):
        status = node.update()
        assert status != py_trees.common.Status.FAILURE


def test_identify_coordinators_never_fails():
    """IdentifyCoordinators (SuccessOrRunning) must never return FAILURE."""
    node = IdentifyCoordinators()
    node.setup()
    for _ in range(50):
        status = node.update()
        assert status != py_trees.common.Status.FAILURE


# --- Exhaustion-based loop: MoreVendors / MoreCoordinators ---


@pytest.fixture(autouse=True)
def clear_blackboard():
    """Clear py_trees global blackboard state between tests."""
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def test_more_vendors_succeeds_when_list_non_empty():
    """MoreVendors returns SUCCESS when identified_vendors is non-empty."""
    node = MoreVendors()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_vendors"] = ["VendorA"]
    status = node.update()
    assert status == py_trees.common.Status.SUCCESS


def test_more_vendors_falls_back_when_list_empty():
    """MoreVendors falls back to probabilistic when identified_vendors is empty."""
    node = MoreVendors()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_vendors"] = []
    # With an empty list the node falls back to UsuallyFail (25% success rate).
    # Run 200 times; at least one FAILURE is virtually certain.
    results = set()
    for _ in range(200):
        results.add(node.update())
    assert py_trees.common.Status.FAILURE in results


def test_more_vendors_falls_back_when_key_absent():
    """MoreVendors falls back to probabilistic when identified_vendors key is absent."""
    node = MoreVendors()
    node.setup()
    # key not written — should still return a valid status without raising
    status = node.update()
    assert status in (
        py_trees.common.Status.SUCCESS,
        py_trees.common.Status.FAILURE,
    )


def test_more_coordinators_succeeds_when_list_non_empty():
    """MoreCoordinators returns SUCCESS when identified_coordinators is non-empty."""
    node = MoreCoordinators()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_coordinators"] = [
        "CoordA"
    ]
    status = node.update()
    assert status == py_trees.common.Status.SUCCESS


def test_more_coordinators_falls_back_when_list_empty():
    """MoreCoordinators falls back to probabilistic when identified_coordinators is empty."""
    node = MoreCoordinators()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_coordinators"] = []
    results = set()
    for _ in range(200):
        results.add(node.update())
    assert py_trees.common.Status.FAILURE in results


def test_more_coordinators_falls_back_when_key_absent():
    """MoreCoordinators falls back to probabilistic when key is absent."""
    node = MoreCoordinators()
    node.setup()
    status = node.update()
    assert status in (
        py_trees.common.Status.SUCCESS,
        py_trees.common.Status.FAILURE,
    )


# --- InjectVendor / InjectCoordinator blackboard writes ---


def test_inject_vendor_pops_from_identified_vendors():
    """InjectVendor pops the first entry from identified_vendors."""
    node = InjectVendor()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_vendors"] = [
        "VendorA",
        "VendorB",
    ]
    py_trees.blackboard.Blackboard.storage["/potential_participants"] = []
    status = node.update()
    assert status == py_trees.common.Status.SUCCESS
    remaining = py_trees.blackboard.Blackboard.storage["/identified_vendors"]
    assert remaining == ["VendorB"]
    participants = py_trees.blackboard.Blackboard.storage[
        "/potential_participants"
    ]
    assert "VendorA" in participants


def test_inject_vendor_appends_to_potential_participants():
    """InjectVendor appends the popped vendor to potential_participants."""
    node = InjectVendor()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_vendors"] = ["VendorX"]
    py_trees.blackboard.Blackboard.storage["/potential_participants"] = [
        "ExistingParty"
    ]
    node.update()
    participants = py_trees.blackboard.Blackboard.storage[
        "/potential_participants"
    ]
    assert participants == ["ExistingParty", "VendorX"]


def test_inject_vendor_succeeds_when_list_empty():
    """InjectVendor still succeeds (no-op) when identified_vendors is empty."""
    node = InjectVendor()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_vendors"] = []
    status = node.update()
    assert status == py_trees.common.Status.SUCCESS


def test_inject_vendor_succeeds_when_key_absent():
    """InjectVendor still succeeds (no-op) when identified_vendors key is absent."""
    node = InjectVendor()
    node.setup()
    status = node.update()
    assert status == py_trees.common.Status.SUCCESS


def test_inject_vendor_creates_potential_participants_if_absent():
    """InjectVendor creates potential_participants list if key was absent."""
    node = InjectVendor()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_vendors"] = [
        "NewVendor"
    ]
    node.update()
    assert "/potential_participants" in py_trees.blackboard.Blackboard.storage
    assert (
        "NewVendor"
        in py_trees.blackboard.Blackboard.storage["/potential_participants"]
    )


def test_inject_coordinator_pops_from_identified_coordinators():
    """InjectCoordinator pops the first entry from identified_coordinators."""
    node = InjectCoordinator()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_coordinators"] = [
        "CoordA",
        "CoordB",
    ]
    py_trees.blackboard.Blackboard.storage["/potential_participants"] = []
    status = node.update()
    assert status == py_trees.common.Status.SUCCESS
    remaining = py_trees.blackboard.Blackboard.storage[
        "/identified_coordinators"
    ]
    assert remaining == ["CoordB"]
    participants = py_trees.blackboard.Blackboard.storage[
        "/potential_participants"
    ]
    assert "CoordA" in participants


def test_inject_coordinator_appends_to_potential_participants():
    """InjectCoordinator appends the popped coordinator to potential_participants."""
    node = InjectCoordinator()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_coordinators"] = [
        "CoordX"
    ]
    py_trees.blackboard.Blackboard.storage["/potential_participants"] = [
        "ExistingParty"
    ]
    node.update()
    participants = py_trees.blackboard.Blackboard.storage[
        "/potential_participants"
    ]
    assert participants == ["ExistingParty", "CoordX"]


def test_inject_coordinator_succeeds_when_list_empty():
    """InjectCoordinator still succeeds (no-op) when identified_coordinators is empty."""
    node = InjectCoordinator()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_coordinators"] = []
    status = node.update()
    assert status == py_trees.common.Status.SUCCESS


def test_inject_coordinator_succeeds_when_key_absent():
    """InjectCoordinator still succeeds (no-op) when key is absent."""
    node = InjectCoordinator()
    node.setup()
    status = node.update()
    assert status == py_trees.common.Status.SUCCESS


def test_inject_coordinator_creates_potential_participants_if_absent():
    """InjectCoordinator creates potential_participants list if key was absent."""
    node = InjectCoordinator()
    node.setup()
    py_trees.blackboard.Blackboard.storage["/identified_coordinators"] = [
        "NewCoord"
    ]
    node.update()
    assert "/potential_participants" in py_trees.blackboard.Blackboard.storage
    assert (
        "NewCoord"
        in py_trees.blackboard.Blackboard.storage["/potential_participants"]
    )


# --- Full exhaustion loop simulation ---


def test_more_vendors_inject_vendor_exhausts_list():
    """MoreVendors+InjectVendor sequence fully drains identified_vendors into potential_participants."""
    vendors = ["VendorA", "VendorB", "VendorC"]
    py_trees.blackboard.Blackboard.storage["/identified_vendors"] = list(
        vendors
    )
    py_trees.blackboard.Blackboard.storage["/potential_participants"] = []

    more = MoreVendors()
    inject = InjectVendor()
    more.setup()
    inject.setup()

    injected = []
    for _ in range(10):  # more iterations than the list length
        if more.update() != py_trees.common.Status.SUCCESS:
            break
        inject.update()
        injected = list(
            py_trees.blackboard.Blackboard.storage["/potential_participants"]
        )

    assert injected == vendors
    assert py_trees.blackboard.Blackboard.storage["/identified_vendors"] == []


def test_more_coordinators_inject_coordinator_exhausts_list():
    """MoreCoordinators+InjectCoordinator sequence fully drains identified_coordinators."""
    coords = ["CoordA", "CoordB"]
    py_trees.blackboard.Blackboard.storage["/identified_coordinators"] = list(
        coords
    )
    py_trees.blackboard.Blackboard.storage["/potential_participants"] = []

    more = MoreCoordinators()
    inject = InjectCoordinator()
    more.setup()
    inject.setup()

    injected = []
    for _ in range(10):
        if more.update() != py_trees.common.Status.SUCCESS:
            break
        inject.update()
        injected = list(
            py_trees.blackboard.Blackboard.storage["/potential_participants"]
        )

    assert injected == coords
    assert (
        py_trees.blackboard.Blackboard.storage["/identified_coordinators"]
        == []
    )
