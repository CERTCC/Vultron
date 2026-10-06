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

"""``-n auto`` is sized to the container's cgroup limits, not the host's cores."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from test import conftest as root_conftest
from test.support import xdist_workers
from test.support.xdist_workers import (
    WORKER_MEMORY_BYTES,
    cgroup_cpu_limit,
    cgroup_memory_limit,
    worker_count,
)

GIB = 1024**3


def _cgroup(root: Path, **files: str) -> Path:
    for relative, content in files.items():
        path = root / relative.replace("__", "/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n")
    return root


def test_cpu_quota_v2_rounds_up_to_whole_cpus(tmp_path):
    assert (
        cgroup_cpu_limit(_cgroup(tmp_path, **{"cpu.max": "150000 100000"}))
        == 2
    )


def test_cpu_quota_v2_max_is_unlimited(tmp_path):
    assert (
        cgroup_cpu_limit(_cgroup(tmp_path, **{"cpu.max": "max 100000"}))
        is None
    )


def test_cpu_quota_v1(tmp_path):
    root = _cgroup(
        tmp_path,
        **{
            "cpu__cpu.cfs_quota_us": "400000",
            "cpu__cpu.cfs_period_us": "100000",
        },
    )
    assert cgroup_cpu_limit(root) == 4


def test_cpu_quota_v1_negative_is_unlimited(tmp_path):
    root = _cgroup(
        tmp_path,
        **{"cpu__cpu.cfs_quota_us": "-1", "cpu__cpu.cfs_period_us": "100000"},
    )
    assert cgroup_cpu_limit(root) is None


def test_no_cgroup_files_means_no_limit(tmp_path):
    assert cgroup_cpu_limit(tmp_path) is None
    assert cgroup_memory_limit(tmp_path) is None


def test_memory_v2(tmp_path):
    root = _cgroup(tmp_path, **{"memory.max": str(6 * GIB)})
    assert cgroup_memory_limit(root) == 6 * GIB


def test_memory_v2_max_is_unlimited(tmp_path):
    assert (
        cgroup_memory_limit(_cgroup(tmp_path, **{"memory.max": "max"})) is None
    )


def test_memory_v1_unlimited_sentinel(tmp_path):
    root = _cgroup(
        tmp_path, **{"memory__memory.limit_in_bytes": "9223372036854771712"}
    )
    assert cgroup_memory_limit(root) is None


def test_a_two_cpu_slot_gets_two_workers_on_a_twelve_core_host(tmp_path):
    """The case that OOM-killed workers: the host's cores, the slot's limits."""
    root = _cgroup(
        tmp_path, **{"cpu.max": "200000 100000", "memory.max": str(6 * GIB)}
    )
    assert worker_count(root, cpus=12) == 2


def test_memory_caps_workers_below_the_cpu_limit(tmp_path):
    root = _cgroup(
        tmp_path,
        **{
            "cpu.max": "800000 100000",
            "memory.max": str(3 * WORKER_MEMORY_BYTES),
        },
    )
    assert worker_count(root, cpus=12) == 3


def test_unlimited_container_uses_every_available_cpu(tmp_path):
    assert worker_count(tmp_path, cpus=12) == 12


def test_never_fewer_than_one_worker(tmp_path):
    root = _cgroup(tmp_path, **{"memory.max": str(WORKER_MEMORY_BYTES // 2)})
    assert worker_count(root, cpus=4) == 1


def _config(numprocesses: object) -> pytest.Config:
    return SimpleNamespace(option=SimpleNamespace(numprocesses=numprocesses))  # type: ignore[return-value]


def test_hook_returns_the_cgroup_sized_count(monkeypatch):
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    monkeypatch.setattr(root_conftest, "worker_count", lambda: 3)
    assert root_conftest.pytest_xdist_auto_num_workers(_config("auto")) == 3


def test_hook_defers_to_the_explicit_env_var(monkeypatch):
    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "5")
    assert root_conftest.pytest_xdist_auto_num_workers(_config("auto")) is None


def test_hook_leaves_logical_to_xdist(monkeypatch):
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    assert (
        root_conftest.pytest_xdist_auto_num_workers(_config("logical")) is None
    )


def test_available_cpus_falls_back_without_affinity(monkeypatch):
    monkeypatch.delattr(xdist_workers.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(xdist_workers.os, "cpu_count", lambda: 7)
    assert xdist_workers.available_cpus() == 7
