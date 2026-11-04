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

"""The story runner (DEMOCI-11-019).

Pins :mod:`vultron.demo.helpers.story.runner`: :func:`run_story` plays the
items in order inside the harness and reports each choice with the deciding
actor's id, against a fake harness and against the real one.
"""

from __future__ import annotations

import contextlib
import pathlib
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from test.demo_unit.story._support import (
    KEPT_ID,
    make_fragment,
    make_session,
    make_state,
    rv_story,
)
from vultron.demo.helpers import (
    harness as harness_module,
)
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.story import (
    StoryState,
    choose,
    run_story,
    runner as story_runner,
    story,
)
from vultron.demo.scenario import registry
from vultron.demo.utils import demo_failures, demo_step, reset_demo_failures
from vultron.errors import (
    DemoScenarioStepError,
    DemoStoryError,
)


class _FakeHarness:
    """Records the step marks a story reports, in order.

    Writes them into the same list the fragments write to, so a test asserts
    where each mark fell relative to the fragments around it — the property
    ``run_story`` exists to guarantee, because it is what fixes the recorded
    ``ledger_tail`` (DEMOCI-11-013).
    """

    def __init__(self, log: list[str] | None = None) -> None:
        self.log: list[str] = [] if log is None else log
        self.marks: list[tuple[str, str, str]] = []
        self.demo_name = "rv"
        self.refuse: str | None = None

    def reach_step(self, branch_point: str, choice: str, *, by: str) -> None:
        if self.refuse == branch_point:
            raise DemoScenarioStepError(
                f"{branch_point} is decided by {by!r}, which is not a "
                "participant in the case (DEMOCI-11-047)."
            )
        self.marks.append((branch_point, choice, by))
        self.log.append(f"mark:{branch_point}")


@pytest.fixture
def fake_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[_FakeHarness]:
    """Stand in for ``scenario_harness``, which needs a real case to check."""
    reset_demo_failures()
    harness = _FakeHarness()

    @contextlib.contextmanager
    def stub(_demo_name: str) -> Iterator[_FakeHarness]:
        yield harness

    monkeypatch.setattr(story_runner, "scenario_harness", stub)
    yield harness
    reset_demo_failures()


class TestRunStory:
    @pytest.mark.spec("DEMOCI-11-013")
    def test_the_runner_marks_each_choice_as_it_passes_it(
        self, fake_harness: _FakeHarness
    ) -> None:
        """No fragment places a reach_step: the runner emits every mark.

        Asserted as one interleaved sequence: a runner that emitted every mark
        first and then ran every fragment would satisfy two separate lists.
        """
        log = fake_harness.log
        state = make_state(
            reporter=make_session("urn:test:reporter"),
            vendor=make_session("urn:test:vendor"),
        )

        run_story("rv", rv_story(log), lambda _harness: state)

        assert log == [
            "mark:reporter-whom-to-tell",
            "submit",
            "mark:vendor-after-answer",
            "fix",
        ]
        assert fake_harness.marks == [
            ("reporter-whom-to-tell", "vendor", "urn:test:reporter"),
            ("vendor-after-answer", "report-fix-ready", "urn:test:vendor"),
        ]

    def test_the_cast_is_opened_inside_the_harness(
        self, fake_harness: _FakeHarness
    ) -> None:
        """``open_cast`` is handed this run's harness, inside its context.

        Only the wiring is asserted here: the state is built from the harness
        the runner entered, which is what puts a seeding failure inside the
        harness that dumps and reports it.  That the failure itself is
        recorded and stops the story is covered on the real seeding path, by
        ``test/demo/coordinated_story/test_cast.py::TestOpenCoordinatedCast::
        test_a_failed_seeding_leaves_no_cast_to_tell_the_story_with``.
        """
        seen: list[object] = []

        def open_cast(harness: Any) -> StoryState:
            seen.append(harness)
            return make_state(
                reporter=make_session("urn:test:reporter"),
                vendor=make_session("urn:test:vendor"),
            )

        run_story("rv", rv_story(), open_cast)
        assert seen == [fake_harness]

    def test_a_choice_by_an_unseated_actor_fails_the_run(
        self, fake_harness: _FakeHarness
    ) -> None:
        state = make_state(vendor=make_session("urn:test:vendor"))
        with pytest.raises(DemoStoryError, match="does not seat"):
            run_story("rv", rv_story(), lambda _harness: state)
        assert fake_harness.marks == []

    @pytest.mark.spec("DEMOCI-11-013")
    def test_a_mis_declared_step_raises_on_a_run_that_had_not_failed(
        self, fake_harness: _FakeHarness
    ) -> None:
        """A declaration defect is not a soft failure to be blessed later."""
        fake_harness.refuse = "vendor-after-answer"
        state = make_state(
            reporter=make_session("urn:test:reporter"),
            vendor=make_session("urn:test:vendor"),
        )
        with pytest.raises(DemoScenarioStepError, match="not a"):
            run_story("rv", rv_story(), lambda _harness: state)

    @pytest.mark.spec("DEMOCI-01-003")
    @pytest.mark.spec("EDF-06-005")
    def test_a_mark_that_an_earlier_failure_broke_stops_the_story(
        self, fake_harness: _FakeHarness
    ) -> None:
        """The failed act is the headline, not the role it never granted.

        The invite trigger failing is the case this exists for: no inert
        participant is seated, so the Vendor's mark cannot read its role.
        Reporting that as the cause would misattribute a transport failure to
        a declaration defect, and raising it would bury the real one.
        """
        log = fake_harness.log
        fake_harness.refuse = "vendor-after-answer"
        state = make_state(
            reporter=make_session("urn:test:reporter"),
            vendor=make_session("urn:test:vendor"),
        )
        plot = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            make_fragment("submit", log, fails=True),
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
            make_fragment("fix", log),
        )

        run_story("rv", plot, lambda _harness: state)

        assert log == ["mark:reporter-whom-to-tell", "submit"], (
            "the story ran on past the mark it could not make"
        )
        failures = demo_failures()
        assert len(failures) == 2
        assert "submit fails" in failures[0]
        assert "reaches vendor-after-answer" in failures[1]

    @pytest.mark.spec("DEMOCI-01-003")
    @pytest.mark.spec("DEMOCI-01-007")
    def test_a_fragment_missing_what_a_failed_step_would_have_made_stops_it(
        self, fake_harness: _FakeHarness
    ) -> None:
        """The flat-sequence form of the nesting a phase scenario used.

        ``rcv-embargo`` ran its termination, publication and closure inside
        one ``demo_gate`` on the revised embargo, so a failed revision skipped
        all three.  A story is flat, so the dependent fragment asks for the
        artifact instead: the step that would have made it recorded its own
        failure and kept nothing, and the story stops where the first
        dependent asks.
        """
        log = fake_harness.log

        def proposes(_state: StoryState) -> None:
            log.append("propose")
            with demo_step("the proposal fails"):
                raise AssertionError("no revision took effect")

        def terminates(state: StoryState) -> None:
            log.append("terminate")
            state.kept(KEPT_ID)

        def publishes(state: StoryState) -> None:
            log.append("publish")

        state = make_state(
            reporter=make_session("urn:test:reporter"),
            vendor=make_session("urn:test:vendor"),
        )
        plot = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            proposes,
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
            terminates,
            publishes,
        )

        run_story("rv", plot, lambda _harness: state)

        assert "publish" not in log, (
            "the story ran the fragments that presupposed the failed step"
        )
        failures = demo_failures()
        assert len(failures) == 2
        assert "the proposal fails" in failures[0]
        assert "cannot run terminates" in failures[1]
        assert "embargo in force" in failures[1]

    def test_a_fragment_missing_an_artifact_on_a_clean_run_raises(
        self, fake_harness: _FakeHarness
    ) -> None:
        """Then the story really is mis-assembled, not merely downstream.

        Reporting it as a soft failure would let the next regeneration bless a
        fragment placed before the one that makes what it reads.
        """

        def terminates(state: StoryState) -> None:
            state.kept(KEPT_ID)

        state = make_state(
            reporter=make_session("urn:test:reporter"),
            vendor=make_session("urn:test:vendor"),
        )
        plot = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            terminates,
        )
        with pytest.raises(DemoStoryError, match="embargo in force"):
            run_story("rv", plot, lambda _harness: state)

    @pytest.mark.spec("DEMOCI-01-003")
    @pytest.mark.spec("EDF-06-005")
    def test_a_mark_that_still_lands_after_a_failure_lets_the_story_go_on(
        self, fake_harness: _FakeHarness
    ) -> None:
        """A recorded failure is not itself a reason to stop the story.

        The third outcome of ``_mark_step``: the accumulator is dirty, so the
        mark is made inside a ``demo_gate`` — and it succeeds, because the
        failed act granted no role this step depends on.  The story then runs
        to its end, and the gate records nothing of its own, so the first
        failure stays the only one reported.
        """
        log = fake_harness.log
        fake_harness.refuse = None
        state = make_state(
            reporter=make_session("urn:test:reporter"),
            vendor=make_session("urn:test:vendor"),
        )
        plot = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            make_fragment("submit", log, fails=True),
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
            make_fragment("fix", log),
        )

        run_story("rv", plot, lambda _harness: state)

        assert log == [
            "mark:reporter-whom-to-tell",
            "submit",
            "mark:vendor-after-answer",
            "fix",
        ]
        assert fake_harness.marks == [
            ("reporter-whom-to-tell", "vendor", "urn:test:reporter"),
            ("vendor-after-answer", "report-fix-ready", "urn:test:vendor"),
        ]
        failures = demo_failures()
        assert len(failures) == 1, failures
        assert "submit fails" in failures[0]


def _opens_the_case(state: StoryState) -> None:
    """A fragment that opens a case, as a story's first one does.

    Opening the case is what makes the harness follow a ledger, which is the
    precondition the real harness puts on every step after the first.
    """
    state.open_case(
        case=MagicMock(id_="urn:test:case"),
        report=MagicMock(),
        offer=MagicMock(),
    )


class TestRunStoryOnTheRealHarness:
    """The runner against ``scenario_harness`` itself, not a stand-in.

    :class:`_FakeHarness` keeps the containers out of the way, and with them
    two refusals the real :meth:`ScenarioHarness.reach_step` makes: a step
    that is not the next one of the scenario's declared path, and a step after
    the first reached before ``follow_ledger`` named the case.  These tests
    drive an already-registered scenario's path through the real harness, so
    what the runner reports is pinned against the object it reports to.
    """

    @pytest.fixture(autouse=True)
    def _real_harness(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> Iterator[None]:
        """Leave the harness real; stub only what reads a container or disk."""
        registry.discover_scenarios()  # so 'rv' has a declared path here
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
        # Both role checks and the ledger tail read the canonical case
        # through a client.  Patched on the harness module, which imported
        # each of them by name, so patching their own module would be a no-op.
        monkeypatch.setattr(
            harness_module, "require_case_role", lambda *a, **k: None
        )
        monkeypatch.setattr(
            harness_module, "require_report_submitter", lambda *a, **k: None
        )
        monkeypatch.setattr(
            harness_module, "case_ledger_length", lambda *a, **k: 2
        )
        reset_demo_failures()
        yield
        reset_demo_failures()

    @staticmethod
    def _open_cast(
        seen: list[ScenarioHarness],
    ) -> Callable[[ScenarioHarness], StoryState]:
        """Build the run's state on the harness the runner entered."""

        def open_cast(harness: ScenarioHarness) -> StoryState:
            seen.append(harness)
            return StoryState(
                cast={
                    "reporter": make_session("urn:test:reporter"),
                    "vendor": make_session("urn:test:vendor"),
                },
                case_actor_client=MagicMock(),
                harness=harness,
                dump=lambda _state: None,
            )

        return open_cast

    @pytest.mark.spec("DEMOCI-11-013")
    def test_the_real_harness_records_each_mark_where_the_story_passed_it(
        self,
    ) -> None:
        """The marks the real harness keeps, with the tail each was made at."""
        seen: list[ScenarioHarness] = []
        plot = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            _opens_the_case,
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
        )

        run_story("rv", plot, self._open_cast(seen))

        (harness,) = seen
        assert [
            (mark.branch_point, mark.choice, mark.ledger_tail)
            for mark in harness.marks
        ] == [
            ("reporter-whom-to-tell", "vendor", 0),
            ("vendor-after-answer", "report-fix-ready", 2),
        ]
        assert not demo_failures()

    @pytest.mark.spec("DEMOCI-11-014")
    def test_a_choice_out_of_the_declared_order_is_refused(self) -> None:
        """The refusal ``_FakeHarness`` cannot make: the ORDER check."""
        seen: list[ScenarioHarness] = []
        plot = story(
            _opens_the_case,
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
        )

        with pytest.raises(DemoScenarioStepError, match="declared path says"):
            run_story("rv", plot, self._open_cast(seen))

        (harness,) = seen
        assert harness.marks == []

    @pytest.mark.spec("DEMOCI-11-013", "DEMOCI-11-047")
    def test_a_later_step_before_the_case_ledger_is_refused(self) -> None:
        """The second refusal it cannot make: no ledger to mark the step in."""
        seen: list[ScenarioHarness] = []
        plot = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
        )

        with pytest.raises(DemoScenarioStepError, match="before following"):
            run_story("rv", plot, self._open_cast(seen))

        (harness,) = seen
        assert [mark.branch_point for mark in harness.marks] == [
            "reporter-whom-to-tell"
        ]
