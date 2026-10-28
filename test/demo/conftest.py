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

"""Shared fixtures and helpers for demo tests."""

import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

import vultron.demo.utils as demo_utils
from test.demo._helpers import (  # noqa: F401 (re-exported for test modules)
    make_testclient_call,
)
from vultron.adapters.driven.datalayer_sqlite import reset_datalayer
from vultron.adapters.driving.fastapi import outbox_handler
from vultron.adapters.driving.fastapi.main import app as api_app
from vultron.adapters.driving.fastapi.outbox_handler import get_default_emitter
from vultron.demo.in_process import InProcessRouter
from vultron.wire.as2.factories import parse_submit_report_offer
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# Eliminate wait delays in all demo tests. The FastAPI TestClient processes
# background tasks synchronously, so no sleep is needed between inbox posts
# and state checks.
demo_utils.DEFAULT_WAIT_SECONDS = 0.0

logger = logging.getLogger(__name__)


def submit_report_through_reporter(
    reporter_tc: TestClient,
    reporter_id: str,
    recipient_id: str,
    report_name: str,
    report_content: str,
) -> tuple[as_VulnerabilityReport, as_Offer]:
    """Submit a report from the reporter's own ``submit-report`` trigger.

    The trigger is how the reporter writes its trust anchor: the pending
    ``ReportCaseLink`` naming *recipient_id* (CBT-01-005).  Posting the Offer
    straight to the recipient's inbox leaves the reporter nothing to check
    the recipient's ``Create(VulnerabilityCase)`` against, so it is refused
    (CBT-01-011, #4472).

    Returns:
        ``(report, offer)`` parsed from the trigger response.
    """
    slug = reporter_id.rstrip("/").rsplit("/", 1)[-1]
    resp = reporter_tc.post(
        f"/api/v2/actors/{slug}/trigger/submit-report",
        json={
            "report_name": report_name,
            "report_content": report_content,
            "recipient_id": recipient_id,
        },
    )
    assert resp.status_code == 202, (
        f"submit-report failed ({resp.status_code}): {resp.text}"
    )
    return parse_submit_report_offer(resp.json()["offer"])


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Mark every test collected from test/demo/ as ``integration``.

    Demo tests spin up a full FastAPI ASGI app via ``TestClient`` and exercise
    end-to-end HTTP request / DataLayer workflows.  They are integration tests
    by nature and should be labelled accordingly so callers can include or
    exclude them explicitly::

        # Run only integration tests
        uv run pytest -m integration

        # Run everything
        uv run pytest -m ""

    This hook runs after collection so it applies regardless of how the tests
    are selected (e.g. ``pytest test/demo/`` or ``pytest`` from the root).
    """
    for item in items:
        path = Path(str(item.fspath))
        if any(
            p.name == "demo" and p.parent.name == "test" for p in path.parents
        ):
            item.add_marker(pytest.mark.integration)


#: Where demo tests expect to find a CaseActor service.
#:
#: This is ``TestClient``'s own base, not the configured ``localhost:7999``,
#: because it must name the node that actually *serves* these tests.
#: ``case_actor_identity()`` derives a CaseActor's id from this value, and the
#: inbox route resolves an incoming path segment against the serving app's base
#: URL.  Point the two at different hosts and the case's CASE_MANAGER participant
#: names one CaseActor while the route opens another's store — so
#: ``CheckIsCaseManagerNode`` finds no match, the guarded commit skips silently,
#: no ``Announce(CaseLedgerEntry)`` is queued, and the fan-out that carries notes
#: and status to the other participants never happens. Nothing raises.
#:
#: Tests using ``create_isolated_actor_app`` override this with their own host.
_CASE_ACTOR_SERVICE_URL = "http://testserver/api/v2"


@pytest.fixture(scope="session", autouse=True)
def configure_case_actor_url_for_demo():
    """Set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL for all demo tests.

    The BT nodes that need the CaseActor identity return FAILURE when
    case_actor_service_url is None (CP-08-005).  Demo tests propose cases
    for the reports they receive, so they need the URL configured to reach
    the case-setup success branch.
    """
    from vultron.config import config_override

    with config_override(
        VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=_CASE_ACTOR_SERVICE_URL
    ):
        yield


def config_snapshot() -> dict:
    """Return the full currently-cached config as a plain dict.

    Snapshotting every field rather than a hand-picked pair means a fixture
    that leaks something other than the two #2086 URLs (e.g.
    ``VULTRON_ACTOR__DEFAULT_CASE_ROLES``) is still detected.
    """
    from vultron.config import get_config

    return get_config().model_dump(mode="json")


def config_url_snapshot() -> tuple[str, str]:
    """Return the currently cached ``(server.base_url, case_actor_service_url)``.

    These are the two settings demo tests repoint at their own fake hosts, and
    the pair whose leakage caused #2086.  Kept as a narrow, readable accessor
    for tests that assert specifically on those URLs;
    :func:`config_snapshot` is what the leak guard compares.
    """
    from vultron.config import get_config

    cfg = get_config()
    return (
        str(cfg.server.base_url),
        str(cfg.actor.case_actor_service_url),
    )


class ConfigLeakLedger:
    """Session-wide record of config leaks the guard had to repair.

    The guard repairs leaks so that one misordered teardown cannot cascade into
    unrelated failures.  That repair also hides the leak, which would leave the
    ``monkeypatch.undo()``-before-``reload_config()`` fixes in the demo modules
    unenforced by any test.  Recording each detection here keeps the repair
    while still giving :mod:`test.demo.test_config_leak_guard` something that
    fails when a fixture teardown regresses (#2086).
    """

    def __init__(self) -> None:
        self.leaks: list[str] = []

    def record(self, before: dict, after: dict) -> None:
        self.leaks.append(f"{_describe_drift(before, after)}")

    def reset(self) -> None:
        self.leaks.clear()


#: Session-wide ledger; asserted on by ``test_config_leak_guard.py``.
config_leak_ledger = ConfigLeakLedger()


def _describe_drift(before: dict, after: dict) -> str:
    """Summarise which config keys changed, for logs and assertion messages."""
    drifted = sorted(
        f"{key}: {before.get(key)!r} -> {after.get(key)!r}"
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    )
    return "; ".join(drifted)


def restore_config_if_leaked(before: dict) -> bool:
    """Reload the module-level config if it drifted from the *before* snapshot.

    The repair is :func:`reload_config`, which re-reads ``os.environ``.  That
    only helps if the offending fixture also undid its env patches, so the
    post-reload state is verified rather than assumed: a reload that fails to
    restore *before* raises instead of reporting a success it did not achieve
    (ARCH-15-001 — a fake success is the same bug as a silent ``None``).

    Args:
        before: Snapshot from :func:`config_snapshot` taken before the code
            under test ran.

    Returns:
        ``True`` if a leak was detected and successfully repaired, ``False``
        if the config never drifted.

    Raises:
        RuntimeError: if the config drifted and the reload did not restore it,
            which means the environment itself is still polluted.
    """
    from vultron.config.app import reload_config

    after = config_snapshot()
    if after == before:
        return False

    drift = _describe_drift(before, after)
    logger.warning(
        "Demo test leaked config (%s); reloading (#2086)",
        drift,
    )
    config_leak_ledger.record(before, after)
    reload_config()

    repaired = config_snapshot()
    if repaired != before:
        raise RuntimeError(
            "Config leak could not be repaired by reload_config(): the "
            "environment is still polluted. A fixture mutated the "
            "environment without undoing it (see #2086). Residual drift: "
            f"{_describe_drift(before, repaired)}"
        )
    return True


@pytest.fixture(autouse=True)
def _no_outbox_row_is_dropped(caplog):
    """Fail any demo test during which the outbox dropped a row (VM-08-003).

    A queued id with no sealed body is logged at ERROR and dropped; the demo
    runner's own "ERROR SUMMARY" covers only exceptions, so without this guard
    a silently undelivered activity would pass every scenario (#2655 AC-5).
    """
    yield
    dropped = [
        r.getMessage()
        for r in caplog.get_records("call")
        if r.levelno >= logging.ERROR and "No sealed body" in r.getMessage()
    ]
    assert not dropped, (
        "the outbox dropped a row nobody sealed:\n" + "\n".join(dropped)
    )


@pytest.fixture(autouse=True)
def _no_outbox_row_is_dead_lettered(caplog):
    """Fail any demo test during which the outbox dead-lettered a row.

    A scenario that runs to completion can still have left an activity
    undelivered: the outbox dead-letters it with an ERROR and carries on
    (OX-13-002, OX-13-013).  A recipient-less ``create-case`` ``Create`` went
    unnoticed this way, retried on backoff in every scenario built on
    ``setup_initialized_case``, until this guard.
    """
    yield
    # Keyed on the outbox handler's logger: the inbox dead-letters with the
    # same wording (IE-06-004), and this guard must not blame the outbox for it.
    dead = [
        r.getMessage()
        for r in caplog.get_records("call")
        if r.name == outbox_handler.__name__
        and r.levelno >= logging.ERROR
        and "moved to dead letter" in r.getMessage().lower()
    ]
    assert not dead, "the outbox dead-lettered a row:\n" + "\n".join(dead)


@pytest.fixture(autouse=True)
def restore_case_actor_url_after_each_test():
    """Restore the session's CaseActor/server config after every demo test.

    Guards against config leakage between demo tests (#2086).  Several demo
    tests point ``VULTRON_SERVER__BASE_URL`` and
    ``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL`` at their own fake hosts and then
    call ``reload_config()``.  If such a test reloads while its env patches are
    still applied, the polluted values are cached in the module-level config for
    the remainder of the session.  Every later test then addresses its
    ``Create(CaseProposal)`` to a host no ``InProcessRouter`` knows about, the
    delivery is silently dropped, the CaseActor never creates the canonical
    case, and ``validate-report`` fails with "no routable recipients".

    Because that depends on test *order*, it presented as CI flakiness.  This
    fixture snapshots the config before each test and reloads after if it
    drifted.

    **Scope limitation**: this fixture is function-scoped, so it only catches
    *function-scoped* offenders.  A module-, class-, or session-scoped fixture
    pollutes the cache *before* this guard takes its ``before`` snapshot, so
    the drift is invisible here and that fixture's teardown runs after this
    one's finalizer.  Higher-scoped fixtures must therefore still order
    ``monkeypatch.undo()`` before ``reload_config()`` themselves — the guard is
    not a substitute.  Any repair performed here is recorded on
    :data:`config_leak_ledger` so ``test_config_leak_guard.py`` fails rather
    than silently masking the regression.
    """
    before = config_snapshot()
    yield
    restore_config_if_leaked(before)


@pytest.fixture(scope="module", autouse=True)
def reset_datalayer_between_modules():
    """Reset all cached DataLayer instances before each demo test module.

    Demo tests create actors, reports, and cases via the API.  Without a
    reset between modules, cached SQLite-backed DataLayer instances can retain
    data created by earlier demo modules, which both slows later tests and
    risks unexpected cross-module visibility.

    Resetting here ensures each module starts from a clean DataLayer cache.
    After the reset, the first API call recreates the SQLite DataLayer with a
    fresh in-memory database (``sqlite:///:memory:``), which provides module
    isolation for the demo test suite.
    """
    reset_datalayer()
    yield
    reset_datalayer()


@pytest.fixture(scope="module")
def client():
    """Provides a shared TestClient instance for demo tests in this module.

    Uses the context-manager form so the FastAPI lifespan events (startup and
    shutdown) are triggered, which initialises the inbox dispatcher via
    :func:`vultron.adapters.driving.fastapi.inbox_handler.init_dispatcher`.

    After the lifespan fires, the module-level default emitter is replaced
    with a ``InProcessRouter`` that routes all actor URLs hosted on
    ``api_app`` back to *test_client* (so cc:-to-self loopback deliveries work
    in-process), while silently dropping deliveries to fictional external URLs
    (e.g. ``https://vultron.example/users/...``) that are unreachable in the
    test environment.  Without this, the lifespan's ``HttpDeliveryAdapter``
    would attempt real HTTP POST requests with retries, which caused the
    integration suite to take 17+ min in CI (#527).

    The default emitter is the only path the routes reach: they read
    ``request.app.state.emitter``, and inside a route ``request.app`` is the
    mounted ``app_v2``, whose lifespan never runs, so it is ``None`` and every
    outbox drain falls back to the default emitter.  ``api_app.state.emitter``
    is left as the lifespan set it; no route reads it.

    See also: #530 (actors sharing a single DataLayer in tests).
    """
    from vultron.adapters.driving.fastapi.outbox_handler import (
        configure_default_emitter,
    )

    with TestClient(api_app) as test_client:
        # The root lifespan now starts the production OutboxMonitor
        # (OX-09-002).  These tests assert on the effect of a trigger right
        # after its 202 and rely on the TestClient running the inline drain
        # before it returns; a monitor draining concurrently would take the
        # rows first and hand the inline drain a "look again" no-op, turning
        # that immediate read into a race.  The monitor's own behaviour is
        # covered by test_outbox_monitor.py, the root-lifespan test and the
        # Docker demo matrix.
        monitor = getattr(api_app.state, "outbox_monitor", None)
        if monitor is not None:
            monitor.stop()
        # Build a router that routes deliveries back to the single app and
        # drops anything sent to external fictional URLs.
        router = InProcessRouter()
        # Register both the TestClient's base_url (http://testserver) and the
        # config's server base_url (e.g. http://localhost:7999) so that all
        # actor IDs hosted on api_app — regardless of which base URL was used
        # to construct them — route back to this TestClient.
        from urllib.parse import urlparse as _urlparse

        from vultron.config import get_config

        tc_base = str(test_client.base_url).rstrip("/")
        router.register(tc_base, test_client)
        cfg_base_url = get_config().server.base_url
        if cfg_base_url:
            parsed = _urlparse(str(cfg_base_url))
            cfg_netloc_base = f"{parsed.scheme}://{parsed.netloc}"
            if cfg_netloc_base != tc_base:
                router.register(cfg_netloc_base, test_client)

        previous_emitter = get_default_emitter()
        configure_default_emitter(router)  # type: ignore[arg-type]

        # Tell the serving app which node it is. These tests address actors as
        # `{TestClient base}/api/v2/actors/{slug}` — TestClient's base_url, not
        # the configured one — so without this the routes resolve a segment into
        # the *configured* namespace and open a different (empty) store than the
        # one `POST /actors/` wrote to. `app_v2` is what carries it because
        # `main.app` mounts it, so `request.app` inside a route is the sub-app.
        from vultron.adapters.driving.fastapi.app import app_v2

        previous_node_base_url = getattr(app_v2.state, "node_base_url", None)
        app_v2.state.node_base_url = f"{tc_base}/api/v2"
        try:
            yield test_client
        finally:
            configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
            app_v2.state.node_base_url = previous_node_base_url


@pytest.fixture(autouse=True)
def every_demo_case_rebuilds_from_its_ledger():
    """No exchange demo leaves a case its ledger cannot rebuild (#4294 AC-5).

    ``route_exchange_demo_at_testclient`` records each case that differs
    when it is rebuilt from its CASE_MANAGER's ledger into an empty store
    (CLP-07-013, CM-23-016), and each entry whose ``semantic_type`` is not
    the registry's label for its payload (ADR-0140, #4724); this fails the
    test that left it.
    """
    from test.demo._helpers import (
        LABELLED_ENTRIES,
        REBUILD_FAILURES,
        REBUILT_CASES,
        assert_no_rebuild_failures,
    )

    REBUILD_FAILURES.clear()
    REBUILT_CASES.clear()
    LABELLED_ENTRIES.clear()
    yield
    assert_no_rebuild_failures()


# The two autouse stubs below change what the protocol does for every test in
# this directory. A test that needs the real run, such as the recorder smoke
# test, lives outside test/demo/ (test/demo_recordings/, #3901).
@pytest.fixture(autouse=True)
def stub_summary_seed():
    """Skip ``stub_summary`` seeding when the case manager's client is a mock.

    Seeding is infrastructure the mock-driven scenario tests do not exercise;
    a real client (in-process app) still seeds, since its Invite needs it
    (#4285).  ``test_invite_chain`` overrides this fixture to test the seed.
    """
    from vultron.demo.helpers import invite_chain

    real = invite_chain._seed_stub_summary

    def seed(client, case):
        if not isinstance(client, Mock):
            real(client, case)

    with patch.object(invite_chain, "_seed_stub_summary", seed):
        yield


@pytest.fixture(autouse=True)
def stub_full_case_reply():
    """Skip the chain's full-case Invite wait and reply in mock-driven tests.

    After the join the invite chain waits for the full-case Invite and answers
    it (CM-11-010, CM-11-011).  Mock-driven scenario tests have no container
    to poll and no trigger to post, so the step is a no-op there;
    ``test_invite_chain`` overrides this fixture to test the real step.
    """
    from vultron.demo.helpers import invite_chain

    with patch.object(invite_chain, "reply_to_full_case_invite"):
        yield
