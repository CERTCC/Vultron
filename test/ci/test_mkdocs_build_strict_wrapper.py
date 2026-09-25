"""The local strict-build wrapper's exit code agrees with what it prints.

Covers #3051 AC-3. ``.github/scripts/mkdocs-build-strict.sh`` is the
``build-docs`` skill's gate: it runs ``mkdocs build --strict`` and forgives
only the classified griffe false positives. Its exit code once disagreed with
its own message in both directions (the ``grep -c || echo 0`` double zero), and
after that fix one hole remained: any non-zero mkdocs exit counted as
"explained" once a single suppressed warning had been printed, so a plugin
traceback beside a forgiven warning printed a success line and exited 0.

Each case runs the real script against a fake ``uv`` on ``PATH`` that prints a
canned mkdocs log and exits with a chosen status, so no site is built.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from test.ci._workflows import REPO_ROOT

WRAPPER = REPO_ROOT / ".github" / "scripts" / "mkdocs-build-strict.sh"

SUPPRESSED = "WARNING -  Inline reference to unknown key dataclass"
REAL = "WARNING -  Doc file 'a.md' contains a link to 'b.md#x', but ..."
ABORTED = "Aborted with {n} warnings in strict mode!"
TRACEBACK = "Traceback (most recent call last):\nRuntimeError: plugin blew up"


def _run(
    tmp_path: Path, log: str, rc: int
) -> subprocess.CompletedProcess[str]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "uv"
    (tmp_path / "log.txt").write_text(log + "\n", "utf-8")
    fake.write_text(
        f"#!/bin/bash\ncat '{tmp_path / 'log.txt'}'\nexit {rc}\n", "utf-8"
    )
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", str(WRAPPER)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "log, rc, passes",
    [
        ("INFO    -  Documentation built", 0, True),
        (f"{SUPPRESSED}\n{ABORTED.format(n=1)}", 1, True),
        (f"{REAL}\n{ABORTED.format(n=1)}", 1, False),
        (f"{SUPPRESSED}\n{REAL}\n{ABORTED.format(n=2)}", 1, False),
        ("ERROR -  Config value 'nav': bad", 1, False),
        (TRACEBACK, 1, False),
        # The remaining hole: a forgiven warning must not explain a crash.
        (f"{SUPPRESSED}\n{TRACEBACK}", 1, False),
    ],
    ids=[
        "clean",
        "suppressed-only",
        "real-warning",
        "real-beside-suppressed",
        "error-line",
        "traceback",
        "traceback-beside-suppressed",
    ],
)
def test_wrapper_exit_code_agrees_with_its_message(
    tmp_path: Path, log: str, rc: int, passes: bool
):
    result = _run(tmp_path, log, rc)
    assert (result.returncode == 0) is passes, result.stdout
    if passes:
        assert "✗" not in result.stdout, result.stdout
    else:
        assert "✗" in result.stdout, (
            "The wrapper failed without saying why, so its exit code and "
            f"message disagree:\n{result.stdout}"
        )
        assert "✓" not in result.stdout, result.stdout
