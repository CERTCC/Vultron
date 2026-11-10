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

"""``--dist loadgroup`` keeps an ``xdist_group`` on one worker, in order (#6181).

``test/test_process_global_isolation.py`` holds ordered pairs that mean
something only when both halves run in one process, in collection order. The
``xdist_group`` mark and the ``--dist loadgroup`` in ``addopts`` are what keep
them together. Under pytest 9.2 with pytest-xdist 3.8.0 the mark silently does
nothing (pytest #15303, pytest-xdist #1386), so a pytest or xdist bump can break
the grouping with no failing test anywhere but those pairs — and only when a run
happens to split them.

The session below runs with this repo's real ``addopts`` and enough workers that
an ungrouped split is certain. Its conftest also drops a test in a ``trylast``
collection hook, as ``test/conftest.py`` and ``test/demo/conftest.py`` change the
collection after xdist's own hook runs; pytest-xdist #1399 crashes or mislabels
groups in exactly that case.
"""

import json

import pytest

pytest_plugins = ["pytester"]

_SESSION_CEILING_SECONDS = 60

_WORKERS = 4

#: The grouped tests, in collection order.
_GROUPED = [f"test_grouped_{i}" for i in range(_WORKERS)]

_CONFTEST = """
import pytest


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    dropped = [item for item in items if item.name == "test_dropped_late"]
    items[:] = [item for item in items if item not in dropped]
    config.hook.pytest_deselected(items=dropped)
"""

_RECORDING_HELPERS = """
import json
import os

import pytest

_LOG = os.environ["LOADGROUP_LOG"]


def _record(name):
    with open(_LOG, "a", encoding="utf-8") as log:
        log.write(json.dumps([os.environ["PYTEST_XDIST_WORKER"], name]) + "\\n")


def test_dropped_late():
    _record("test_dropped_late")
"""

_UNGROUPED_TESTS = f"""
@pytest.mark.parametrize("i", range({_WORKERS * 2}))
def test_ungrouped(i):
    _record(f"test_ungrouped_{{i}}")
"""

_GROUPED_TEST = """
@pytest.mark.xdist_group("pair")
def {name}():
    _record("{name}")
"""

_RECORDING_TESTS = (
    _RECORDING_HELPERS
    + _UNGROUPED_TESTS
    + "".join(_GROUPED_TEST.format(name=name) for name in _GROUPED)
)


@pytest.mark.spec("TB-06-003")
def test_loadgroup_keeps_an_xdist_group_on_one_worker_in_order(
    pytester, pytestconfig, monkeypatch
):
    log = pytester.path / "loadgroup.log"
    monkeypatch.setenv("LOADGROUP_LOG", str(log))
    pytester.makeconftest(_CONFTEST)
    pytester.makepyfile(test_grouping=_RECORDING_TESTS)

    result = pytester.runpytest_subprocess(
        *pytestconfig.getini("addopts"),
        "-n",
        str(_WORKERS),
        "-p",
        "no:cacheprovider",
        timeout=_SESSION_CEILING_SECONDS,
    )

    assert result.ret == pytest.ExitCode.OK, result.stdout.str()
    runs = [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
    ]
    names = [name for _, name in runs]
    assert "test_dropped_late" not in names
    grouped = [(worker, name) for worker, name in runs if name in _GROUPED]
    assert [name for _, name in grouped] == _GROUPED, (
        "the xdist_group tests did not each run once, in collection order"
    )
    workers = {worker for worker, _ in grouped}
    assert len(workers) == 1, (
        f"the xdist_group tests ran on {sorted(workers)}, not one worker: "
        "--dist loadgroup no longer honors the mark (#6181)"
    )
