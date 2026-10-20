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

"""Tests for vultron.core.participants.ownership_offer (CM-21-011)."""

from datetime import UTC, datetime, timedelta

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.participants.ownership_offer import (
    offer_made_from_proposal,
    open_ownership_offer,
    ownership_offer_id,
    recorded_ownership_offer,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import offer_case_ownership_transfer_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_MANAGER = "https://example.org/actors/case-manager"
_TRANSFEREE = "https://example.org/actors/transferee"
_CASE_ID = "https://example.org/cases/ownership-offer"
_T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def dl() -> SqliteDataLayer:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
    store.create(as_VulnerabilityCase(id_=_CASE_ID, name="Ownership offer"))
    return store


def _ledger(
    dl: SqliteDataLayer,
    index: int,
    object_id: str,
    semantic_type: str,
    at: datetime,
    target: str | None = _TRANSFEREE,
    **snapshot_extra: str,
) -> None:
    """Seed one ledger entry directly; only the fields read here matter."""
    snapshot = {"id": object_id, **snapshot_extra}
    if target is not None:
        snapshot["target"] = target
    dl.save(
        CaseLedgerEntry(
            case_id=_CASE_ID,
            log_index=index,
            log_object_id=object_id,
            semantic_type=semantic_type,
            payload_snapshot=snapshot,
            prev_log_hash="",
            entry_hash="",
            received_at=at,
        )
    )


def _planted(
    dl: SqliteDataLayer, offer_id: str, at: datetime, in_reply_to: str
):
    """Store an Offer the CASE_MANAGER never made, linked to a recorded one."""
    case = dl.read_case(_CASE_ID)
    assert case is not None
    offer = offer_case_ownership_transfer_activity(
        case,
        target=_TRANSFEREE,
        actor=_MANAGER,
        id_=offer_id,
        published=at,
        in_reply_to=in_reply_to,
    )
    dl.create(offer)
    return offer


def test_ledgered_offer_is_found_open(dl):
    _ledger(dl, 0, "urn:offer:1", "offer_case_ownership_transfer", _T0)

    offer = recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")

    assert offer.offer_id == "urn:offer:1"
    assert offer.transferee_id == _TRANSFEREE
    assert offer.pair.is_pending()
    assert not offer.is_answered_other_than("urn:accept:any")


def test_answered_offer_counts_its_own_answer_as_a_redelivery(dl):
    _ledger(dl, 0, "urn:offer:1", "offer_case_ownership_transfer", _T0)
    _ledger(dl, 1, "urn:accept:1", "accept_case_ownership_transfer", _T0)

    offer = recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")

    assert offer.is_answered_other_than("urn:accept:2")
    assert not offer.is_answered_other_than("urn:accept:1")


def test_offer_never_ledgered_is_not_found(dl):
    with pytest.raises(VultronNotFoundError):
        recorded_ownership_offer(dl, _CASE_ID, "urn:offer:none")


def test_ledgered_offer_naming_no_transferee_is_not_found(dl):
    _ledger(dl, 0, "urn:offer:1", "offer_case_ownership_transfer", _T0, None)

    with pytest.raises(VultronNotFoundError):
        recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")


@pytest.mark.spec("CM-21-011")
def test_an_offer_linked_to_the_recorded_one_stands_for_nothing(dl):
    """No back-link is followed: only the recorded Offer's own id names it
    (ADR-0148)."""
    _ledger(dl, 0, "urn:offer:1", "offer_case_ownership_transfer", _T0)
    _planted(dl, "urn:planted:1", _T0, "urn:offer:1")

    with pytest.raises(VultronNotFoundError):
        recorded_ownership_offer(dl, _CASE_ID, "urn:planted:1")


@pytest.mark.spec("CM-21-005")
def test_the_offer_id_is_derived_from_the_manager_case_and_proposal():
    """The CASE_MANAGER keys its Offer by an id it derives, never by one the
    owner chose, and the same proposal always derives the same id."""
    made = ownership_offer_id(_MANAGER, _CASE_ID, "urn:proposal:1")

    assert made == ownership_offer_id(_MANAGER, _CASE_ID, "urn:proposal:1")
    assert made != "urn:proposal:1"
    assert made != ownership_offer_id(_MANAGER, _CASE_ID, "urn:proposal:2")
    assert made != ownership_offer_id(
        "https://example.org/actors/other", _CASE_ID, "urn:proposal:1"
    )


def _managed_case(dl: SqliteDataLayer) -> None:
    from test.core.use_cases.received.conftest import (
        seed_case_manager_participant,
    )

    case = dl.read_case(_CASE_ID)
    assert case is not None
    seed_case_manager_participant(dl, case, _MANAGER)
    dl.save(case)


@pytest.mark.spec("CM-21-019")
@pytest.mark.spec("HP-01-003")
def test_the_offer_made_from_a_proposal_is_found_by_the_proposal(dl):
    _managed_case(dl)
    made = ownership_offer_id(_MANAGER, _CASE_ID, "urn:proposal:1")
    _ledger(
        dl,
        0,
        made,
        "offer_case_ownership_transfer",
        _T0,
        actor=_MANAGER,
        attributedTo="https://example.org/actors/owner",
    )

    offer = offer_made_from_proposal(dl, _CASE_ID, "urn:proposal:1")

    assert offer is not None and offer.offer_id == made
    assert offer.offerer_id(_MANAGER) == "https://example.org/actors/owner"
    assert offer_made_from_proposal(dl, _CASE_ID, "urn:proposal:2") is None


def test_no_offer_is_made_from_a_proposal_on_a_case_with_no_manager(dl):
    made = ownership_offer_id(_MANAGER, _CASE_ID, "urn:proposal:1")
    _ledger(dl, 0, made, "offer_case_ownership_transfer", _T0)

    assert offer_made_from_proposal(dl, _CASE_ID, "urn:proposal:1") is None


_OWNER = "https://example.org/actors/owner"


@pytest.mark.spec("CM-21-015")
def test_offerer_is_the_participant_a_delegated_offer_speaks_for(dl):
    """CM-24-002: the CASE_MANAGER sends it; ``attributedTo`` names the owner."""
    _ledger(
        dl,
        0,
        "urn:offer:1",
        "offer_case_ownership_transfer",
        _T0,
        actor=_MANAGER,
        attributedTo=_OWNER,
    )

    offer = recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")

    assert offer.offerer_id(_MANAGER) == _OWNER


@pytest.mark.spec("CM-21-015")
def test_offerer_of_an_offer_sent_directly_is_its_actor(dl):
    _ledger(
        dl,
        0,
        "urn:offer:1",
        "offer_case_ownership_transfer",
        _T0,
        actor=_OWNER,
    )

    offer = recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")

    assert offer.offerer_id(_MANAGER) == _OWNER


@pytest.mark.spec("CM-21-015")
@pytest.mark.spec("CM-24-002")
def test_attributed_to_counts_only_on_an_offer_the_manager_sent(dl):
    """A direct Offer's ``attributedTo`` is an unchecked claim: ignored."""
    _ledger(
        dl,
        0,
        "urn:offer:1",
        "offer_case_ownership_transfer",
        _T0,
        actor=_OWNER,
        attributedTo="urn:actor:someone_else",
    )

    offer = recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")

    assert offer.offerer_id(_MANAGER) == _OWNER


@pytest.mark.spec("CM-21-014")
@pytest.mark.spec("CM-21-015")
def test_withdrawal_closes_the_offer(dl):
    """A withdrawal entry closes the Offer as an answer does (AC-7)."""
    _ledger(dl, 0, "urn:offer:1", "offer_case_ownership_transfer", _T0)
    assert open_ownership_offer(dl, _CASE_ID) is not None
    _ledger(dl, 1, "urn:undo:1", "undo_case_ownership_transfer", _T0)

    offer = recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")

    assert offer.answer_id == "urn:undo:1"
    assert offer.closed_by_semantic_type == "undo_case_ownership_transfer"
    assert open_ownership_offer(dl, _CASE_ID) is None


@pytest.mark.spec("CM-21-014")
@pytest.mark.spec("CM-21-017")
def test_expiry_closes_the_offer(dl):
    """The CASE_MANAGER's expiry entry closes the Offer (AC-7)."""
    _ledger(dl, 0, "urn:offer:1", "offer_case_ownership_transfer", _T0)
    _ledger(dl, 1, "urn:offer:1", "offer_case_ownership_transfer_expired", _T0)

    offer = recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")

    assert offer.closed_by_expiry
    assert open_ownership_offer(dl, _CASE_ID) is None


@pytest.mark.spec("CM-21-016")
def test_deadline_is_read_from_the_ledgered_offer_in_utc(dl):
    """The ledgered Offer's endTime is the deadline, in UTC (CS-13-001)."""
    _ledger(
        dl,
        0,
        "urn:offer:1",
        "offer_case_ownership_transfer",
        _T0,
        endTime="2026-10-01T17:00:00+05:00",
    )

    offer = recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")

    assert offer.end_time == _T0
    assert offer.end_time is not None and offer.end_time.tzinfo == UTC
    assert not offer.is_past_deadline(_T0 - timedelta(seconds=1))
    # The deadline instant itself is too late.
    assert offer.is_past_deadline(_T0)


@pytest.mark.spec("CM-21-016")
def test_offer_without_a_deadline_never_passes_one(dl):
    _ledger(dl, 0, "urn:offer:1", "offer_case_ownership_transfer", _T0)

    offer = recorded_ownership_offer(dl, _CASE_ID, "urn:offer:1")

    assert offer.end_time is None
    assert not offer.is_past_deadline(_T0 + timedelta(days=365))


@pytest.mark.spec("ASK-03-002")
@pytest.mark.spec("CM-21-016")
def test_ownership_offer_expiry_is_void():
    """A late answer authorizes nothing: the deadline is binding."""
    from vultron.core.models.protocol_pair import (
        OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRY,
        AskExpiry,
    )

    assert OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRY is AskExpiry.VOID
