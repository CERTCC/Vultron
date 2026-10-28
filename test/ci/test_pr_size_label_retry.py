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
"""The PR size label job survives a GitHub server error on a label write.

GitHub sometimes answers a label write with a server error (a GraphQL
"Something went wrong" from ``gh pr edit``, an HTTP 500 from ``gh label
create``) that a retry clears. One swap call (``--add-label X --remove-label
Y``) once removed the old label and failed to add the new one, which left the
PR with no ``size:`` label (#4524, PAD-05-002, PAD-05-011).

The job therefore retries every GitHub call a bounded number of times, adds
the new label in its own call before it removes any stale one, and stops
before the removals when the add fails. These tests run the workflow's own
step scripts against a fake ``gh``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import REPO_ROOT, load_workflow

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-size-label.yml"
RETRY_HELPER = REPO_ROOT / ".github" / "scripts" / "retry.sh"

# A stand-in for ``gh``. It logs each call, answers ``pr view`` with the
# labels in ``$FAKE_CURRENT``, and fails a call whose arguments contain
# ``$FAKE_FAIL_MATCH`` the first ``$FAKE_FAIL_TIMES`` times it is made (a
# negative count fails it every time), as GitHub's server error did.
_FAKE_GH = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_GH_LOG"
if [ -n "${FAKE_FAIL_MATCH:-}" ] && [[ "$*" == *"$FAKE_FAIL_MATCH"* ]]; then
  count_file="$FAKE_GH_LOG.failures"
  count=$(cat "$count_file" 2>/dev/null || echo 0)
  if [ "$FAKE_FAIL_TIMES" -lt 0 ] || [ "$count" -lt "$FAKE_FAIL_TIMES" ]; then
    echo $((count + 1)) > "$count_file"
    echo "GraphQL: Something went wrong while executing your query." >&2
    exit 1
  fi
fi
case "$1 $2" in
  "pr view") printf '%s\n' "$FAKE_CURRENT" ;;
esac
"""

# A stand-in for ``uv`` that runs ``uv run pr-size ...`` in this interpreter,
# so the step reads the real band table (PAD-05-011) without a nested uv.
_FAKE_UV = f"""#!/usr/bin/env bash
shift 2
exec {sys.executable} -c 'import sys; \
from vultron.metadata.planning.size_bands import main; \
sys.exit(main(sys.argv[1:]))' "$@"
"""


def _step(name_fragment: str) -> dict[str, Any]:
    steps: list[dict[str, Any]] = load_workflow(WORKFLOW)["jobs"]["label"][
        "steps"
    ]
    matches = [s for s in steps if name_fragment in str(s.get("name", ""))]
    assert len(matches) == 1, (
        f"Expected one pr-size-label.yml step named like {name_fragment!r}, "
        f"found {len(matches)}; update this test if the step was renamed."
    )
    return matches[0]


def _run_step(
    tmp_path: Path,
    step: dict[str, Any],
    *,
    current: str = "",
    fail_match: str = "",
    fail_times: int = 0,
    keep: str = "size:L",
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run *step*'s script against the fakes; return the result and gh calls."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("gh", _FAKE_GH), ("uv", _FAKE_UV)):
        path = bin_dir / name
        path.write_text(body)
        path.chmod(0o755)
    log = tmp_path / "gh.log"
    log.touch()
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": str(REPO_ROOT),
        "FAKE_GH_LOG": str(log),
        "FAKE_CURRENT": current,
        "FAKE_FAIL_MATCH": fail_match,
        "FAKE_FAIL_TIMES": str(fail_times),
        "GH_RETRY_DELAY": "0",
        "GH_TOKEN": "fake-token",
        "GITHUB_OUTPUT": str(tmp_path / "output"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "PR": "4509",
        "REPO": "OWNER/REPO",
        "LABEL": keep,
        "KEEP": keep,
    }
    result = subprocess.run(
        ["bash", "-e", "-c", str(step["run"])],
        check=False,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return result, log.read_text().splitlines()


def _edits(calls: list[str]) -> list[str]:
    return [c for c in calls if c.startswith("pr edit")]


APPLY = "Apply it"
ENSURE = "Ensure the label exists"


def test_new_label_is_added_before_the_stale_one_is_removed(
    tmp_path: Path,
) -> None:
    result, calls = _run_step(tmp_path, _step(APPLY), current="size:M,bug")
    assert result.returncode == 0, result.stderr
    assert _edits(calls) == [
        "pr edit 4509 --repo OWNER/REPO --add-label size:L",
        "pr edit 4509 --repo OWNER/REPO --remove-label size:M",
    ], (
        "The new size label must be added in its own call before any stale "
        "one is removed, so a failure part-way never leaves the PR with no "
        "size label (#4524)."
    )


def test_a_transient_add_failure_is_retried(tmp_path: Path) -> None:
    result, calls = _run_step(
        tmp_path,
        _step(APPLY),
        current="size:M",
        fail_match="--add-label",
        fail_times=2,
    )
    assert result.returncode == 0, result.stderr
    assert _edits(calls) == [
        *["pr edit 4509 --repo OWNER/REPO --add-label size:L"] * 3,
        "pr edit 4509 --repo OWNER/REPO --remove-label size:M",
    ]


def test_a_lasting_add_failure_keeps_the_old_label_and_fails(
    tmp_path: Path,
) -> None:
    result, calls = _run_step(
        tmp_path,
        _step(APPLY),
        current="size:M",
        fail_match="--add-label",
        fail_times=-1,
    )
    assert result.returncode != 0, "A failed add must fail the step."
    edits = _edits(calls)
    assert edits, "The step never tried to add the label."
    assert all("--add-label" in c for c in edits), (
        "The step removed the old size label after the add failed, leaving "
        f"the PR with no size label (#4524). Calls: {edits}"
    )
    assert len(edits) > 1, "The add was not retried."


def test_a_transient_removal_failure_is_retried(tmp_path: Path) -> None:
    """A removal is safe to repeat, so a server error on it is retried."""
    result, calls = _run_step(
        tmp_path,
        _step(APPLY),
        current="size:L,size:M",
        fail_match="--remove-label",
        fail_times=1,
    )
    assert result.returncode == 0, result.stderr
    assert (
        _edits(calls)
        == ["pr edit 4509 --repo OWNER/REPO --remove-label size:M"] * 2
    )


def test_a_transient_failure_reading_the_labels_is_retried(
    tmp_path: Path,
) -> None:
    result, calls = _run_step(
        tmp_path,
        _step(APPLY),
        current="size:M",
        fail_match="pr view",
        fail_times=1,
    )
    assert result.returncode == 0, result.stderr
    assert len(_edits(calls)) == 2


def test_label_already_applied_needs_no_add(tmp_path: Path) -> None:
    result, calls = _run_step(tmp_path, _step(APPLY), current="size:L")
    assert result.returncode == 0, result.stderr
    assert _edits(calls) == []


def test_a_transient_label_upsert_failure_is_retried(tmp_path: Path) -> None:
    """The second occurrence (#4524 comment): ``gh label create`` got a 500."""
    result, calls = _run_step(
        tmp_path,
        _step(ENSURE),
        fail_match="label create",
        fail_times=1,
    )
    assert result.returncode == 0, result.stderr
    assert sum(c.startswith("label create size:L") for c in calls) == 2


@pytest.mark.parametrize("step_name", ["Classify", ENSURE, APPLY])
def test_every_github_call_goes_through_the_retry_helper(
    step_name: str,
) -> None:
    """A ``gh`` call outside ``retry`` would bring back the one-shot failure."""
    script = str(_step(step_name)["run"])
    assert "source .github/scripts/retry.sh" in script
    bare = [
        line.strip()
        for line in script.splitlines()
        if "gh " in line
        and not line.strip().startswith("#")
        and "retry gh " not in line
    ]
    assert bare == [], f"Unretried gh call(s) in {step_name!r}: {bare}"


def test_retry_helper_gives_up_after_its_bound(tmp_path: Path) -> None:
    counter = tmp_path / "count"
    script = (
        f"source {RETRY_HELPER}\nretry bash -c 'echo x >> {counter}; exit 7'\n"
    )
    result = subprocess.run(
        ["bash", "-e", "-c", script],
        check=False,
        env={**os.environ, "GH_RETRY_DELAY": "0", "GH_RETRY_ATTEMPTS": "3"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 7, "retry must return the command's status."
    assert counter.read_text().count("x") == 3
