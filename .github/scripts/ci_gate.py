"""Wait for every other check on a pull request's head commit, then judge them.

The ``CI gate`` job (``.github/workflows/ci-gate.yml``) runs this on every pull
request to ``main``. Every other CI workflow has ``paths`` filters, so a ruleset
that required one of their jobs would leave a docs-only pull request waiting for
a status that never arrives. This gate always runs, and passes only when every
other check passed or was skipped, so it is the one check a ruleset requires.

The verdict rules are those of ``.agents/skills/shared/wait-for-ci.sh``:
``success``, ``skipped`` and ``neutral`` are green; every other conclusion
(``failure``, ``cancelled``, ``timed_out``, ``action_required``,
``startup_failure``, ``stale``, or one GitHub adds later) is red.

What counts as "every other check":

- The latest run of each workflow on the head commit, except this gate's own
  workflow. A run superseded on the same commit (its concurrency group
  cancelled it, or an ``edited`` event re-ran it) is not judged; only its
  newest run is. Waiting on workflow runs, not only on check runs, is what
  catches a job whose check run does not exist yet because it ``needs:`` a job
  still running, and a run that failed before any job started.
- The check runs of those latest runs, which name the red jobs.
- Check runs in no workflow run's check suite, such as a GitHub App's code
  scanning result, each judged by its newest run of that name.

The gate polls the workflow runs alone while any is still running, and reads
the check runs only once none is, so a long CI run costs about one API call a
minute against the repository's ``GITHUB_TOKEN`` rate limit.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gh_cli import gh, write_github_file

GREEN = frozenset({"success", "skipped", "neutral"})

#: How long the gate waits before it may conclude, so a workflow that GitHub
#: starts a little after this one is not missed.
DEFAULT_GRACE_SECONDS = 90
DEFAULT_POLL_SECONDS = 60
#: Below the job's ``timeout-minutes``, so a check that never finishes ends the
#: gate red with the pending checks named, not cancelled with no message.
DEFAULT_DEADLINE_MINUTES = 60

PAGE_SIZE = 100

Record = Mapping[str, Any]


@dataclass(frozen=True)
class Verdict:
    """What the gate saw on one poll."""

    pending: list[str] = field(default_factory=list)
    red: list[str] = field(default_factory=list)
    green: list[str] = field(default_factory=list)

    @property
    def done(self) -> bool:
        """True when nothing the gate waits on is still running."""
        return not self.pending


def own_workflow_path(workflow_ref: str) -> str:
    """The workflow file path in ``GITHUB_WORKFLOW_REF``.

    The ref reads ``<owner>/<repo>/<path>@<ref>``; a workflow run's ``path``
    field holds only ``<path>``.
    """
    parts = workflow_ref.split("@", 1)[0].split("/", 2)
    if len(parts) != 3 or not parts[2]:
        raise ValueError(f"not a workflow ref: {workflow_ref!r}")
    return parts[2]


def _path(run: Record) -> str:
    return str(run.get("path", "")).split("@", 1)[0]


def latest_runs(runs: Iterable[Record], own_path: str) -> list[Record]:
    """The newest run of each workflow, without this gate's own workflow."""
    newest: dict[Any, Record] = {}
    for run in runs:
        if _path(run) == own_path:
            continue
        key = run["workflow_id"]
        if key not in newest or run["id"] > newest[key]["id"]:
            newest[key] = run
    return sorted(newest.values(), key=lambda r: r["id"])


def judged_check_runs(
    check_runs: Iterable[Record], runs: Iterable[Record], own_path: str
) -> list[Record]:
    """The check runs the gate judges.

    Those in a latest run's check suite, plus the newest of each name among
    check runs in no workflow run's suite. A check run in a superseded run's
    suite, or in this gate's own suite, is dropped.
    """
    runs = list(runs)
    all_suites = {r.get("check_suite_id") for r in runs}
    judged_suites = {
        r.get("check_suite_id") for r in latest_runs(runs, own_path)
    }
    kept: list[Record] = []
    standalone: dict[str, Record] = {}
    for check in check_runs:
        suite = (check.get("check_suite") or {}).get("id")
        if suite in judged_suites:
            kept.append(check)
        elif suite not in all_suites:
            name = check["name"]
            if name not in standalone or check["id"] > standalone[name]["id"]:
                standalone[name] = check
    return kept + sorted(standalone.values(), key=lambda c: c["id"])


def _is_red(record: Record) -> bool:
    return record.get("conclusion") not in GREEN


def judge(
    runs: Sequence[Record],
    check_runs: Sequence[Record] | None,
    own_path: str,
) -> Verdict:
    """Sort the checks into pending, red and green.

    ``check_runs`` is ``None`` when a workflow run is still in progress, so the
    gate has not read them yet: the verdict is then pending on those runs.
    """
    latest = latest_runs(runs, own_path)
    pending = [
        f"{r['name']} (workflow, {r.get('status')})"
        for r in latest
        if r.get("status") != "completed"
    ]
    if check_runs is None:
        if not pending:
            raise ValueError("check runs are needed once no workflow runs")
        return Verdict(pending=pending)

    checks = judged_check_runs(check_runs, runs, own_path)
    red: list[str] = []
    green: list[str] = []
    red_suites: set[Any] = set()
    for check in checks:
        label = f"{check['name']}: {check.get('conclusion')}"
        if check.get("status") != "completed":
            pending.append(f"{check['name']} ({check.get('status')})")
        elif _is_red(check):
            red.append(label)
            red_suites.add((check.get("check_suite") or {}).get("id"))
        else:
            green.append(label)
    # A run can fail with no red job to name it: a workflow that fails to
    # start has no check runs at all.
    for run in latest:
        if (
            run.get("status") == "completed"
            and _is_red(run)
            and run.get("check_suite_id") not in red_suites
        ):
            red.append(f"{run['name']} (workflow): {run.get('conclusion')}")
    return Verdict(pending=pending, red=red, green=green)


def _pages(endpoint: str, key: str) -> list[Record]:
    """Every item under *key* across the pages of a list endpoint."""
    items: list[Record] = []
    page = 1
    while True:
        sep = "&" if "?" in endpoint else "?"
        body = json.loads(
            gh("api", f"{endpoint}{sep}per_page={PAGE_SIZE}&page={page}")
        )
        batch = body[key]
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            return items
        page += 1


@dataclass(frozen=True)
class GitHub:
    """The two reads the gate makes, for one repository and commit."""

    repo: str
    sha: str

    def workflow_runs(self) -> list[Record]:
        """Every workflow run on the commit."""
        return _pages(
            f"repos/{self.repo}/actions/runs?head_sha={self.sha}",
            "workflow_runs",
        )

    def check_runs(self) -> list[Record]:
        """Every check run on the commit."""
        return _pages(
            f"repos/{self.repo}/commits/{self.sha}/check-runs", "check_runs"
        )


def wait(
    github: GitHub,
    own_path: str,
    *,
    grace_seconds: float,
    poll_seconds: float,
    deadline_seconds: float,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> tuple[Verdict, bool]:
    """Poll until nothing is pending and the grace period is over.

    Returns the last verdict and whether the deadline passed first.
    """
    start = clock()
    while True:
        runs = github.workflow_runs()
        running = any(
            r.get("status") != "completed" for r in latest_runs(runs, own_path)
        )
        checks = None if running else github.check_runs()
        verdict = judge(runs, checks, own_path)
        elapsed = clock() - start
        if verdict.done and elapsed >= grace_seconds:
            return verdict, False
        if elapsed >= deadline_seconds:
            return verdict, True
        if verdict.pending:
            log(
                f"Waiting on {len(verdict.pending)} check(s) after "
                f"{int(elapsed)} s: {', '.join(verdict.pending)}"
            )
        sleep(poll_seconds)


def report(verdict: Verdict, timed_out: bool) -> int:
    """Log the verdict, write the step summary, and return the exit status."""
    lines = ["## CI gate", ""]
    if timed_out:
        for name in verdict.pending:
            print(f"::error::Still running at the gate's deadline: {name}")
        lines.append(f"Timed out waiting on: {', '.join(verdict.pending)}")
    for name in verdict.red:
        print(f"::error::Red check: {name}")
        lines.append(f"- ❌ {name}")
    for name in verdict.green:
        lines.append(f"- ✅ {name}")
    if not (verdict.red or verdict.green or verdict.pending):
        print("::warning::No other check ran on this commit.")
        lines.append("No other check ran on this commit.")
    write_github_file("GITHUB_STEP_SUMMARY", "\n".join(lines) + "\n")
    if timed_out or verdict.red:
        print(
            f"CI gate: red ({len(verdict.red)} red, "
            f"{len(verdict.pending)} still running)."
        )
        return 1
    print(f"CI gate: green ({len(verdict.green)} check(s) passed or skipped).")
    return 0


def _seconds(env: Mapping[str, str], name: str, default: float) -> float:
    return float(env.get(name, default))


def main(env: Mapping[str, str] = os.environ) -> int:
    """Run the gate for ``REPO`` and ``HEAD_SHA`` from the environment."""
    github = GitHub(repo=env["REPO"], sha=env["HEAD_SHA"])
    verdict, timed_out = wait(
        github,
        own_workflow_path(env["GITHUB_WORKFLOW_REF"]),
        grace_seconds=_seconds(
            env, "GATE_GRACE_SECONDS", DEFAULT_GRACE_SECONDS
        ),
        poll_seconds=_seconds(env, "GATE_POLL_SECONDS", DEFAULT_POLL_SECONDS),
        deadline_seconds=60
        * _seconds(env, "GATE_DEADLINE_MINUTES", DEFAULT_DEADLINE_MINUTES),
    )
    return report(verdict, timed_out)


if __name__ == "__main__":
    sys.exit(main())
