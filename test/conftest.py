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

This file provides test session hooks for cleanup of test artifacts.
"""

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db_files():
    """
    Automatically clean up any TinyDB files created during tests.

    This fixture runs once per test session and removes mydb.json
    both before and after the test run to prevent test pollution.
    """
    # Get repository root
    repo_root = Path(__file__).parent.parent
    test_db_file = repo_root / "mydb.json"

    # Clean up before tests
    if test_db_file.exists():
        test_db_file.unlink()

    yield

    # Clean up after tests
    if test_db_file.exists():
        test_db_file.unlink()
