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

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"
DEV_STAGE = "dev"

_FROM = re.compile(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)
_PYTHONPATH_ENV = re.compile(r"^ENV\s+PYTHONPATH\s*=\s*(\S*)", re.IGNORECASE)


def _stages(text: str) -> dict[str, tuple[str, list[str]]]:
    """Each named stage's parent image and its own instruction lines."""
    stages: dict[str, tuple[str, list[str]]] = {}
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
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


def test_dev_image_does_not_export_pythonpath() -> None:
    """No stage the devcontainer image builds on sets a non-empty PYTHONPATH."""
    stages = _stages(DOCKERFILE.read_text(encoding="utf-8"))
    lineage = _lineage(stages, DEV_STAGE)
    assert lineage[0] == DEV_STAGE, f"no {DEV_STAGE!r} stage in {DOCKERFILE}"

    exports = [
        f"{stage}: {line}"
        for stage in lineage
        for line in stages[stage][1]
        if (match := _PYTHONPATH_ENV.match(line))
        and match.group(1) not in ("", '""')
    ]

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
        check=True,
        cwd=tmp_path,
        env=dict(os.environ),
    )

    resolved = Path(result.stdout.strip()).resolve()
    assert resolved.is_relative_to(REPO_ROOT), (
        f"vultron resolved to {resolved}, outside {REPO_ROOT}; "
        f"PYTHONPATH={os.environ.get('PYTHONPATH')!r}"
    )
