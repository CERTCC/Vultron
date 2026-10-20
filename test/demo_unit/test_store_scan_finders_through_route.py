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

"""Received-activity reads find what intake archives, through the real route.

The demo reads a received activity only from the receiver's
``ReceivedActivityRecord``, kept under a key the receiver derives from the
activity's id (CLP-10-017, ADR-0111): a receiver holds no received activity
under the sender's id (DL-06-006), and inbox ingress writes no such row
(#4871).  These tests archive an activity the way intake does, with and
without a row of the activity's type under the sender's id beside it (the row
ingress used to write), and serve every read through the real route function,
so a read that would count such a row fails here instead of in a Docker demo.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from test.support.received import archive_received
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.routers.datalayer import (
    get_datalayer_contents,
    get_objects,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.demo.helpers import workflow
from vultron.demo.helpers.polling import (
    assert_received_from,
    find_case_invite_for_actor,
    find_full_case_invite_for_actor,
    find_ownership_transfer_offer_for_actor,
    wait_for_received_activity,
)
from vultron.demo.helpers.verification import verify_activity_in_inbox
from vultron.demo.utils import (
    get_offer_from_datalayer,
    read_received_activities,
    read_received_activity,
    verify_received_activity_stored,
)
from vultron.wire.as2.factories import (
    rm_invite_to_case_activity,
    rm_invite_to_full_case_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.factories.case import (
    offer_case_ownership_transfer_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

CASE_ID = "http://example.com/cases/case-1"
INVITEE = "http://example.com/actors/vendor2"
MANAGER = "http://example.com/actors/case-actor"
FINDER = "http://example.com/actors/finder"
REPORT_ID = "http://example.com/reports/report-1"

#: Whether a row under the sender's id sits beside intake's record.
WITH_AND_WITHOUT_INGRESS_ROW = pytest.mark.parametrize(
    "ingress_row", [True, False], ids=["with-ingress-row", "record-only"]
)


def _route_client(dl: SqliteDataLayer) -> MagicMock:
    """A client whose reads are served by the real DataLayer route functions."""
    client = MagicMock()
    client.base_url = "http://vendor2:7999"
    client.actor_id = INVITEE
    client.dl_path.side_effect = lambda key="", actor_id=None: (
        f"/datalayer/{key}"
    )

    def _get(path: str, params: dict[str, Any] | None = None) -> Any:
        key = path.removeprefix("/datalayer/")
        if key == "":
            types = (params or {}).get("type")
            return get_datalayer_contents(datalayer=dl, types=types)
        return get_objects(key.removesuffix("s/"), datalayer=dl)

    client.get.side_effect = _get
    return client


def _row_under_senders_id(dl: SqliteDataLayer, activity: Any) -> None:
    """Write *activity* under its sender's id, as inbox ingress once did."""
    dl.create(object_to_record(activity))


def _receive(activity: Any, *, ingress_row: bool) -> SqliteDataLayer:
    """The invitee's store after receiving *activity*.

    Intake's record is always written; *ingress_row* adds a row under the
    sender's id beside it.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE)
    if ingress_row:
        _row_under_senders_id(dl, activity)
    archive_received(dl, activity)
    return dl


def _ingress_only(activity: Any) -> SqliteDataLayer:
    """The invitee's store holding *activity* only under the sender's id."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE)
    _row_under_senders_id(dl, activity)
    return dl


def _full_case_invite():
    return rm_invite_to_full_case_activity(
        INVITEE,
        CASE_ID,
        LedgerPosition(log_index=3, entry_hash="ab" * 32),
        actor=MANAGER,
        id_="http://example.com/activities/full-invite-1",
    )


def _ownership_offer():
    return offer_case_ownership_transfer_activity(
        as_VulnerabilityCase(id_=CASE_ID, attributed_to=MANAGER),
        target=INVITEE,
        actor=MANAGER,
        id_="http://example.com/activities/forwarded-offer-1",
    )


def _stub_invite():
    return rm_invite_to_case_activity(
        as_Service(id_=INVITEE),
        target=as_VulnerabilityCase(
            id_=CASE_ID, stub_summary="Security issue for test invite"
        ),
        actor=MANAGER,
        id_="http://example.com/activities/stub-invite-1",
    )


def _report_offer():
    return rm_submit_report_activity(
        as_VulnerabilityReport(id_=REPORT_ID, name="r", content="c"),
        to=INVITEE,
        actor=FINDER,
        id_="urn:uuid:2b6f6d5e-1c8a-4c39-9d43-6a7c4c1b0f11",
    )


_QUICK = {"timeout_seconds": 0.05, "poll_interval": 0.01}


# ---------------------------------------------------------------------------
# Finders: the archive record only (DL-06-006)
# ---------------------------------------------------------------------------


@WITH_AND_WITHOUT_INGRESS_ROW
def test_finds_a_full_case_invite_from_its_archive_record(ingress_row):
    invite = _full_case_invite()
    client = _route_client(_receive(invite, ingress_row=ingress_row))

    found = find_full_case_invite_for_actor(client, CASE_ID, INVITEE, **_QUICK)

    assert found == invite.id_


@WITH_AND_WITHOUT_INGRESS_ROW
def test_finds_an_ownership_transfer_offer_from_its_archive_record(
    ingress_row,
):
    offer = _ownership_offer()
    client = _route_client(_receive(offer, ingress_row=ingress_row))

    found = find_ownership_transfer_offer_for_actor(
        client, CASE_ID, INVITEE, **_QUICK
    )

    assert found == offer.id_


@pytest.mark.spec("DL-06-006")
@pytest.mark.parametrize(
    ("make", "find"),
    [
        pytest.param(
            _full_case_invite,
            lambda c: find_full_case_invite_for_actor(
                c, CASE_ID, INVITEE, **_QUICK
            ),
            id="full-case-invite",
        ),
        pytest.param(
            _ownership_offer,
            lambda c: find_ownership_transfer_offer_for_actor(
                c, CASE_ID, INVITEE, **_QUICK
            ),
            id="ownership-transfer-offer",
        ),
    ],
)
def test_a_row_under_the_senders_id_alone_is_not_found(make, find):
    client = _route_client(_ingress_only(make()))

    with pytest.raises(AssertionError, match="Timed out"):
        find(client)


@pytest.mark.spec("DL-06-006")
def test_a_stub_invite_under_the_senders_id_alone_is_not_found():
    """Intake archives a stub Invite on arrival (PCR-06-005), so a row under
    the sender's id is never read as the Invite received (#4870 AC-1)."""
    invite = _stub_invite()
    client = _route_client(_ingress_only(invite))

    with pytest.raises(AssertionError, match="Timed out"):
        find_case_invite_for_actor(client, CASE_ID, INVITEE, **_QUICK)
    with pytest.raises(AssertionError):
        assert_received_from(client, invite.id_, MANAGER, "consequence")


@WITH_AND_WITHOUT_INGRESS_ROW
def test_a_stub_invite_is_found_from_its_archive_record(ingress_row):
    invite = _stub_invite()
    client = _route_client(_receive(invite, ingress_row=ingress_row))

    assert find_case_invite_for_actor(client, CASE_ID, INVITEE, **_QUICK) == (
        invite.id_
    )


# ---------------------------------------------------------------------------
# Reads by id: the archive record only (DL-06-006)
# ---------------------------------------------------------------------------


@WITH_AND_WITHOUT_INGRESS_ROW
def test_read_received_activity_reads_the_archive_record(ingress_row):
    offer = _report_offer()
    client = _route_client(_receive(offer, ingress_row=ingress_row))

    activity = read_received_activity(client, offer.id_)

    assert activity is not None
    assert activity["id"] == offer.id_
    assert activity["type"] == "Offer"


@pytest.mark.spec("DL-06-006")
def test_read_received_activity_ignores_a_row_under_the_senders_id():
    offer = _report_offer()
    client = _route_client(_ingress_only(offer))

    assert read_received_activity(client, offer.id_) is None
    with pytest.raises(AssertionError, match="holds no received activity"):
        verify_received_activity_stored(client, offer.id_)
    with pytest.raises(AssertionError, match="holds no received activity"):
        assert_received_from(client, offer.id_, FINDER, "consequence")
    with pytest.raises(AssertionError, match="holds no received Offer"):
        get_offer_from_datalayer(client, INVITEE, offer.id_)
    assert not verify_activity_in_inbox(client, INVITEE, offer.id_)
    with pytest.raises(AssertionError, match="to archive received activity"):
        wait_for_received_activity(
            client, offer.id_, timeout_seconds=0.05, poll_interval=0.01
        )


@WITH_AND_WITHOUT_INGRESS_ROW
def test_get_offer_from_datalayer_reads_the_received_offer(ingress_row):
    offer = _report_offer()
    client = _route_client(_receive(offer, ingress_row=ingress_row))

    got = get_offer_from_datalayer(client, INVITEE, offer.id_)

    assert got.id_ == offer.id_
    assert got.actor == FINDER


@WITH_AND_WITHOUT_INGRESS_ROW
def test_receipt_checks_read_the_archive_record(ingress_row):
    offer = _report_offer()
    client = _route_client(_receive(offer, ingress_row=ingress_row))

    assert verify_received_activity_stored(client, offer.id_)["id"] == (
        offer.id_
    )
    assert verify_activity_in_inbox(client, INVITEE, offer.id_)
    wait_for_received_activity(
        client, offer.id_, timeout_seconds=0.05, poll_interval=0.01
    )
    assert_received_from(client, offer.id_, FINDER, "consequence")


@WITH_AND_WITHOUT_INGRESS_ROW
def test_find_case_for_offer_reads_the_report_from_the_received_offer(
    ingress_row,
):
    offer = _report_offer()
    client = _route_client(_receive(offer, ingress_row=ingress_row))
    case = as_VulnerabilityCase(id_=CASE_ID)

    with patch.object(
        workflow, "find_case_by_report_id", return_value=case
    ) as by_report:
        assert workflow.find_case_for_offer(client, offer.id_) is case

    by_report.assert_called_once_with(client, REPORT_ID)


def test_find_case_for_offer_finds_nothing_from_a_row_under_the_senders_id():
    offer = _report_offer()
    client = _route_client(_ingress_only(offer))

    with patch.object(workflow, "find_case_by_report_id") as by_report:
        assert workflow.find_case_for_offer(client, offer.id_) is None

    by_report.assert_not_called()


@WITH_AND_WITHOUT_INGRESS_ROW
def test_read_received_activities_lists_one_type_from_the_records(ingress_row):
    offer, invite = _report_offer(), _stub_invite()
    dl = _receive(offer, ingress_row=ingress_row)
    if ingress_row:
        _row_under_senders_id(dl, invite)
    archive_received(dl, invite)
    client = _route_client(dl)

    assert [a["id"] for a in read_received_activities(client, "Offer")] == [
        offer.id_
    ]
    assert [a["id"] for a in read_received_activities(client, "Invite")] == [
        invite.id_
    ]
    assert read_received_activities(client, "Accept") == []


def test_read_received_activities_ignores_rows_under_the_senders_id():
    client = _route_client(_ingress_only(_report_offer()))

    assert read_received_activities(client, "Offer") == []
