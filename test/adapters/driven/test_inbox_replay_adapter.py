#!/usr/bin/env python

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

"""Tests for ``InboxReplayAdapter`` (SYNC-14-009, ADR-0135)."""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.inbox_replay_adapter import InboxReplayAdapter
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.ports.inbox_replay import InboxReplayPort
from vultron.errors import VultronWiringError

_RECEIVER = "https://example.org/actors/receiver"
_ANNOUNCE_ID = "https://example.org/activities/announce-3"


@pytest.fixture
def dl():
    db = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    yield db
    db.close()


def _hold(dl: SqliteDataLayer) -> None:
    dl.create(
        DeferredInboxActivity(
            activity_id=_ANNOUNCE_ID,
            received_body=f'{{"id": "{_ANNOUNCE_ID}", "type": "Announce"}}',
        )
    )


def test_adapter_satisfies_the_port(dl):
    port: InboxReplayPort = InboxReplayAdapter(dl)
    assert callable(port.replay_held)


@pytest.mark.spec("SYNC-14-009")
def test_queues_the_held_activity_by_its_own_id(dl):
    _hold(dl)

    InboxReplayAdapter(dl).replay_held(_ANNOUNCE_ID)

    assert dl.inbox_list() == [_ANNOUNCE_ID]
    # The body stays held for the replay to read (IO-03-004).
    assert isinstance(
        dl.read(DeferredInboxActivity.build_id(_ANNOUNCE_ID)),
        DeferredInboxActivity,
    )


@pytest.mark.spec("SYNC-14-009")
def test_an_id_already_queued_is_not_queued_twice(dl):
    _hold(dl)
    adapter = InboxReplayAdapter(dl)

    adapter.replay_held(_ANNOUNCE_ID)
    adapter.replay_held(_ANNOUNCE_ID)

    assert dl.inbox_list() == [_ANNOUNCE_ID]


@pytest.mark.spec("SYNC-14-009")
def test_an_activity_nothing_holds_is_a_wiring_error(dl):
    """A queued id with no held body would be dropped by the replay."""
    with pytest.raises(VultronWiringError, match="nothing holds"):
        InboxReplayAdapter(dl).replay_held(_ANNOUNCE_ID)

    assert dl.inbox_list() == []
