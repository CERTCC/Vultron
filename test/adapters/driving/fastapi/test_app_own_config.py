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

import contextvars

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.app import create_app
from vultron.config import (
    AppConfig,
    RunMode,
    clear_config_cache,
    get_config,
    load_actor_config,
)
from vultron.config.actor import ActorConfig
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError


@pytest.fixture(autouse=True)
def _fresh_process_config():
    clear_config_cache()
    yield
    clear_config_cache()


def _own_config(retries: int, role: CVDRole) -> AppConfig:
    # ``AppConfig(...)`` keyword arguments are not a settings source, so an
    # app's own config is a copy of the loaded one with its values changed.
    return AppConfig().model_copy(
        update={
            "max_inbox_retry_attempts": retries,
            "actor": ActorConfig(default_case_roles=[role]),
        }
    )


def _with_config_probes(app: FastAPI) -> FastAPI:
    """Add one async and one sync route that report the config they read."""

    @app.get("/probe/async")
    async def _async_probe() -> dict[str, object]:
        return {
            "retries": get_config().max_inbox_retry_attempts,
            "roles": [str(r) for r in load_actor_config().default_case_roles],
        }

    @app.get("/probe/sync")
    def _sync_probe() -> dict[str, object]:
        # A sync endpoint runs in a worker thread; the scope must reach it.
        return {
            "retries": get_config().max_inbox_retry_attempts,
            "roles": [str(r) for r in load_actor_config().default_case_roles],
        }

    return app


def _app(config: AppConfig | None) -> FastAPI:
    return _with_config_probes(
        create_app(docs_url=None, openapi_url=None, config=config)
    )


@pytest.mark.parametrize("path", ["/probe/async", "/probe/sync"])
def test_two_apps_in_one_process_each_read_their_own_config(path: str) -> None:
    vendor = _own_config(3, CVDRole.VENDOR)
    finder = _own_config(8, CVDRole.REPORTER)

    with TestClient(_app(vendor)) as a, TestClient(_app(finder)) as b:
        # Interleaved, so neither app's answer is left over from the other.
        first_a = a.get(path).json()
        first_b = b.get(path).json()
        second_a = a.get(path).json()

    assert first_a == {"retries": 3, "roles": [str(CVDRole.VENDOR)]}
    assert second_a == first_a
    assert first_b == {"retries": 8, "roles": [str(CVDRole.REPORTER)]}


def test_app_with_no_config_reads_the_process_wide_config() -> None:
    process_wide = get_config()
    with TestClient(_app(None)) as client:
        body = client.get("/probe/async").json()
    assert body["retries"] == process_wide.max_inbox_retry_attempts


def test_app_with_no_config_beside_one_holding_its_own() -> None:
    """A config-less app keeps reading the process-wide config, refused not."""
    process_wide = get_config()
    own = _own_config(4, CVDRole.VENDOR)
    with TestClient(_app(own)) as held, TestClient(_app(None)) as plain:
        assert held.get("/probe/sync").json()["retries"] == 4
        assert (
            plain.get("/probe/sync").json()["retries"]
            == process_wide.max_inbox_retry_attempts
        )


def test_read_that_lost_its_scope_raises_while_the_app_runs() -> None:
    """AC-3: no fallback to the process-wide config while an app holds one."""
    own = _own_config(4, CVDRole.VENDOR)
    with TestClient(_app(own)):
        with pytest.raises(VultronWiringError, match="ADR-0206"):
            contextvars.Context().run(get_config)
    # The app has stopped, so the process-wide read is allowed again.
    assert contextvars.Context().run(get_config) is get_config()


def test_create_app_reads_its_mode_from_its_own_config() -> None:
    """The factory's own read uses the app's config, not the process one."""

    def _demo_trigger_paths(app: FastAPI) -> list[str]:
        return [p for p in app.openapi()["paths"] if "/demo/" in p]

    assert get_config().mode == RunMode.PROTOTYPE
    prod = AppConfig().model_copy(update={"mode": RunMode.PROD})

    assert _demo_trigger_paths(_app(None))
    assert not _demo_trigger_paths(_app(prod))
