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

"""Tests for get_datalayer() factory and VULTRON_DB_URL env var support."""

import os

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    get_datalayer,
    reset_datalayer,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure the datalayer singletons are cleared before and after each test."""
    reset_datalayer()
    yield
    reset_datalayer()


def test_get_datalayer_returns_sqlite_instance():
    dl = get_datalayer(db_url="sqlite:///:memory:")
    assert isinstance(dl, SqliteDataLayer)


def test_get_datalayer_in_memory_by_default():
    """Default db_url should use in-memory SQLite during tests."""
    dl = get_datalayer()
    assert dl.ping()


@pytest.mark.integration
def test_get_datalayer_file_backed_with_explicit_url(tmp_path):
    """Passing an explicit db_url must create a file-backed DataLayer."""
    db_file = str(tmp_path / "test.sqlite")
    db_url = f"sqlite:///{db_file}"
    dl = get_datalayer(db_url=db_url)
    assert dl.ping()


def test_get_datalayer_returns_singleton_for_same_actor_id():
    dl_a = get_datalayer(actor_id="actor1")
    dl_b = get_datalayer(actor_id="actor1")
    assert dl_a is dl_b


def test_get_datalayer_returns_different_instances_for_different_actors():
    dl_a = get_datalayer(actor_id="actor1")
    dl_b = get_datalayer(actor_id="actor2")
    assert dl_a is not dl_b


def test_default_db_url_uses_vultron_db_url_env_var(monkeypatch, tmp_path):
    """get_datalayer() must honour VULTRON_DB_URL when it is set."""
    db_file = str(tmp_path / "env_test.sqlite")
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("VULTRON_DB_URL", db_url)

    dl = get_datalayer()
    assert dl.ping()
    # The URL used should be the one from the env var — verify by checking
    # that the backing engine URL matches.
    assert db_url in str(dl._engine.url)


def test_default_db_url_falls_back_to_sqlite_mydb():
    """When VULTRON_DB_URL is not set, _DEFAULT_DB_URL falls back to sqlite:///mydb.sqlite."""
    import vultron.adapters.driven.datalayer_sqlite as mod

    if os.environ.get("VULTRON_DB_URL"):
        pytest.skip("VULTRON_DB_URL is set in the environment")
    assert mod._DEFAULT_DB_URL == "sqlite:///mydb.sqlite"
