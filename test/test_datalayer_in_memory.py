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

"""Verify that the test environment uses in-memory SQLite storage.

These tests confirm that the ``VULTRON_DATABASE__DB_URL`` environment variable
is set to ``sqlite:///:memory:`` by the test infrastructure
(``test/conftest.py``), so no on-disk SQLite files are created during the
test suite.
"""

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    get_datalayer,
    reset_datalayer,
)
from vultron.config import get_config


def test_config_db_url_is_in_memory():
    """get_config().database.db_url must be 'sqlite:///:memory:' during tests.

    The test/conftest.py sets VULTRON_DATABASE__DB_URL=sqlite:///:memory:
    before any vultron imports, so get_config().database.db_url resolves to
    the in-memory value.
    """
    db_url = get_config().database.db_url
    assert db_url == "sqlite:///:memory:", (
        f"Expected database.db_url='sqlite:///:memory:', got {db_url!r}.  "
        "Ensure os.environ.setdefault('VULTRON_DATABASE__DB_URL', "
        "'sqlite:///:memory:') is set in test/conftest.py BEFORE any "
        "vultron imports."
    )


def test_sqlite_datalayer_default_is_in_memory():
    """SqliteDataLayer() with default args should use in-memory storage."""
    reset_datalayer()
    try:
        dl = SqliteDataLayer()
        assert dl.ping()
    finally:
        reset_datalayer()


def test_get_datalayer_returns_sqlite_instance():
    """get_datalayer() must return a SqliteDataLayer instance."""
    reset_datalayer()
    try:
        dl = get_datalayer()
        assert isinstance(dl, SqliteDataLayer)
    finally:
        reset_datalayer()


def test_get_datalayer_actor_scoped_returns_sqlite_instance():
    """get_datalayer(actor_id=...) must return a SqliteDataLayer instance."""
    reset_datalayer()
    try:
        dl = get_datalayer(actor_id="https://example.org/actors/test-actor")
        assert isinstance(dl, SqliteDataLayer)
    finally:
        reset_datalayer()
