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

"""Tests for get_datalayer() factory and VULTRON_DB_PATH env var support."""

import importlib
import os

import pytest
from tinydb.storages import MemoryStorage

from vultron.adapters.driven.datalayer_tinydb import (
    TinyDbDataLayer,
    get_datalayer,
    reset_datalayer,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure the datalayer singletons are cleared before and after each test."""
    reset_datalayer()
    yield
    reset_datalayer()


def test_get_datalayer_returns_tinydb_instance():
    dl = get_datalayer(db_path=None)
    assert isinstance(dl, TinyDbDataLayer)


def test_get_datalayer_in_memory_when_db_path_none():
    """Passing db_path=None explicitly must use in-memory storage."""
    dl = get_datalayer(db_path=None)
    assert dl._db_path is None
    assert isinstance(dl._db.storage, MemoryStorage)


def test_get_datalayer_file_backed_with_explicit_path(tmp_path):
    """Passing an explicit db_path must create a file-backed DataLayer."""
    db_file = str(tmp_path / "test.json")
    dl = get_datalayer(db_path=db_file)
    assert dl._db_path == db_file


def test_get_datalayer_returns_singleton_for_same_actor_id():
    dl_a = get_datalayer(actor_id="actor1", db_path=None)
    dl_b = get_datalayer(actor_id="actor1", db_path=None)
    assert dl_a is dl_b


def test_get_datalayer_returns_different_instances_for_different_actors():
    dl_a = get_datalayer(actor_id="actor1", db_path=None)
    dl_b = get_datalayer(actor_id="actor2", db_path=None)
    assert dl_a is not dl_b


def test_default_db_path_uses_vultron_db_path_env_var(monkeypatch, tmp_path):
    """_DEFAULT_DB_PATH must read VULTRON_DB_PATH when set at module import time."""
    import vultron.adapters.driven.datalayer_tinydb as mod

    db_file = str(tmp_path / "env_test.json")
    monkeypatch.setenv("VULTRON_DB_PATH", db_file)

    # Reload the module with the patched env var to verify module-level
    # constant picks it up at import time.
    importlib.reload(mod)
    assert mod._DEFAULT_DB_PATH == db_file

    # Restore module state: reload again now that monkeypatch will clean up.
    monkeypatch.delenv("VULTRON_DB_PATH", raising=False)
    importlib.reload(mod)


def test_default_db_path_falls_back_to_mydb_json():
    """When VULTRON_DB_PATH is not set, _DEFAULT_DB_PATH must fall back to mydb.json."""
    import vultron.adapters.driven.datalayer_tinydb as mod

    if os.environ.get("VULTRON_DB_PATH"):
        pytest.skip("VULTRON_DB_PATH is set in the environment")
    assert mod._DEFAULT_DB_PATH == "mydb.json"
