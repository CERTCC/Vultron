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

"""Shared fixtures for TriggerActivityAdapter unit tests."""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)

#: The store's actor when a test module declares no ``STORE_OWNER``.
DEFAULT_STORE_OWNER = "https://test.example/api/v2/actors/test-actor"


@pytest.fixture
def store_owner(request: pytest.FixtureRequest) -> str:
    """The actor whose store ``dl`` is, and so the only actor it signs for.

    An outbox signs only its own actor's activities (SIG-05-004), so a test
    sends as the store's owner.  A module sets ``STORE_OWNER``; a test that
    sends as another actor overrides it with
    ``@pytest.mark.parametrize("store_owner", [actor_id])``.
    """
    return getattr(request.module, "STORE_OWNER", DEFAULT_STORE_OWNER)


@pytest.fixture
def dl(store_owner: str):
    """In-memory SQLite DataLayer for adapter tests, owned by *store_owner*."""
    _dl = SqliteDataLayer("sqlite:///:memory:", actor_id=store_owner)
    yield _dl
    _dl.clear_all()
    _dl.close()


@pytest.fixture
def adapter(dl):
    """TriggerActivityAdapter backed by the in-memory DataLayer."""
    return TriggerActivityAdapter(dl)
