#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""An in-process delivery chain never waits on the loop's shared thread pool.

``InProcessRouter`` posts each delivery from a worker thread, and a
``TestClient`` POST returns only when the target app's background tasks have
finished, so a hop holds its thread for as long as the rest of the chain runs.
Borrowed from the loop's default AnyIO pool, those threads ran out: every one
waited on a hop that needed one more, the loop stopped, and the ``TestClient``
could never close.  Under ``timeout_method = "signal"`` the trip then hung the
xdist worker for good, so a loaded run sat at 99% until the gate's wall-clock
ceiling ended it with exit 124 (#6190, TB-14-002, TB-14-008).

The chain is run in a child process (``_nested_delivery_probe``) because a
stalled ``TestClient`` cannot be closed: asking in-process would hang this test
the same way.
"""

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Backstop for the child.  The probe gives up on its own after
#: ``WAIT_SECONDS``; this only bounds a child that cannot even do that.
_CHILD_CEILING_SECONDS = 100


def test_a_delivery_chain_deeper_than_the_thread_pool_finishes():
    try:
        result = subprocess.run(
            [sys.executable, "-m", "test.demo._nested_delivery_probe"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=_CHILD_CEILING_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"the delivery-chain probe never exited: {exc}")
    assert result.returncode == 0, result.stderr
