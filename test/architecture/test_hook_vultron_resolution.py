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

"""A pre-commit hook imports the ``vultron`` of the checkout it runs in (#5571).

Hooks run ``uv run <console-script>``; a console script's first ``sys.path``
entry is the venv's ``bin/``, so any inherited ``PYTHONPATH`` entry outranks
the checkout's editable install.  The devcontainer image once exported
``PYTHONPATH=/app``, and every hook in a worktree then checked ``/app``'s code.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"
DEV_STAGE = "dev"

# ``FROM [--flag=...]... <parent> [AS <name>]``; flags such as ``--platform``
# are not the parent image.
_FROM = re.compile(
    r"^FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE
)
_ENV = re.compile(r"^ENV\s+(.*)$", re.IGNORECASE)
# ``PYTHONPATH=<value>`` anywhere on a multi-key line, or the legacy
# ``ENV PYTHONPATH <value>`` single-key form.
_PYTHONPATH_KEY = re.compile(r"(?:^|\s)PYTHONPATH(?:=|\s+)(\S*)")
_EMPTY_VALUES = ("", '""', "''")


def _instructions(text: str) -> list[str]:
    """Dockerfile instructions, one per entry, with ``\\`` continuations joined."""
    instructions: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not pending and (not line or line.startswith("#")):
            continue
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        instructions.append(pending + line)
        pending = ""
    if pending:
        instructions.append(pending.strip())
    return instructions


def _stages(text: str) -> dict[str, tuple[str, list[str]]]:
    """Each named stage's parent image and its own instruction lines."""
    stages: dict[str, tuple[str, list[str]]] = {}
    lines: list[str] = []
    for line in _instructions(text):
        match = _FROM.match(line)
        if match:
            parent, name = match.groups()
            lines = []
            stages[name or parent] = (parent, lines)
        else:
            lines.append(line)
    return stages


def _lineage(
    stages: dict[str, tuple[str, list[str]]], stage: str
) -> list[str]:
    """*stage* and every stage it builds on, nearest first."""
    chain: list[str] = []
    while stage in stages:
        chain.append(stage)
        stage = stages[stage][0]
    return chain


def _dev_exports(text: str) -> list[str]:
    """Each non-empty PYTHONPATH export in the dev stage's lineage."""
    stages = _stages(text)
    lineage = _lineage(stages, DEV_STAGE)
    assert lineage, f"no {DEV_STAGE!r} stage in {DOCKERFILE}"

    exports = [
        f"{stage}: {line}"
        for stage in lineage
        for line in stages[stage][1]
        if (env := _ENV.match(line))
        and (key := _PYTHONPATH_KEY.search(env.group(1)))
        and key.group(1) not in _EMPTY_VALUES
    ]
    return exports


@pytest.mark.parametrize(
    "env_line",
    [
        "ENV PYTHONPATH=/app",
        "ENV PYTHONPATH /app",
        "ENV FOO=1 PYTHONPATH=/app",
        "ENV FOO=1 \\\n    PYTHONPATH=/app",
    ],
    ids=["equals", "space-form", "multi-key", "continuation"],
)
def test_guard_detects_every_env_form(env_line: str) -> None:
    """The guard sees an export however ``ENV`` spells it, through ``--platform``."""
    text = (
        "FROM --platform=$BUILDPLATFORM python:3.13 AS base\n"
        f"{env_line}\n"
        "FROM base AS dev\n"
        "RUN true\n"
    )
    assert _dev_exports(text) == [
        f"base: {line}" for line in _instructions(env_line)
    ]


@pytest.mark.parametrize(
    "env_line",
    ["ENV PYTHONPATH=", 'ENV PYTHONPATH=""', "ENV OTHERPYTHONPATH=/x"],
)
def test_guard_ignores_cleared_or_unrelated_keys(env_line: str) -> None:
    """Clearing PYTHONPATH, or a key merely ending in it, is not an export."""
    assert _dev_exports(f"FROM python:3.13 AS dev\n{env_line}\n") == []


def test_dev_image_does_not_export_pythonpath() -> None:
    """No stage the devcontainer image builds on sets a non-empty PYTHONPATH."""
    exports = _dev_exports(DOCKERFILE.read_text(encoding="utf-8"))
    assert not exports, (
        "The devcontainer image must not export PYTHONPATH: it outranks each "
        "checkout's editable install, so hooks in a worktree import another "
        f"checkout's vultron (#5571). Found: {exports}"
    )


def test_console_script_child_resolves_this_checkout(tmp_path: Path) -> None:
    """A child given the hook environment unmodified imports this ``vultron``.

    The probe runs as a script outside the checkout, so — as for a console
    script — nothing but the editable install and the inherited environment
    puts ``vultron`` on its path.  A failure here inside a worktree means the
    container still exports ``PYTHONPATH``: rebuild it with
    ``./start-dev.sh <slot> --rebuild``.
    """
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import vultron\nprint(vultron.__file__)\n", encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, str(probe)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env=dict(os.environ),
    )
    assert result.returncode == 0, (
        f"probe could not import vultron "
        f"(PYTHONPATH={os.environ.get('PYTHONPATH')!r}):\n{result.stderr}"
    )

    resolved = Path(result.stdout.strip()).resolve()
    assert resolved.is_relative_to(REPO_ROOT), (
        f"vultron resolved to {resolved}, outside {REPO_ROOT}; "
        f"PYTHONPATH={os.environ.get('PYTHONPATH')!r}"
    )
