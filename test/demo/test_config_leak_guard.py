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

* teardown must undo env patches *before* reloading (the source fix), enforced
  by :class:`TestNoFixtureLeakedConfig` asserting the guard never had to repair
  anything during the session, and
* the autouse ``restore_case_actor_url_after_each_test`` guard must detect and
  repair a leak if any fixture gets the order wrong again (defense in depth).
"""

import anyio
import logging

import pytest
from _pytest.monkeypatch import MonkeyPatch

from vultron.config.app import reload_config
from vultron.core.models.activity import VultronActivity
from test.demo.conftest import (
    _CASE_ACTOR_SERVICE_URL,
    _KNOWN_FICTIONAL_HOSTS,
    _TestClientRouter,
    config_leak_ledger,
    config_snapshot,
    config_url_snapshot,
    restore_config_if_leaked,
)

_FAKE_HOST = "http://leaky-host.invalid/api/v2"


def _patch_env_at_fake_host(mp: MonkeyPatch) -> None:
    """Apply the env patches that demo fixtures apply, without reloading.

    Kept separate from the reload so each test below can perform the
    reload/undo sequence in the order it is actually testing.
    """
    mp.setenv("VULTRON_SERVER__BASE_URL", _FAKE_HOST)
    mp.setenv("VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _FAKE_HOST)


def _repoint_config_at_fake_host(mp: MonkeyPatch) -> None:
    """Apply the env patches that demo fixtures apply, and cache them."""
    _patch_env_at_fake_host(mp)
    reload_config()


def _discard_own_ledger_entries(baseline: int) -> None:
    """Trim ledger entries this test deliberately caused.

    The tests below leak config on purpose, so they must not leave their own
    entries behind for :class:`TestNoFixtureLeakedConfig` to trip over.  They
    truncate back to *baseline* rather than clearing, so genuine leaks recorded
    by earlier fixtures survive and are still reported.
    """
    del config_leak_ledger.leaks[baseline:]


class TestConfigLeakGuard:
    """The conftest guard detects and repairs a leaked config snapshot."""

    def test_snapshot_is_stable_when_nothing_changes(self):
        """No reload happens when the config never drifted."""
        before = config_snapshot()
        assert restore_config_if_leaked(before) is False
        assert config_snapshot() == before

    def test_guard_restores_config_after_a_leak(self):
        """A fixture that reloads while patched is repaired by the guard."""
        baseline = len(config_leak_ledger.leaks)
        before = config_snapshot()
        mp = MonkeyPatch()
        try:
            # The buggy teardown order: env still patched when reload runs.
            _repoint_config_at_fake_host(mp)
            assert config_snapshot() != before
        finally:
            mp.undo()

        # The guard sees the drift and reloads from the (now clean) env.
        assert restore_config_if_leaked(before) is True
        assert config_snapshot() == before
        # The repair is recorded rather than silently swallowed, so a real
        # fixture regression cannot hide behind the guard.
        assert len(config_leak_ledger.leaks) == baseline + 1
        _discard_own_ledger_entries(baseline)

    def test_guard_detects_non_url_drift(self):
        """Drift outside the two #2086 URLs is caught too."""
        baseline = len(config_leak_ledger.leaks)
        before = config_snapshot()
        mp = MonkeyPatch()
        try:
            mp.setenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", '["VENDOR"]')
            reload_config()
            assert config_snapshot() != before
        finally:
            mp.undo()

        assert restore_config_if_leaked(before) is True
        assert config_snapshot() == before
        _discard_own_ledger_entries(baseline)

    def test_guard_raises_when_repair_is_impossible(self):
        """An un-undone env patch must fail loudly, not report a fake repair.

        Mutates ``os.environ`` directly (not via ``monkeypatch``) to simulate a
        fixture that never undid its patch, so ``reload_config()`` cannot
        recover the pre-test values.  The session-scoped demo patch is captured
        and restored by hand for the same reason.
        """
        import os

        baseline = len(config_leak_ledger.leaks)
        env_key = "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL"
        original = os.environ.get(env_key)
        before = config_snapshot()
        os.environ[env_key] = _FAKE_HOST
        reload_config()
        try:
            with pytest.raises(RuntimeError, match="still polluted"):
                restore_config_if_leaked(before)
        finally:
            if original is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original
            reload_config()
            _discard_own_ledger_entries(baseline)

        assert config_snapshot() == before


class TestTeardownOrdering:
    """``monkeypatch.undo()`` must precede ``reload_config()`` in teardown."""

    def test_reload_after_undo_leaves_no_leak(self):
        """The corrected order restores the cached config on its own."""
        before = config_snapshot()
        mp = MonkeyPatch()
        _patch_env_at_fake_host(mp)
        reload_config()
        assert config_snapshot() != before

        # Corrected teardown: undo first, reload second.
        mp.undo()
        reload_config()

        assert config_snapshot() == before
        assert restore_config_if_leaked(before) is False

    def test_reload_before_undo_leaks(self):
        """The buggy order pins the fake host into the module-level cache.

        This is the mechanism behind #2086; asserting it keeps the comments in
        the demo fixtures honest.
        """
        before = config_snapshot()
        mp = MonkeyPatch()
        try:
            _patch_env_at_fake_host(mp)
            # Buggy teardown: reload while the env patches are still applied.
            reload_config()
            assert config_snapshot() != before
            # Undoing afterwards does NOT evict the already-cached values —
            # that is precisely why the order matters.
            mp.undo()
            assert config_snapshot() != before
        finally:
            mp.undo()
            reload_config()

        assert config_snapshot() == before


class TestNoFixtureLeakedConfig:
    """No demo fixture may leak config during the session.

    This is what pins the ``monkeypatch.undo()``-before-``reload_config()``
    fixes in ``test_fvcv_handoff_demo.py``, ``test_pcr_late_joiner.py``,
    ``test_case_proposal_round_trip.py``, and ``test_pcr_engage_case.py``.  The
    autouse guard repairs leaks, which keeps one bad teardown from cascading —
    but without this assertion the repair would also make a regression of those
    four fixes invisible to CI.

    Note this only observes fixtures that ran *before* this module in the
    session, so it is order-dependent by nature: it is a ratchet that catches
    regressions on most orderings, not a proof of absence on every ordering.
    """

    def test_guard_recorded_no_leaks(self):
        assert config_leak_ledger.leaks == [], (
            "A demo fixture leaked config into the module-level cache. The "
            "autouse guard repaired it, but the offending fixture must order "
            "monkeypatch.undo() BEFORE reload_config() in its teardown "
            "(#2086). Recorded drift: " + " | ".join(config_leak_ledger.leaks)
        )


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


def _make_mock_activity() -> VultronActivity:
    return VultronActivity(
        id_="urn:test:act1",
        type_="Create",
        actor="urn:test:actor",
    )


class TestTestClientRouterDropLogging:
    """_TestClientRouter.emit logs WARNING for unexpected drops, DEBUG for allowlisted ones."""

    def test_warning_for_unregistered_non_allowlisted_host(self, caplog):
        """emit() logs WARNING when dropping to a host not in _KNOWN_FICTIONAL_HOSTS."""
        router = _TestClientRouter()
        activity = _make_mock_activity()
        with caplog.at_level(logging.DEBUG):
            anyio.run(
                router.emit, activity, ["http://stale-config.test/actors/a1"]
            )
        router_records = [
            r for r in caplog.records if r.name == "test.demo.conftest"
        ]
        assert any(r.levelname == "WARNING" for r in router_records)

    def test_debug_for_allowlisted_host_drop(self, caplog):
        """emit() logs DEBUG (not WARNING) when dropping to a known-fictional host."""
        assert "vultron.example" in _KNOWN_FICTIONAL_HOSTS
        router = _TestClientRouter()
        activity = _make_mock_activity()
        with caplog.at_level(logging.DEBUG):
            anyio.run(
                router.emit,
                activity,
                ["https://vultron.example/users/finder"],
            )
        router_records = [
            r for r in caplog.records if r.name == "test.demo.conftest"
        ]
        assert not any(r.levelname == "WARNING" for r in router_records)
        assert any(r.levelname == "DEBUG" for r in router_records)
