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

"""
Tests for the integration-tier per-test timeout (issue #2270).

The global ``timeout = 30`` in ``pyproject.toml`` is sized for the unit suite.
``test/conftest.py`` widens it for ``integration``-marked tests only. These
tests pin both tiers so neither ceiling can silently creep back down and abort
the session again.

``TestApplyIntegrationTimeout`` exercises the hook against a stub item, which
pins its own contract but cannot show that pytest-timeout honours a marker
added at collection time. ``TestResolvedTimeoutsUnderRealPytest`` closes that
gap by running a real pytest session and reading the timeout each item
actually resolved to, and ``TestDemoItemsResolveToTheIntegrationTier`` does
the same for the real ``test/demo/`` collection (#3604).

``TestTimeoutTripFailsOneTest`` and ``TestTimeoutTripReleasesTheBtLock`` pin
what a trip costs under the configured ``timeout_method`` (#3603).

``TestTheUnitCeilingIsLive`` pins that the ceiling is *applied*, not merely
written down (#5597) — everything else here either stubs the resolution hook or
supplies the probe session's ceiling with ``-o timeout=``.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_timeout

from test.conftest import (
    INTEGRATION_TIMEOUT_SECONDS,
    apply_integration_timeout,
)
from test.support.child_env import child_env

pytest_plugins = ["pytester"]

#: Slowest integration test under ``-n auto`` on a quiet host, in seconds
#: (``test_rvcv_extension_demo.py``, 30.05 s; #5188).
_SLOWEST_QUIET_INTEGRATION_SECONDS = 30

#: How far host contention stretched the CPU-bound demos over their quiet
#: time (#5188): 2-3x at ``-n 0`` under host load ~30 on 16 cores, and about
#: 4x under a loaded ``-n auto`` run, where the 60 s tier tripped.
_MEASURED_LOAD_INFLATION = 4


class FakeItem:
    """Minimal stand-in for a pytest ``Item``.

    Only the two marker operations the hook uses are implemented:
    ``get_closest_marker`` and ``add_marker``.
    """

    def __init__(self, *marker_names, timeout=None):
        self.names = set(marker_names)
        self.added = []
        self.explicit_timeout = timeout

    def get_closest_marker(self, name):
        if name == "timeout":
            if self.explicit_timeout is not None:
                return pytest.mark.timeout(self.explicit_timeout).mark
            for mark in self.added:
                if mark.name == "timeout":
                    return mark
            return None
        return (
            pytest.mark.__getattr__(name).mark if name in self.names else None
        )

    def add_marker(self, marker):
        self.added.append(marker.mark)

    @property
    def applied_timeout(self):
        for mark in self.added:
            if mark.name == "timeout":
                return mark.args[0]
        return None


class TestApplyIntegrationTimeout:
    def test_integration_item_gets_the_integration_tier_timeout(self):
        item = FakeItem("integration")

        assert apply_integration_timeout([item]) == 1
        assert item.applied_timeout == INTEGRATION_TIMEOUT_SECONDS

    def test_unit_item_is_left_at_the_global_default(self):
        item = FakeItem()

        assert apply_integration_timeout([item]) == 0
        assert item.applied_timeout is None

    @pytest.mark.spec("TB-14-007")
    def test_explicit_timeout_marker_wins(self):
        """A deliberate per-test value must not be overwritten."""
        item = FakeItem("integration", timeout=180)

        assert apply_integration_timeout([item]) == 0
        assert item.applied_timeout is None

    def test_explicit_shorter_timeout_also_wins(self):
        """Tests that assert on a timeout firing must keep their short value."""
        item = FakeItem("integration", timeout=1)

        assert apply_integration_timeout([item]) == 0
        assert item.applied_timeout is None

    def test_mixed_collection_only_touches_integration_items(self):
        integration = FakeItem("integration")
        unit = FakeItem()
        explicit = FakeItem("integration", timeout=10)

        assert apply_integration_timeout([integration, unit, explicit]) == 1
        assert integration.applied_timeout == INTEGRATION_TIMEOUT_SECONDS
        assert unit.applied_timeout is None
        assert explicit.applied_timeout is None

    def test_applying_twice_is_idempotent(self):
        """Re-running the hook must not stack duplicate timeout markers."""
        item = FakeItem("integration")

        apply_integration_timeout([item])
        assert apply_integration_timeout([item]) == 0
        assert [m.name for m in item.added].count("timeout") == 1

    def test_empty_collection_is_a_no_op(self):
        assert apply_integration_timeout([]) == 0


_UNIT_TIER_FOR_PROBE = 30

_PROBE_CONFTEST = """
import json
import pathlib

import pytest_timeout

from test.conftest import apply_integration_timeout

_resolved = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: integration test")


def pytest_collection_modifyitems(items):
    apply_integration_timeout(items)


def pytest_runtest_setup(item):
    _resolved[item.name] = pytest_timeout._get_item_settings(item).timeout


def pytest_sessionfinish(session, exitstatus):
    pathlib.Path(session.config.rootpath / "resolved.json").write_text(
        json.dumps(_resolved)
    )
"""

_PROBE_TESTS = """
import pytest


@pytest.mark.integration
def test_integration_tier():
    pass


def test_unit_tier():
    pass


@pytest.mark.integration
@pytest.mark.timeout(7)
def test_explicit_marker_wins():
    pass
"""


class TestResolvedTimeoutsUnderRealPytest:
    """Assert the timeout each item *actually* resolves to (issue #2270).

    The stub-based tests above verify the hook's own logic. This one runs a
    real pytest session and asks pytest-timeout what it resolved for each
    item, which is the only way to catch a hook-ordering regression: the
    marker is added at collection time, but pytest-timeout reads it much
    later, in ``pytest_runtest_protocol``.
    """

    @pytest.fixture
    def resolved(self, pytester):
        pytester.makeconftest(_PROBE_CONFTEST)
        pytester.makepyfile(test_probe=_PROBE_TESTS)

        result = pytester.runpytest(
            "-p",
            "no:randomly",
            "-o",
            f"timeout={_UNIT_TIER_FOR_PROBE}",
            "-o",
            "timeout_method=thread",
        )
        result.assert_outcomes(passed=3)

        return json.loads((pytester.path / "resolved.json").read_text())

    def test_integration_item_resolves_to_the_integration_tier(self, resolved):
        assert resolved["test_integration_tier"] == INTEGRATION_TIMEOUT_SECONDS

    def test_unit_item_resolves_to_the_unit_tier(self, resolved):
        assert resolved["test_unit_tier"] == _UNIT_TIER_FOR_PROBE

    @pytest.mark.spec("TB-14-007")
    def test_explicit_marker_beats_the_tier_default(self, resolved):
        """The demo suite's deliberate values (10, 180) depend on this."""
        assert resolved["test_explicit_marker_wins"] == 7


class TestIntegrationTimeoutValue:
    @pytest.mark.spec("TB-14-003")
    def test_clears_the_slowest_quiet_demo_under_measured_load(self):
        """The tier covers the slowest demo at the load the suite meets.

        The exchange demos are CPU-bound, so load stretches them in
        proportion. The slowest integration test measured
        :data:`_SLOWEST_QUIET_INTEGRATION_SECONDS` under ``-n auto`` on a
        quiet host, and contention stretched the demos about
        :data:`_MEASURED_LOAD_INFLATION` times, which tripped the embargo
        demos at a 60 s tier (#5188).

        The inputs are measured constants, so this pins a floor against a
        revert; it does not re-measure the suite.
        """
        assert INTEGRATION_TIMEOUT_SECONDS >= (
            _SLOWEST_QUIET_INTEGRATION_SECONDS * _MEASURED_LOAD_INFLATION
        )

    def test_is_still_a_bounded_hang_detector(self):
        assert INTEGRATION_TIMEOUT_SECONDS <= 300


class TestUnitTierTimeout:
    """Pin the unit-tier ceiling in ``pyproject.toml`` (issue #2270).

    Four sessions re-diagnosed a too-tight unit ceiling as flakiness before it
    was raised. These assertions make a silent revert fail loudly.
    """

    @staticmethod
    def _configured_timeout(pytestconfig):
        return int(pytestconfig.getini("timeout"))

    def test_unit_tier_clears_the_slowest_ast_ratchet(self, pytestconfig):
        """AST-walking architecture ratchets run ~3.4s in isolation.

        Under full-suite load they were tripping a 5s ceiling. Require enough
        headroom that load variance cannot reach it.
        """
        assert self._configured_timeout(pytestconfig) >= 15

    def test_unit_tier_is_still_a_bounded_hang_detector(self, pytestconfig):
        assert self._configured_timeout(pytestconfig) <= 60

    def test_integration_tier_is_wider_than_the_unit_tier(self, pytestconfig):
        assert (
            self._configured_timeout(pytestconfig)
            < INTEGRATION_TIMEOUT_SECONDS
        )


#: Per-test ceiling inside the probe sessions below: long enough to import
#: pytest, short enough that the hanging test trips it at once.
_PROBE_TRIP_SECONDS = 1

#: Ceiling on each probe session.  A trip under ``thread`` ends the session in
#: about a second, and a hang never ends; either way this bounds the test.
_PROBE_SESSION_CEILING_SECONDS = 20

#: Ceiling on the ``-n 2`` probe session, which pays for two worker boots
#: before any test runs.  Its caller is integration-tiered for the same reason.
_XDIST_PROBE_SESSION_CEILING_SECONDS = 60

#: The ``-n`` probe's whole body: one test that outlives the ceiling.  A trip's
#: blast radius is pinned serially, so the xdist run asks only whether the
#: ceiling reached the worker at all.
_XDIST_TRIP_TEST = """
import time


def test_hangs():
    time.sleep(30)
"""

_TIMEOUT_TRIP_TESTS = """
import time


def test_hangs():
    time.sleep(30)


def test_fails_after_the_hang():
    assert False


def test_passes_after_the_hang():
    pass
"""

_LOCK_TRIP_TESTS = """
import threading
import time

from vultron.core.behaviors.bridge.lock import _BT_GLOBAL_LOCK


def _acquire_from_another_thread():
    # The lock is re-entrant, so only another thread can tell whether the
    # timed-out test left it held.
    acquired = []

    def attempt():
        got = _BT_GLOBAL_LOCK.acquire(timeout=5)
        if got:
            _BT_GLOBAL_LOCK.release()
        acquired.append(got)

    worker = threading.Thread(target=attempt)
    worker.start()
    worker.join()
    return acquired == [True]


def test_times_out_while_holding_the_lock():
    with _BT_GLOBAL_LOCK:
        time.sleep(30)


def test_lock_is_free_after_the_trip():
    assert _acquire_from_another_thread()


def test_times_out_while_waiting_for_the_lock():
    held = threading.Event()
    release = threading.Event()

    def holder():
        with _BT_GLOBAL_LOCK:
            held.set()
            release.wait(timeout=10)

    threading.Thread(target=holder, daemon=True).start()
    held.wait()
    try:
        with _BT_GLOBAL_LOCK:
            pass
    finally:
        release.set()


def test_lock_is_free_after_the_interrupted_wait():
    assert _acquire_from_another_thread()
"""


def _run_probe_session(
    pytester,
    pytestconfig,
    tests,
    *extra_args,
    session_ceiling=_PROBE_SESSION_CEILING_SECONDS,
):
    """Run *tests* under this repo's ``timeout_method`` in a subprocess.

    A subprocess, not ``runpytest``: an inline session would share this
    process's ``SIGALRM`` handler, and a ``thread`` trip would end this process.

    *extra_args* go on the command line after the fixed options, so a caller can
    add ``-n`` to run the same probe under ``pytest-xdist``; *session_ceiling*
    is there for that caller, because booting workers is not free.
    """
    pytester.makepyfile(test_probe=tests)
    try:
        return pytester.runpytest_subprocess(
            "-p",
            "no:cacheprovider",
            "-o",
            f"timeout={_PROBE_TRIP_SECONDS}",
            "-o",
            f"timeout_method={pytestconfig.getini('timeout_method')}",
            *extra_args,
            timeout=session_ceiling,
        )
    except pytester.TimeoutExpired:
        pytest.fail(
            "the probe session outran its own"
            f" {session_ceiling}s ceiling with args {extra_args!r}, so either a"
            " per-test timeout trip did not end the hanging test or the"
            " session never got that far — under -n, worker startup on a"
            " loaded host is the other candidate"
        )


@pytest.mark.spec("TB-14-002", "TB-14-008", "TB-14-009")
class TestTimeoutTripFailsOneTest:
    """A per-test timeout trip fails that test alone (#3603).

    Under ``timeout_method = "thread"`` a trip ends the whole process: tests
    after it never run, failures already recorded are never named, and under
    ``-n`` the dead process is an xdist worker (#4809).  These pin the property
    against the configured method, not the config string.
    """

    def test_session_continues_and_names_every_failure(
        self, pytester, pytestconfig
    ):
        result = _run_probe_session(
            pytester, pytestconfig, _TIMEOUT_TRIP_TESTS
        )

        result.assert_outcomes(passed=1, failed=2)
        result.stdout.fnmatch_lines(
            [
                "FAILED test_probe.py::test_hangs - Failed: Timeout*",
                "FAILED test_probe.py::test_fails_after_the_hang*",
            ],
            consecutive=False,
        )


@pytest.mark.spec("TB-14-002")
class TestTimeoutTripReleasesTheBtLock:
    """A trip never leaves ``_BT_GLOBAL_LOCK`` held (#3603 AC-5).

    The ``signal`` method raises in the main thread at an arbitrary point.  The
    risk is a trip that leaves the process-global blackboard lock held, so every
    later BT test in that worker deadlocks.  Every acquire in ``vultron/`` is a
    ``with`` block, which releases on the raised ``Failed``; and since Python
    3.2 a blocked acquire is interruptible by a signal on POSIX.  These check
    both paths rather than rely on that reading.
    """

    def test_lock_is_free_after_a_trip_inside_or_waiting_on_it(
        self, pytester, pytestconfig
    ):
        result = _run_probe_session(pytester, pytestconfig, _LOCK_TRIP_TESTS)

        result.assert_outcomes(passed=2, failed=2)


_REPO_ROOT = Path(__file__).parents[1]

#: Records each collected item's markers after every
#: ``pytest_collection_modifyitems`` implementation has run.  A wrapper, not
#: ``trylast``: it surrounds every implementation, so "explicit" is the
#: ``timeout`` marker an item carried before either conftest hook touched it.
_COLLECTION_PROBE = """
import json
import os

import pytest
import pytest_timeout


@pytest.hookimpl(wrapper=True)
def pytest_collection_modifyitems(items):
    explicit = {i.nodeid for i in items if i.get_closest_marker("timeout")}
    result = yield
    resolved = {
        i.nodeid: {
            "integration": i.get_closest_marker("integration") is not None,
            "explicit_timeout": i.nodeid in explicit,
            "timeout": pytest_timeout._get_item_settings(i).timeout,
        }
        for i in items
    }
    with open(os.environ["TIER_PROBE_OUT"], "w") as out:
        json.dump(resolved, out)
    return result
"""

#: Ceiling on the collection subprocess: ~10s on an idle machine.
_COLLECTION_CEILING_SECONDS = 150


@pytest.fixture(scope="module")
def demo_items(tmp_path_factory):
    """Each collected ``test/demo/`` item's resolved markers, by node id."""
    probe_dir = tmp_path_factory.mktemp("tier_probe")
    (probe_dir / "tier_probe.py").write_text(_COLLECTION_PROBE)
    out = probe_dir / "resolved.json"
    env = {**child_env(probe_dir), "TIER_PROBE_OUT": str(out)}

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "test/demo",
            "-m",
            "",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "tier_probe",
        ],
        check=False,
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=_COLLECTION_CEILING_SECONDS,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(out.read_text())


@pytest.mark.spec("TB-14-001")
@pytest.mark.integration
# Collects all of test/demo/ in a subprocess (~10s idle), which load can push
# past the integration tier this test exists to check.
@pytest.mark.timeout(_COLLECTION_CEILING_SECONDS + 30)
class TestDemoItemsResolveToTheIntegrationTier:
    """Every really-collected ``test/demo/`` item is in the integration tier (#3604).

    ``test/demo/conftest.py`` adds the ``integration`` marker and root
    ``test/conftest.py`` turns that marker into the tier timeout, so the tier
    depends on the order the two hooks run in.  The ``FakeItem`` tests above
    cannot see that order; this asks a real collection of the real directory.
    """

    def test_collection_found_demo_items(self, demo_items):
        assert demo_items, "the probe saw no test/demo/ items"

    def test_every_item_is_marked_integration(self, demo_items):
        unmarked = sorted(
            nodeid
            for nodeid, item in demo_items.items()
            if not item["integration"]
        )

        assert unmarked == []

    def test_every_item_without_its_own_marker_gets_the_tier(self, demo_items):
        """An item's own ``@pytest.mark.timeout(N)`` wins, in either direction."""
        off_tier = sorted(
            nodeid
            for nodeid, item in demo_items.items()
            if not item["explicit_timeout"]
            and item["timeout"] != INTEGRATION_TIMEOUT_SECONDS
        )

        assert off_tier == []


# ---------------------------------------------------------------------------
# The ceiling is live, not merely configured (#5597)
# ---------------------------------------------------------------------------
#
# Everything above either stubs the resolution hook or runs a probe session
# whose ceiling is supplied with ``-o timeout=``.  Both are deliberate: they
# isolate the hook's logic and a trip's blast radius from the configured value.
# Neither asks the question #5597 raised, though — does *this* session, launched
# the canonical way, actually apply ``timeout`` from ``pyproject.toml`` to an
# ordinary unit test?  Without that, a test that polls a ``MagicMock`` for a
# minute reads as healthy.
#
# A ceiling can go inert three ways:
#
# 1. ``pytest-timeout`` is absent or disabled, so nothing resolves at all.
# 2. The ini is never read, because pytest's rootdir resolution found no
#    ``configfile``.  This is the one #5597's own control experiment hit: in a
#    scratch directory outside the repo a test sleeping 35 s passed, there being
#    no configuration to apply.  Inside the tree the same file is killed at 30 s,
#    serially and under ``-n`` alike, so the ceiling was never the defect.
# 3. The ceiling resolves in the controlling process but never reaches an xdist
#    worker, where almost every test actually runs.
#
# ``test_this_session_resolves_the_configured_ceiling`` closes 1 and 2 by asking
# pytest-timeout what it resolved for the running test and checking that the
# configuration pytest loaded is this repo's.
# ``test_a_trip_reaches_an_xdist_worker`` closes 3.  The ceiling's *value* is
# pinned by :class:`TestUnitTierTimeout` and a trip's behaviour by
# :class:`TestTimeoutTripFailsOneTest`, so between the four the ceiling cannot
# go inert without one of them saying so.


@pytest.mark.spec("TB-14-001")
class TestTheUnitCeilingIsLive:
    """The configured unit ceiling is applied to real tests (#5597)."""

    def test_this_session_resolves_the_configured_ceiling(
        self, request, pytestconfig
    ):
        """This very test runs under the ``timeout`` in ``pyproject.toml``.

        Read from ``pytest_timeout`` rather than from the ini, because the ini
        is what *should* apply; ``_get_item_settings`` is what does.  A missing
        plugin or an unread config both land as ``None`` here.

        Skipped when the ceiling is overridden for the session.
        ``pytest_timeout.get_env_settings`` prefers ``--timeout`` and then
        ``PYTEST_TIMEOUT`` over the ini, so under the ``--timeout=0`` that
        ``docs/reference/codebase/TESTING.md`` documents for diagnosing a
        suite-level hang, the resolved value is honestly 0 and the ini is
        honestly 30.  The canonical gate command passes neither, so the gate
        still runs on every real session — but a diagnostic switch must not
        turn into a spurious red.
        """
        override = pytestconfig.getvalue("timeout")
        if override is not None or os.environ.get("PYTEST_TIMEOUT"):
            pytest.skip(
                "the per-test ceiling is overridden for this session"
                f" (--timeout={override!r},"
                f" PYTEST_TIMEOUT={os.environ.get('PYTEST_TIMEOUT')!r}), so"
                " the configured value is not what applies"
            )

        assert pytestconfig.inipath is not None, (
            "pytest loaded no configuration file, so"
            " [tool.pytest.ini_options] — the per-test ceiling included — is"
            " not in force.  This is the whole of #5597: a control test run"
            " from a directory outside the repo gets no configfile and sleeps"
            " past the ceiling untouched."
        )
        assert pytestconfig.inipath.name == "pyproject.toml"

        resolved = pytest_timeout._get_item_settings(request.node).timeout

        assert resolved is not None, (
            "no per-test timeout resolved for this unit test: the ceiling is"
            " inert (#5597)"
        )
        assert resolved == float(pytestconfig.getini("timeout"))

    # Integration-tiered deliberately: this spawns a pytest subprocess which
    # itself boots two xdist workers, and worker startup on a loaded host does
    # not reliably fit the 30 s unit tier.  The thing under test is a process
    # tree, which is what the wider tier is for (TB-14-003: move the tier, do
    # not sprinkle markers).  Its serial twin above stays in the unit tier.
    @pytest.mark.integration
    def test_a_trip_reaches_an_xdist_worker(self, pytester, pytestconfig):
        """A worker process kills its own over-ceiling test.

        Each worker is a separate process, so the ``signal`` method's
        ``SIGALRM`` has to land on that worker's main thread rather than the
        controller's.  The canonical gate command is ``-n auto``, which makes
        this the configuration nearly every test actually runs in.

        Only the hanging test is in this probe: that a trip leaves the session
        running and names every failure is :class:`TestTimeoutTripFailsOneTest`'s
        subject, and pinning it again here would only buy worker boots.
        """
        result = _run_probe_session(
            pytester,
            pytestconfig,
            _XDIST_TRIP_TEST,
            "-n",
            "2",
            session_ceiling=_XDIST_PROBE_SESSION_CEILING_SECONDS,
        )

        result.assert_outcomes(failed=1)
        result.stdout.fnmatch_lines(
            ["*test_hangs*Failed: Timeout*"], consecutive=False
        )
