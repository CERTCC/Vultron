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

"""The check tree a scenario run leaves (DEMOCI-11-056, DEMOCI-11-057)."""

import json

import pytest

from vultron.demo.utils.check_tree import (
    CheckKind,
    CheckNode,
    CheckOutcome,
    active_recorder,
    enter_check,
    leave_check,
    note_container_read,
    recording_checks,
    tree_from_json,
    tree_lines,
    tree_to_json,
)
from vultron.demo.utils.failures import (
    demo_check,
    demo_failures,
    demo_gate,
    demo_step,
    reset_demo_failures,
)
from vultron.errors import DemoRecordingError


@pytest.fixture(autouse=True)
def _clean_accumulator():
    """The failure accumulator is module-level, so clear it either side."""
    reset_demo_failures()
    yield
    reset_demo_failures()


class TestCaptureIsOffByDefault:
    """A scenario run outside the recorder behaves exactly as before."""

    @pytest.mark.spec("DEMOCI-11-056")
    def test_no_recorder_is_installed_by_default(self):
        assert active_recorder() is None

    def test_the_three_context_managers_still_accumulate(self):
        with demo_step("1. act"), demo_check("the act landed"):
            raise RuntimeError("no")
        assert [f.split(":")[0] for f in demo_failures()] == ["CHECK FAILED"]

    def test_the_hooks_do_nothing(self):
        # Called with no capture installed, as every non-recorded demo run
        # does; an unpaired leave would raise if the slot were filled.
        enter_check(CheckKind.STEP, "nowhere")
        leave_check(CheckOutcome.PASSED)
        note_container_read("actor0")
        assert active_recorder() is None


class TestRecordedTree:
    @pytest.mark.spec("DEMOCI-11-056")
    def test_every_entered_node_is_listed_in_order_and_nested(self):
        with recording_checks() as recorder:
            with demo_step("1. the Reporter submits"):
                pass
            with demo_gate("the Vendor reached RM.VALID"):
                with demo_check("the Vendor holds the case"):
                    pass
                with demo_step("2. the Vendor engages"):
                    pass
            with demo_check("the ledger is shared"):
                pass

        tree = recorder.tree()
        assert [node.label for node in tree] == [
            "1. the Reporter submits",
            "the Vendor reached RM.VALID",
            "the ledger is shared",
        ]
        assert [node.kind for node in tree] == [
            CheckKind.STEP,
            CheckKind.GATE,
            CheckKind.CHECK,
        ]
        assert [child.label for child in tree[1].children] == [
            "the Vendor holds the case",
            "2. the Vendor engages",
        ]

    @pytest.mark.spec("DEMOCI-11-057")
    def test_a_node_carries_its_outcome(self):
        with recording_checks() as recorder:
            with demo_check("this holds"):
                pass
            with demo_check("this does not"):
                raise AssertionError("no")

        assert [node.outcome for node in recorder.tree()] == [
            CheckOutcome.PASSED,
            CheckOutcome.FAILED,
        ]

    def test_a_failed_gate_skips_the_steps_inside_it(self):
        """The gate's own contract (DEMOCI-01-009) read off the tree."""
        with recording_checks() as recorder:
            with demo_gate("the precondition"):
                raise AssertionError("unmet")
                with demo_step("3. dependent"):  # pragma: no cover
                    pass

        [gate] = recorder.tree()
        assert gate.outcome is CheckOutcome.FAILED
        assert gate.children == ()

    def test_a_base_exception_closes_the_node_as_failed(self):
        """A timeout or an interrupt is not a pass."""
        with pytest.raises(KeyboardInterrupt), recording_checks() as recorder:
            with demo_step("1. interrupted"):
                raise KeyboardInterrupt

        [node] = recorder.tree()
        assert node.outcome is CheckOutcome.FAILED


class TestReadAttribution:
    @pytest.mark.spec("DEMOCI-11-057")
    def test_a_read_lands_on_the_innermost_open_node(self):
        with recording_checks() as recorder:
            with demo_gate("the Vendor reached RM.VALID"):
                note_container_read("actor1")
                with demo_check("the Coordinator agrees"):
                    note_container_read("actor2")

        [gate] = recorder.tree()
        assert gate.reads == ("actor1",)
        assert gate.children[0].reads == ("actor2",)

    def test_reads_are_reported_in_name_order_without_repeats(self):
        """Delivery runs on worker threads, so call order is not stable."""
        with recording_checks() as recorder:
            with demo_check("the roster"):
                note_container_read("case-actor")
                note_container_read("actor1")
                note_container_read("case-actor")

        [node] = recorder.tree()
        assert node.reads == ("actor1", "case-actor")

    def test_a_read_outside_every_node_is_dropped(self):
        with recording_checks() as recorder:
            note_container_read("actor0")
            with demo_step("1. act"):
                pass

        assert recorder.tree() == (
            CheckNode(
                kind=CheckKind.STEP,
                label="1. act",
                outcome=CheckOutcome.PASSED,
            ),
        )


class TestRecorderRefusals:
    def test_a_second_capture_is_refused(self):
        with (
            recording_checks(),
            pytest.raises(
                DemoRecordingError, match="one run records one tree"
            ),
        ):
            with recording_checks():
                pass  # pragma: no cover - the inner block never runs

    def test_the_capture_is_removed_when_the_run_raises(self):
        with pytest.raises(RuntimeError), recording_checks():
            raise RuntimeError("the scenario failed")
        assert active_recorder() is None

    def test_an_unpaired_leave_is_refused(self):
        with recording_checks() as recorder:
            with pytest.raises(
                DemoRecordingError, match="while none was open"
            ):
                recorder.leave(CheckOutcome.PASSED)

    def test_reading_the_tree_with_a_node_open_is_refused(self):
        with recording_checks() as recorder:
            recorder.enter(CheckKind.GATE, "still open")
            with pytest.raises(DemoRecordingError, match="still open"):
                recorder.tree()
            recorder.leave(CheckOutcome.PASSED)


class TestRendering:
    TREE = (
        CheckNode(
            kind=CheckKind.GATE,
            label="the Vendor reached RM.VALID",
            outcome=CheckOutcome.PASSED,
            reads=("actor1",),
            children=(
                CheckNode(
                    kind=CheckKind.CHECK,
                    label="the Vendor holds the case",
                    outcome=CheckOutcome.FAILED,
                ),
            ),
        ),
    )

    def test_each_node_renders_on_its_own_indented_line(self):
        assert tree_lines(self.TREE) == [
            "gate the Vendor reached RM.VALID -> passed reads=actor1",
            "  check the Vendor holds the case -> failed reads=-",
        ]

    def test_a_tree_round_trips_through_json(self):
        assert (
            tree_from_json(json.loads(json.dumps(tree_to_json(self.TREE))))
            == self.TREE
        )

    @pytest.mark.parametrize(
        "raw",
        [
            "not a list",
            [{"kind": "step"}],
            [
                {
                    "kind": "wizard",
                    "label": "x",
                    "outcome": "passed",
                    "reads": [],
                    "children": [],
                }
            ],
            [
                {
                    "kind": "step",
                    "label": 7,
                    "outcome": "passed",
                    "reads": [],
                    "children": [],
                }
            ],
            [
                {
                    "kind": "step",
                    "label": "x",
                    "outcome": "maybe",
                    "reads": [],
                    "children": [],
                }
            ],
            [
                {
                    "kind": "step",
                    "label": "x",
                    "outcome": "passed",
                    "reads": [3],
                    "children": [],
                }
            ],
            [
                {
                    "kind": "step",
                    "label": "x",
                    "outcome": "passed",
                    "reads": [],
                    "children": ["no"],
                }
            ],
        ],
    )
    def test_a_malformed_tree_is_refused(self, raw):
        with pytest.raises(DemoRecordingError):
            tree_from_json(raw)
