"""Run a heavy local check in one of this host's heavy-check slots (#5947).

Every slot container on a host shares the CPUs and memory of one Docker VM,
and each ``pytest -n auto``, pyright run or site build sizes itself to its own
container without seeing the others. This script caps how many such commands
run at once on the host: it holds one of N slot lock files while the command
runs, and waits while all N are taken.

Usage::

    uv run python .agents/skills/shared/run-heavy.py [--wait SECONDS] [--] COMMAND...

It waits at most ``--wait SECONDS`` (default 3600) for a slot, then prints one
line and exits 75 without running the command, so a gate behind a holder that
never ends still ends (TB-14-005).

The slot files live in ``/home/vscode/.data/locks/``, in the named volume every
slot container on a host mounts, so one host shares them and another host has
its own. ``VULTRON_HEAVY_LOCK_DIR`` names another directory. ``start-dev.sh``
writes N to the ``slots`` file there; a missing or unreadable file means 2.

Put the wrapper outside a wall-clock ceiling (``run-heavy.py timeout -k 30
1800 ...``), so time spent waiting is not charged to the run. The command does
not inherit the slot's file descriptor, so the slot frees when this process
ends, whether the command ended or this process was killed. A command already
running in a slot (it sees ``VULTRON_HEAVY_LOCK_HELD``) runs a nested heavy
check directly, without taking a second slot. The exit status is the
command's own, or 128 + the signal that ended it.

Standard library only, so it runs the same on Linux and macOS.
"""

from __future__ import annotations

import fcntl
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

DEFAULT_LOCK_DIR = "/home/vscode/.data/locks"
LOCK_DIR_ENV = "VULTRON_HEAVY_LOCK_DIR"
HELD_ENV = "VULTRON_HEAVY_LOCK_HELD"
SLOTS_FILE = "slots"

#: The slot count when ``start-dev.sh`` has written none.
DEFAULT_SLOTS = 2

#: How long a check waits for a slot unless ``--wait`` says otherwise.
DEFAULT_WAIT = 3600

#: ``--wait`` ran out before a slot came free; the command did not run.
WAIT_EXPIRED = 75
USAGE_ERROR = 2

POLL_SECONDS = 0.5
_FORWARDED = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)

USAGE = "usage: run-heavy.py [--wait SECONDS] [--] COMMAND..."


class UsageError(ValueError):
    """The command line names no command, or a malformed ``--wait``."""


def _say(message: str) -> None:
    print(f"run-heavy: {message}", file=sys.stderr, flush=True)


def parse_args(argv: Sequence[str]) -> tuple[int, list[str]]:
    """The ``--wait`` limit in seconds and the command to run."""
    args = list(argv)
    wait = DEFAULT_WAIT
    if args[:1] == ["--wait"]:
        if len(args) < 2 or not args[1].isdigit():
            raise UsageError("--wait needs a whole number of seconds")
        wait = int(args[1])
        args = args[2:]
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        raise UsageError(USAGE)
    return wait, args


def slot_count(lock_dir: Path) -> int:
    """N from the ``slots`` file, or :data:`DEFAULT_SLOTS` without a usable one."""
    try:
        value = int((lock_dir / SLOTS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_SLOTS
    return value if value >= 1 else DEFAULT_SLOTS


def _slot_path(lock_dir: Path, index: int) -> Path:
    return lock_dir / f"heavy-{index}.lock"


def try_acquire(lock_dir: Path, slots: int) -> tuple[int, int] | None:
    """Lock the first free slot: ``(fd, index)``, or ``None`` when all are taken."""
    for index in range(slots):
        fd = os.open(
            _slot_path(lock_dir, index), os.O_RDWR | os.O_CREAT, 0o666
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            continue
        return fd, index
    return None


def holders(lock_dir: Path, slots: int) -> str:
    """Who holds each slot, as the holders recorded themselves."""
    seen = []
    for index in range(slots):
        path = _slot_path(lock_dir, index).with_suffix(".holder")
        try:
            seen.append(" ".join(path.read_text(encoding="utf-8").split()))
        except OSError:
            seen.append("unknown")
    return "; ".join(seen)


def acquire(lock_dir: Path, wait: int) -> tuple[int, int] | None:
    """Wait for a slot; ``None`` when *wait* seconds passed without one.

    N is re-read on every try, so a slot count ``start-dev.sh`` rewrites
    reaches a check that is already waiting.
    """
    deadline = time.monotonic() + wait
    announced = False
    while True:
        slots = slot_count(lock_dir)
        held = try_acquire(lock_dir, slots)
        if held is not None:
            return held
        if not announced:
            _say(
                f"all {slots} heavy-check slots on this host are busy; "
                f"waiting ({holders(lock_dir, slots)})"
            )
            announced = True
        if time.monotonic() >= deadline:
            return None
        time.sleep(POLL_SECONDS)


def _record_holder(lock_dir: Path, index: int, command: Sequence[str]) -> None:
    holder = _slot_path(lock_dir, index).with_suffix(".holder")
    text = (
        f"pid {os.getpid()} on {socket.gethostname()} in {os.getcwd()}: "
        f"{' '.join(command)}\n"
    )
    try:
        holder.write_text(text, encoding="utf-8")
    except OSError:
        pass  # The record only names the holder in a wait line.


def run(command: Sequence[str], env: dict[str, str]) -> int:
    """Run *command*, forwarding termination signals; its shell-style status."""
    try:
        proc = subprocess.Popen(list(command), env=env)
    except FileNotFoundError:
        _say(f"command not found: {command[0]}")
        return 127

    def forward(signum: int, _frame: FrameType | None) -> None:
        proc.send_signal(signum)

    for signum in _FORWARDED:
        signal.signal(signum, forward)
    code = proc.wait()
    return 128 - code if code < 0 else code


def main(argv: Sequence[str] | None = None) -> int:
    try:
        wait, command = parse_args(sys.argv[1:] if argv is None else argv)
    except UsageError as exc:
        _say(str(exc))
        return USAGE_ERROR
    lock_dir = Path(os.environ.get(LOCK_DIR_ENV, DEFAULT_LOCK_DIR))
    env = dict(os.environ)
    if env.get(HELD_ENV) == str(lock_dir):
        return run(command, env)
    try:
        lock_dir.mkdir(parents=True, exist_ok=True)
        held = acquire(lock_dir, wait)
    except OSError as exc:
        _say(f"cannot use {lock_dir} ({exc.strerror}); running without a slot")
        return run(command, env)
    if held is None:
        _say(f"gave up after {wait}s waiting for a heavy-check slot")
        return WAIT_EXPIRED
    fd, index = held
    _record_holder(lock_dir, index, command)
    env[HELD_ENV] = str(lock_dir)
    try:
        return run(command, env)
    finally:
        os.close(fd)


if __name__ == "__main__":
    sys.exit(main())
