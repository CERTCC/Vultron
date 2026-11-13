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

"""Fixtures shared by this directory's SQLite store tests.

``dl`` here runs a test on both pool kinds (:mod:`test.support.pool_kind_stores`).
It replaces ``test/adapters/driven/conftest.py``'s in-memory ``dl`` for this
directory; a module that needs only that one defines its own ``dl``, as
``test_find_protocol_pair.py`` does.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from test.support.pool_kind_stores import POOL_KINDS, open_pool_kind_store
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer


@pytest.fixture(params=POOL_KINDS)
def dl(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[SqliteDataLayer]:
    """The pool-kind actor's store, once in memory and once file-backed."""
    store = open_pool_kind_store(request.param, tmp_path)
    try:
        yield store
    finally:
        store.close()
