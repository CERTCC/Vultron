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

"""Tests for the received-side BT verdict helper (#2255)."""

import py_trees
import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityIncompleteNode,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderClosureNotRecordedNode,
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    ClosedSenderCheck,
    SenderCheckContext,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    closed_sender_verdict,
    door_guards_admitted,
    failure_reason,
    find_named,
    find_node,
    guard_refusal,
    incomplete_activity_refusal,
    intake_verdict,
    node_failed,
    node_succeeded,
    not_case_manager_refusal,
    verdict_from_bt,
)
from vultron.errors import VultronBTInternalError, VultronWiringError
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class _Fixed(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, status: Status, message: str = "") -> None:
        super().__init__(name=name)
        self._status = status
        self._message = message

    def update(self) -> Status:
        self.feedback_message = self._message
        return self._status


class _Guard(_Fixed):
    pass


def _ran(
    *children: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    root = py_trees.composites.Sequence(name="Root", memory=False)
    root.add_children(list(children))
    root.tick_once()
    return root


def test_success_is_applied():
    tree = _ran(_Fixed("Ok", Status.SUCCESS))
    verdict = verdict_from_bt(
        tree, BTExecutionResult(status=Status.SUCCESS), label="TestBT"
    )
    assert verdict.disposition == HandlerDisposition.APPLIED


def test_failure_is_refused_with_leaf_reason():
    tree = _ran(_Fixed("Check", Status.FAILURE, "sender is not a participant"))
    verdict = verdict_from_bt(
        tree,
        BTExecutionResult(status=Status.FAILURE, feedback_message="root"),
        label="TestBT",
    )
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == "TestBT: sender is not a participant"


def test_raised_node_reason_comes_from_result():
    """A node that raised has no status, so only the bridge saw the reason."""
    tree = py_trees.composites.Sequence(name="Root", memory=False)
    tree.add_child(_Fixed("Never", Status.SUCCESS))
    result = BTExecutionResult(
        status=Status.FAILURE,
        feedback_message="BT execution failed: VultronError: boom",
    )
    assert failure_reason(tree, result) == result.feedback_message


def test_internal_error_raises():
    tree = _ran(_Fixed("Check", Status.FAILURE))
    with pytest.raises(VultronBTInternalError, match="TestBT"):
        verdict_from_bt(
            tree,
            BTExecutionResult(
                status=Status.FAILURE,
                feedback_message="KeyError: x",
                internal_error=True,
            ),
            label="TestBT",
        )


def test_leader_skip_is_skipped():
    tree = py_trees.composites.Sequence(name="Root", memory=False)
    verdict = verdict_from_bt(
        tree,
        BTExecutionResult(status=Status.FAILURE, leader_skipped=True),
        label="TestBT",
    )
    assert verdict.disposition == HandlerDisposition.SKIPPED


def test_node_lookup_by_type_accepts_tree_wrapper():
    guard = _Guard("Guard", Status.FAILURE, "already stored")
    root = py_trees.composites.Selector(name="Root", memory=False)
    root.add_children([guard, _Fixed("Work", Status.SUCCESS)])
    wrapper = py_trees.trees.BehaviourTree(root)
    wrapper.tick()
    assert find_node(wrapper, _Guard) is guard
    assert node_failed(wrapper, _Guard)
    assert not node_succeeded(wrapper, _Guard)


def test_node_lookup_missing_type_is_false():
    tree = _ran(_Fixed("Ok", Status.SUCCESS))
    assert find_node(tree, _Guard) is None
    assert not node_failed(tree, _Guard)
    assert not node_succeeded(tree, _Guard)


@pytest.mark.parametrize(
    "message",
    [
        "DataLayer not available",
        "DataLayer or actor_id not available",
        "trigger_activity_factory not available",
    ],
)
def test_missing_wiring_raises_rather_than_refusing(message):
    """A node that could not reach its DataLayer or a port reports a
    deployment fault, not the sender's error, so it is never REFUSED."""
    tree = _ran(_Fixed("NeedsPort", Status.FAILURE, message))
    with pytest.raises(VultronBTInternalError, match=message):
        verdict_from_bt(
            tree, BTExecutionResult(status=Status.FAILURE), label="TestBT"
        )


def test_node_failed_matches_any_node_of_the_type():
    """One node type can sit on several branches; a later one failing counts."""
    first = _Guard("First", Status.SUCCESS)
    second = _Guard("Second", Status.FAILURE)
    tree = _ran(first, second)
    assert node_failed(tree, _Guard)
    assert node_succeeded(tree, _Guard)


def test_find_named_locates_a_composite_by_name():
    arm = py_trees.composites.Sequence(name="Arm", memory=False)
    arm.add_child(_Fixed("Leaf", Status.SUCCESS))
    tree = _ran(arm)
    assert find_named(tree, "Arm") is arm
    assert find_named(tree, "Missing") is None


def test_applied_or_raise_raises_on_any_failure():
    """An intake-only tree's failure is a local fault, never a refusal."""
    tree = _ran(_Fixed("Store", Status.FAILURE, "write failed"))
    with pytest.raises(VultronBTInternalError, match="write failed"):
        applied_or_raise(
            tree, BTExecutionResult(status=Status.FAILURE), label="TestBT"
        )


def test_applied_or_raise_passes_success_through():
    tree = _ran(_Fixed("Store", Status.SUCCESS))
    verdict = applied_or_raise(
        tree, BTExecutionResult(status=Status.SUCCESS), label="TestBT"
    )
    assert verdict.disposition == HandlerDisposition.APPLIED


# ---------------------------------------------------------------------------
# intake_verdict (HP-01-003, ADR-0111)
# ---------------------------------------------------------------------------


class _Intake(IntakeReceivedActivityNode):
    """An intake node that reports a fixed outcome without a DataLayer."""

    def __init__(self, stored: list[str]) -> None:
        super().__init__(name="Intake")
        self._stored = stored

    def initialise(self) -> None:  # no ports: ticked without a bridge
        pass

    def update(self) -> Status:
        self.stored_ids = list(self._stored)
        return Status.SUCCESS


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("CLP-10-017")
def test_intake_verdict_is_applied_when_intake_stored_something():
    tree = _ran(_Intake(stored=["https://example.org/activities/a-1"]))
    verdict = intake_verdict(
        tree, BTExecutionResult(status=Status.SUCCESS), label="IntakeBT"
    )
    assert verdict.disposition == HandlerDisposition.APPLIED


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("CLP-10-017")
def test_intake_verdict_is_skipped_when_everything_was_already_stored():
    """A redelivery is a benign no-op, not a refusal (HP-01-003)."""
    tree = _ran(_Intake(stored=[]))
    verdict = intake_verdict(
        tree, BTExecutionResult(status=Status.SUCCESS), label="IntakeBT"
    )
    assert verdict.disposition == HandlerDisposition.SKIPPED
    assert verdict.reason is not None and "already held" in verdict.reason


@pytest.mark.spec("HP-01-003")
def test_intake_verdict_keeps_a_refusal():
    """A guard's FAILURE after intake is still the sender's refusal."""
    tree = _ran(_Intake(stored=["x"]), _Guard("Refuse", Status.FAILURE, "no"))
    verdict = intake_verdict(
        tree, BTExecutionResult(status=Status.FAILURE), label="IntakeBT"
    )
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == "IntakeBT: no"


def test_intake_verdict_raises_when_the_tree_has_no_intake_node():
    """Asking intake's verdict of a tree without intake is a wiring fault."""
    tree = _ran(_Fixed("Ok", Status.SUCCESS))
    with pytest.raises(VultronBTInternalError, match="no intake node"):
        intake_verdict(
            tree, BTExecutionResult(status=Status.SUCCESS), label="IntakeBT"
        )


# ---------------------------------------------------------------------------
# not_case_manager_refusal (HP-01-005, #3752)
# ---------------------------------------------------------------------------


_CASE_ID = "https://example.org/cases/gate-verdict"
_STORE_OWNER = "https://example.org/actors/store-owner"
_OTHER_MANAGER = "https://example.org/actors/other-manager"


def _store(
    holds_case: bool = True, manager_id: str | None = _OTHER_MANAGER
) -> SqliteDataLayer:
    """The store-owner's own store, holding (or not) the case.

    *manager_id* names who holds ``CVDRole.CASE_MANAGER`` on the case; ``None``
    seeds a case with no role holder at all.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_OWNER)
    if holds_case:
        case = as_VulnerabilityCase(id_=_CASE_ID, name="Gate verdict")
        if manager_id is not None:
            seed_case_manager_participant(dl, case, manager_id)
        dl.create(case)
    return dl


def _gated_run(gate_status: Status) -> py_trees.behaviour.Behaviour:
    """A tree whose CASE_MANAGER check reports *gate_status*.

    The check is the real node, so the helper's type lookup finds it; its
    status is set directly rather than ticked, since ticking needs the BT
    bridge's ports and store.
    """
    from vultron.core.behaviors.case.nodes.conditions import (
        CheckIsCaseManagerNode,
    )

    check = CheckIsCaseManagerNode(case_id=_CASE_ID)
    check.status = gate_status
    root = py_trees.composites.Selector(name="Root", memory=False)
    root.add_children(
        [
            py_trees.decorators.Inverter(name="Inv", child=check),
            _Fixed("Work", Status.SUCCESS),
        ]
    )
    return root


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_is_none_when_the_gate_passed():
    tree = _gated_run(Status.SUCCESS)
    assert not_case_manager_refusal(tree, _store(), _CASE_ID) is None


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_is_none_without_a_gate():
    tree = _ran(_Fixed("Ok", Status.SUCCESS))
    assert not_case_manager_refusal(tree, _store(), _CASE_ID) is None


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_names_the_missing_role():
    """Somebody else holds CASE_MANAGER: this actor is not it."""
    tree = _gated_run(Status.FAILURE)
    verdict = not_case_manager_refusal(tree, _store(), _CASE_ID)
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == f"not the CASE_MANAGER of case '{_CASE_ID}'"


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_names_the_unknown_case():
    tree = _gated_run(Status.FAILURE)
    verdict = not_case_manager_refusal(
        tree, _store(holds_case=False), _CASE_ID
    )
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == f"unknown case '{_CASE_ID}'"


@pytest.mark.spec("HP-01-005")
def test_not_case_manager_refusal_names_a_case_with_no_manager():
    """The gate also fails when no participant holds the role at all.

    That is a distinct state from "somebody else is the manager", and the
    reason says which, because at such a case nobody can pass the gate
    (CM-02-014, CM-02-015).
    """
    tree = _gated_run(Status.FAILURE)
    verdict = not_case_manager_refusal(tree, _store(manager_id=None), _CASE_ID)
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == f"case '{_CASE_ID}' has no CASE_MANAGER"


def _door_tree(door: Status) -> ReceivedActivityTree:
    """One door guard returning *door*, then a precondition guard that fails."""
    guard = _Fixed("Door", door)
    tree = ReceivedActivityTree(
        name="Probe",
        children=[guard, _Fixed("Precondition", Status.FAILURE)],
        door_guards=[guard],
    )
    tree.tick_once()
    return tree


@pytest.mark.spec("CLP-10-010")
def test_door_guards_admitted_once_every_door_guard_succeeded():
    """Admitted even though a later precondition guard failed the run."""
    assert door_guards_admitted(_door_tree(Status.SUCCESS)) is True


@pytest.mark.spec("CLP-10-010")
def test_door_guards_not_admitted_when_a_door_guard_refused():
    assert door_guards_admitted(_door_tree(Status.FAILURE)) is False


@pytest.mark.spec("CLP-10-010")
def test_door_guards_not_admitted_before_the_tree_ran():
    guard = _Fixed("Door", Status.SUCCESS)
    tree = ReceivedActivityTree(
        name="Probe", children=[guard], door_guards=[guard]
    )
    assert door_guards_admitted(tree) is False


def test_door_guards_admitted_needs_a_received_activity_tree():
    with pytest.raises(VultronWiringError, match="not a received-activity"):
        door_guards_admitted(_Fixed("Plain", Status.SUCCESS))


@pytest.mark.spec("CLP-10-005")
def test_guard_refusal_carries_the_guards_own_reason():
    """No tree label: the guard's message is the whole refusal (#4643)."""
    tree = _ran(_Guard("Guard", Status.FAILURE, "untrusted sender"))
    verdict = guard_refusal(tree, _Guard)
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == "untrusted sender"


@pytest.mark.parametrize(
    "children",
    [
        (_Guard("Guard", Status.SUCCESS),),
        # The guard never ran: an earlier node failed first.
        (
            _Fixed("First", Status.FAILURE, "closed"),
            _Guard("Guard", Status.FAILURE),
        ),
        (),
    ],
    ids=["passed", "never-ran", "absent"],
)
def test_guard_refusal_is_none_unless_the_guard_failed(children):
    assert guard_refusal(_ran(*children), _Guard) is None


@pytest.mark.spec("CLP-10-018")
def test_incomplete_activity_refusal_reads_the_incomplete_guard():
    tree = _ran(ActivityIncompleteNode("Add(X) is missing its id"))
    verdict = incomplete_activity_refusal(tree)
    assert verdict is not None
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == "Add(X) is missing its id"
    assert (
        incomplete_activity_refusal(_ran(_Fixed("Ok", Status.SUCCESS))) is None
    )


@pytest.mark.spec("CLP-10-018")
def test_verdict_from_bt_keeps_the_incomplete_guards_own_reason():
    """The incomplete-activity refusal carries no tree label (#4643)."""
    tree = _ran(ActivityIncompleteNode("Add(X) is missing its id"))
    verdict = verdict_from_bt(
        tree, BTExecutionResult(status=Status.FAILURE), label="TestBT"
    )
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == "Add(X) is missing its id"


@pytest.mark.spec("HP-01-005")
def test_leader_skip_of_an_incomplete_activity_is_skipped():
    """A follower that never ran the tree does not refuse the activity."""
    tree = py_trees.composites.Sequence(name="Root", memory=False)
    tree.add_child(ActivityIncompleteNode("Add(X) is missing its id"))
    verdict = verdict_from_bt(
        tree,
        BTExecutionResult(status=Status.FAILURE, leader_skipped=True),
        label="TestBT",
    )
    assert verdict.disposition == HandlerDisposition.SKIPPED


def test_guard_refusal_lets_a_wiring_fault_raise():
    """A guard composed without its DataLayer is our fault (ADR-0095)."""
    tree = _ran(_Guard("Guard", Status.FAILURE, "DataLayer not available"))
    assert guard_refusal(tree, _Guard) is None
    with pytest.raises(VultronBTInternalError):
        verdict_from_bt(
            tree, BTExecutionResult(status=Status.FAILURE), label="TestBT"
        )


# --- closed_sender_verdict (CM-23-018, ID-05-003) -----------------------

_CLOSED_CASE = "https://example.org/cases/closed-sender-verdict"
_CLOSED_SENDER = "https://example.org/actors/closed-sender"
_CLOSURE = (
    f"'{_CLOSED_SENDER}' is already closed on case '{_CLOSED_CASE}'"
    " (CM-23-018)"
)


def _closed_door_tree(*, sender_closed: bool | None) -> ReceivedActivityTree:
    """A factory tree whose closed-sender door ran (``None``: never ran)."""
    tree = create_receive_activity_tree(
        name="ClosedSenderBT",
        case_id=_CLOSED_CASE,
        precondition_guards=[],
        closed_sender=ClosedSenderCheck(sender_id=_CLOSED_SENDER),
        sender_rule=SenderRule.in_case(SenderEntitlementKind.PARTICIPANT),
        sender_context=SenderCheckContext(
            sender_id=_CLOSED_SENDER, case_id=_CLOSED_CASE
        ),
    )
    if sender_closed is not None:
        (door,) = (
            n
            for n in tree.children
            if isinstance(n, SenderClosureNotRecordedNode)
        )
        door.status = Status.FAILURE
        door.sender_closed = sender_closed
        door.feedback_message = _CLOSURE
    return tree


@pytest.mark.spec("CM-23-018", "ID-05-003")
def test_closed_sender_verdict_skips_a_repeated_closing_act():
    verdict = closed_sender_verdict(
        _closed_door_tree(sender_closed=True), closes=True, label="Reject"
    )

    assert verdict is not None
    assert verdict.disposition is HandlerDisposition.SKIPPED
    assert verdict.reason == (
        f"Reject: {_CLOSURE} — a repeat of a closing act, nothing to apply"
        " (ID-05-003)"
    )


@pytest.mark.spec("CM-23-018")
def test_closed_sender_verdict_refuses_any_other_act():
    verdict = closed_sender_verdict(
        _closed_door_tree(sender_closed=True), closes=False, label="Accept"
    )

    assert verdict is not None
    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason == (
        f"Accept: {_CLOSURE} — it may act on nothing further"
    )


@pytest.mark.parametrize("sender_closed", [False, None])
def test_closed_sender_verdict_is_none_unless_the_door_found_a_closure(
    sender_closed: bool | None,
):
    tree = _closed_door_tree(sender_closed=sender_closed)

    assert closed_sender_verdict(tree, closes=True, label="X") is None


def test_closed_sender_verdict_needs_a_received_activity_tree():
    tree = py_trees.composites.Sequence(name="AdHoc", memory=False)

    with pytest.raises(VultronWiringError, match="received-activity"):
        closed_sender_verdict(tree, closes=True, label="X")
