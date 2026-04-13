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

"""Verify that the test environment forces in-memory TinyDB storage.

These tests confirm that the test-suite infrastructure (via pytest_configure in
test/conftest.py) correctly patches TinyDbDataLayer to use MemoryStorage rather
than a disk-backed JSON file.  Disk-backed storage in tests causes the test
suite to slow to >15 minutes as mydb.json grows across hundreds of test cases.

If these tests fail, TinyDbDataLayer.__init__ is not being patched and the test
suite will be slow.
"""

from vultron.adapters.driven.datalayer_tinydb import (
    TinyDbDataLayer,
    get_datalayer,
    reset_datalayer,
)


def test_tinydb_datalayer_init_uses_memory_storage():
    """TinyDbDataLayer() with no args should use MemoryStorage during tests.

    Before the fix, this creates a file-backed instance (db_path='mydb.json').
    After the fix, the patch in pytest_configure forces db_path=None (in-memory).
    """
    reset_datalayer()
    try:
        dl = TinyDbDataLayer()
        assert dl._db_path is None, (
            f"Expected in-memory storage (db_path=None), "
            f"but got db_path={dl._db_path!r}.  "
            "TinyDbDataLayer is using disk-backed storage during tests, "
            "which causes the test suite to run slowly.  "
            "See test/conftest.py:pytest_configure for the fix."
        )
    finally:
        reset_datalayer()


def test_get_datalayer_returns_in_memory_instance():
    """get_datalayer() should return an in-memory instance during tests."""
    reset_datalayer()
    try:
        dl = get_datalayer()
        assert dl._db_path is None, (
            f"Expected in-memory storage (db_path=None), "
            f"but got db_path={dl._db_path!r}.  "
            "get_datalayer() is returning a disk-backed instance."
        )
    finally:
        reset_datalayer()


def test_get_datalayer_actor_scoped_uses_memory_storage():
    """get_datalayer(actor_id=...) should also return an in-memory instance."""
    reset_datalayer()
    try:
        dl = get_datalayer(actor_id="https://example.org/actors/test-actor")
        assert dl._db_path is None, (
            f"Expected in-memory storage (db_path=None), "
            f"but got db_path={dl._db_path!r}.  "
            "Actor-scoped get_datalayer() is returning a disk-backed instance."
        )
    finally:
        reset_datalayer()
