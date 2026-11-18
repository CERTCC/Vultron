"""Tests that each ``create_app()`` app resolves its own config (ADR-0206).

Two apps in one process are given different ``AppConfig`` values, and each
request shows that ``get_config()`` and ``load_actor_config()`` read only its
own app's config.  An app with none reads the process-wide config, and while
an app holding its own config runs, a read that lost its app's scope raises
``VultronWiringError``.
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import asyncio
import contextvars

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test.support.app_configs import own_app_config
from vultron.adapters.driving.fastapi import app as app_module
from vultron.adapters.driving.fastapi.app import create_app
from vultron.config import (
    AppConfig,
    RunMode,
    config_override,
    get_config,
    load_actor_config,
)
from vultron.config.actor import ActorConfig
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError


def _own_config(retries: int, role: CVDRole) -> AppConfig:
    return own_app_config(
        max_inbox_retry_attempts=retries,
        actor=ActorConfig(default_case_roles=[role]),
    )


def _config_read() -> dict[str, object]:
    return {
        "retries": get_config().max_inbox_retry_attempts,
        "roles": [str(r) for r in load_actor_config().default_case_roles],
    }


def _with_config_probes(app: FastAPI) -> FastAPI:
    """Add one async and one sync route that report the config they read."""

    @app.get("/probe/async")
    async def _async_probe() -> dict[str, object]:
        return _config_read()

    @app.get("/probe/sync")
    def _sync_probe() -> dict[str, object]:
        # A sync endpoint runs in a worker thread; the scope must reach it.
        return _config_read()

    return app


def _app(config: AppConfig | None) -> FastAPI:
    return _with_config_probes(
        create_app(docs_url=None, openapi_url=None, config=config)
    )


@pytest.mark.parametrize("path", ["/probe/async", "/probe/sync"])
def test_two_apps_in_one_process_each_read_their_own_config(path: str) -> None:
    vendor = _own_config(3, CVDRole.VENDOR)
    reporter = _own_config(8, CVDRole.REPORTER)

    with TestClient(_app(vendor)) as a, TestClient(_app(reporter)) as b:
        # Interleaved, so neither app's answer is left over from the other.
        first_a = a.get(path).json()
        first_b = b.get(path).json()
        second_a = a.get(path).json()

    assert first_a == {"retries": 3, "roles": [str(CVDRole.VENDOR)]}
    assert second_a == first_a
    assert first_b == {"retries": 8, "roles": [str(CVDRole.REPORTER)]}


def test_lifespan_reads_the_apps_own_config(monkeypatch) -> None:
    """Startup, a task the lifespan starts, and shutdown read the app's config.

    The probes hook the per-app dispatcher factory (startup) and the per-app
    teardown (shutdown) that the real lifespan calls.
    """
    own = _own_config(6, CVDRole.VENDOR)
    reads: dict[str, AppConfig] = {}
    tasks: list[asyncio.Task[None]] = []
    make_dispatcher = app_module.make_dispatcher
    teardown = app_module._teardown_per_app_state

    async def _task_read() -> None:
        reads["task"] = get_config()

    def _startup_probe():
        reads["startup"] = get_config()
        tasks.append(asyncio.get_running_loop().create_task(_task_read()))
        return make_dispatcher()

    def _shutdown_probe(application: FastAPI) -> None:
        reads["shutdown"] = get_config()
        teardown(application)

    monkeypatch.setattr(app_module, "make_dispatcher", _startup_probe)
    monkeypatch.setattr(app_module, "_teardown_per_app_state", _shutdown_probe)

    with TestClient(_app(own)) as client:
        client.get("/probe/async")

    assert tasks and tasks[0].done()
    assert reads == {"startup": own, "task": own, "shutdown": own}


def test_app_with_no_config_reads_the_process_wide_config() -> None:
    with config_override(VULTRON_MAX_INBOX_RETRY_ATTEMPTS="13"):
        with TestClient(_app(None)) as client:
            body = client.get("/probe/async").json()
    assert body["retries"] == 13


def test_app_with_no_config_beside_one_holding_its_own() -> None:
    """A config-less app keeps reading the process-wide config, refused not."""
    own = _own_config(4, CVDRole.VENDOR)
    with config_override(VULTRON_MAX_INBOX_RETRY_ATTEMPTS="13"):
        with TestClient(_app(own)) as held, TestClient(_app(None)) as plain:
            assert held.get("/probe/sync").json()["retries"] == 4
            assert plain.get("/probe/sync").json()["retries"] == 13


def test_read_that_lost_its_scope_raises_while_the_app_runs() -> None:
    """AC-3: no fallback to the process-wide config while an app holds one."""
    own = _own_config(4, CVDRole.VENDOR)
    with TestClient(_app(own)):
        with pytest.raises(VultronWiringError, match="ADR-0206"):
            contextvars.Context().run(get_config)
    # The app has stopped, so the process-wide read is allowed again.
    assert contextvars.Context().run(get_config) is get_config()


def _demo_trigger_paths(app: FastAPI) -> list[str]:
    return [p for p in app.openapi()["paths"] if "/demo/" in p]


@pytest.mark.parametrize("process_mode", [RunMode.PROTOTYPE, RunMode.PROD])
def test_create_app_reads_its_mode_from_its_own_config(
    process_mode: RunMode,
) -> None:
    """The factory's mode read (TRIG-09-002) uses the app's own config."""
    with config_override(VULTRON_MODE=process_mode.value):
        proto = _app(own_app_config(mode=RunMode.PROTOTYPE))
        prod = _app(own_app_config(mode=RunMode.PROD))
        plain = _app(None)

    assert _demo_trigger_paths(proto)
    assert not _demo_trigger_paths(prod)
    assert bool(_demo_trigger_paths(plain)) is (
        process_mode == RunMode.PROTOTYPE
    )
