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
"""Run a ``.agents/skills/shared/`` script against stand-in ``gh`` and ``uv``.

Shared by the tests of the pr-ship decision scripts (``sync-decision.sh``,
``verify-merge-gate.sh``, ``verify-ci-gate.sh``). ``gh`` is ``_fake_gh.py``,
driven by rules; ``uv`` prints ``$FAKE_UV_STDOUT`` and exits
``$FAKE_UV_EXIT``, standing in for ``uv run targeted-tests --overlap``.

Like ``test/support/git_repo.py``, every git call drops inherited ``GIT_*``
variables (a git hook running the suite sets them) and turns signing off.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SHARED = Path(__file__).resolve().parents[2] / ".agents/skills/shared"
_FAKE_GH = Path(__file__).with_name("_fake_gh.py")
_FAKE_UV = (
    '#!/bin/sh\nprintf "%s" "${FAKE_UV_STDOUT:-}"\nexit "${FAKE_UV_EXIT:-0}"\n'
)


_IDENTITY = (
    "-c", "user.email=t@t",
    "-c", "user.name=t",
    "-c", "commit.gpgsign=false",
)  # fmt: skip


def clean_env() -> dict[str, str]:
    """``os.environ`` without the ``GIT_*`` variables a hook would leak."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> str:
    """Run git in *repo* with a fixed identity; return its stdout."""
    return subprocess.run(
        ["git", *_IDENTITY, *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=clean_env(),
    ).stdout.strip()


def commit(repo: Path, name: str, text: str, message: str = "work") -> None:
    """Write *name* in *repo* and commit everything."""
    (repo / name).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", message)


def pr_view(
    mergeable: str = "MERGEABLE",
    status: str = "CLEAN",
    *,
    base: str = "main",
) -> dict:
    """A rule answering ``gh pr view --json <merge-state fields>``."""
    return {
        "match": ["pr view", "mergeable"],
        "stdout": json.dumps(
            {
                "number": 7,
                "mergeable": mergeable,
                "mergeStateStatus": status,
                "isDraft": status == "DRAFT",
                "baseRefName": base,
                "headRefName": "task/7-x",
                "state": "OPEN",
            }
        ),
    }


def status_rollup(*runs: tuple[str, str, str | None]) -> dict:
    """A rule answering ``gh pr view --json statusCheckRollup``.

    Each run is ``(name, status, conclusion)``, **oldest first**: that order
    sets ``startedAt``. The rule then lists them newest-first, the opposite
    order, so a caller that reads the array's last entry rather than sorting by
    ``startedAt`` reads the wrong run and fails.
    """
    entries = [
        {
            "__typename": "CheckRun",
            "name": name,
            "status": status,
            "conclusion": conclusion,
            "startedAt": f"2026-11-06T15:{index:02d}:00Z",
        }
        for index, (name, status, conclusion) in enumerate(runs)
    ]
    return {
        "match": ["pr view", "statusCheckRollup"],
        "stdout": json.dumps({"statusCheckRollup": list(reversed(entries))}),
    }


def green_gate() -> dict:
    """The rollup of a head commit whose one `CI gate` run passed."""
    return status_rollup(("CI gate", "COMPLETED", "SUCCESS"))


def run_script(
    tmp: Path,
    script: str,
    *args: str,
    cwd: Path,
    rules: list[dict],
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``SHARED/<script>`` in *cwd* with the fakes first on ``PATH``."""
    bin_dir = tmp / "fake-bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(f'#!/bin/sh\nexec {sys.executable} {_FAKE_GH} "$@"\n')
    uv = bin_dir / "uv"
    uv.write_text(_FAKE_UV)
    for tool in (gh, uv):
        tool.chmod(0o755)
    (tmp / "gh-rules.json").write_text(json.dumps(rules))
    full_env = {
        **clean_env(),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_GH_LOG": str(tmp / "gh-log.jsonl"),
        "FAKE_GH_RULES": str(tmp / "gh-rules.json"),
        "MERGE_STATE_ATTEMPTS": "1",
        **(env or {}),
    }
    return subprocess.run(
        [shutil.which("bash") or "bash", str(SHARED / script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=full_env,
    )


def fields(result: subprocess.CompletedProcess[str]) -> dict[str, list[str]]:
    """Every ``key=value`` line of *result*'s stdout, grouped by key."""
    out: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            out.setdefault(key, []).append(value)
    return out
