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
"""An answer to a forwarded ownership-transfer Offer follows its link (CM-21-018).

The CASE_MANAGER's forward to the transferee carries ``inReplyTo`` naming the
recorded Offer it forwards.  An Accept or Reject naming the forward resolves
to that Offer through the link and never by comparing times, so a late answer
to one Offer cannot close a newer Offer to the same transferee recorded in the
same second.  A forward with no link, or one linked to another transferee's
Offer, stands for no recorded Offer and its answer is refused.
"""

from collections.abc import Callable
from typing import Any

import pytest

from test.core.use_cases.received.actor.test_ownership import (
    _COORDINATOR_ID,
    _VENDOR_ID,
    # Aliased so pytest does not collect the class's tests here a second time.
    TestAcceptIsActedOnOnlyFromTheTransferee as _AcceptSenderTests,
    _accept,
    _event_types,
    _owner,
    _owner_roles,
    _ownership_offer_harness,
    _reject,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.participants.ownership_offer import open_ownership_offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service

_FINDER_ID = "https://example.org/users/finder"

_Answer = Callable[..., Any]


def _forward_harness(make_payload, case_id: str):
    """A CASE_MANAGER store whose trigger adapter mints real forwards."""
    dl, deliver, _ = _ownership_offer_harness(
        make_payload, case_id, forward=True
    )
    # In the CASE_MANAGER's address book, so the ledger snapshot can inline
    # the forward's bare-id target (CLP-07).
    dl.create(as_Service(id_=_COORDINATOR_ID, name="Coordinator"))
    return dl, deliver


def _forward_of(dl, offer_id: str):
    """The forward in the CASE_MANAGER's outbox that links to *offer_id*."""
    (forward,) = [
        item
        for item in (dl.read(i) for i in dl.outbox_list())
        if item is not None
        and getattr(getattr(item, "type_", None), "value", None) == "Offer"
        and getattr(item, "in_reply_to", None) == offer_id
    ]
    return forward


def _offer_entry(dl, offer_id: str) -> CaseLedgerEntry:
    (entry,) = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry) and obj.log_object_id == offer_id
    ]
    return entry


@pytest.mark.spec("CM-21-018")
@pytest.mark.spec("CM-21-014")
@pytest.mark.parametrize("late_answer", [_accept, _reject])
def test_late_answer_to_an_old_forward_does_not_close_a_same_second_offer(
    make_payload, late_answer: _Answer
):
    """Offer A is forwarded and declined; Offer B to the same transferee
    follows in the same second.  A second answer naming A's forward resolves
    to A, already closed, and B stays open (#4565)."""
    case_id = "https://example.org/cases/case_ot_link_race"
    dl, deliver = _forward_harness(make_payload, case_id)
    offer_a_id = "https://example.org/activities/offer_link_a"
    offer_b_id = "https://example.org/activities/offer_link_b"
    assert (
        deliver(_COORDINATOR_ID, offer_a_id)[0] is HandlerDisposition.APPLIED
    )
    forward_a = _forward_of(dl, offer_a_id)
    assert (
        _reject(dl, make_payload, forward_a).disposition
        is HandlerDisposition.APPLIED
    )
    assert (
        deliver(_COORDINATOR_ID, offer_b_id)[0] is HandlerDisposition.APPLIED
    )
    # Pin the race: A's forward published in the very second B was recorded,
    # the tie a time comparison resolves to B.
    dl.save(
        forward_a.model_copy(
            update={"published": _offer_entry(dl, offer_b_id).received_at}
        )
    )
    entries_before = _event_types(dl)
    outbox_before = dl.outbox_list()

    result = late_answer(dl, make_payload, forward_a)

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason is not None and "already closed" in result.reason
    assert _event_types(dl) == entries_before
    assert dl.outbox_list() == outbox_before
    still_open = open_ownership_offer(dl, case_id)
    assert still_open is not None and still_open.offer_id == offer_b_id
    assert _owner(dl, case_id) == _VENDOR_ID


@pytest.mark.spec("CM-21-018")
@pytest.mark.parametrize("answer", [_accept, _reject])
@pytest.mark.parametrize(
    ("transferee_id", "linked"),
    [
        pytest.param(_COORDINATOR_ID, False, id="no-in-reply-to"),
        pytest.param(_FINDER_ID, True, id="linked-to-another-transferee"),
    ],
)
def test_answer_to_an_unlinked_forward_is_refused(
    make_payload, answer: _Answer, transferee_id: str, linked: bool
):
    """No link, or a link to another transferee's Offer: a protocol error.

    The answer is refused with no ledger commit and no outbound activity;
    nothing falls back to matching the forward by time.
    """
    case_id = "https://example.org/cases/case_ot_link_missing"
    dl, deliver = _forward_harness(make_payload, case_id)
    dl.create(as_Service(id_=_FINDER_ID, name="Finder"))
    offer_id = "https://example.org/activities/offer_link_recorded"
    assert deliver(transferee_id, offer_id)[0] is HandlerDisposition.APPLIED
    forward = _AcceptSenderTests._plant_forged_forward(
        dl,
        case_id,
        _COORDINATOR_ID,
        "https://example.org/activities/forward_unlinked",
        offer_id if linked else None,
    )
    roles_before = _owner_roles(dl, case_id)
    entries_before = _event_types(dl)
    outbox_before = dl.outbox_list()

    result = answer(dl, make_payload, forward)

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason is not None and "never recorded" in result.reason
    assert _event_types(dl) == entries_before
    assert dl.outbox_list() == outbox_before
    assert _owner(dl, case_id) == _VENDOR_ID
    assert _owner_roles(dl, case_id) == roles_before
    still_open = open_ownership_offer(dl, case_id)
    assert still_open is not None and still_open.offer_id == offer_id
