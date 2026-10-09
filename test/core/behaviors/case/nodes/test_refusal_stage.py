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
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
    RefusalEffectsBestEffort,
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
