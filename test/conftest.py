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

"""
Root pytest configuration file.

This file provides test session hooks for cleanup of test artifacts
and forces in-memory TinyDB storage to keep the test suite fast.
"""

from pathlib import Path

import pytest

from vultron.adapters.driven.datalayer_tinydb import (
    TinyDbDataLayer,
    reset_datalayer,
)


def pytest_configure(config: pytest.Config) -> None:
    """Force in-memory TinyDB storage for the entire test session.

    Patches ``TinyDbDataLayer.__init__`` so every instance created anywhere
    in the test process — regardless of how the class was imported — uses
    ``MemoryStorage`` instead of a disk-backed JSON file.

    Without this patch, the default ``db_path='mydb.json'`` causes TinyDB to
    re-read and re-write the entire JSON file on every read/write operation.
    As the file grows across hundreds of test cases the suite slows to >15
    minutes.  With in-memory storage each operation is effectively instant,
    keeping the full suite under ~1 minute.

    Patching ``__init__`` (rather than ``get_datalayer``) is the correct
    approach because ``get_datalayer`` is imported by name in several modules
    at import time; a module-attribute patch would not affect those already-
    bound references.  ``__init__`` is always looked up through the class
    object at construction time, so the patch applies universally.
    """
    _original_init = TinyDbDataLayer.__init__
    # Store for retrieval by integration tests that need real file-backed storage.
    TinyDbDataLayer._test_original_init = _original_init  # type: ignore[attr-defined]

    def _in_memory_init(
        self: TinyDbDataLayer,
        db_path: "str | None" = None,
        actor_id: "str | None" = None,
    ) -> None:
        # Always force db_path=None (MemoryStorage) regardless of what the
        # caller requested.
        _original_init(self, db_path=None, actor_id=actor_id)

    TinyDbDataLayer.__init__ = _in_memory_init  # type: ignore[method-assign]


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db_files():
    """Clean up any stale TinyDB files left from previous runs.

    With the ``pytest_configure`` patch above, no new ``mydb.json`` should be
    created during this session.  This fixture remains as a safety net: it
    deletes any pre-existing file before tests start and removes it again
    after the session ends, preventing state from leaking across separate
    test runs.
    """
    repo_root = Path(__file__).parent.parent
    test_db_file = repo_root / "mydb.json"

    # Close any lingering handles and delete leftover file before tests.
    reset_datalayer()
    if test_db_file.exists():
        test_db_file.unlink()

    yield

    # Close handles and delete any file that somehow got created.
    reset_datalayer()
    if test_db_file.exists():
        test_db_file.unlink()
