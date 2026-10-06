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

Each worktree slot runs under ``docker run --cpus 2 --memory 6g``
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

DEFAULT_CGROUP_ROOT = Path("/sys/fs/cgroup")


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def cgroup_cpu_limit(root: Path = DEFAULT_CGROUP_ROOT) -> int | None:
    """Return the cgroup CPU quota rounded up to whole CPUs, or ``None``."""
    v2 = _read(root / "cpu.max")
    if v2 is not None:
        quota, _, period = v2.partition(" ")
        if quota == "max" or not period:
            return None
        return max(1, math.ceil(int(quota) / int(period)))
    quota_v1 = _read(root / "cpu" / "cpu.cfs_quota_us")
    period_v1 = _read(root / "cpu" / "cpu.cfs_period_us")
    if quota_v1 is None or period_v1 is None or int(quota_v1) <= 0:
        return None
    return max(1, math.ceil(int(quota_v1) / int(period_v1)))


def cgroup_memory_limit(root: Path = DEFAULT_CGROUP_ROOT) -> int | None:
    """Return the cgroup memory limit in bytes, or ``None`` when unlimited."""
    raw = _read(root / "memory.max")
    if raw is None:
        raw = _read(root / "memory" / "memory.limit_in_bytes")
    if raw is None or raw == "max":
        return None
    limit = int(raw)
    # cgroup v1 spells "unlimited" as a page-rounded near-2**63 value.
    return None if limit >= 2**62 else limit


def available_cpus() -> int:
    """Return the CPUs this process may be scheduled on."""
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:  # not on Linux
        return os.cpu_count() or 1


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
