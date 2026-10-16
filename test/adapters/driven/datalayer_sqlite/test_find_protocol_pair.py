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
"""Tests for SqliteDataLayer.find_protocol_pair() (CLP-11).

Verifies:
- Open pair when request exists but no reply yet
- Closed pair when matching reply is found
- Reply not correlated to wrong offer (two parallel offers in same case)
- Returns open pair when request entry has never been ledgered
- Works correctly for different reply types (accept vs. reject)
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.protocol_pair import (
    OFFER_CASE_PARTICIPANT_REPLY_TYPES,
    ProtocolPair,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

CASE_ID = "https://example.org/cases/clp11-test-case"
REQUEST_TYPE = "offer_case_participant"
OBJECT_ID_A = "https://example.org/activities/offer-001"
OBJECT_ID_B = "https://example.org/activities/offer-002"
REPLY_ID_A = "https://example.org/activities/accept-001"
REPLY_ID_B = "https://example.org/activities/accept-002"
ACTOR_ID = "https://example.org/actors/case-actor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_ledger_counter: dict[str, int] = {}


def _seed_ledger_entry(
    dl,
    case_id,
    object_id,
    event_type,
    actor_id=ACTOR_ID,
    payload_snapshot=None,
):
    """Insert a CaseLedgerEntry directly without traversing the hash chain.

    Uses a simple per-test counter for log_index so entries don't collide.
    Hash fields are left as empty strings — find_protocol_pair only reads
    event_type, case_id, and log_object_id.
    """
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry

    _ledger_counter[case_id] = _ledger_counter.get(case_id, -1) + 1
    index = _ledger_counter[case_id]
    entry = CaseLedgerEntry(
        case_id=case_id,
        log_index=index,
        log_object_id=object_id,
        event_type=event_type,
        payload_snapshot=payload_snapshot or {},
        prev_log_hash="",
        entry_hash="",
    )
    dl.save(entry)
    return entry


@pytest.fixture(autouse=True)
def reset_counter():
    _ledger_counter.clear()
    yield
    _ledger_counter.clear()


@pytest.fixture
def dl():
    layer = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )
    case = as_VulnerabilityCase(id_=CASE_ID, name="CLP11Test")
    layer.create(case)
    return layer


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFindProtocolPairOpenState:
    def test_returns_open_when_request_exists_but_no_reply(self, dl):
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert isinstance(pair, ProtocolPair)
        assert pair.is_open()
        assert pair.reply_object_id is None
        assert pair.reply_event_type is None

    def test_returns_open_when_no_request_entry_at_all(self, dl):
        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.is_open()
        assert pair.reply_object_id is None

    def test_returns_open_when_reply_exists_for_different_case(self, dl):
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)
        other_case_id = "https://example.org/cases/other-case"
        _seed_ledger_entry(
            dl,
            other_case_id,
            REPLY_ID_A,
            "accept_offer_case_participant",
            ACTOR_ID,
        )

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.is_open()


class TestFindProtocolPairClosedState:
    def test_returns_closed_when_accept_reply_found(self, dl):
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)
        _seed_ledger_entry(
            dl,
            CASE_ID,
            REPLY_ID_A,
            "accept_offer_case_participant",
            ACTOR_ID,
        )

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.is_closed()
        assert pair.reply_object_id == REPLY_ID_A
        assert pair.reply_event_type == "accept_offer_case_participant"

    def test_returns_closed_when_reject_reply_found(self, dl):
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)
        _seed_ledger_entry(
            dl,
            CASE_ID,
            REPLY_ID_A,
            "reject_offer_case_participant",
            ACTOR_ID,
        )

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.is_closed()
        assert pair.reply_event_type == "reject_offer_case_participant"

    def test_returned_pair_carries_correct_metadata(self, dl):
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)
        _seed_ledger_entry(
            dl,
            CASE_ID,
            REPLY_ID_A,
            "accept_offer_case_participant",
            ACTOR_ID,
        )

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.case_id == CASE_ID
        assert pair.request_event_type == REQUEST_TYPE
        assert pair.object_id == OBJECT_ID_A
        assert pair.reply_event_types == OFFER_CASE_PARTICIPANT_REPLY_TYPES


class TestFindProtocolPairRequestFound:
    """Tests for the request_found field added for AC-6/AC-7 duplicate detection."""

    def test_request_found_true_when_request_entry_exists(self, dl):
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.request_found is True

    def test_request_found_false_when_no_request_entry(self, dl):
        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.request_found is False

    def test_is_pending_true_when_request_found_and_no_reply(self, dl):
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.is_pending() is True
        assert pair.is_open() is True

    def test_is_pending_false_when_no_prior_request(self, dl):
        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.is_pending() is False
        assert pair.is_open() is True  # is_open() still True for fresh pair

    def test_is_pending_false_when_reply_found(self, dl):
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)
        _seed_ledger_entry(
            dl, CASE_ID, REPLY_ID_A, "accept_offer_case_participant", ACTOR_ID
        )

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.is_pending() is False
        assert pair.is_closed() is True


class TestFindProtocolPairIsolation:
    def test_open_pair_distinct_from_closed_pair_in_same_case(self, dl):
        """Open pair is correctly identified even when another reply exists in the same case.

        Note: CaseLedgerEntry has no structural link from a reply to the
        specific request that triggered it (in_reply_to is YAGNI per CLP-11-004).
        find_protocol_pair() is therefore most reliable when at most one open
        offer of a given request_event_type exists per case at a time —
        the expected protocol usage per ADR-0026/CM-16.

        This test verifies the no-reply-at-all case: when no reply entry of
        the right type exists, the pair remains open regardless of whether
        other request entries are in the ledger.
        """
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_B, REQUEST_TYPE, ACTOR_ID)
        # No reply entries at all → both pairs should be open
        pair_a = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )
        pair_b = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_B,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair_a.is_open()
        assert pair_b.is_open()


class TestFindProtocolPairOrdering:
    @pytest.mark.spec("CM-21-014")
    def test_reply_recorded_before_the_request_does_not_close_it(self, dl):
        """A reply that answered an earlier request leaves a later one open.

        A case offered again after an answered Offer must not read the new
        Offer as already answered.
        """
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)
        _seed_ledger_entry(
            dl, CASE_ID, REPLY_ID_A, "accept_offer_case_participant", ACTOR_ID
        )
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_B, REQUEST_TYPE, ACTOR_ID)

        first = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )
        second = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_B,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert first.reply_object_id == REPLY_ID_A
        assert second.is_pending()

    @pytest.mark.spec("CLP-11-001")
    def test_a_repeated_request_is_not_closed_by_the_earlier_reply(self, dl):
        """When the same object is requested again, the latest request counts.

        The reply to the first request does not close the second.
        """
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)
        _seed_ledger_entry(
            dl, CASE_ID, REPLY_ID_A, "reject_offer_case_participant", ACTOR_ID
        )
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE, ACTOR_ID)

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_A,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.is_pending()


def _seed_reply(dl, reply_id: str, answered: object) -> None:
    """A reply entry whose snapshot carries *answered* as its ``object``."""
    _seed_ledger_entry(
        dl,
        CASE_ID,
        reply_id,
        "accept_offer_case_participant",
        ACTOR_ID,
        payload_snapshot={"object": answered},
    )


@pytest.mark.spec("CLP-11-001")
@pytest.mark.spec("CM-33-005")
class TestFindProtocolPairAnswering:
    """With ``answering``, only a reply to one of those ids closes the pair."""

    def _pair(self, dl, object_id: str, answering: frozenset[str]):
        return dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=object_id,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
            answering=answering,
        )

    def test_a_reply_to_another_request_leaves_the_pair_open(self, dl):
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE)
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_B, REQUEST_TYPE)
        _seed_reply(dl, REPLY_ID_A, {"id": OBJECT_ID_A})

        assert self._pair(dl, OBJECT_ID_B, frozenset({OBJECT_ID_B})).is_open()
        closed = self._pair(dl, OBJECT_ID_A, frozenset({OBJECT_ID_A}))
        assert closed.reply_object_id == REPLY_ID_A

    def test_a_reply_naming_another_id_of_the_request_closes_it(self, dl):
        """A reply to the request's forward, by id, closes the request."""
        forward_id = f"{OBJECT_ID_A}/forward"
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE)
        _seed_reply(dl, REPLY_ID_A, forward_id)

        pair = self._pair(
            dl, OBJECT_ID_A, frozenset({OBJECT_ID_A, forward_id})
        )

        assert pair.reply_object_id == REPLY_ID_A

    def test_without_answering_any_later_reply_closes_it(self, dl):
        """The default reading is unchanged."""
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_A, REQUEST_TYPE)
        _seed_ledger_entry(dl, CASE_ID, OBJECT_ID_B, REQUEST_TYPE)
        _seed_reply(dl, REPLY_ID_A, {"id": OBJECT_ID_A})

        pair = dl.find_protocol_pair(
            case_id=CASE_ID,
            request_event_type=REQUEST_TYPE,
            object_id=OBJECT_ID_B,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

        assert pair.reply_object_id == REPLY_ID_A
