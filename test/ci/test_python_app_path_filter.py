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
"""``python-app.yml`` fires on each path the suite it runs actually reads.

A check is only installed if the workflow that runs it fires on the change it
polices; one that is not is green on exactly the pull request it exists to
catch (DOCBW-03-015, #4506). This module pins one entry of the filter per
defect that found it, each with the file the suite reads through it:

- ``uv.lock``. The demo workflow skips Dependabot PRs on the premise that this
  workflow still tests them (DEMOCI-02-004), which DEMOCI-02-016 secures. A
  bump inside an existing version range touches only the lockfile, so without
  it no test ran at all — which is how the py_trees 2.6.0 bump reached ``main``
  untested (#3610).
- Committed vocab examples. A hand edit or a half-finished regeneration of one
  touches only ``docs/reference/examples/``, which
  ``test/architecture/test_vocab_examples_current.py`` compares byte for byte
  against a fresh generation (DEMOCI-02-021, #5776).
- Shell scripts. ``test_shell_script_portability.py`` reads every tracked
  ``*.sh``, and a `mapfile` added under ``.github/scripts/`` would otherwise
  have reached ``main`` with every check green (#5698).
- Composite actions. ``test_workflow_failure_notification.py`` asserts the
  ``notify-failure`` action's steps (CISEC-05-017, CISEC-05-018, CISEC-05-020)
  and ``test_site_build_shared_action.py`` its build-site step order, but the
  only other job a change under ``.github/actions/`` triggers is
  ``actions-lint.yml``, which runs actionlint rather than pytest.
- The demo UI's committed artifacts and recordings. The drift tests under
  ``test/metadata/demo_scenarios/`` compare ``ui/src/data/`` with a fresh
  export, and ``test/demo_unit/test_recordings.py`` validates
  ``ui/src/recordings/`` and ``ui/src/synthetic-ledgers/``, but a pull request
  that edited only them ran neither (#4728).
- ``docker/Dockerfile``. ``test_python_version_floor.py`` checks that the base
  image runs the ``requires-python`` floor or later (IMPLTS-01-010), and no
  other entry matches the Dockerfile, so a base-image bump alone ran no test
  (#6052).

Markdown guarded by a pytest ratchet is the same gap, tracked by #5708.
"""

from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import load_workflow, triggers

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "python-app.yml"
)


def _triggers() -> dict[str, Any]:
    return triggers(load_workflow(WORKFLOW))


@pytest.mark.spec("DEMOCI-02-016")
@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_python_app_workflow_runs_on_lockfile_change(event: str) -> None:
    assert "uv.lock" in _triggers()[event]["paths"]


@pytest.mark.spec("DEMOCI-02-021")
@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_python_app_workflow_runs_on_a_committed_example_change(
    event: str,
) -> None:
    assert "docs/reference/examples/**" in _triggers()[event]["paths"]


@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_python_app_workflow_runs_on_a_shell_script_change(event: str) -> None:
    """A tracked ``*.sh`` reaches the suite that reads it (#5698)."""
    paths = _triggers()[event]["paths"]
    assert "**/*.sh" in paths, (
        f"The {event} paths must include '**/*.sh', or a shell script can "
        "change without test_shell_script_portability.py running:\n"
        + "\n".join(f"  {pattern}" for pattern in paths)
    )
    # The dot-directories `**` may not descend into, named as `*.py` is.
    for directory in (".agents", ".github", ".devcontainer"):
        assert f"{directory}/**/*.sh" in paths, (
            f"The {event} paths must name '{directory}/**/*.sh' explicitly: a "
            "leading-dot directory is not reliably matched by '**'."
        )


@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_python_app_workflow_runs_on_a_composite_action_change(
    event: str,
) -> None:
    """A composite action reaches the suite that asserts its steps."""
    paths = _triggers()[event]["paths"]
    assert ".github/actions/**" in paths, (
        f"The {event} paths must include '.github/actions/**', or an action "
        "can change without the test/ci assertions that read it running:\n"
        + "\n".join(f"  {pattern}" for pattern in paths)
    )


@pytest.mark.parametrize("event", ["push", "pull_request"])
@pytest.mark.parametrize(
    "pattern",
    ["ui/src/data/**", "ui/src/recordings/**", "ui/src/synthetic-ledgers/**"],
)
def test_python_app_workflow_runs_on_a_demo_ui_artifact_change(
    event: str, pattern: str
) -> None:
    """A committed UI artifact or recording reaches the tests that read it."""
    paths = _triggers()[event]["paths"]
    assert pattern in paths, (
        f"The {event} paths must include {pattern!r}, or the committed file can "
        "change without the Python tests that read it running:\n"
        + "\n".join(f"  {p}" for p in paths)
    )


@pytest.mark.spec("IMPLTS-01-010")
@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_python_app_workflow_runs_on_a_dockerfile_change(event: str) -> None:
    """A base-image bump reaches the test that compares it with the floor."""
    paths = _triggers()[event]["paths"]
    assert "docker/Dockerfile" in paths, (
        f"The {event} paths must include 'docker/Dockerfile', or the base "
        "image can change without test_python_version_floor.py running:\n"
        + "\n".join(f"  {p}" for p in paths)
    )
