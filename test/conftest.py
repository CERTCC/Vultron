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

Forces SQLite in-memory storage for the entire test session so that no
on-disk database files are created and the test suite stays fast.
"""

import os

# Set VULTRON_DB_URL BEFORE any vultron module imports so that _DEFAULT_DB_URL
# in datalayer_sqlite.py picks up the in-memory value at import time.
os.environ.setdefault("VULTRON_DB_URL", "sqlite:///:memory:")

import pytest  # noqa: E402
from vultron.adapters.driven.datalayer_sqlite import (  # noqa: E402
    reset_datalayer,
)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_datalayer():
    """Reset all cached DataLayer instances before and after the session.

    Ensures no stale in-memory database state leaks between test modules.
    """
    reset_datalayer()
    yield
    reset_datalayer()
