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

"""One store per SQLite pool kind, for tests whose mechanics differ by pool.

An in-memory store shares one connection (``StaticPool``); a file-backed one
opens a connection per use (``NullPool``).  Transaction and read mechanics
differ between the two, so the tests that pin them run on both.  The
``memory_or_file_dl`` fixture in
``test/adapters/driven/datalayer_sqlite/conftest.py`` opens them through
:func:`open_pool_kind_store`.
"""

from pathlib import Path

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

POOL_KINDS = ("memory", "file")

POOL_KIND_ACTOR = "https://example.org/actors/tx-actor"


def open_pool_kind_store(kind: str, tmp_path: Path) -> SqliteDataLayer:
    """Open the pool-kind actor's store of pool *kind*, ``memory`` or ``file``."""
    url = (
        "sqlite:///:memory:"
        if kind == "memory"
        else f"sqlite:///{tmp_path / 'pool-kind.db'}"
    )
    return SqliteDataLayer(url, actor_id=POOL_KIND_ACTOR)


def example_note(name: str) -> as_Note:
    """A note whose id and content are both derived from *name*."""
    return make(as_Note, id_=f"https://example.org/notes/{name}", content=name)
