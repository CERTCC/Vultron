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

"""Reading an activity as this actor holds it (CLP-10-017, DL-06-006)."""

import pytest

from test.support.received import archive_received
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.activity import VultronActivity
from vultron.core.services.received_activity import (
    read_held_activity,
    read_received_activity,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import rm_invite_to_case_activity

_ME = "https://example.org/actors/me"
_PEER = "https://example.org/actors/peer"
_CASE = "https://example.org/cases/held"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_ME)


def _invite(actor: str, invitee: str):
    return rm_invite_to_case_activity(
        invitee, target=_CASE, actor=actor, to=[invitee]
    )


@pytest.mark.spec("DL-06-006")
@pytest.mark.parametrize(
    "reader", [read_held_activity, read_received_activity]
)
def test_a_received_activity_is_read_from_its_archive(dl, reader) -> None:
    invite = _invite(_PEER, _ME)
    archive_received(dl, invite)
    assert dl.read(invite.id_) is None

    held = reader(dl, invite.id_)

    assert isinstance(held, VultronActivity)
    assert held.id_ == invite.id_


@pytest.mark.spec("DL-06-006")
def test_an_activity_this_actor_sent_is_read_under_its_own_id(dl) -> None:
    invite = _invite(_ME, _PEER)
    dl.create(invite)

    held = read_held_activity(dl, invite.id_)

    assert held.id_ == invite.id_


@pytest.mark.parametrize(
    "reader", [read_held_activity, read_received_activity]
)
def test_an_activity_this_store_does_not_hold_is_not_found(dl, reader) -> None:
    with pytest.raises(VultronNotFoundError, match="Invite"):
        reader(dl, "urn:uuid:never-held", "Invite")
