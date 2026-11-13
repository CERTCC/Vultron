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
"""The received-tree runner and its reading of a finished run (ADR-0195).

Tree tests: they read outcomes through ``core/behaviors`` alone, never
through ``use_cases`` (#5774).
"""

import logging

import py_trees
import pytest
from py_trees.common import Status

from test.support.objects import make
from test.support.received import TEST_SENDER_POSITION, with_evidence
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityIncompleteNode,
)
from vultron.core.behaviors.case.nodes.seen_before import (
    ActivityNotSeenBeforeNode,
    SeenBefore,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.received_run import (
    ReceivedOutcome,
    closed_sender_reader,
    door_guards_admitted,
    failure_reason,
    find_named,
    find_node,
    first_reading,
    guard_refusal,
    incomplete_activity_refusal,
    node_failed,
    node_succeeded,
    read_outcome,
    run_received_tree,
)
from vultron.core.behaviors.helpers import DATALAYER_UNAVAILABLE
from vultron.core.behaviors.idempotency import (
    DeclaredRefusalMixin,
    ReportsIdempotentRepeat,
    ReportsNoChange,
    ReportsRefusal,
    refusal_ending_run,
    repeat_ending_run,
    unchanged_by_run,
)
from vultron.core.behaviors.report.nodes.conditions import (
    CheckParticipantRMState,
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
from vultron.core.behaviors.status.nodes.case_status import (
    CheckCaseStatusIdempotencyNode,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.note import AddNoteToCaseReceivedEvent
from vultron.core.models.note import VultronNote
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.rm import RM
from vultron.errors import (
    VultronBTInternalError,
    VultronValidationError,
    VultronWiringError,
)

_LABEL = "TestBT"
_FAILED = BTExecutionResult(status=Status.FAILURE)
_SUCCEEDED = BTExecutionResult(status=Status.SUCCESS)


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


class _RepeatGuard(_Fixed):
    """A guard that reports its FAILURE as an idempotent repeat."""

    def __init__(self, name: str, *, repeat: bool, message: str = "") -> None:
        super().__init__(name, Status.FAILURE, message)
        self.repeat = repeat

    @property
    def failed_as_repeat(self) -> bool:
        return self.repeat and self.status == Status.FAILURE


class _RefusingGuard(DeclaredRefusalMixin, _Fixed):
    """A guard that declares its FAILURE a refusal, or fails as a fault."""

    def __init__(self, name: str, reason: str, message: str = "") -> None:
        super().__init__(name, Status.FAILURE, message)
        self.reason = reason
        self.refuses = True

    def update(self) -> Status:
        status = super().update()
        return self._refuse(self.reason) if self.refuses else status


class _NoChange(_Fixed):
    """A node that reports its SUCCESS changed nothing."""

    def __init__(self, name: str, *, unchanged: bool) -> None:
        super().__init__(name, Status.SUCCESS)
        self.unchanged = unchanged

    @property
    def succeeded_without_change(self) -> bool:
        return self.unchanged and self.status == Status.SUCCESS

    @property
    def no_change_reason(self) -> str:
        return "already in place"


class _SeenDoor(ActivityNotSeenBeforeNode):
    """A seen-before door that found the activity applied, with no DataLayer."""

    def __init__(self) -> None:
        super().__init__(label=_LABEL, name="SeenBefore")

    def initialise(self) -> None:  # no ports: ticked without a bridge
        pass

    def update(self) -> Status:
        self.seen = SeenBefore.APPLIED
        self.feedback_message = f"{_LABEL}: seen before (applied)"
        return Status.FAILURE


def _ran(
    *children: py_trees.behaviour.Behaviour,
    selector: bool = False,
) -> py_trees.behaviour.Behaviour:
    composite = (
        py_trees.composites.Selector
        if selector
        else py_trees.composites.Sequence
    )
    root = composite(name="Root", memory=False)
    root.add_children(list(children))
    root.tick_once()
    return root


def _read(
    tree: py_trees.behaviour.Behaviour,
    result: BTExecutionResult | None = None,
    **kwargs: object,
) -> HandlerResult:
    if result is None:
        result = _SUCCEEDED if tree.status == Status.SUCCESS else _FAILED
    return read_outcome(
        ReceivedOutcome.of(tree, result, _LABEL),
        **kwargs,  # type: ignore[arg-type]
    )


# --- the general reading (HP-01-003, ADR-0095) ------------------------------


def test_success_is_applied():
    assert _read(_ran(_Fixed("Ok", Status.SUCCESS))) == HandlerResult.applied()


def test_failure_is_refused_with_leaf_reason():
    tree = _ran(_Fixed("Check", Status.FAILURE, "sender is not a participant"))
    verdict = _read(
        tree, BTExecutionResult(status=Status.FAILURE, feedback_message="root")
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
        _read(
            tree,
            BTExecutionResult(
                status=Status.FAILURE,
                feedback_message="KeyError: x",
                internal_error=True,
            ),
        )


def test_leader_skip_is_skipped():
    tree = py_trees.composites.Sequence(name="Root", memory=False)
    tree.add_child(ActivityIncompleteNode("Add(X) is missing its id"))
    verdict = _read(
        tree, BTExecutionResult(status=Status.FAILURE, leader_skipped=True)
    )
    assert verdict.disposition == HandlerDisposition.SKIPPED


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
        _read(tree)


def test_a_tree_that_judges_nothing_raises_on_any_failure():
    """A store-only tree's failure is a local fault, never a refusal."""
    tree = _ran(_Fixed("Store", Status.FAILURE, "write failed"))
    with pytest.raises(VultronBTInternalError, match="write failed"):
        _read(tree, judges=False)


def test_a_tree_that_judges_nothing_still_answers_at_its_doors():
    tree = _ran(_SeenDoor(), _Fixed("Store", Status.FAILURE, "x"))
    verdict = _read(tree, judges=False)
    assert verdict.disposition is HandlerDisposition.SKIPPED


@pytest.mark.spec("HP-01-014")
def test_a_tree_that_judges_nothing_still_reads_a_declared_repeat():
    tree = _ran(_RepeatGuard("Repeat", repeat=True, message="again"))
    assert _read(tree, judges=False) == HandlerResult.skipped("again")


def test_a_tree_that_judges_nothing_passes_success_through():
    assert (
        _read(_ran(_Fixed("Store", Status.SUCCESS)), judges=False)
        == HandlerResult.applied()
    )


@pytest.mark.spec("HP-01-014")
def test_the_seen_before_doors_answer_is_the_verdict():
    """A resend is answered at the door, never read off intake (ADR-0154)."""
    tree = _ran(_SeenDoor(), _Fixed("Intake", Status.SUCCESS))
    verdict = _read(tree)
    assert verdict.disposition == HandlerDisposition.SKIPPED
    assert verdict.reason == "TestBT: seen before (applied)"


@pytest.mark.spec("CLP-10-018")
def test_the_incomplete_guards_own_reason_has_no_label():
    """The incomplete-activity refusal carries no tree label (#4643)."""
    tree = _ran(ActivityIncompleteNode("Add(X) is missing its id"))
    verdict = _read(tree)
    assert verdict.disposition == HandlerDisposition.REFUSED
    assert verdict.reason == "Add(X) is missing its id"


# --- a node-declared repeat (AC-2: HP-01-014, ID-05-003) --------------------


@pytest.mark.spec("HP-01-014")
def test_a_guard_that_failed_as_a_repeat_is_skipped_with_its_reason():
    tree = _ran(_RepeatGuard("Repeat", repeat=True, message="already done"))
    verdict = _read(tree)
    assert verdict.disposition is HandlerDisposition.SKIPPED
    assert verdict.reason == "already done"


@pytest.mark.spec("HP-01-014")
def test_a_silent_repeat_is_skipped_naming_the_guard():
    tree = _ran(_RepeatGuard("Repeat", repeat=True))
    verdict = _read(tree)
    assert verdict.disposition is HandlerDisposition.SKIPPED
    assert verdict.reason == "TestBT: Repeat found an idempotent repeat"


@pytest.mark.spec("HP-01-003")
def test_a_guard_failing_for_another_reason_is_refused():
    tree = _ran(_RepeatGuard("Repeat", repeat=False, message="bad terms"))
    verdict = _read(tree)
    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason == "TestBT: bad terms"


@pytest.mark.spec("HP-01-003")
def test_a_repeat_off_the_failure_chain_does_not_decide_the_run():
    """A Selector's earlier alternative did not end the run."""
    tree = _ran(
        _RepeatGuard("Tried", repeat=True),
        _Fixed("Last", Status.FAILURE, "real refusal"),
        selector=True,
    )
    assert repeat_ending_run(tree) is None
    verdict = _read(tree)
    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason == "TestBT: real refusal"


@pytest.mark.spec("HP-01-014")
def test_a_repeat_deep_on_the_chain_is_found():
    inner = py_trees.composites.Sequence(name="Inner", memory=False)
    guard = _RepeatGuard("Repeat", repeat=True, message="again")
    inner.add_children([_Fixed("Ok", Status.SUCCESS), guard])
    tree = _ran(_Fixed("First", Status.SUCCESS), inner)
    assert repeat_ending_run(tree) is guard


def test_the_case_status_guard_reports_a_repeat():
    node = CheckCaseStatusIdempotencyNode(
        case_id="https://example.org/cases/c", status_id="s"
    )
    assert isinstance(node, ReportsIdempotentRepeat)


# --- a node-declared refusal (HP-01-003, HP-01-005, #5775) -----------------


@pytest.mark.spec("HP-01-003")
def test_a_declared_refusal_is_refused_with_the_nodes_reason():
    """The node's reason is the whole reason: no tree label is added."""
    tree = _ran(_RefusingGuard("Check", "entry hash broken (SYNC-03-006)"))
    verdict = _read(tree)
    assert verdict == HandlerResult.refused("entry hash broken (SYNC-03-006)")


@pytest.mark.spec("HP-01-003")
def test_a_declared_refusal_ahead_of_its_failed_fallback_is_found():
    """Every alternative of a failed Selector decided it, the guard first."""
    guard = _RefusingGuard("Check", "refused (SYNC-03-006)")
    answer = py_trees.composites.Selector(
        name="CheckOrFault",
        memory=False,
        children=[guard, _Fixed("EmitFault", Status.FAILURE, "fault sent")],
    )
    tree = _ran(_Fixed("Ok", Status.SUCCESS), answer)
    assert refusal_ending_run(tree) is guard
    assert _read(tree).reason == "refused (SYNC-03-006)"


@pytest.mark.spec("HP-01-003")
def test_a_declared_refusal_that_did_not_decide_the_run_is_not_read():
    """A refusal a decorator turned into SUCCESS is not the run's verdict."""
    tree = _ran(
        py_trees.decorators.FailureIsSuccess(
            name="Swallowed", child=_RefusingGuard("Check", "not this")
        ),
        _Fixed("Last", Status.FAILURE, "real refusal"),
    )
    assert refusal_ending_run(tree) is None
    assert _read(tree).reason == "TestBT: real refusal"


@pytest.mark.spec("HP-01-014")
def test_a_declared_repeat_is_read_before_a_declared_refusal():
    """A guard whose failure is a repeat is SKIPPED, not refused."""

    class _RepeatAndRefusal(DeclaredRefusalMixin, _RepeatGuard):
        def update(self) -> Status:
            super().update()
            return self._refuse("not this")

    tree = _ran(_RepeatAndRefusal("Guard", repeat=True, message="again"))
    assert _read(tree) == HandlerResult.skipped("again")


def test_the_doors_and_the_reader_are_read_before_a_declared_refusal():
    tree = _ran(_RefusingGuard("Check", "declared"))
    assert _read(tree, reader=_refuse_all) == HandlerResult.refused(
        "reader: TestBT"
    )
    door_tree = _ran(
        ActivityIncompleteNode("Add(X) is missing its id"),
        _RefusingGuard("Check", "declared"),
        selector=True,
    )
    assert _read(door_tree) == HandlerResult.refused(
        "Add(X) is missing its id"
    )


def test_a_tree_that_judges_nothing_still_reads_a_declared_refusal():
    tree = _ran(_RefusingGuard("Check", "declared"))
    assert _read(tree, judges=False) == HandlerResult.refused("declared")


def test_a_fault_of_a_declaring_node_raises_rather_than_refusing():
    """A node that fails without ``_refuse`` declares no refusal (ADR-0095)."""
    node = _RefusingGuard("Check", "unused", DATALAYER_UNAVAILABLE)
    node.refuses = False
    tree = _ran(node)
    assert isinstance(node, ReportsRefusal)
    assert node.declared_refusal is None
    with pytest.raises(VultronBTInternalError):
        _read(tree)


def test_a_declared_refusal_is_cleared_by_the_next_run():
    node = _RefusingGuard("Check", "first")
    tree = _ran(node)
    assert node.declared_refusal == "first"
    node.refuses = False
    tree.tick_once()
    assert node.status == Status.FAILURE
    assert node.declared_refusal is None


# --- a node-declared no-change (AC-4: ID-05-003, RSH-08-002) ----------------


@pytest.mark.spec("ID-05-003")
@pytest.mark.spec("RSH-08-002")
def test_a_run_a_node_says_changed_nothing_is_skipped():
    tree = _ran(_NoChange("AlreadyThere", unchanged=True), selector=True)
    verdict = _read(tree)
    assert verdict.disposition is HandlerDisposition.SKIPPED
    assert verdict.reason == "TestBT: already in place"


@pytest.mark.spec("HP-01-003")
def test_a_run_whose_nodes_declare_a_change_is_applied():
    tree = _ran(_NoChange("Changed", unchanged=False))
    assert unchanged_by_run(tree) is None
    assert _read(tree) == HandlerResult.applied()


def test_no_change_is_not_read_on_a_failed_run():
    tree = _ran(
        _NoChange("AlreadyThere", unchanged=True),
        _Fixed("Then", Status.FAILURE, "refused"),
    )
    assert unchanged_by_run(tree) is None
    assert _read(tree).disposition is HandlerDisposition.REFUSED


@pytest.mark.spec("RSH-08-002")
def test_the_rm_repeat_guard_declares_no_change_on_success():
    node = CheckParticipantRMState(
        case_id="https://example.org/cases/c",
        actor_id="https://example.org/actors/a",
        target_rm=RM.ACCEPTED,
    )
    assert isinstance(node, ReportsNoChange)
    node.status = Status.SUCCESS
    assert node.succeeded_without_change
    node.status = Status.FAILURE
    assert not node.succeeded_without_change


# --- the handler's own reader (AC-7) and the reading order ------------------


def _refuse_all(outcome: ReceivedOutcome) -> HandlerResult | None:
    return HandlerResult.refused(f"reader: {outcome.label}")


def test_a_reader_answer_stands_in_front_of_the_generic_readings():
    tree = _ran(_RepeatGuard("Repeat", repeat=True))
    verdict = _read(tree, reader=_refuse_all)
    assert verdict == HandlerResult.refused("reader: TestBT")


def test_a_reader_that_answers_none_leaves_the_generic_reading():
    tree = _ran(_RepeatGuard("Repeat", repeat=True, message="again"))
    verdict = _read(tree, reader=lambda _outcome: None)
    assert verdict == HandlerResult.skipped("again")


def test_the_doors_are_read_before_the_reader():
    tree = _ran(_SeenDoor(), _Fixed("Intake", Status.SUCCESS))
    verdict = _read(tree, reader=_refuse_all)
    assert verdict.disposition is HandlerDisposition.SKIPPED


def test_an_internal_error_raises_before_the_reader():
    tree = _ran(_Fixed("Check", Status.FAILURE))
    crashed = BTExecutionResult(
        status=Status.FAILURE, feedback_message="boom", internal_error=True
    )
    with pytest.raises(VultronBTInternalError, match="boom"):
        _read(tree, crashed, reader=_refuse_all)


def test_first_reading_keeps_the_first_answer():
    skip = HandlerResult.skipped("first")
    reader = first_reading(lambda _o: None, lambda _o: skip, _refuse_all)
    tree = _ran(_Fixed("Ok", Status.SUCCESS))
    assert _read(tree, reader=reader) is skip


# --- node lookups -----------------------------------------------------------


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


def test_node_failed_matches_any_node_of_the_type():
    """One node type can sit on several branches; a later one failing counts."""
    tree = _ran(
        _Guard("First", Status.SUCCESS), _Guard("Second", Status.FAILURE)
    )
    assert node_failed(tree, _Guard)
    assert node_succeeded(tree, _Guard)


def test_find_named_locates_a_composite_by_name():
    arm = py_trees.composites.Sequence(name="Arm", memory=False)
    arm.add_child(_Fixed("Leaf", Status.SUCCESS))
    tree = _ran(arm)
    assert find_named(tree, "Arm") is arm
    assert find_named(tree, "Missing") is None


# --- door guards (CLP-10-010) ----------------------------------------------


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


def test_guard_refusal_lets_a_wiring_fault_raise():
    """A guard composed without its DataLayer is our fault (ADR-0095)."""
    tree = _ran(_Guard("Guard", Status.FAILURE, "DataLayer not available"))
    assert guard_refusal(tree, _Guard) is None
    with pytest.raises(VultronBTInternalError):
        _read(tree)


# --- closed_sender_reader (CM-23-018, ID-05-003) ----------------------------

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
        sender_rule=SenderRule.on_every_path(
            SenderEntitlementKind.PARTICIPANT
        ),
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


def _closed(tree: py_trees.behaviour.Behaviour, label: str) -> ReceivedOutcome:
    return ReceivedOutcome.of(tree, _FAILED, label)


@pytest.mark.spec("CM-23-018", "ID-05-003")
@pytest.mark.spec("CM-23-049")
def test_closed_sender_reader_skips_a_repeated_closing_act():
    verdict = closed_sender_reader(closes=True)(
        _closed(_closed_door_tree(sender_closed=True), "Reject")
    )
    assert verdict is not None
    assert verdict.disposition is HandlerDisposition.SKIPPED
    assert verdict.reason == (
        f"Reject: {_CLOSURE} — a repeat of a closing act, nothing to apply"
        " (ID-05-003)"
    )


@pytest.mark.spec("CM-23-018")
def test_closed_sender_reader_refuses_any_other_act():
    verdict = closed_sender_reader(closes=False)(
        _closed(_closed_door_tree(sender_closed=True), "Accept")
    )
    assert verdict is not None
    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason == (
        f"Accept: {_CLOSURE} — it may act on nothing further"
    )


@pytest.mark.parametrize("sender_closed", [False, None])
def test_closed_sender_reader_is_none_unless_the_door_found_a_closure(
    sender_closed: bool | None,
):
    tree = _closed_door_tree(sender_closed=sender_closed)
    assert closed_sender_reader(closes=True)(_closed(tree, "X")) is None


def test_closed_sender_reader_needs_a_received_activity_tree():
    tree = py_trees.composites.Sequence(name="AdHoc", memory=False)
    with pytest.raises(VultronWiringError, match="received-activity"):
        closed_sender_reader(closes=True)(_closed(tree, "X"))


@pytest.mark.spec("CM-23-018", "ARCH-15-001")
@pytest.mark.parametrize("closes", [True, False])
def test_a_crash_at_the_closed_sender_door_raises(closes: bool):
    """A crash in the door (e.g. its Case Owner check) is never a verdict."""
    crashed = BTExecutionResult(
        status=Status.FAILURE,
        feedback_message="owner check exploded",
        internal_error=True,
    )
    with pytest.raises(VultronBTInternalError, match="owner check exploded"):
        read_outcome(
            ReceivedOutcome.of(
                _closed_door_tree(sender_closed=True), crashed, "Leave"
            ),
            reader=closed_sender_reader(closes=closes),
        )


# --- run_received_tree (BT-17-005, BT-17-009, CLP-10-005) -------------------

_RECEIVER = "https://example.org/actors/receiver"
_SENDER = "https://example.org/actors/sender"
_CASE_ID = "https://example.org/cases/runner"


class _Records(py_trees.behaviour.Behaviour):
    """Records the actor and a context key the run placed on the blackboard."""

    def __init__(self, status: Status = Status.SUCCESS) -> None:
        super().__init__(name="Records")
        self._status = status
        self.seen: dict[str, object] = {}
        self.ticks = 0

    def update(self) -> Status:
        storage = py_trees.blackboard.Blackboard.storage
        for key in ("actor_id", "case_id"):
            self.seen[key] = storage.get(f"/{key}")
        self.ticks += 1
        self.feedback_message = "the probe refused"
        return self._status


def _event(receiving_actor_id: str | None) -> AddNoteToCaseReceivedEvent:
    note = make(
        VultronNote,
        id_="https://example.org/notes/n-runner",
        content="x",
        context=_CASE_ID,
    )
    activity = make(
        VultronActivity,
        id_="https://example.org/activities/add-note-runner",
        type_="Add",
        actor=_SENDER,
        object_=note,
        target=_CASE_ID,
        to=[_RECEIVER],
    )
    return with_evidence(
        AddNoteToCaseReceivedEvent(
            ledger_position=TEST_SENDER_POSITION,
            activity_id=activity.id_,
            actor_id=_SENDER,
            object_=note,
            activity=activity,
            receiving_actor_id=receiving_actor_id,
        )
    )


def _probe_tree(probe: _Records) -> py_trees.behaviour.Behaviour:
    root = py_trees.composites.Sequence(name="ProbeBT", memory=False)
    root.add_child(probe)
    return root


@pytest.mark.spec("BT-17-005")
@pytest.mark.spec("CLP-10-005")
def test_the_runner_runs_the_tree_once_as_the_receiver():
    probe = _Records()
    verdict = run_received_tree(
        _probe_tree(probe),
        dl=SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER),
        request=_event(_RECEIVER),
        label="ProbeBT",
        case_id=_CASE_ID,
    )
    assert verdict == HandlerResult.applied()
    assert probe.ticks == 1
    assert probe.seen == {"actor_id": _RECEIVER, "case_id": _CASE_ID}


@pytest.mark.spec("BT-17-009")
def test_the_runner_falls_back_to_the_stores_owner():
    """No ``receiving_actor_id`` stamp: the store's owner, never the sender."""
    probe = _Records()
    run_received_tree(
        _probe_tree(probe),
        dl=SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER),
        request=_event(None),
        label="ProbeBT",
    )
    assert probe.seen["actor_id"] == _RECEIVER


class _NoOwnerStore:
    """A store that reports no ``actor_id`` of its own."""

    actor_id = None


@pytest.mark.spec("BT-17-009")
@pytest.mark.spec("ARCH-15-001")
def test_the_runner_raises_when_no_receiver_can_be_resolved():
    """No stamp and no store owner: a wiring fault, never a refusal."""
    probe = _Records()
    with pytest.raises(VultronValidationError):
        run_received_tree(
            _probe_tree(probe),
            dl=_NoOwnerStore(),  # type: ignore[arg-type]
            request=_event(None),
            label="ProbeBT",
        )
    assert probe.ticks == 0


@pytest.mark.spec("HP-01-003")
def test_the_runner_reads_and_logs_a_refusal(caplog):
    caplog.set_level(logging.WARNING)
    verdict = run_received_tree(
        _probe_tree(_Records(Status.FAILURE)),
        dl=SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER),
        request=_event(_RECEIVER),
        label="ProbeBT",
    )
    assert verdict == HandlerResult.refused("ProbeBT: the probe refused")
    assert "ProbeBT did not succeed for activity" in caplog.text


def test_the_runner_hands_its_reader_only_the_finished_run():
    seen: list[ReceivedOutcome] = []

    def reader(outcome: ReceivedOutcome) -> HandlerResult | None:
        seen.append(outcome)
        return None

    tree = _probe_tree(_Records())
    run_received_tree(
        tree,
        dl=SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER),
        request=_event(_RECEIVER),
        label="ProbeBT",
        reader=reader,
    )
    (outcome,) = seen
    assert outcome.tree is tree
    assert outcome.label == "ProbeBT"
    assert outcome.succeeded
