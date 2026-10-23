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

"""The refusal-effects stage runs only on a refusal, once (CLP-10-022)."""

import logging

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.diversion_stage import DiversionStage
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
    RefusalEffectsBestEffort,
    enclosing_refusal_reason,
)
from vultron.core.behaviors.idempotency import (
    ReportsIdempotentRepeat,
    SilentIdempotencyGuardMixin,
)


class _Counting(py_trees.behaviour.Behaviour):
    """Counts its ticks and returns a fixed status."""

    def __init__(self, name: str, status: Status = Status.SUCCESS) -> None:
        super().__init__(name=name)
        self.ticks = 0
        self._status = status

    def update(self) -> Status:
        self.ticks += 1
        self.feedback_message = f"{self.name} said {self._status.name}"
        return self._status


def _stage(
    guard_status: Status,
    effect_status: Status = Status.SUCCESS,
    found_ids: list[str] | None = None,
) -> tuple[PreconditionGuardStage, _Counting, _Counting]:
    guard = _Counting("Guard", guard_status)
    effect = _Counting("Effect", effect_status)
    intake = IntakeReceivedActivityNode()
    intake.found_ids = list(found_ids or [])
    stage = PreconditionGuardStage(
        name="Stage",
        guards=py_trees.composites.Sequence(
            name="PreconditionGuards", memory=False, children=[guard]
        ),
        refusal=RefusalEffectsBestEffort(name="RefusalEffects", child=effect),
        intake=intake,
    )
    return stage, guard, effect


@pytest.mark.spec("CLP-10-006")
@pytest.mark.spec("CLP-10-022")
def test_an_accepted_delivery_runs_no_refusal_effect() -> None:
    stage, guard, effect = _stage(Status.SUCCESS)

    stage.tick_once()

    assert stage.status == Status.SUCCESS
    assert guard.ticks == 1
    assert effect.ticks == 0
    assert effect.status == Status.INVALID


@pytest.mark.spec("CLP-10-022")
def test_a_refusal_runs_the_refusal_effects_and_still_fails() -> None:
    stage, _, effect = _stage(Status.FAILURE)

    stage.tick_once()

    assert stage.status == Status.FAILURE
    assert effect.ticks == 1
    assert BTBridge.get_failure_reason(stage) == "Guard said FAILURE"


@pytest.mark.spec("CLP-10-022")
def test_a_failed_refusal_effect_keeps_the_guards_reason(caplog) -> None:
    stage, _, effect = _stage(Status.FAILURE, effect_status=Status.FAILURE)

    with caplog.at_level(logging.WARNING):
        stage.tick_once()

    assert stage.status == Status.FAILURE
    assert effect.status == Status.FAILURE
    assert BTBridge.get_failure_reason(stage) == "Guard said FAILURE"
    assert any(
        "refusal effect 'Effect' failed" in r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING
    )


@pytest.mark.spec("CLP-10-022")
def test_a_redelivery_skips_the_refusal_effects() -> None:
    stage, _, effect = _stage(
        Status.FAILURE, found_ids=["urn:uuid:already-archived"]
    )

    stage.tick_once()

    assert stage.status == Status.FAILURE
    assert stage.skipped_as_redelivery
    assert effect.ticks == 0
    assert effect.status == Status.INVALID
    assert BTBridge.get_failure_reason(stage) == "Guard said FAILURE"


class _RunningThenSuccess(_Counting):
    """Returns RUNNING on its first tick, then SUCCESS."""

    def update(self) -> Status:
        self.ticks += 1
        return Status.RUNNING if self.ticks == 1 else Status.SUCCESS


@pytest.mark.spec("CLP-10-022")
def test_a_running_refusal_effect_resumes_without_rejudging() -> None:
    guard = _Counting("Guard", Status.FAILURE)
    effect = _RunningThenSuccess("Effect")
    stage = PreconditionGuardStage(
        name="Stage",
        guards=py_trees.composites.Sequence(
            name="PreconditionGuards", memory=False, children=[guard]
        ),
        refusal=RefusalEffectsBestEffort(name="RefusalEffects", child=effect),
        intake=IntakeReceivedActivityNode(),
    )

    stage.tick_once()
    assert stage.status == Status.RUNNING

    stage.tick_once()

    assert guard.ticks == 1
    assert effect.ticks == 2
    assert stage.status == Status.FAILURE
    assert BTBridge.get_failure_reason(stage) == "Guard said FAILURE"


def test_a_second_run_resets_the_stage() -> None:
    stage, guard, effect = _stage(Status.FAILURE)
    stage.tick_once()
    stage.tick_once()

    assert guard.ticks == 2
    assert effect.ticks == 2
    assert stage.status == Status.FAILURE


class _RepeatGuard(SilentIdempotencyGuardMixin, py_trees.behaviour.Behaviour):
    """Fails as an idempotent repeat, or as a plain refusal."""

    def __init__(self, repeat: bool) -> None:
        super().__init__(name="RepeatGuard")
        self._repeat = repeat

    def update(self) -> Status:
        self.feedback_message = "already recorded"
        if self._repeat:
            return self._idempotent_failure(
                logging.getLogger(__name__), "%s: repeat", self.name
            )
        return Status.FAILURE


def _stage_with(guard: py_trees.behaviour.Behaviour, effect: _Counting):
    return PreconditionGuardStage(
        name="Stage",
        guards=py_trees.composites.Sequence(
            name="PreconditionGuards", memory=False, children=[guard]
        ),
        refusal=RefusalEffectsBestEffort(name="RefusalEffects", child=effect),
        intake=IntakeReceivedActivityNode(),
    )


@pytest.mark.spec("CLP-10-022")
@pytest.mark.spec("CLP-05-001")
def test_a_skipped_repeat_runs_no_refusal_effect() -> None:
    """A guard's failure that is an idempotent repeat is not a refusal.

    The repeat's effect is already in place, so a ``Reject`` of it would
    contradict that effect (CLP-10-022, CLP-05-001).
    """
    guard = _RepeatGuard(repeat=True)
    effect = _Counting("Effect")
    stage = _stage_with(guard, effect)

    stage.tick_once()

    assert isinstance(guard, ReportsIdempotentRepeat)
    assert guard.failed_as_repeat
    assert stage.status == Status.FAILURE
    assert stage.skipped_as_repeat
    assert effect.ticks == 0
    assert stage.refusal_reason == ""
    assert BTBridge.get_failure_reason(stage) == "already recorded"


@pytest.mark.spec("CLP-10-022")
def test_a_plain_refusal_by_a_repeat_aware_guard_runs_the_effects() -> None:
    guard = _RepeatGuard(repeat=False)
    effect = _Counting("Effect")
    stage = _stage_with(guard, effect)

    stage.tick_once()

    assert not guard.failed_as_repeat
    assert not stage.skipped_as_repeat
    assert effect.ticks == 1


class _ReadsReason(_Counting):
    """Records the refusal reason it can see while it runs."""

    seen: str | None = None

    def update(self) -> Status:
        self.seen = enclosing_refusal_reason(self)
        return super().update()


@pytest.mark.spec("CLP-05-001")
def test_a_refusal_effect_reads_the_guards_reason() -> None:
    guard = _Counting("Guard", Status.FAILURE)
    effect = _ReadsReason("Effect")
    stage = _stage_with(guard, effect)

    stage.tick_once()

    assert stage.refusal_reason == "Guard said FAILURE"
    assert effect.seen == "Guard said FAILURE"


def test_a_node_outside_the_refusal_effects_has_no_refusal_reason() -> None:
    guard = _Counting("Guard", Status.FAILURE)
    effect = _Counting("Effect")
    stage = _stage_with(guard, effect)
    stage.tick_once()

    assert enclosing_refusal_reason(guard) is None
    assert enclosing_refusal_reason(_Counting("Loose")) is None


class _RepeatThenRefusal(_RepeatGuard):
    """A repeat on its first run, a plain refusal after."""

    def update(self) -> Status:
        status = super().update()
        self._repeat = False
        return status


@pytest.mark.spec("CLP-10-022")
def test_the_repeat_flag_is_reset_on_the_next_run() -> None:
    """``SilentIdempotencyGuardMixin.initialise`` clears the last run's repeat."""
    guard = _RepeatThenRefusal(repeat=True)
    effect = _Counting("Effect")
    stage = _stage_with(guard, effect)

    stage.tick_once()
    assert guard.failed_as_repeat
    assert stage.skipped_as_repeat
    assert effect.ticks == 0

    stage.tick_once()

    assert not guard.failed_as_repeat
    assert not stage.skipped_as_repeat
    assert stage.refusal_reason == "already recorded"
    assert effect.ticks == 1


@pytest.mark.spec("CLP-10-022")
def test_a_repeat_off_the_failure_chain_does_not_skip_the_effects() -> None:
    """A Selector's first alternative failing as a repeat did not decide."""
    selector = py_trees.composites.Selector(
        name="Alternatives",
        memory=False,
        children=[
            _RepeatGuard(repeat=True),
            _Counting("Guard", Status.FAILURE),
        ],
    )
    effect = _Counting("Effect")
    stage = _stage_with(selector, effect)

    stage.tick_once()

    assert not stage.skipped_as_repeat
    assert effect.ticks == 1
    assert stage.refusal_reason == "Guard said FAILURE"


@pytest.mark.spec("CLP-10-022")
def test_a_repeat_on_the_failure_chain_skips_the_effects() -> None:
    selector = py_trees.composites.Selector(
        name="Alternatives",
        memory=False,
        children=[
            _Counting("Guard", Status.FAILURE),
            _RepeatGuard(repeat=True),
        ],
    )
    effect = _Counting("Effect")
    stage = _stage_with(selector, effect)

    stage.tick_once()

    assert stage.skipped_as_repeat
    assert effect.ticks == 0


def _diverting_stage(
    condition: _Counting, guard: _Counting
) -> tuple[PreconditionGuardStage, DiversionStage, _Counting]:
    """A stage whose guards are a diversion on *condition*, then *guard*."""
    diversion = DiversionStage("Divert", condition, _Counting("Answer"))
    guards = py_trees.composites.Sequence(
        name="Guards", memory=False, children=[diversion, guard]
    )
    effect = _Counting("Effect")
    return _stage_with(guards, effect), diversion, effect


@pytest.mark.spec("CLP-10-026")
@pytest.mark.spec("CLP-10-022")
def test_a_diverted_delivery_runs_no_refusal_effect() -> None:
    """The diversion already answered the delivery (CLP-10-026)."""
    stage, diversion, effect = _diverting_stage(
        _Counting("Condition"), _Counting("Guard")
    )

    stage.tick_once()

    assert diversion.taken
    assert stage.status == Status.FAILURE
    assert stage.skipped_as_diversion
    assert effect.ticks == 0
    assert stage.refusal_reason == ""
    assert "diverted to Divert" in BTBridge.get_failure_reason(stage)


@pytest.mark.spec("CLP-10-026")
@pytest.mark.spec("CLP-10-022")
def test_a_guard_refusal_after_an_untaken_diversion_runs_the_effects() -> None:
    stage, diversion, effect = _diverting_stage(
        _Counting("Condition", Status.FAILURE),
        _Counting("Guard", Status.FAILURE),
    )

    stage.tick_once()

    assert not diversion.taken
    assert not stage.skipped_as_diversion
    assert effect.ticks == 1
    assert stage.refusal_reason == "Guard said FAILURE"


@pytest.mark.spec("CLP-10-026")
def test_the_diversion_flag_is_reset_on_the_next_run() -> None:
    condition, guard = _Counting("Condition"), _Counting("Guard")
    stage, _, effect = _diverting_stage(condition, guard)
    stage.tick_once()
    assert stage.skipped_as_diversion

    condition._status = Status.FAILURE
    guard._status = Status.FAILURE
    stage.tick_once()

    assert not stage.skipped_as_diversion
    assert effect.ticks == 1


@pytest.mark.spec("CLP-10-026")
@pytest.mark.spec("CLP-10-022")
def test_a_refusal_ahead_of_a_diversion_taken_last_run_runs_the_effects() -> (
    None
):
    """A diversion the next run never reaches has diverted nothing."""
    before = _Counting("Before")
    condition = _Counting("Condition")
    diversion = DiversionStage("Divert", condition, _Counting("Answer"))
    guards = py_trees.composites.Sequence(
        name="Guards", memory=False, children=[before, diversion]
    )
    effect = _Counting("Effect")
    stage = _stage_with(guards, effect)
    stage.tick_once()
    assert stage.skipped_as_diversion and diversion.taken

    before._status = Status.FAILURE
    stage.tick_once()

    assert not diversion.taken
    assert not stage.skipped_as_diversion
    assert effect.ticks == 1
    assert stage.refusal_reason == "Before said FAILURE"
