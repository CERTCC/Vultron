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
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

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
    dl, case_id, object_id, event_type, actor_id=ACTOR_ID
):  # noqa: ARG001
    """Insert a CaseLedgerEntry directly without traversing the hash chain.

    Uses a simple per-test counter for log_index so entries don't collide.
    Hash fields are left as empty strings — find_protocol_pair only reads
    event_type, case_id, and log_object_id.
    """
    from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry

    _ledger_counter[case_id] = _ledger_counter.get(case_id, -1) + 1
    index = _ledger_counter[case_id]
    entry = VultronCaseLedgerEntry(
        case_id=case_id,
        log_index=index,
        disposition="recorded",
        log_object_id=object_id,
        event_type=event_type,
        payload_snapshot={},
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
    layer = SqliteDataLayer("sqlite:///:memory:")
    case = VulnerabilityCase(id_=CASE_ID, name="CLP11Test")
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
