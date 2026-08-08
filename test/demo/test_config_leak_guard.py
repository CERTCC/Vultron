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

"""Regression tests for demo-suite config leakage (#2086).

Several demo fixtures repoint ``VULTRON_SERVER__BASE_URL`` and
``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL`` at their own fake hosts and then call
``reload_config()``.  ``reload_config()`` re-reads the environment into the
*module-level* config cache, so the order of ``monkeypatch.undo()`` and
``reload_config()`` in teardown determines whether the fake host outlives the
test.

When it does outlive the test, every later demo test derives its CaseActor ID
from a host no ``_TestClientRouter`` has registered.  ``_TestClientRouter.emit``
silently drops the ``Create(CaseProposal)`` delivery, the CaseActor never
creates the canonical case, and ``trigger/validate-report`` fails with
"no routable recipients".  Because it depends on test order (pytest-randomly
reseeds each run), this presented as CI flakiness in
``TestBootstrapSequence.test_announce_creates_case_replica``.

These tests pin both halves of the fix:

* teardown must undo env patches *before* reloading (the source fix), and
* the autouse ``restore_case_actor_url_after_each_test`` guard must detect and
  repair a leak if any fixture gets the order wrong again (defense in depth).
"""

from _pytest.monkeypatch import MonkeyPatch

from vultron.config.app import reload_config
from test.demo.conftest import (
    _CASE_ACTOR_SERVICE_URL,
    config_url_snapshot,
    restore_config_if_leaked,
)

_FAKE_HOST = "http://leaky-host.invalid/api/v2"


def _repoint_config_at_fake_host(mp: MonkeyPatch) -> None:
    """Apply the env patches that demo fixtures apply, and cache them."""
    mp.setenv("VULTRON_SERVER__BASE_URL", _FAKE_HOST)
    mp.setenv("VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _FAKE_HOST)
    reload_config()


class TestConfigLeakGuard:
    """The conftest guard detects and repairs a leaked config snapshot."""

    def test_snapshot_is_stable_when_nothing_changes(self):
        """No reload happens when the config never drifted."""
        before = config_url_snapshot()
        assert restore_config_if_leaked(before) is False
        assert config_url_snapshot() == before

    def test_guard_restores_config_after_a_leak(self):
        """A fixture that reloads while patched is repaired by the guard."""
        before = config_url_snapshot()
        mp = MonkeyPatch()
        try:
            # The buggy teardown order: env still patched when reload runs.
            _repoint_config_at_fake_host(mp)
            assert config_url_snapshot() != before
        finally:
            mp.undo()

        # The guard sees the drift and reloads from the (now clean) env.
        assert restore_config_if_leaked(before) is True
        assert config_url_snapshot() == before


class TestTeardownOrdering:
    """``monkeypatch.undo()`` must precede ``reload_config()`` in teardown."""

    def test_reload_after_undo_leaves_no_leak(self):
        """The corrected order restores the cached config on its own."""
        before = config_url_snapshot()
        mp = MonkeyPatch()
        try:
            _repoint_config_at_fake_host(mp)
        finally:
            mp.undo()
            reload_config()

        assert config_url_snapshot() == before
        assert restore_config_if_leaked(before) is False

    def test_reload_before_undo_leaks(self):
        """The buggy order pins the fake host into the module-level cache.

        This is the mechanism behind #2086; asserting it keeps the comments in
        the demo fixtures honest.
        """
        before = config_url_snapshot()
        mp = MonkeyPatch()
        try:
            _repoint_config_at_fake_host(mp)
            # Buggy teardown: reload first, undo second.
            reload_config()
            assert config_url_snapshot() != before
        finally:
            mp.undo()
            reload_config()

        assert config_url_snapshot() == before


class TestDemoSessionBaseline:
    """The demo session's CaseActor URL is intact when a test starts.

    This is the invariant that CI violated: with pytest-randomly, this test may
    run after any leak-prone demo module, so a surviving leak fails it here.
    """

    def test_case_actor_service_url_matches_demo_session_value(self):
        _, case_actor_url = config_url_snapshot()
        assert case_actor_url.rstrip("/") == _CASE_ACTOR_SERVICE_URL.rstrip(
            "/"
        )
