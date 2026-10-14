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

"""Store-scan finders find what ingress stores, through the filtered route.

The demo's finders read only the stored types their object can be held as
(#4600).  Ingress stores every inbound activity bare, under its own ``type``
(``_store_inbox_activity``), and intake may add a ``ReceivedActivityRecord``
beside it.  These tests store an activity the way ingress does and serve the
finder's reads through the real route function, so a type list that misses
the stored form fails here instead of timing out in a Docker demo.
"""

from typing import Any
from unittest.mock import MagicMock

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_storage import (
    _store_inbox_activity,
)
from vultron.adapters.driving.fastapi.routers.datalayer import (
    get_datalayer_contents,
    get_objects,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.demo.helpers.polling import (
    find_full_case_invite_for_actor,
    find_ownership_transfer_offer_for_actor,
)
from vultron.wire.as2.factories import rm_invite_to_full_case_activity
from vultron.wire.as2.factories.case import (
    offer_case_ownership_transfer_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "http://example.com/cases/case-1"
INVITEE = "http://example.com/actors/vendor2"
MANAGER = "http://example.com/actors/case-actor"


def _route_client(dl: SqliteDataLayer) -> MagicMock:
    """A client whose reads are served by the real DataLayer route functions."""
    client = MagicMock()
    client.base_url = "http://vendor2:7999"
    client.dl_path.side_effect = lambda key="": f"/datalayer/{key}"

    def _get(path: str, params: dict[str, Any] | None = None) -> Any:
        key = path.removeprefix("/datalayer/")
        if key == "":
            types = (params or {}).get("type")
            return get_datalayer_contents(datalayer=dl, types=types)
        return get_objects(key.removesuffix("s/"), datalayer=dl)

    client.get.side_effect = _get
    return client


def test_finds_a_full_case_invite_stored_bare_by_ingress():
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE)
    invite = rm_invite_to_full_case_activity(
        INVITEE,
        CASE_ID,
        LedgerPosition(log_index=3, entry_hash="ab" * 32),
        actor=MANAGER,
        id_="http://example.com/activities/full-invite-1",
    )
    assert _store_inbox_activity(dl, invite)

    found = find_full_case_invite_for_actor(
        _route_client(dl),
        CASE_ID,
        INVITEE,
        timeout_seconds=0.05,
        poll_interval=0.01,
    )

    assert found == invite.id_


def test_finds_an_ownership_transfer_offer_stored_bare_by_ingress():
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE)
    offer = offer_case_ownership_transfer_activity(
        as_VulnerabilityCase(id_=CASE_ID, attributed_to=MANAGER),
        target=INVITEE,
        actor=MANAGER,
        id_="http://example.com/activities/forwarded-offer-1",
    )
    assert _store_inbox_activity(dl, offer)

    found = find_ownership_transfer_offer_for_actor(
        _route_client(dl),
        CASE_ID,
        INVITEE,
        timeout_seconds=0.05,
        poll_interval=0.01,
    )

    assert found == offer.id_
