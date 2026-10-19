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

"""A dead ``pytest-xdist`` worker fails the run instead of hanging it (#4809).

Under ``--dist loadgroup`` xdist's ``remove_node`` re-queues the crashed
worker's *whole* workload, completed work units included. The replacement
worker is then handed a unit with nothing left to run, runs nothing, reports
nothing, and the controller waits forever. ``--max-worker-restart=0`` in
``addopts`` stops xdist starting that replacement, so the run ends at once and
names the test the worker was running.

The session below runs with this repo's real ``addopts``, so dropping the option
(or changing the scheduler) is what this test catches — not a config string.
"""

import pytest

pytest_plugins = ["pytester"]

#: The crashing session finishes in ~4s; a hang never does.  Well under the
#: 30s unit tier, so a regression fails here rather than tripping that ceiling.
_SESSION_CEILING_SECONDS = 20

_CRASHING_TESTS = """
import os
import time

import pytest


@pytest.mark.parametrize("i", range(20))
def test_ok(i):
    time.sleep(0.05)


def test_worker_dies():
    os._exit(1)
"""


@pytest.mark.spec("TB-14-004")
def test_dead_worker_fails_run_instead_of_hanging(pytester, pytestconfig):
    pytester.makepyfile(test_crash=_CRASHING_TESTS)

    try:
        result = pytester.runpytest_subprocess(
            *pytestconfig.getini("addopts"),
            "-n",
            "2",
            "-p",
            "no:cacheprovider",
            timeout=_SESSION_CEILING_SECONDS,
        )
    except pytester.TimeoutExpired:
        pytest.fail(
            "the session hung after an xdist worker died (#4809); "
            "is --max-worker-restart=0 still in addopts?"
        )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(
        ["*worker 'gw*' crashed while running*test_worker_dies*"]
    )
    # No passed count: how many ``test_ok`` items run before shutdown depends
    # on which worker drew the crash, and that is not what this pins.
    assert result.parseoutcomes()["failed"] == 1
