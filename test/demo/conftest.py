#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""Shared fixtures and helpers for demo tests."""

import pytest
from fastapi.testclient import TestClient

import vultron.demo.utils as demo_utils
from vultron.api.main import app as api_app
from test.demo._helpers import (
    make_testclient_call,
)  # noqa: F401 (re-exported for test modules)

# Eliminate wait delays in all demo tests. The FastAPI TestClient processes
# background tasks synchronously, so no sleep is needed between inbox posts
# and state checks.
demo_utils.DEFAULT_WAIT_SECONDS = 0.0


@pytest.fixture(scope="module")
def client():
    """Provides a shared TestClient instance for demo tests in this module."""
    return TestClient(api_app)
