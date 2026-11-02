"""Shared ``gh`` and ``git`` plumbing for the Python scripts in ``.github/scripts``.

A workflow runs each script as a file, often under ``python -I``, which leaves
the script's directory off ``sys.path``, so each importer puts it back first::

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gh_cli import gh
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

# A hung call fails its step instead of holding the job to its cap, where it
# would end as cancelled and go unreported (CISEC-05-006).
CALL_TIMEOUT_SECONDS = 300


def run(*argv: str) -> str:
    """A command's stdout; on failure its stderr goes to the log, then it raises."""
    try:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            list(argv),
            check=True,
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT_SECONDS,
        ).stdout
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr or "")
        raise


def gh(*args: str, retry: bool = True) -> str:
    """``gh``'s stdout; on failure its stderr goes to the log, then it raises.

    A failed call is retried with the bounds ``retry.sh`` uses
    (``GH_RETRY_ATTEMPTS``, default 4; ``GH_RETRY_DELAY`` seconds, default 5,
    doubled each time), because GitHub sometimes answers with a 5xx that the
    same call clears seconds later. Pass ``retry=False`` for a call that is
    not safe to repeat: a retried ``issue create`` whose first attempt landed
    would file a second report.
    """
    attempts = int(os.environ.get("GH_RETRY_ATTEMPTS", "4")) if retry else 1
    delay = float(os.environ.get("GH_RETRY_DELAY", "5"))
    for attempt in range(1, attempts + 1):
        try:
            return run("gh", *args)
        except subprocess.CalledProcessError:
            if attempt >= attempts:
                raise
            time.sleep(delay)
            delay *= 2
    raise AssertionError("unreachable")  # pragma: no cover
