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
"""The story API: fragments, named prefixes, choices and the runner (#5533).

A scenario written as composition states its story once and the registry reads
its path off the story's choices (DEMOCI-11-019); declaring both forms fails
discovery (DEMOCI-11-024).  These tests cover the derivation, both declaration
forms, the refusals, and the runner's own job: play the items in order and
report each choice to the harness with the deciding actor's id, so a composed
scenario places no ``reach_step`` by hand.

Kept in ``test/demo_unit/`` for the reason ``test_scenario_registry.py``
gives: ``test/demo/`` is auto-marked ``integration`` and deselected by default.
"""

from __future__ import annotations

import contextlib
import pathlib
from collections.abc import Callable, Iterator
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import (
    harness as harness_module,
    story as story_module,
)
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.story import (
    Choose,
    Story,
    StoryProp,
    StoryState,
    UnseatedContainer,
    choose,
    run_story,
    story,
)
from vultron.demo.scenario import registry
from vultron.demo.scenario.registry import ScenarioSpec, scenario
from vultron.demo.scenario.tree import build_scenario_tree
from vultron.demo.utils import demo_failures, demo_step, reset_demo_failures
from vultron.errors import (
    DemoScenarioRegistryError,
    DemoScenarioStepError,
    DemoStoryError,
)

#: ``rv``'s path, as choices of a story.  Reused as the fixture story so the
#: fixture registry it is spliced into stays one well-formed tree.
_RV_CHOICES = (
    ("reporter-whom-to-tell", "vendor"),
    ("vendor-after-answer", "report-fix-ready"),
)


def _fragment(
    name: str, log: list[str], fails: bool = False
) -> Callable[[StoryState], None]:
    """A fragment that records that it ran, and optionally fails doing it.

    A failing fragment fails the way a demo fragment does: inside
    ``demo_step``, which records the failure and lets the story go on
    (DEMOCI-01-003).
    """

    def run(_state: StoryState) -> None:
        log.append(name)
        if fails:
            with demo_step(f"{name} fails"):
                raise AssertionError(f"{name} exploded")

    run.__name__ = name
    return run


def _session(actor_id: str) -> ActorSession:
    """A session whose actor carries *actor_id* and nothing else."""
    actor = MagicMock()
    actor.id_ = actor_id
    return ActorSession(client=MagicMock(base_url="x"), actor=actor)


def _state(
    unseated: dict[str, UnseatedContainer] | None = None,
    **cast: ActorSession,
) -> StoryState:
    return StoryState(
        cast=cast,
        case_actor_client=MagicMock(),
        harness=MagicMock(),
        dump=lambda _state: None,
        unseated=unseated or {},
    )


#: A prop of the shape a family declares beside its own fragments.
_KEPT_ID: StoryProp[str] = StoryProp("embargo in force", str)


def _rv_story(log: list[str] | None = None) -> Story:
    """A composed fixture story walking ``rv``'s path."""
    entries = log if log is not None else []
    return story(
        choose("reporter-whom-to-tell", "vendor", by="reporter"),
        _fragment("submit", entries),
        choose("vendor-after-answer", "report-fix-ready", by="vendor"),
        _fragment("fix", entries),
    )


# ---------------------------------------------------------------------------
# choose(...) and story(...)
# ---------------------------------------------------------------------------


class TestChoose:
    @pytest.mark.spec("DEMOCI-11-013")
    def test_an_unknown_branch_point_is_refused_where_it_is_written(
        self,
    ) -> None:
        with pytest.raises(
            DemoScenarioRegistryError, match="unknown branch point"
        ):
            choose("no-such-branch-point", "vendor", by="reporter")

    @pytest.mark.spec("DEMOCI-11-013")
    def test_an_unknown_choice_is_refused_where_it_is_written(self) -> None:
        with pytest.raises(DemoScenarioRegistryError, match="no choice"):
            choose("reporter-whom-to-tell", "nobody", by="reporter")

    @pytest.mark.spec("DEMOCI-11-013")
    @pytest.mark.parametrize("by", ["", None])
    def test_a_choice_names_the_actor_that_decides(self, by: Any) -> None:
        with pytest.raises(DemoStoryError, match="as the actor that decides"):
            choose("reporter-whom-to-tell", "vendor", by=by)

    def test_the_step_is_the_branch_point_and_choice_pair(self) -> None:
        item = choose("reporter-whom-to-tell", "vendor", by="reporter")
        assert item.step == ("reporter-whom-to-tell", "vendor")


class TestStoryAssembly:
    def test_a_named_prefix_is_spliced_not_nested(self) -> None:
        """A prefix's items become the start of the whole, one flat sequence."""
        log: list[str] = []
        prefix = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            _fragment("submit", log),
        )
        whole = story(
            prefix,
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
            _fragment("fix", log),
        )
        assert whole.items[:2] == prefix.items
        assert len(whole.items) == 4
        assert not any(isinstance(item, Story) for item in whole.items)

    @pytest.mark.spec("DEMOCI-11-019")
    def test_the_path_is_the_choices_in_order(self) -> None:
        assert _rv_story().path == _RV_CHOICES

    def test_a_story_with_no_items_is_refused(self) -> None:
        with pytest.raises(DemoStoryError, match="at least one item"):
            story()

    def test_a_part_that_is_not_an_item_is_refused(self) -> None:
        with pytest.raises(DemoStoryError, match="neither a named prefix"):
            story("reporter-whom-to-tell")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# StoryState
# ---------------------------------------------------------------------------


class TestStoryState:
    def test_an_unseated_actor_names_the_cast_it_is_missing_from(self) -> None:
        state = _state(reporter=_session("urn:test:reporter"))
        with pytest.raises(DemoStoryError, match=r"it seats \['reporter'\]"):
            state.actor("vendor")

    def test_reading_the_case_before_it_opens_raises(self) -> None:
        state = _state(reporter=_session("urn:test:reporter"))
        with pytest.raises(DemoStoryError, match="has not opened a case"):
            _ = state.case
        with pytest.raises(DemoStoryError, match="no report yet"):
            _ = state.report
        with pytest.raises(DemoStoryError, match="no report Offer yet"):
            _ = state.offer

    def test_opening_the_case_arms_the_dump_and_follows_the_ledger(
        self,
    ) -> None:
        """DEMOMA-23-003: the dump is registered the moment there is a case."""
        state = _state(reporter=_session("urn:test:reporter"))
        case = MagicMock(id_="urn:test:case")
        dumped: list[StoryState] = []
        state.dump = dumped.append

        state.open_case(case=case, report=MagicMock(), offer=MagicMock())

        assert state.case is case
        harness = cast(MagicMock, state.harness)
        harness.follow_ledger.assert_called_once_with(
            state.case_actor_client, "urn:test:case"
        )
        harness.dump_with.assert_called_once()
        harness.dump_with.call_args.args[0]()
        assert dumped == [state]

    def test_a_delivered_invite_is_read_back_by_cast_name(self) -> None:
        state = _state(vendor=_session("urn:test:vendor"))
        assert state.delivered_invite("vendor") is None
        state.invited("vendor", "urn:test:invite")
        assert state.delivered_invite("vendor") == "urn:test:invite"

    def test_an_undelivered_invite_clears_the_slot(self) -> None:
        """``None`` is what the answer fragment refuses in its own gate."""
        state = _state(vendor=_session("urn:test:vendor"))
        state.invited("vendor", "urn:test:invite")
        state.invited("vendor", None)
        assert state.delivered_invite("vendor") is None

    def test_an_invite_for_an_unseated_actor_raises(self) -> None:
        state = _state(vendor=_session("urn:test:vendor"))
        with pytest.raises(DemoStoryError, match="does not seat"):
            state.invited("coordinator", "urn:test:invite")
        with pytest.raises(DemoStoryError, match="does not seat"):
            state.delivered_invite("coordinator")

    def test_an_actor_with_no_id_cannot_decide_a_step(self) -> None:
        session = _session("urn:test:reporter")
        cast(MagicMock, session.actor).id_ = None
        state = _state(reporter=session)
        with pytest.raises(DemoStoryError, match="has no actor id"):
            state.actor_id("reporter")


# ---------------------------------------------------------------------------
# run_story
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-17-001")
class TestStoryProps:
    """What one family passes between its own steps (#5534).

    A prop rather than a field on the state or a per-family subclass: a
    fragment is typed ``Callable[[StoryState], None]``, so a subclass of the
    state is not assignable to it.
    """

    def test_a_kept_prop_is_read_back_by_the_later_fragment(self) -> None:
        state = _state()
        state.keep(_KEPT_ID, "urn:uuid:embargo-1")
        assert state.kept(_KEPT_ID) == "urn:uuid:embargo-1"

    def test_a_prop_no_fragment_kept_raises(self) -> None:
        """The accessor raises rather than handing back a ``None``.

        That is what lets ``run_story`` stop a story whose earlier step failed
        instead of acting on a stand-in.
        """
        with pytest.raises(DemoStoryError, match="embargo in force"):
            _state().kept(_KEPT_ID)

    def test_a_value_of_the_wrong_type_is_refused_where_it_is_kept(
        self,
    ) -> None:
        """A helper that records its own failure returns ``None``.

        Keeping that would leave the dependent fragment reading a stand-in, so
        the refusal happens on the way in, not on the way out.
        """
        state = _state()
        with pytest.raises(DemoStoryError, match="is not one"):
            state.keep(_KEPT_ID, cast(Any, None))
        with pytest.raises(DemoStoryError):
            state.kept(_KEPT_ID)

    def test_two_props_of_the_same_type_do_not_collide(self) -> None:
        """A second revision keeps a second prop, never overwrites the first.

        Overwriting would leave the previous id in place when a revision
        failed, and the steps that presuppose the new one would run against
        the old embargo instead of stopping.
        """
        revised: StoryProp[str] = StoryProp("revised embargo", str)
        state = _state()
        state.keep(_KEPT_ID, "first")
        state.keep(revised, "second")
        assert (state.kept(_KEPT_ID), state.kept(revised)) == (
            "first",
            "second",
        )


@pytest.mark.spec("DEMOCI-11-018")
class TestSeatingACharacterActor:
    """Containers the shared opening leaves for a later step to seed.

    The opening seeds only the containers every sibling of the family uses:
    each actor and peer record it writes is one more read of the recording
    clock, so one extra container moves the first ledger entry's timestamp
    away from the siblings whose bytes it must match (#5532, #5534).
    """

    def test_a_waiting_container_carries_its_client_and_deterministic_id(
        self,
    ) -> None:
        client = MagicMock(base_url="v2")
        state = _state(
            unseated={"v2": UnseatedContainer("V2", client, "urn:test:v2")}
        )
        waiting = state.container("v2")
        assert (waiting.client, waiting.actor_id) == (client, "urn:test:v2")

    def test_seating_moves_the_name_from_waiting_to_the_cast(self) -> None:
        state = _state(
            unseated={"v2": UnseatedContainer("V2", MagicMock(), None)}
        )
        session = _session("urn:test:v2")
        state.seat("v2", session)
        assert state.actor("v2") is session
        assert "v2" not in state.unseated

    def test_seating_a_name_twice_is_refused(self) -> None:
        """Re-seating would redirect every later fragment that names it."""
        state = _state(
            unseated={"v2": UnseatedContainer("V2", MagicMock(), None)}
        )
        state.seat("v2", _session("urn:test:v2"))
        with pytest.raises(DemoStoryError, match="already seats"):
            state.seat("v2", _session("urn:test:other"))

    def test_seating_a_name_no_container_waited_for_is_refused(self) -> None:
        with pytest.raises(DemoStoryError, match="no container waiting"):
            _state().seat("v2", _session("urn:test:v2"))

    def test_an_unseated_actor_says_the_container_is_still_waiting(
        self,
    ) -> None:
        """The message tells a reader which half of the handover is missing."""
        state = _state(
            unseated={"v2": UnseatedContainer("V2", MagicMock(), None)}
        )
        with pytest.raises(DemoStoryError, match="does not seat yet"):
            state.actor("v2")


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
                "participant in the case (DEMOCI-11-013)."
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

    monkeypatch.setattr(story_module, "scenario_harness", stub)
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
        state = _state(
            reporter=_session("urn:test:reporter"),
            vendor=_session("urn:test:vendor"),
        )

        run_story("rv", _rv_story(log), lambda _harness: state)

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
        ``test/demo/test_coordinated_story.py::TestOpenCoordinatedCast::
        test_a_failed_seeding_leaves_no_cast_to_tell_the_story_with``.
        """
        seen: list[object] = []

        def open_cast(harness: Any) -> StoryState:
            seen.append(harness)
            return _state(
                reporter=_session("urn:test:reporter"),
                vendor=_session("urn:test:vendor"),
            )

        run_story("rv", _rv_story(), open_cast)
        assert seen == [fake_harness]

    def test_a_choice_by_an_unseated_actor_fails_the_run(
        self, fake_harness: _FakeHarness
    ) -> None:
        state = _state(vendor=_session("urn:test:vendor"))
        with pytest.raises(DemoStoryError, match="does not seat"):
            run_story("rv", _rv_story(), lambda _harness: state)
        assert fake_harness.marks == []

    @pytest.mark.spec("DEMOCI-11-013")
    def test_a_mis_declared_step_raises_on_a_run_that_had_not_failed(
        self, fake_harness: _FakeHarness
    ) -> None:
        """A declaration defect is not a soft failure to be blessed later."""
        fake_harness.refuse = "vendor-after-answer"
        state = _state(
            reporter=_session("urn:test:reporter"),
            vendor=_session("urn:test:vendor"),
        )
        with pytest.raises(DemoScenarioStepError, match="not a"):
            run_story("rv", _rv_story(), lambda _harness: state)

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
        state = _state(
            reporter=_session("urn:test:reporter"),
            vendor=_session("urn:test:vendor"),
        )
        plot = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            _fragment("submit", log, fails=True),
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
            _fragment("fix", log),
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
            state.kept(_KEPT_ID)

        def publishes(state: StoryState) -> None:
            log.append("publish")

        state = _state(
            reporter=_session("urn:test:reporter"),
            vendor=_session("urn:test:vendor"),
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
            state.kept(_KEPT_ID)

        state = _state(
            reporter=_session("urn:test:reporter"),
            vendor=_session("urn:test:vendor"),
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
        state = _state(
            reporter=_session("urn:test:reporter"),
            vendor=_session("urn:test:vendor"),
        )
        plot = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            _fragment("submit", log, fails=True),
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
            _fragment("fix", log),
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
                    "reporter": _session("urn:test:reporter"),
                    "vendor": _session("urn:test:vendor"),
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

    @pytest.mark.spec("DEMOCI-11-013")
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


# ---------------------------------------------------------------------------
# @scenario(story=...) — the path is read off the story (DEMOCI-11-019)
# ---------------------------------------------------------------------------


def _register_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    name: str,
    story_obj: Story | None = None,
    path: Any = None,
) -> ScenarioSpec:
    """Register a fixture scenario in an isolated copy of the registry."""
    monkeypatch.setattr(registry, "_REGISTRY", dict(registry._REGISTRY))
    registry._REGISTRY.pop(name, None)
    decorate = scenario(
        name=name,
        label=name.upper(),
        participants="Reporter + Vendor",
        feature="Fixture",
        in_pr_set=False,
        story=story_obj,
        path=path,
    )

    def fixture_main() -> None:
        """Stand in for a composed scenario's main()."""

    fixture_main.__module__ = "test.demo_unit.test_story"
    decorate(fixture_main)
    return registry._REGISTRY[name]


class TestRegisteringAStory:
    @pytest.mark.spec("DEMOCI-11-019")
    def test_a_composed_scenarios_path_is_its_storys_choices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The derived path is the one the fixture registry's tree holds."""
        composed = _rv_story()
        spec = _register_fixture(monkeypatch, name="rv", story_obj=composed)
        assert spec.path == composed.path
        # Which form declared the path is what the ratchets read to decide
        # whether the scenario may place a reach_step by hand (DEMOCI-11-019).
        assert spec.composed is True

        tree = build_scenario_tree(registry.registered_scenarios())
        assert tree.endings()["rv"].prefix == composed.path

    @pytest.mark.spec("DEMOCI-11-014")
    def test_a_scenario_not_yet_composed_still_declares_a_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spec = _register_fixture(monkeypatch, name="rv", path=_RV_CHOICES)
        assert spec.path == _RV_CHOICES
        assert spec.composed is False

    @pytest.mark.spec("DEMOCI-11-024")
    def test_declaring_both_a_story_and_a_path_fails_discovery(self) -> None:
        with pytest.raises(
            DemoScenarioRegistryError, match="both a story and a path"
        ):
            scenario(
                name="rv",
                label="RV",
                participants="Reporter + Vendor",
                feature="Fixture",
                in_pr_set=False,
                story=_rv_story(),
                path=_RV_CHOICES,
            )

    @pytest.mark.spec("DEMOCI-11-014")
    def test_declaring_neither_fails_discovery(self) -> None:
        with pytest.raises(
            DemoScenarioRegistryError, match="neither a story nor a path"
        ):
            scenario(
                name="rv",
                label="RV",
                participants="Reporter + Vendor",
                feature="Fixture",
                in_pr_set=False,
            )


# ---------------------------------------------------------------------------
# The composed scenarios keep their place on the tree (DEMOMA-17-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOCI-11-019", "DEMOMA-17-002")
@pytest.mark.parametrize(
    ("module_name", "expected"),
    [
        (
            "vultron.demo.scenario.rcv_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "accept"),
                ("reporter-after-join", "ask-vendor"),
                ("coordinator-after-answer", "publish"),
            ),
        ),
        (
            "vultron.demo.scenario.rcv_reject_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "reject"),
            ),
        ),
        (
            "vultron.demo.scenario.rcvcv_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "accept"),
                ("reporter-after-join", "ask-vendor"),
                ("coordinator-after-answer", "invite-coordinator"),
            ),
        ),
        (
            "vultron.demo.scenario.rcv_embargo_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "accept"),
                ("reporter-after-join", "propose-embargo"),
                ("vendor-after-embargo", "report-fix-ready"),
            ),
        ),
        (
            "vultron.demo.scenario.rcvv_embargo_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "accept"),
                ("reporter-after-join", "propose-embargo"),
                ("vendor-after-embargo", "propose-revision"),
            ),
        ),
    ],
)
def test_a_composed_scenario_keeps_the_path_it_declared(
    module_name: str, expected: tuple[tuple[str, str], ...]
) -> None:
    """Composition moved the code, not the scenario's place on the tree.

    Pinned against literals rather than against the registry, which would
    compare the derivation with itself.
    """
    import importlib

    module = importlib.import_module(module_name)
    assert module.STORY.path == expected


@pytest.mark.spec("DEMOMA-17-001")
def test_the_two_composed_scenarios_share_one_opening() -> None:
    """``rcv`` and ``rcv-reject`` start from the same prefix object's items."""
    import importlib

    from vultron.demo.helpers.coordinated_story import (
        COORDINATOR_INVITES_VENDOR,
    )

    rcv = importlib.import_module("vultron.demo.scenario.rcv_demo")
    rcv_reject = importlib.import_module(
        "vultron.demo.scenario.rcv_reject_demo"
    )
    shared = len(COORDINATOR_INVITES_VENDOR.items)
    assert rcv.STORY.items[:shared] == COORDINATOR_INVITES_VENDOR.items
    assert rcv_reject.STORY.items[:shared] == COORDINATOR_INVITES_VENDOR.items
    assert isinstance(rcv.STORY.items[shared], Choose)
    assert isinstance(rcv_reject.STORY.items[shared], Choose)


#: Each stretch the Reporter → Coordinator → Vendor family shares, with the
#: scenarios that start from it.  One named prefix per branch point the family
#: parts at, each nesting the one before (#5534).
_FAMILY_PREFIXES = [
    (
        "COORDINATOR_INVITES_VENDOR",
        ("rcv", "rcv_reject", "rcvcv", "rcv_embargo", "rcvv_embargo"),
    ),
    (
        "VENDOR_JOINS_THE_CASE",
        ("rcv", "rcvcv", "rcv_embargo", "rcvv_embargo"),
    ),
    ("REPORTER_ASKS_THE_VENDOR", ("rcv", "rcvcv")),
]


@pytest.mark.spec("DEMOMA-17-001")
@pytest.mark.spec("DEMOCI-11-018")
@pytest.mark.parametrize(("prefix_name", "scenarios"), _FAMILY_PREFIXES)
def test_every_shared_stretch_of_the_family_is_one_named_prefix(
    prefix_name: str, scenarios: tuple[str, ...]
) -> None:
    """Each scenario starts from the prefix object's own items, not a copy.

    Assembling siblings from fragments alone lets one of them slip a step in
    before the branch point, which the byte-identity check would then catch
    only after a regeneration.  Comparing against the prefix's items pins it
    where the story is written.  The item right after the prefix must be a
    choice: that is the branch point the scenarios part at.
    """
    import importlib

    from vultron.demo.helpers import coordinated_story

    prefix: Story = getattr(coordinated_story, prefix_name)
    shared = len(prefix.items)
    for stem in scenarios:
        module = importlib.import_module(f"vultron.demo.scenario.{stem}_demo")
        assert module.STORY.items[:shared] == prefix.items, (
            f"{stem} does not start from {prefix_name}"
        )
        assert isinstance(module.STORY.items[shared], Choose), (
            f"{stem} places a step before the branch point it parts at"
        )


@pytest.mark.spec("DEMOMA-20-013")
@pytest.mark.spec("DEMOMA-21-015")
def test_the_embargo_pair_shares_the_proposal_opening() -> None:
    """Both embargo scenarios start from ``REPORTER_PROPOSES_EMBARGO``.

    The pair's own prefix nests ``VENDOR_JOINS_THE_CASE`` and carries on
    through the default embargo's confirmation, the Reporter's revision of it
    and the note thread that follows.
    """
    import importlib

    from vultron.demo.helpers.coordinated_embargo_story import (
        REPORTER_PROPOSES_EMBARGO,
    )
    from vultron.demo.helpers.coordinated_story import VENDOR_JOINS_THE_CASE

    joined = len(VENDOR_JOINS_THE_CASE.items)
    assert (
        REPORTER_PROPOSES_EMBARGO.items[:joined] == VENDOR_JOINS_THE_CASE.items
    )

    shared = len(REPORTER_PROPOSES_EMBARGO.items)
    for stem in ("rcv_embargo", "rcvv_embargo"):
        module = importlib.import_module(f"vultron.demo.scenario.{stem}_demo")
        assert (
            module.STORY.items[:shared] == REPORTER_PROPOSES_EMBARGO.items
        ), f"{stem} does not start from REPORTER_PROPOSES_EMBARGO"
        assert isinstance(module.STORY.items[shared], Choose)
