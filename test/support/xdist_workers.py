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

"""Size ``pytest -n auto`` to the container's limits, not the host's cores.

Each worktree slot runs under ``docker run --cpus`` and ``--memory`` limits
(``start-dev.sh``), but ``os.cpu_count()`` — and so xdist's own ``auto`` —
reports every host core.  Twelve workers in a two-CPU, 6 GiB slot ran slower
than two and were OOM-killed mid-run, which xdist reports as test failures.

The cgroup files are read directly: CPU quota (``cpu.max``, v2;
``cpu.cfs_quota_us`` / ``cpu.cfs_period_us``, v1), the scheduler affinity, and
the memory limit (``memory.max``, v2; ``memory.limit_in_bytes``, v1).  An
absent file or an ``max`` value means "no limit" for that resource.
"""

import math
import os
from pathlib import Path

#: Memory budgeted per xdist worker.  The full suite's heaviest workers (the
#: demo scenarios) peak well under this; ten workers in a 6 GiB slot did not
#: fit, two did.
WORKER_MEMORY_BYTES = 1536 * 1024 * 1024

#: Memory budgeted per child interpreter a *test* spawns.  Measured: the
#: fresh-import driver's children peak at ~270 MiB resident, each importing
#: pydantic, fastapi and one ``vultron`` module; rounded up for headroom.
CHILD_MEMORY_BYTES = 384 * 1024 * 1024

DEFAULT_CGROUP_ROOT = Path("/sys/fs/cgroup")


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def _ratio(quota: str, period: str) -> int | None:
    """Return ``quota / period`` rounded up to whole CPUs, or ``None``.

    Non-integer text means "no limit" rather than an exception: this runs in
    ``pytest_cmdline_main``, where a raise aborts the session before any test
    is collected.
    """
    try:
        quota_us, period_us = int(quota), int(period)
    except ValueError:
        return None
    if quota_us <= 0 or period_us <= 0:
        return None
    return max(1, math.ceil(quota_us / period_us))


def cgroup_cpu_limit(root: Path = DEFAULT_CGROUP_ROOT) -> int | None:
    """Return the cgroup CPU quota rounded up to whole CPUs, or ``None``."""
    v2 = _read(root / "cpu.max")
    if v2 is not None:
        quota, _, period = v2.partition(" ")
        return _ratio(quota, period)
    quota_v1 = _read(root / "cpu" / "cpu.cfs_quota_us")
    period_v1 = _read(root / "cpu" / "cpu.cfs_period_us")
    if quota_v1 is None or period_v1 is None:
        return None
    return _ratio(quota_v1, period_v1)


def cgroup_memory_limit(root: Path = DEFAULT_CGROUP_ROOT) -> int | None:
    """Return the cgroup memory limit in bytes, or ``None`` when unlimited."""
    raw = _read(root / "memory.max")
    if raw is None:
        raw = _read(root / "memory" / "memory.limit_in_bytes")
    if raw is None:
        return None
    try:
        limit = int(raw)
    except ValueError:  # "max", or text this parser does not know
        return None
    # cgroup v1 spells "unlimited" as a page-rounded near-2**63 value.
    return None if limit >= 2**62 else limit


def available_cpus() -> int:
    """Return the CPUs this process may be scheduled on."""
    # Linux-only; looked up by name so type checkers on other platforms,
    # whose ``os`` stubs omit it, do not flag the call (#4762).
    sched_getaffinity = getattr(os, "sched_getaffinity", None)
    if sched_getaffinity is None:  # not on Linux
        return os.cpu_count() or 1
    return len(sched_getaffinity(0))


def worker_count(
    root: Path = DEFAULT_CGROUP_ROOT, cpus: int | None = None
) -> int:
    """Return how many xdist workers fit the container's CPU and memory."""
    count = available_cpus() if cpus is None else cpus
    cpu_limit = cgroup_cpu_limit(root)
    if cpu_limit is not None:
        count = min(count, cpu_limit)
    memory_limit = cgroup_memory_limit(root)
    if memory_limit is not None:
        count = min(count, memory_limit // WORKER_MEMORY_BYTES)
    return max(1, count)


def child_process_budget(
    root: Path = DEFAULT_CGROUP_ROOT, cpus: int | None = None
) -> int:
    """How many child interpreters one test may run at once.

    A test that spawns children runs inside one xdist worker, and every other
    worker is spending its own share of the container at the same time, so the
    fan-out is budgeted from the memory *one* worker is given
    (:data:`WORKER_MEMORY_BYTES` / :data:`CHILD_MEMORY_BYTES`), never from the
    host's core count.  Sizing it from ``os.cpu_count()`` put sixteen children
    beside sixteen workers on a sixteen-core host; the container's OOM killer
    then took a worker, which xdist reports as a crash of whatever test that
    worker happened to hold (#5184, ``notes/testing-pitfalls.md`` § "A Dead
    xdist Worker Hung the Run").

    Capped by :func:`worker_count`, so a two-CPU slot runs two children rather
    than four: the cap is the same cgroup reading ``-n auto`` is sized from.
    """
    from_memory = WORKER_MEMORY_BYTES // CHILD_MEMORY_BYTES
    return max(1, min(from_memory, worker_count(root, cpus)))
