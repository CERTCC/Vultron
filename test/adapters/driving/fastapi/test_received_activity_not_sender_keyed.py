#!/usr/bin/env python
"""
DL-06-006: a received activity is never held under its sender's id.

The receiver's type tables are where its own sent activities live, so a
received copy stored there under the sender's id is read as one of its own
(#4866).  Inbox ingress writes nothing to the receiver's store (#4871), so
each "did I send it" scan stays sound: every test here delivers, through the
real inbox, an activity the scan would match, and asserts it is not counted.
"""

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

from typing import Any

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIQueuePort,
)
from vultron.adapters.driving.fastapi.inbox_staging import (
    InlineObjectStaging,
)
from vultron.core.behaviors.case.nodes.proposal_retry_marker import (
    announced_case_id,
    case_is_announced,
)
from vultron.core.behaviors.case.stub_invite_lifetime import (
    recorded_stub_invites,
)
from vultron.core.behaviors.inbox import InboxOutcome, process_payload
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.services.case_replica_seeding import (
    find_case_create_sent_by,
)
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_SENDER_URI = "https://example.org/actors/mallory"
_RECEIVER_URI = "https://example.org/actors/case-actor"
_INVITEE_URI = "https://example.org/actors/vendor"
_CASE_ID = "https://example.org/cases/c1"
_PROPOSAL_ID = "https://example.org/activities/proposal-1"


@pytest.fixture
def receiver_dl():
    """The receiving actor's own store (ADR-0073)."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER_URI)
    yield dl
    dl.close()


def _create_case(actor: str, **kwargs: Any) -> as_Create:
    return as_Create(
        actor=actor,
        object_=as_VulnerabilityCase(id_=_CASE_ID, name="c1"),
        context=_CASE_ID,
        to=[_RECEIVER_URI],
        **kwargs,
    )


def _body(activity: as_Activity) -> dict[str, Any]:
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


def _deliver(dl: SqliteDataLayer, activity: as_Activity) -> InboxOutcome:
    """Deliver *activity* through the real inbox, as a sender would.

    Production wiring throughout (IBP-04-002): parse, staged rebuild,
    extraction, deferral and dispatch to the real use case.
    """
    staging = InlineObjectStaging(dl)
    return process_payload(
        _body(activity),
        FastAPIIngressAdapter(dl=dl, staging=staging),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_RECEIVER_URI, dispatcher=make_dispatcher()
        ),
        FastAPIQueuePort(
            dl=dl, actor_dl=dl, actor_id=_RECEIVER_URI, staging=staging
        ),
    )


def _assert_not_under_its_id(dl: SqliteDataLayer, activity_id: str) -> None:
    assert dl.read(activity_id) is None, (
        f"{activity_id!r} is held under the id its sender chose (DL-06-006)"
    )


@pytest.mark.spec("DL-06-006")
def test_the_receivers_own_create_is_an_announcement(receiver_dl):
    """Control: the scans do count what the receiver itself stored."""
    receiver_dl.create(_create_case(_RECEIVER_URI))
    assert case_is_announced(receiver_dl, _CASE_ID) is True


@pytest.mark.spec("DL-06-006", "IO-03-004")
def test_ingress_holds_nothing_under_the_senders_id(receiver_dl):
    """AC-1: parsing and rebuilding a delivery writes nothing at all."""
    activity = _create_case(_SENDER_URI)
    ingress = FastAPIIngressAdapter(receiver_dl)

    parsed = ingress.parse(_body(activity))
    assert parsed is not None
    ingress.rehydrate(parsed)

    _assert_not_under_its_id(receiver_dl, activity.id_)
    assert sum(receiver_dl.count_all().values()) == 0


@pytest.mark.spec("DL-06-006")
def test_ingress_of_a_parsed_activity_holds_nothing_either(receiver_dl):
    """The route hands ingress a parsed activity; that path writes nothing."""
    ingress = FastAPIIngressAdapter(receiver_dl)
    parsed = ingress.parse(_create_case(_SENDER_URI))
    assert parsed is not None
    ingress.rehydrate(parsed)

    assert sum(receiver_dl.count_all().values()) == 0


@pytest.mark.spec("DL-06-006")
def test_a_received_create_naming_the_case_is_not_an_announcement(
    receiver_dl,
):
    """``case_is_announced`` scans Creates whose ``context`` names the case."""
    activity = _create_case(_SENDER_URI)

    _deliver(receiver_dl, activity)

    _assert_not_under_its_id(receiver_dl, activity.id_)
    assert case_is_announced(receiver_dl, _CASE_ID) is False


@pytest.mark.spec("DL-06-006")
def test_a_received_create_under_the_proposal_derived_id_is_not_one_sent(
    receiver_dl,
):
    """``announced_case_id`` reads the Create under the proposal's derived id.

    A sender that names its Create after the id the receiver derives from a
    proposal would otherwise read as the receiver's own announcement, or as
    a squatter that refuses the real one.
    """
    create_id = PendingCreateCaseActivity.create_activity_id(_PROPOSAL_ID)
    activity = _create_case(_SENDER_URI, id_=create_id)

    _deliver(receiver_dl, activity)

    _assert_not_under_its_id(receiver_dl, create_id)
    assert announced_case_id(receiver_dl, _PROPOSAL_ID) is None


@pytest.mark.spec("DL-06-006")
def test_a_received_create_whose_actor_names_the_receiver_is_not_one_sent(
    receiver_dl,
):
    """``find_case_create_sent_by`` matches on the unsigned ``actor`` (#2841)."""
    activity = _create_case(_RECEIVER_URI)

    _deliver(receiver_dl, activity)

    _assert_not_under_its_id(receiver_dl, activity.id_)
    assert (
        find_case_create_sent_by(receiver_dl, _RECEIVER_URI, _CASE_ID) is None
    )


@pytest.mark.spec("DL-06-006", "CM-11-017")
def test_a_received_stub_invite_whose_actor_names_the_receiver_is_not_one_sent(
    receiver_dl,
):
    """``recorded_stub_invites`` matches on the unsigned ``actor`` (#2841).

    A copy counted here would let its invitee be admitted as if this
    CASE_MANAGER had invited it.
    """
    activity = rm_invite_to_case_activity(
        _INVITEE_URI,
        target=as_VulnerabilityCase(
            id_=_CASE_ID, stub_summary="A vul in a widget"
        ),
        actor=_RECEIVER_URI,
        to=[_RECEIVER_URI],
    )

    _deliver(receiver_dl, activity)

    _assert_not_under_its_id(receiver_dl, activity.id_)
    assert recorded_stub_invites(receiver_dl, _CASE_ID, _RECEIVER_URI) == []


@pytest.mark.spec("DL-06-006", "CLP-10-017")
def test_a_delivered_activity_is_held_only_as_received(receiver_dl):
    """What a delivery that reaches its use case leaves: the archive alone."""
    activity = _create_case(_SENDER_URI)

    _deliver(receiver_dl, activity)

    _assert_not_under_its_id(receiver_dl, activity.id_)
    assert isinstance(
        receiver_dl.read(ReceivedActivityRecord.build_id(activity.id_)),
        ReceivedActivityRecord,
    )
