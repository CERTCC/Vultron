"""Shared ``gh`` and ``git`` plumbing for the Python scripts in ``.github/scripts``.

A workflow runs each script as a file, often under ``python -I``, which leaves
the script's directory off ``sys.path``, so each importer puts it back first::

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gh_cli import gh
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

# A hung call fails its step instead of holding the job to its cap, where it
# would end as cancelled and go unreported (CISEC-05-006). A workflow whose cap
# is near this default lowers it with ``GH_CALL_TIMEOUT_SECONDS``.
CALL_TIMEOUT_SECONDS = 300


def call_timeout_seconds() -> float:
    """The per-call timeout: ``GH_CALL_TIMEOUT_SECONDS``, else the default."""
    return float(
        os.environ.get("GH_CALL_TIMEOUT_SECONDS", str(CALL_TIMEOUT_SECONDS))
    )


def run(*argv: str) -> str:
    """A command's stdout; on failure its stderr goes to the log, then it raises."""
    try:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            list(argv),
            check=True,
            capture_output=True,
            text=True,
            timeout=call_timeout_seconds(),
        ).stdout
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr or "")
        raise


def write_github_file(env_var: str, text: str) -> None:
    """Append *text* to the Actions file *env_var* names, if it names one.

    ``GITHUB_OUTPUT`` and ``GITHUB_STEP_SUMMARY`` are such files; outside a
    workflow run the variable is unset and nothing is written.
    """
    path = os.environ.get(env_var)
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)


def gh(*args: str, retry: bool = True) -> str:
    """``gh``'s stdout; on failure its stderr goes to the log, then it raises.

    A failed call is retried with the bounds ``retry.sh`` uses
    (``GH_RETRY_ATTEMPTS``, default 4; ``GH_RETRY_DELAY`` seconds, default 5,
    doubled each time), because GitHub sometimes answers with a 5xx that the
    same call clears seconds later. Pass ``retry=False`` for a call that is
    not safe to repeat: a retried ``issue create`` whose first attempt landed
    would file a second report.
    """
    delays = retry_delays() if retry else []
    for delay in delays:
        try:
            return run("gh", *args)
        except subprocess.CalledProcessError:
            time.sleep(delay)
    return run("gh", *args)


def retry_delays() -> list[float]:
    """The pauses between attempts of a retried call, one per retry.

    ``retry.sh``'s bounds: ``GH_RETRY_ATTEMPTS`` attempts (default 4), the
    first pause ``GH_RETRY_DELAY`` seconds (default 5), doubled each time.
    """
    attempts = int(os.environ.get("GH_RETRY_ATTEMPTS", "4"))
    delay = float(os.environ.get("GH_RETRY_DELAY", "5"))
    return [delay * 2**n for n in range(max(attempts, 1) - 1)]


def paginated(
    endpoint: str, key: str | None = None
) -> list[dict[str, object]]:
    """Every item of a REST list endpoint, across all its pages.

    ``--slurp`` yields one entry per page. A plain list endpoint's page is the
    item list; an endpoint that wraps it in an object (``workflow_runs``,
    ``check_runs``) names the wrapping field in *key*. The read is retried as
    :func:`gh` retries.
    """
    pages = json.loads(gh("api", "--paginate", "--slurp", endpoint))
    if key is None:
        return [item for page in pages for item in page]
    return [item for page in pages for item in page[key]]
