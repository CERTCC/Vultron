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
"""``SyncActivityAdapter.resend_sealed_activity`` requeues a sealed body.

SYNC-20-003: a resent Invite is the activity as first sent, from the body
sealed at emission, under its first id; nothing is resent without one.
SYNC-20-004: an id still pending in the outbox is not queued twice.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.outbox_sealed_body import (
    SealedOutboundBody,
    read_sealed_body,
    sealed_body_id,
)
from vultron.core.ports.sync_activity import ResendOutcome

OWNER = "https://example.org/actors/owner"
INVITE = "https://example.org/activities/invite-1"
BODY = '{"id": "https://example.org/activities/invite-1", "type": "Invite"}'


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)


def _seal(dl: SqliteDataLayer) -> None:
    dl.save(
        SealedOutboundBody(
            id_=sealed_body_id(INVITE), activity_id=INVITE, body=BODY
        )
    )


@pytest.mark.spec("SYNC-20-003")
def test_an_id_with_no_sealed_body_is_not_resent(dl, caplog) -> None:
    with caplog.at_level("WARNING"):
        outcome = SyncActivityAdapter(dl).resend_sealed_activity(INVITE)

    assert outcome is ResendOutcome.NOT_SEALED
    assert dl.outbox_list() == []
    assert "no sealed body" in caplog.text


@pytest.mark.spec("SYNC-20-004", "OX-06-002")
def test_an_id_still_pending_is_not_queued_twice(dl) -> None:
    _seal(dl)
    dl.outbox_append(INVITE)

    outcome = SyncActivityAdapter(dl).resend_sealed_activity(INVITE)

    assert outcome is ResendOutcome.PENDING
    assert dl.outbox_list() == [INVITE]


@pytest.mark.spec("SYNC-20-003")
def test_a_delivered_id_is_queued_again_with_its_first_body(dl) -> None:
    _seal(dl)
    dl.outbox_append(INVITE)
    assert dl.outbox_pop() == INVITE

    outcome = SyncActivityAdapter(dl).resend_sealed_activity(INVITE)

    assert outcome is ResendOutcome.QUEUED
    assert dl.outbox_list() == [INVITE]
    sealed = read_sealed_body(dl, INVITE)
    assert sealed is not None and sealed.body == BODY
