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
"""Scored answers, keyed on a nav hash, and the pass rule that compares two navs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Outcome(StrEnum):
    """How one answer scored."""

    SUCCESS = "success"
    """The answer opens a destination page."""
    NEAR = "near"
    """The answer is a group holding a destination, not the page itself."""
    FAIL = "fail"
    GAVE_UP = "gave-up"


class TaskResult(BaseModel):
    """One scored answer, for one task, persona and nav."""

    model_config = ConfigDict(extra="forbid")

    task: str
    persona: str
    run: int = 1
    stage: Literal[1, 2] = 1
    outcome: Outcome
    answer: str | None = None
    """The page the answer opened (Stage 1) or ended on (Stage 2)."""
    label_path: list[str] = Field(default_factory=list)
    clicks: int | None = None
    stalled_at_home: bool = False
    why: str | None = None


class Results(BaseModel):
    """Every scored answer for one nav, keyed on its hash."""

    model_config = ConfigDict(extra="forbid")

    nav: str
    """A name for the nav, such as ``baseline`` or ``proposed``."""
    nav_hash: str
    source: str
    """Where the nav came from: a commit, or a branch at a commit."""
    model: str | None = None
    results: list[TaskResult] = Field(default_factory=list)


@dataclass
class Verdict:
    """The pass rule applied to two navs' results for one stage."""

    baseline_success: int
    proposed_success: int
    total: int
    stalls: list[str]
    worse: list[str]
    """Tasks the proposed nav lost that the baseline won."""
    better: list[str]

    @property
    def passed(self) -> bool:
        return (
            self.proposed_success >= self.baseline_success and not self.stalls
        )


def _success_rate(results: list[TaskResult]) -> dict[str, float]:
    by_task: dict[str, list[bool]] = {}
    for r in results:
        by_task.setdefault(r.task, []).append(r.outcome is Outcome.SUCCESS)
    return {task: sum(wins) / len(wins) for task, wins in by_task.items()}


def tally(
    baseline: Results, proposed: Results, stage: Literal[1, 2] = 1
) -> Verdict:
    """Apply the pass rule: no worse on task success, no stall at home.

    Repeated runs of a task are averaged, so a task counts as a success in
    proportion to the runs that found it.
    """
    base = _success_rate([r for r in baseline.results if r.stage == stage])
    prop = _success_rate([r for r in proposed.results if r.stage == stage])
    tasks = sorted(set(base) | set(prop))
    stalls = sorted(
        {
            r.task
            for r in proposed.results
            if r.stage == stage and r.stalled_at_home
        }
    )
    return Verdict(
        baseline_success=round(sum(base.get(t, 0.0) for t in tasks)),
        proposed_success=round(sum(prop.get(t, 0.0) for t in tasks)),
        total=len(tasks),
        stalls=stalls,
        worse=[t for t in tasks if prop.get(t, 0.0) < base.get(t, 0.0)],
        better=[t for t in tasks if prop.get(t, 0.0) > base.get(t, 0.0)],
    )


def load_results(path: Path) -> Results:
    return Results.model_validate(yaml.safe_load(path.read_text("utf-8")))


def save_results(path: Path, results: Results) -> None:
    data = results.model_dump(mode="json", exclude_none=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88),
        "utf-8",
    )
