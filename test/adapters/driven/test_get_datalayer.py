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

"""Tests for get_datalayer() factory and env var config support."""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    get_datalayer,
    reset_datalayer,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure the datalayer singletons and config cache are reset each test."""
    import vultron.config.app as _cfg_module

    reset_datalayer()
    yield
    reset_datalayer()
    # Clear config cache without reloading — monkeypatch reverts env vars
    # AFTER this teardown, so calling reload_config() here would lock in
    # the test's env state rather than the session-level conftest defaults.
    _cfg_module._config_cache = None


def test_get_datalayer_returns_sqlite_instance():
    dl = get_datalayer(
        "https://test.example/api/v2/actors/test-actor",
        db_url="sqlite:///:memory:",
    )
    assert isinstance(dl, SqliteDataLayer)


def test_get_datalayer_in_memory_by_default():
    """Default db_url should use in-memory SQLite during tests."""
    dl = get_datalayer("https://test.example/api/v2/actors/test-actor")
    assert dl.ping()


@pytest.mark.integration
def test_get_datalayer_file_backed_with_explicit_url(tmp_path):
    """Passing an explicit db_url must create a file-backed DataLayer.

    The actor is mandatory (DL-07-002), and the configured URL is a *template*:
    the file this opens is derived from it per actor (DL-07-003), so the assertion
    below is that the derived path is under *this* URL rather than that it equals
    it.
    """
    from vultron.adapters.driven.datalayer_sqlite.engine import actor_db_url

    actor_id = "https://test.example/api/v2/actors/file-backed-actor"
    db_file = str(tmp_path / "test.sqlite")
    db_url = f"sqlite:///{db_file}"
    dl = get_datalayer(actor_id, db_url=db_url)
    assert dl.ping()
    assert str(dl._engine.url) == actor_db_url(db_url, actor_id)
    assert str(tmp_path) in str(dl._engine.url)


def test_get_datalayer_returns_singleton_for_same_actor_id():
    dl_a = get_datalayer(actor_id="actor1")
    dl_b = get_datalayer(actor_id="actor1")
    assert dl_a is dl_b


def test_get_datalayer_returns_different_instances_for_different_actors():
    dl_a = get_datalayer(actor_id="actor1")
    dl_b = get_datalayer(actor_id="actor2")
    assert dl_a is not dl_b


def test_default_db_url_uses_vultron_database_db_url_env_var(
    monkeypatch, tmp_path
):
    """get_datalayer() must honour VULTRON_DATABASE__DB_URL when it is set."""
    from vultron.config import reload_config

    db_file = str(tmp_path / "env_test.sqlite")
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("VULTRON_DATABASE__DB_URL", db_url)
    reload_config()

    actor_id = "https://test.example/api/v2/actors/test-actor"
    dl = get_datalayer(actor_id)
    assert dl.ping()
    # The configured URL is a *template*, not a location: under ADR-0066 each
    # actor gets its own file derived from it, so `env_test.sqlite` becomes
    # `env_test-test-actor.sqlite` and the raw value no longer appears verbatim.
    # Assert the derivation the adapter actually performs — comparing against a
    # hand-written expected name would just restate `actor_db_url`'s suffix rule
    # in the test, and that rule is not what this test is about.
    from vultron.adapters.driven.datalayer_sqlite.engine import actor_db_url

    assert str(dl._engine.url) == actor_db_url(db_url, actor_id)
    # ...and that the derivation started from the env var, not the default.
    assert str(tmp_path) in str(dl._engine.url)


def test_default_db_url_falls_back_to_config_default(monkeypatch):
    """When no DB URL env var is set, get_config().database.db_url falls back
    to the default 'sqlite:///vultron.db'."""
    from vultron.config import get_config, reload_config

    monkeypatch.delenv("VULTRON_DATABASE__DB_URL", raising=False)
    reload_config()

    db_url = get_config().database.db_url
    assert db_url == "sqlite:///vultron.db"
