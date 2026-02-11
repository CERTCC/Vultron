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

import pytest

from vultron.api.v2.data import utils, actor_io


@pytest.fixture(autouse=True)
def test_base_url(monkeypatch):
    """
    Provide a stable BASE_URL for tests; original tests used a fixture with
    this name so we keep the same name to avoid changing test signatures.
    """
    base_url = "https://test.vultron.local/"
    monkeypatch.setattr(utils, "BASE_URL", base_url)
    return base_url


# @pytest.fixture
# def ds():
#     """
#     DataStore fixture shared by tests in this directory.
#     """
#     ds_inst = tinydb
#     yield ds_inst
#     ds_inst.clear()
#


@pytest.fixture(autouse=True)
def clear_actor_io_store():
    """
    Ensure actor_io store is cleared before/after each test (original tests
    used an autouse fixture in test_actor_io.py).
    """
    actor_io.ACTOR_IO_STORE.clear()
    yield
    actor_io.ACTOR_IO_STORE.clear()
