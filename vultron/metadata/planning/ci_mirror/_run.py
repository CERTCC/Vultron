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
"""Plan and run the mirror: what the branch diff triggers, and each verdict."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import IO

from vultron.metadata.planning.ci_mirror._registry import (
    RUN_IF_CHANGED,
    CheckContext,
    MirrorCheck,
)
from vultron.metadata.planning.ci_mirror._workflows import (
    KEY_SEPARATOR,
    PullRequestTrigger,
    WorkflowStep,
    matches_filter,
)
from vultron.metadata.planning.heavy_lock import (
    WAIT_EXPIRED,
    under_heavy_lock,
)

#: GitHub's default shell for a ``run:`` step on a Linux runner.
STEP_SHELL = ("bash", "--noprofile", "--norc", "-eo", "pipefail", "-c")

#: Default per-check ceiling; the slowest check, the site build, takes about
#: six minutes locally.
DEFAULT_TIMEOUT = 1200

#: How long a heavy check waits for a per-host heavy-check slot before it is
#: reported unrun. Its ceiling is its timeout plus this, so time spent waiting
#: behind another slot's suite does not end its own run early (#5947).
LOCK_WAIT = DEFAULT_TIMEOUT

#: What the wrapper prints when ``--wait`` runs out, so a check that exits
#: :data:`WAIT_EXPIRED` on its own is not mistaken for one that never ran.
_WAIT_EXPIRED_LINE = "run-heavy: gave up after"


class CheckStatus(StrEnum):
    """A check's verdict. ``FAIL``, ``NO-VERDICT`` and ``UNAVAILABLE`` block.

    ``NO-VERDICT`` is a check its environment stopped before it could judge
    the diff: a ceiling trip, a kill that left no output, or a heavy check
    that never got the lock. It is not a finding, and its reason names the
    remedy (#5735).

    ``PLAN`` is ``--list``'s word for a check that would run; it never reaches
    a real run's report.
    """

    PLANNED = "PLAN"
    PASSED = "PASS"
    FAILED = "FAIL"
    NO_VERDICT = "NO-VERDICT"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_TRIGGERED = "NOT-TRIGGERED"
    NOT_APPLICABLE = "N/A"
    SKIPPED = "SKIPPED"

    @property
    def blocks(self) -> bool:
        return self in (
            CheckStatus.FAILED,
            CheckStatus.NO_VERDICT,
            CheckStatus.UNAVAILABLE,
        )


@dataclass(frozen=True)
class PlannedCheck:
    """A check with the decision whether, and how, it runs."""

    check: MirrorCheck
    argv: tuple[str, ...] | None
    cwd: str | None
    env: Mapping[str, str]
    status: CheckStatus | None
    reason: str = ""


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one planned check."""

    id: str
    status: CheckStatus
    reason: str
    seconds: float
    log: str | None
    returncode: int | None


def _substitute(text: str, placeholders: Mapping[str, str]) -> str:
    for name, value in placeholders.items():
        text = text.replace("{" + name + "}", value)
    return text


def _step_env(step: WorkflowStep | None) -> dict[str, str]:
    # A value naming a GitHub expression (``${{ secrets.X }}``) has no local
    # meaning; a check that needs one declares its own value in ``env``.
    if step is None:
        return {}
    return {k: v for k, v in step.env.items() if "${{" not in v}


def _trigger_reason(
    check: MirrorCheck,
    trigger: PullRequestTrigger | None,
    base: str,
    changed: Collection[str],
) -> str | None:
    """Why the check would not run in CI for this diff, or ``None``."""
    if trigger is not None and not trigger.runs_for(base, changed):
        return "its workflow's pull_request filter does not match the diff"
    if check.paths is not None and not any(
        matches_filter(p, check.paths) for p in changed
    ):
        return "no changed path is in its narrowed set"
    return None


def locked(argv: Sequence[str]) -> tuple[str, ...]:
    """*argv* in a heavy-check slot, waiting at most :data:`LOCK_WAIT` for one.

    A memoized command takes the lock inside its memo, so a check whose
    inputs are unchanged skips without waiting behind another slot.
    """
    command = tuple(argv)
    if command[:2] == ("bash", RUN_IF_CHANGED) and "--" in command:
        cut = command.index("--") + 1
        memo, tool = command[:cut], command[cut:]
        return (*memo, *under_heavy_lock(tool, wait=LOCK_WAIT))
    return under_heavy_lock(command, wait=LOCK_WAIT)


def _argv(
    check: MirrorCheck,
    step: WorkflowStep | None,
    context: CheckContext,
) -> tuple[str, ...] | None:
    """The check's argv, or ``None`` when the diff gives it nothing to read."""
    if check.command is None:
        if step is None or step.run is None:
            raise ValueError(f"{check.id}: no command and no run: script")
        argv: tuple[str, ...] = (*STEP_SHELL, step.run)
    else:
        raw = (
            check.command(context)
            if callable(check.command)
            else check.command
        )
        if raw is None:
            return None
        argv = tuple(_substitute(arg, context.placeholders) for arg in raw)
    return locked(argv) if check.heavy else argv


def plan(
    checks: Iterable[MirrorCheck],
    steps: Mapping[str, WorkflowStep],
    triggers: Mapping[str, PullRequestTrigger],
    context: CheckContext,
    *,
    base: str,
    skip: Collection[str] = (),
    which: Callable[[str], str | None] = shutil.which,
) -> list[PlannedCheck]:
    """Decide, for each check, whether it runs on this diff and with what."""
    planned: list[PlannedCheck] = []
    for check in checks:
        step = steps.get(check.step) if check.step else None
        workflow = (
            check.step.split(KEY_SEPARATOR, 1)[0] if check.step else None
        )
        trigger = triggers.get(workflow) if workflow else None
        env = _step_env(step) | {
            k: _substitute(v, context.placeholders)
            for k, v in check.env.items()
        }
        cwd = step.working_directory if step else None
        status: CheckStatus | None = None
        reason = ""
        if check.step is not None and step is None:
            status, reason = (
                CheckStatus.FAILED,
                (
                    f"its CI step {check.step!r} no longer runs; the registry is "
                    "stale (test/ci/test_prepush_ci_mirror_parity.py)"
                ),
            )
        elif check.id in skip:
            status, reason = CheckStatus.SKIPPED, "skipped on request (--skip)"
        elif why := _trigger_reason(check, trigger, base, context.changed):
            status, reason = CheckStatus.NOT_TRIGGERED, why
        elif check.needs_pr and not context.placeholders.get("pr"):
            status, reason = (
                CheckStatus.NOT_APPLICABLE,
                "needs a PR number (--pr)",
            )
        elif check.tool and which(check.tool) is None:
            status, reason = (
                CheckStatus.UNAVAILABLE,
                f"{check.tool} is not on PATH",
            )
        argv = _argv(check, step, context) if status is None else None
        if status is None and argv is None:
            status, reason = (
                CheckStatus.NOT_TRIGGERED,
                "the diff has nothing for it",
            )
        planned.append(PlannedCheck(check, argv, cwd, env, status, reason))
    return planned


def default_log_dir(root: Path) -> Path:
    """One log directory per worktree: parallel sessions share the temp dir."""
    return Path(tempfile.gettempdir()) / f"vultron-{root.name}-ci-mirror"


def log_tail(path: Path | str | None, lines: int = 15) -> str:
    """The last *lines* of a log, or ``""`` when there is none."""
    if path is None or not Path(path).is_file():
        return ""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


#: The process groups the mirror has running, so a terminated mirror can stop
#: them: a heavy check left running would hold its host slot to the end.
_RUNNING: set[subprocess.Popen[bytes]] = set()
_RUNNING_GUARD = threading.Lock()


def stop_running() -> None:
    """Kill every process group the mirror started that is still running."""
    with _RUNNING_GUARD:
        running = list(_RUNNING)
    for proc in running:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # It ended between the snapshot and the kill.


def run_in_session(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    out: IO[str],
    timeout: float | None,
) -> int | None:
    """Run *argv* in its own process group; ``None`` when it timed out.

    On a timeout the whole group is killed, so a grandchild (an xdist worker,
    a site build) cannot keep running past it.
    """
    proc = subprocess.Popen(  # nosec B603 - argv from the registry
        list(argv),
        cwd=cwd,
        env=dict(env),
        stdout=out,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    with _RUNNING_GUARD:
        _RUNNING.add(proc)
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        return None
    except BaseException:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        raise
    finally:
        with _RUNNING_GUARD:
            _RUNNING.discard(proc)


def _run_one(
    item: PlannedCheck,
    root: Path,
    base_env: Mapping[str, str],
    timeout: int,
    log_dir: Path,
) -> CheckResult:
    assert item.argv is not None
    log = log_dir / f"{item.check.id}.log"
    started = time.monotonic()
    cwd = root / item.cwd if item.cwd else root
    ceiling = timeout + LOCK_WAIT if item.check.heavy else timeout
    with log.open("w", encoding="utf-8") as out:
        code = run_in_session(
            item.argv,
            cwd=cwd,
            env={**base_env, **item.env},
            out=out,
            timeout=ceiling,
        )
        if code is None:
            out.write(f"\n[ci-mirror] timed out after {ceiling}s\n")
    seconds = time.monotonic() - started
    status, reason = verdict(item.check, code, ceiling, log)
    return CheckResult(item.check.id, status, reason, seconds, str(log), code)


#: The lowest exit status a shell reports for a process a signal ended.
_SIGNAL_EXIT = 128


def _wrapper_gave_up(log: Path) -> bool:
    text = log.read_text(encoding="utf-8", errors="replace")
    return any(
        line.startswith(_WAIT_EXPIRED_LINE) for line in text.splitlines()
    )


def _said_nothing(log: Path) -> bool:
    """Whether the check wrote no output of its own (the lock's lines aside)."""
    text = log.read_text(encoding="utf-8", errors="replace")
    return not any(
        line.strip() and not line.startswith("run-heavy:")
        for line in text.splitlines()
    )


def verdict(
    check: MirrorCheck, code: int | None, ceiling: int, log: Path
) -> tuple[CheckStatus, str]:
    """The status and reason for a check that exited *code* (``None``: timed out).

    A run its environment stopped is ``NO-VERDICT``, with the remedy in the
    reason, so it never reads as a finding (#5735).
    """
    if code == 0:
        return CheckStatus.PASSED, ""
    if code is None:
        return CheckStatus.NO_VERDICT, (
            f"timed out ({ceiling}s); rerun it with a longer --timeout or "
            "with nothing else running"
        )
    if code == WAIT_EXPIRED and _wrapper_gave_up(log):
        return CheckStatus.NO_VERDICT, (
            f"not run: waited {LOCK_WAIT}s for a heavy-check slot; rerun "
            "it once the checks the log names end"
        )
    if (code < 0 or code >= _SIGNAL_EXIT) and _said_nothing(log):
        return CheckStatus.NO_VERDICT, (
            f"exit {code} with no output: a signal from its environment, such "
            "as an out-of-memory kill; rerun it with nothing else running"
        )
    return CheckStatus.FAILED, f"exit {code}"


def _groups(planned: Sequence[PlannedCheck]) -> list[list[PlannedCheck]]:
    by_group: dict[str, list[PlannedCheck]] = {}
    lanes: list[list[PlannedCheck]] = []
    for item in planned:
        if item.status is not None:
            continue
        if item.check.group is None:
            lanes.append([item])
        elif item.check.group in by_group:
            by_group[item.check.group].append(item)
        else:
            by_group[item.check.group] = lane = [item]
            lanes.append(lane)
    return lanes


def _run_lane(
    lane: Sequence[PlannedCheck],
    root: Path,
    base_env: Mapping[str, str],
    timeout: int,
    log_dir: Path,
) -> list[CheckResult]:
    """Run a group in order.

    The first member produces what the rest read (the site build), so when it
    fails they do not run. A later member's failure stops nothing, as in CI,
    where each runs under ``!cancelled()``.
    """
    results: list[CheckResult] = []
    for item in lane:
        if results and results[0].status.blocks:
            failed = results[0].id
            results.append(
                CheckResult(
                    item.check.id,
                    CheckStatus.FAILED,
                    f"not run: {failed} failed first",
                    0.0,
                    None,
                    None,
                )
            )
            continue
        results.append(_run_one(item, root, base_env, timeout, log_dir))
    return results


def run_checks(
    planned: Sequence[PlannedCheck],
    root: Path,
    *,
    jobs: int,
    timeout: int = DEFAULT_TIMEOUT,
    env: Mapping[str, str] | None = None,
    log_dir: Path | None = None,
) -> list[CheckResult]:
    """Run every planned check that is to run; report every check."""
    base_env = dict(os.environ if env is None else env)
    logs = log_dir or default_log_dir(root)
    logs.mkdir(parents=True, exist_ok=True)
    lanes = _groups(planned)
    shared = [lane for lane in lanes if not lane[0].check.alone]
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        ran = [
            result
            for lane_results in pool.map(
                lambda lane: _run_lane(lane, root, base_env, timeout, logs),
                shared,
            )
            for result in lane_results
        ]
    for lane in lanes:
        if lane[0].check.alone:
            ran += _run_lane(lane, root, base_env, timeout, logs)
    by_id = {r.id: r for r in ran}
    return [
        by_id.get(item.check.id)
        or CheckResult(
            item.check.id,
            item.status or CheckStatus.FAILED,
            item.reason,
            0.0,
            None,
            None,
        )
        for item in planned
    ]
