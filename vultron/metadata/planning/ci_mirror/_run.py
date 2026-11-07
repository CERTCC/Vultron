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
#: reported unrun (#5947). Its run gets its own ``timeout`` once it holds the
#: slot, so waiting behind another slot's suite does not shorten it.
LOCK_WAIT = DEFAULT_TIMEOUT

#: The ``timeout -k`` grace, and the slack the backstop ceiling allows over
#: the wait and the run.
_KILL_GRACE = 30
_BACKSTOP_SLACK = 60

#: ``timeout``'s exit status when the command ran out of time.
_TIMED_OUT = 124
#: ``timeout``'s exit status when the command ignored SIGTERM and was killed
#: after the ``-k`` grace (128 + SIGKILL).
_KILLED_AFTER_GRACE = 137


def _ran_out(code: int | None, seconds: float, timeout: int) -> bool:
    """Whether a heavy check's own ``timeout`` ended it.

    124 is a command that stopped on SIGTERM. A command that ignored it is
    killed after the grace and reads 137, which counts only once the run
    reached its *timeout*: earlier, a 137 is some other kill.
    """
    return code == _TIMED_OUT or (
        code == _KILLED_AFTER_GRACE and seconds >= timeout
    )


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


def locked(
    argv: Sequence[str],
    timeout: int,
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[str, ...]:
    """*argv* in a heavy-check slot, then under its own *timeout*.

    It waits at most :data:`LOCK_WAIT` for a slot, and ``timeout`` starts
    only once it holds one, so ``--timeout`` bounds the run alone. A memoized
    command takes the slot inside its memo, so a check whose inputs are
    unchanged skips without waiting. Without a ``timeout`` binary (stock
    macOS) the session's backstop ceiling is the only bound.
    """
    command = tuple(argv)
    memo: tuple[str, ...] = ()
    if command[:2] == ("bash", RUN_IF_CHANGED) and "--" in command:
        cut = command.index("--") + 1
        memo, command = command[:cut], command[cut:]
    if which("timeout") is not None:
        command = ("timeout", "-k", str(_KILL_GRACE), str(timeout), *command)
    return (*memo, *under_heavy_lock(command, wait=LOCK_WAIT))


def heavy_ceiling(timeout: int) -> int:
    """The session backstop for a heavy check: its slot wait, run and grace."""
    return LOCK_WAIT + timeout + _KILL_GRACE + _BACKSTOP_SLACK


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
    return argv


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
#: Set by :func:`stop_running`; no check starts once it is set.
_STOPPING = threading.Event()


class MirrorStopped(RuntimeError):
    """The mirror is stopping, so a check that was about to start does not."""


#: How long a stopped check's process group has to end after SIGTERM before
#: it is killed. Shorter than the outer ``timeout -k 30`` on the mirror, so the
#: mirror ends its checks before that kills it.
_STOP_GRACE = 10


def _signal_group(proc: subprocess.Popen[bytes], signum: int) -> None:
    try:
        os.killpg(proc.pid, signum)
    except ProcessLookupError:
        pass  # The group already ended.


def _end_groups(procs: Sequence[subprocess.Popen[bytes]]) -> None:
    """End each check's process group: SIGTERM, then SIGKILL after a grace.

    SIGTERM comes first because SIGKILL to the group would miss a heavy
    check's command: GNU ``timeout`` puts itself in a process group of its
    own, so only a signal the slot wrapper forwards reaches it, and
    ``timeout`` relays that signal to its own group (#5947).
    """
    for proc in procs:
        _signal_group(proc, signal.SIGTERM)
    deadline = time.monotonic() + _STOP_GRACE
    while time.monotonic() < deadline and any(
        proc.poll() is None for proc in procs
    ):
        time.sleep(0.05)
    for proc in procs:
        if proc.poll() is None:
            _signal_group(proc, signal.SIGKILL)
        proc.wait()


def stop_running() -> None:
    """End every process group the mirror started, and start no more.

    The flag and the snapshot share the guard that :func:`run_in_session`
    holds from ``Popen`` to registering the process, so no check can start
    unseen between them.
    """
    with _RUNNING_GUARD:
        _STOPPING.set()
        running = list(_RUNNING)
    _end_groups(running)


def run_in_session(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    out: IO[str],
    timeout: float,
) -> int | None:
    """Run *argv* in its own process group; ``None`` when it timed out.

    On a timeout the whole group is ended (:func:`_end_groups`), so a
    grandchild (an xdist worker, a site build) cannot keep running past it.
    Every check has a ceiling, so there is no wait-forever caller to admit.
    """
    with _RUNNING_GUARD:
        if _STOPPING.is_set():
            raise MirrorStopped("the mirror is stopping")
        proc = subprocess.Popen(  # nosec B603 - argv from the registry
            list(argv),
            cwd=cwd,
            env=dict(env),
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        _RUNNING.add(proc)
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _end_groups([proc])
        return None
    except BaseException:
        _end_groups([proc])
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
    argv = locked(item.argv, timeout) if item.check.heavy else item.argv
    ceiling = heavy_ceiling(timeout) if item.check.heavy else timeout
    with log.open("w", encoding="utf-8") as out:
        code = run_in_session(
            argv,
            cwd=cwd,
            env={**base_env, **item.env},
            out=out,
            timeout=ceiling,
        )
        if code is None:
            out.write(f"\n[ci-mirror] timed out after {ceiling}s\n")
    seconds = time.monotonic() - started
    if (
        item.check.heavy
        and "timeout" in argv
        and _ran_out(code, seconds, timeout)
    ):
        code, ceiling = None, timeout  # its own ceiling, inside the slot
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


def _not_run_after(item: PlannedCheck, first: CheckResult) -> CheckResult:
    """A lane member skipped because the member it reads did not pass.

    It inherits that member's kind of block: behind a ``NO-VERDICT`` it has no
    verdict either, and is not a finding (#5735).
    """
    if first.status is CheckStatus.NO_VERDICT:
        status, why = CheckStatus.NO_VERDICT, "had no verdict"
    else:
        status, why = CheckStatus.FAILED, "failed first"
    return CheckResult(
        item.check.id, status, f"not run: {first.id} {why}", 0.0, None, None
    )


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
            results.append(_not_run_after(item, results[0]))
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
