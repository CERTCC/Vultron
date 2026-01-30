#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Provides pytest fixtures for testing the FastAPI v2 application.
"""

import pytest
from fastapi.testclient import TestClient

from vultron.api.v2.app import app_v2 as app


@pytest.fixture
def client():
    app.dependency_overrides = {}
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def datalayer():
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    datalayer = get_datalayer()
    # Clear the datalayer before each test
    datalayer.clear_all()
    yield datalayer
    # Clear the datalayer after each test
    datalayer.clear_all()
