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

"""The committed recordings under ``ui/src/recordings/``, and their layout check."""

import shutil
from collections.abc import Sequence
from pathlib import Path

import click

from vultron.demo.recordings.ledgers import CANONICAL_ACTOR
from vultron.demo.recordings.topology import REPO_ROOT

RECORDINGS_DIR = REPO_ROOT / "ui" / "src" / "recordings"
RECORDING_SUFFIX = ".jsonl"


def recording_path(scenario: str) -> Path:
    """Return the committed path of a scenario's recording."""
    return RECORDINGS_DIR / scenario / f"{CANONICAL_ACTOR}{RECORDING_SUFFIX}"


def write_recording(scenario: str, recording: str) -> Path:
    """Replace the committed recording of *scenario* with *recording*.

    Anything else in the scenario's directory is removed with it.
    """
    scenario_dir = RECORDINGS_DIR / scenario
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True)
    path = recording_path(scenario)
    path.write_text(recording, encoding="utf-8")
    return path


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
    expected = f"{CANONICAL_ACTOR}{RECORDING_SUFFIX}"
    for name in sorted(registered & recorded):
        held = sorted(path.name for path in (RECORDINGS_DIR / name).iterdir())
        if expected not in held:
            problems.append(f"{name}: has no {expected}")
        if extra := [held_name for held_name in held if held_name != expected]:
            problems.append(
                f"{name}: holds files other than {expected}: {extra}"
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
