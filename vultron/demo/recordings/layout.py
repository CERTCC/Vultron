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

"""The committed recordings under ``ui/src/recordings/``, and their layout check.

Each scenario's directory holds two files: the canonical ledger
(``case-actor.jsonl``) and its step marks (``steps.json``), the ledger tail at
each declared step of the scenario's path, which the shared-prefix check reads
(:mod:`.prefix`, DEMOCI-11-017).
"""

import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import click

from vultron.demo.helpers.harness import StepMark, step_marks_text
from vultron.demo.recordings.ledgers import CANONICAL_ACTOR, parse_step_marks
from vultron.demo.recordings.topology import REPO_ROOT
from vultron.demo.scenario.tree import PathStep
from vultron.errors import DemoRecordingError

RECORDINGS_DIR = REPO_ROOT / "ui" / "src" / "recordings"
RECORDING_SUFFIX = ".jsonl"
STEPS_FILENAME = "steps.json"


@dataclass(frozen=True)
class Recording:
    """One scenario's recording: its canonical ledger and its step marks.

    Attributes:
        scenario: The scenario name.
        ledger: The canonical ledger, as JSONL.
        steps: The ledger tail at each declared step of the scenario's path.

    Raises:
        DemoRecordingError: When a step's ledger tail lies past the ledger.
    """

    scenario: str
    ledger: str
    steps: tuple[StepMark, ...]

    def __post_init__(self) -> None:
        entries = len(self.ledger.splitlines())
        for mark in self.steps:
            if mark.ledger_tail > entries:
                raise DemoRecordingError(
                    f"scenario {self.scenario!r} marked step "
                    f"{mark.branch_point}:{mark.choice} at ledger tail "
                    f"{mark.ledger_tail}, past the {entries} entries its "
                    "canonical ledger holds."
                )

    @property
    def entries(self) -> list[str]:
        """The ledger's JSONL lines, one per entry."""
        return self.ledger.splitlines()

    def steps_text(self) -> str:
        """Return the step marks as committed in ``steps.json``."""
        return step_marks_text(self.steps)


def recording_path(scenario: str) -> Path:
    """Return the committed path of a scenario's recording."""
    return RECORDINGS_DIR / scenario / f"{CANONICAL_ACTOR}{RECORDING_SUFFIX}"


def steps_path(scenario: str) -> Path:
    """Return the committed path of a scenario's step marks."""
    return RECORDINGS_DIR / scenario / STEPS_FILENAME


def write_recording(recording: Recording) -> Path:
    """Replace the committed recording of its scenario with *recording*.

    Anything else in the scenario's directory is removed with it.

    Returns:
        The path of the ledger written.
    """
    scenario_dir = RECORDINGS_DIR / recording.scenario
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True)
    path = recording_path(recording.scenario)
    path.write_text(recording.ledger, encoding="utf-8")
    steps_path(recording.scenario).write_text(
        recording.steps_text(), encoding="utf-8"
    )
    return path


def read_recording(scenario: str, path: Sequence[PathStep]) -> Recording:
    """Return the committed recording of *scenario*.

    Args:
        scenario: The scenario name.
        path: Its declared path, which the step marks must cover.

    Raises:
        DemoRecordingError: When either file is missing or unreadable, as
            :func:`~.ledgers.parse_step_marks`, or when a step's ledger tail
            lies past the ledger.
    """
    try:
        ledger = recording_path(scenario).read_text(encoding="utf-8")
        steps = steps_path(scenario).read_text(encoding="utf-8")
    except OSError as exc:
        raise DemoRecordingError(
            f"scenario {scenario!r} has no readable committed recording: "
            f"{exc}. Regenerate with uv run export-demo-recordings."
        ) from exc
    return Recording(
        scenario,
        ledger=ledger,
        steps=parse_step_marks(steps, scenario, path),
    )


def is_current(recording: Recording) -> bool:
    """Whether the committed files of its scenario equal *recording*."""
    ledger, steps = (
        recording_path(recording.scenario),
        steps_path(recording.scenario),
    )
    return (
        ledger.is_file()
        and steps.is_file()
        and ledger.read_text(encoding="utf-8") == recording.ledger
        and steps.read_text(encoding="utf-8") == recording.steps_text()
    )


def layout_problems(scenario_names: Sequence[str]) -> list[str]:
    """Return how the committed recordings disagree with the registry.

    This checks the part of the recordings the registry decides, which set of
    scenarios is recorded (DEMOCI-11-005), and is cheap enough for pre-commit.
    Whether a recording's content is current takes a run of its scenario, which
    the scheduled ``demo-recordings`` workflow does (``--report-changes``).
    """
    registered = set(scenario_names)
    recorded = (
        {path.name for path in RECORDINGS_DIR.iterdir() if path.is_dir()}
        if RECORDINGS_DIR.is_dir()
        else set()
    )
    problems = [
        f"{name}: registered but not recorded"
        for name in sorted(registered - recorded)
    ]
    problems += [
        f"{name}: recorded but not a registered scenario"
        for name in sorted(recorded - registered)
    ]
    expected = (f"{CANONICAL_ACTOR}{RECORDING_SUFFIX}", STEPS_FILENAME)
    for name in sorted(registered & recorded):
        held = sorted(path.name for path in (RECORDINGS_DIR / name).iterdir())
        problems += [
            f"{name}: has no {file_name}"
            for file_name in expected
            if file_name not in held
        ]
        if extra := [
            held_name for held_name in held if held_name not in expected
        ]:
            problems.append(
                f"{name}: holds files other than {' and '.join(expected)}: "
                f"{extra}"
            )
    return problems


def remove_unregistered(registered: set[str]) -> list[str]:
    """Drop the recordings of scenarios no longer registered (a full run).

    Returns the names removed.
    """
    removed = []
    for stale in sorted(RECORDINGS_DIR.glob("*/")):
        if stale.name not in registered:
            shutil.rmtree(stale)
            removed.append(stale.name)
            click.echo(f"Removed {stale.relative_to(REPO_ROOT)}")
    return removed
