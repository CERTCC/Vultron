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

"""Unit tests for polling helpers (issue #2202).

Covers new and modified helpers with positive cases (condition satisfied)
and negative cases (timeout → AssertionError).
"""

import inspect
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from test.support.received import archive_received
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_status import CaseStatus
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.demo.helpers.polling import (
    CROSS_CONTAINER_TIMEOUT,
    LATE_JOINER_REPLICA_TIMEOUT,
    LATE_JOINER_TIMEOUT,
    PARTICIPANT_JOIN_TIMEOUT,
    _received_activity,
    _received_activity_id,
    assert_received_from,
    find_case_invite_for_actor,
    find_embargo_invite_for_actor,
    wait_for_case_attributed_to,
    wait_for_case_em_state,
    wait_for_case_participants,
    wait_for_ledger_event,
    wait_for_participant_embargo_accepted,
    wait_for_participant_embargo_consent,
    wait_for_pending_inbox_quiescent,
)
from vultron.wire.as2.factories.case import rm_invite_to_case_activity
from vultron.wire.as2.factories.embargo import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "http://example.com/cases/case-123"
ACTOR_A = "http://example.com/actors/finder"
ACTOR_B = "http://example.com/actors/vendor"


# ---------------------------------------------------------------------------
# Timeout constant tests (AC-7)
# ---------------------------------------------------------------------------


def test_cross_container_timeout_value():
    assert CROSS_CONTAINER_TIMEOUT >= 15.0


def test_participant_join_timeout_value():
    assert PARTICIPANT_JOIN_TIMEOUT >= 20.0


def test_late_joiner_timeout_value():
    assert LATE_JOINER_TIMEOUT >= 90.0


def test_late_joiner_replica_timeout_value():
    assert LATE_JOINER_REPLICA_TIMEOUT >= 30.0


# ---------------------------------------------------------------------------
# wait_for_case_participants tests (AC-2)
# ---------------------------------------------------------------------------


def test_wait_for_case_participants_default_timeout_at_least_15s():
    """Default timeout must survive cross-container CI contention (#2305)."""
    sig = inspect.signature(wait_for_case_participants)
    default = sig.parameters["timeout_seconds"].default
    assert default >= 15.0, (
        f"wait_for_case_participants default ({default}s) is too short; "
        "must be >=15 s for cross-container convergence under CI load"
    )


def test_wait_for_case_participants_accepts_set_parameter():
    """Function must accept expected_actor_ids as a set (AC-2)."""
    sig = inspect.signature(wait_for_case_participants)
    assert "expected_actor_ids" in sig.parameters
    assert "expected_count" not in sig.parameters


def test_wait_for_case_participants_succeeds_when_actors_present():
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "type": "VulnerabilityCase",
        "id": CASE_ID,
        "actor_participant_index": {
            ACTOR_A: "participant-a",
            ACTOR_B: "participant-b",
        },
    }
    wait_for_case_participants(
        vendor_client=client,
        case_id=CASE_ID,
        expected_actor_ids={ACTOR_A, ACTOR_B},
        timeout_seconds=1.0,
    )
    client.get.assert_called()


def test_wait_for_case_participants_subset_check():
    """Subset check: additional actors in index do not prevent success."""
    actor_c = "http://example.com/actors/case-actor"
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "type": "VulnerabilityCase",
        "id": CASE_ID,
        "actor_participant_index": {
            ACTOR_A: "p-a",
            ACTOR_B: "p-b",
            actor_c: "p-c",
        },
    }
    wait_for_case_participants(
        vendor_client=client,
        case_id=CASE_ID,
        expected_actor_ids={ACTOR_A, ACTOR_B},
        timeout_seconds=1.0,
    )


def test_wait_for_case_participants_raises_on_timeout():
    """Missing actor → AssertionError after timeout."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "type": "VulnerabilityCase",
        "id": CASE_ID,
        "actor_participant_index": {ACTOR_A: "p-a"},
    }
    with pytest.raises(
        AssertionError, match="Timed out waiting for participants"
    ):
        wait_for_case_participants(
            vendor_client=client,
            case_id=CASE_ID,
            expected_actor_ids={ACTOR_A, ACTOR_B},
            timeout_seconds=0,
            poll_interval=0.01,
        )


# ---------------------------------------------------------------------------
# wait_for_ledger_event tests (AC-1)
# ---------------------------------------------------------------------------

_LEDGER_ENTRY = {
    "type": "CaseLedgerEntry",
    "case_id": CASE_ID,
    "event_type": "close_case",
    "log_object_id": CASE_ID,
    "log_index": 5,
}


def _make_ledger_client(entries: list) -> MagicMock:
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {str(i): e for i, e in enumerate(entries)}
    return client


def test_wait_for_ledger_event_match_any():
    client = _make_ledger_client([_LEDGER_ENTRY])
    wait_for_ledger_event(
        client=client,
        case_id=CASE_ID,
        event_type="close_case",
        timeout_seconds=1.0,
    )


def test_wait_for_ledger_event_keyed_by_object_id():
    client = _make_ledger_client([_LEDGER_ENTRY])
    wait_for_ledger_event(
        client=client,
        case_id=CASE_ID,
        event_type="close_case",
        log_object_id=CASE_ID,
        timeout_seconds=1.0,
    )


def test_wait_for_ledger_event_keyed_by_min_log_index():
    client = _make_ledger_client([_LEDGER_ENTRY])
    wait_for_ledger_event(
        client=client,
        case_id=CASE_ID,
        event_type="close_case",
        min_log_index=5,
        timeout_seconds=1.0,
    )


def test_wait_for_ledger_event_object_id_mismatch_then_timeout():
    """Wrong log_object_id → never satisfied → AssertionError."""
    client = _make_ledger_client([_LEDGER_ENTRY])
    with pytest.raises(
        AssertionError, match="Timed out waiting for ledger event"
    ):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            event_type="close_case",
            log_object_id="http://example.com/cases/other-case",
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_ledger_event_min_log_index_too_high_then_timeout():
    """Entry with log_index=5 does not satisfy min_log_index=6."""
    client = _make_ledger_client([_LEDGER_ENTRY])
    with pytest.raises(
        AssertionError, match="Timed out waiting for ledger event"
    ):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            event_type="close_case",
            min_log_index=6,
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_ledger_event_wrong_event_type_then_timeout():
    client = _make_ledger_client([_LEDGER_ENTRY])
    with pytest.raises(
        AssertionError, match="Timed out waiting for ledger event"
    ):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            event_type="open_case",
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_ledger_event_empty_ledger_then_timeout():
    client = _make_ledger_client([])
    with pytest.raises(AssertionError):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            event_type="close_case",
            timeout_seconds=0,
            poll_interval=0.01,
        )


# ---------------------------------------------------------------------------
# wait_for_case_attributed_to tests (AC-4)
# ---------------------------------------------------------------------------


def test_wait_for_case_attributed_to_succeeds_string_value():
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "id": CASE_ID,
        "attributed_to": ACTOR_A,
    }
    wait_for_case_attributed_to(
        client=client,
        case_id=CASE_ID,
        expected_attributed_to=ACTOR_A,
        timeout_seconds=1.0,
    )


def test_wait_for_case_attributed_to_succeeds_dict_value():
    """Also handles attributed_to as a dict with an 'id' key."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "id": CASE_ID,
        "attributedTo": {"id": ACTOR_A, "type": "Actor"},
    }
    wait_for_case_attributed_to(
        client=client,
        case_id=CASE_ID,
        expected_attributed_to=ACTOR_A,
        timeout_seconds=1.0,
    )


def test_wait_for_case_attributed_to_wrong_actor_then_timeout():
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "id": CASE_ID,
        "attributed_to": ACTOR_B,
    }
    with pytest.raises(AssertionError, match="Timed out waiting for case"):
        wait_for_case_attributed_to(
            client=client,
            case_id=CASE_ID,
            expected_attributed_to=ACTOR_A,
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_case_attributed_to_missing_field_then_timeout():
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {"id": CASE_ID}
    with pytest.raises(AssertionError):
        wait_for_case_attributed_to(
            client=client,
            case_id=CASE_ID,
            expected_attributed_to=ACTOR_A,
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_case_attributed_to_default_timeout():
    sig = inspect.signature(wait_for_case_attributed_to)
    default = sig.parameters["timeout_seconds"].default
    assert default >= 20.0


# ---------------------------------------------------------------------------
# wait_for_pending_inbox_quiescent tests (AC-8)
# ---------------------------------------------------------------------------


def test_wait_for_pending_inbox_quiescent_absent():
    """Returns immediately when pending inbox is absent (falsy data)."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {}
    wait_for_pending_inbox_quiescent(
        client=client,
        case_id=CASE_ID,
        timeout_seconds=1.0,
    )


def test_wait_for_pending_inbox_quiescent_empty_list():
    """Returns immediately when activity_ids is empty."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {"activity_ids": []}
    wait_for_pending_inbox_quiescent(
        client=client,
        case_id=CASE_ID,
        timeout_seconds=1.0,
    )


def test_wait_for_pending_inbox_quiescent_exception_treated_as_quiescent():
    """Exceptions from client.get → treat as quiescent (inbox does not exist)."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.side_effect = Exception("404 not found")
    wait_for_pending_inbox_quiescent(
        client=client,
        case_id=CASE_ID,
        timeout_seconds=1.0,
    )


def test_wait_for_pending_inbox_quiescent_raises_when_not_empty():
    """Non-empty activity_ids → AssertionError after timeout."""
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.get.return_value = {
        "activity_ids": ["http://example.com/activities/act-1"]
    }
    with pytest.raises(AssertionError, match="PendingCaseInbox"):
        wait_for_pending_inbox_quiescent(
            client=client,
            case_id=CASE_ID,
            timeout_seconds=0,
            poll_interval=0.01,
        )


# ---------------------------------------------------------------------------
# case_actor_participant_id_in (extracted in #2789)
# ---------------------------------------------------------------------------


def _case_with_index(index: dict[str, str]):
    """Build an as_VulnerabilityCase carrying *index* as its participant index."""
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case = as_VulnerabilityCase(id_="urn:uuid:case-cap", name="Case")
    case.actor_participant_index.update(index)
    return case


class TestCaseActorParticipantIdIn:
    """The read-free CaseActor lookup `setup_canonical_case` depends on.

    `find_case_actor_participant_id` is only ever monkeypatched in the suite, so
    the predicate it delegates to had no coverage of its own until this class.
    `setup_canonical_case` asserts on the result, which turns a silent miss into
    a confusing failure about `ProposeReportCaseToActorNode` — so the match rule
    is worth pinning explicitly.
    """

    def test_returns_the_case_actor_uri(self):
        from vultron.demo.helpers.polling import case_actor_participant_id_in

        case = _case_with_index(
            {
                "http://vendor.test/api/v2/actors/vendor": "urn:uuid:p1",
                "http://ca.test/api/v2/actors/case-actor": "urn:uuid:p2",
                "http://finder.test/api/v2/actors/finder": "urn:uuid:p3",
            }
        )
        assert (
            case_actor_participant_id_in(case)
            == "http://ca.test/api/v2/actors/case-actor"
        )

    def test_returns_none_when_no_case_actor_participant(self):
        from vultron.demo.helpers.polling import case_actor_participant_id_in

        case = _case_with_index(
            {
                "http://vendor.test/api/v2/actors/vendor": "urn:uuid:p1",
                "http://finder.test/api/v2/actors/finder": "urn:uuid:p2",
            }
        )
        assert case_actor_participant_id_in(case) is None

    def test_returns_none_for_an_empty_index(self):
        from vultron.demo.helpers.polling import case_actor_participant_id_in

        assert case_actor_participant_id_in(_case_with_index({})) is None

    def test_matches_on_the_shared_slug_constant(self):
        """The predicate must follow CASE_ACTOR_SLUG, not a private literal.

        The slug is the container-wide CaseActor identity (CP-08-002/003). If it
        is ever renamed, this lookup has to move with it rather than silently
        stop matching.
        """
        from vultron.demo.helpers.polling import case_actor_participant_id_in
        from vultron.demo.utils import CASE_ACTOR_SLUG

        actor_id = f"http://ca.test/api/v2/actors/{CASE_ACTOR_SLUG}"
        case = _case_with_index({actor_id: "urn:uuid:p1"})
        assert case_actor_participant_id_in(case) == actor_id

    def test_find_case_actor_participant_id_delegates_to_the_predicate(self):
        """The polling wrapper must reuse the predicate, not re-implement it."""
        from vultron.demo.helpers.polling import find_case_actor_participant_id

        actor_id = "http://ca.test/api/v2/actors/case-actor"
        client = MagicMock()
        client.dl_path.return_value = "/actors/x/datalayer/urn:uuid:case-cap"
        client.get.return_value = {
            "id": "urn:uuid:case-cap",
            "type": "VulnerabilityCase",
            "name": "Case",
            "actorParticipantIndex": {actor_id: "urn:uuid:p1"},
        }
        assert (
            find_case_actor_participant_id(client, "urn:uuid:case-cap")
            == actor_id
        )


# ---------------------------------------------------------------------------
# #3602: CaseActor-ledger gate and shared fan-out budget
# ---------------------------------------------------------------------------


@pytest.mark.spec("EDF-06-002")
def test_wait_for_case_actor_ledger_event_reads_the_case_actor_store(
    monkeypatch,
):
    """The gate scopes the ledger read to the CaseActor's own store."""
    from vultron.demo.helpers import polling

    client = MagicMock()
    seen: dict = {}
    monkeypatch.setattr(
        polling,
        "resolve_case_actor_store_id",
        lambda c, case_id: "urn:test:case-actor",
    )
    monkeypatch.setattr(
        polling,
        "wait_for_event_type_in_ledger",
        lambda **kwargs: seen.update(kwargs),
    )

    polling.wait_for_case_actor_ledger_event(
        client=client,
        case_id="urn:test:case",
        event_type="accept_case_ownership_transfer",
        timeout_seconds=7.0,
    )

    assert seen["client"] is client
    assert seen["dl_actor_id"] == "urn:test:case-actor"
    assert seen["event_type"] == "accept_case_ownership_transfer"
    assert seen["timeout_seconds"] == 7.0


@pytest.mark.spec("EDF-06-008")
def test_shared_budget_hands_out_what_is_left_and_never_goes_negative(
    monkeypatch,
):
    from vultron.demo.helpers import polling

    now = [1000.0]
    monkeypatch.setattr(polling.time, "monotonic", lambda: now[0])
    budget = polling.SharedBudget(10.0)

    assert budget.remaining() == 10.0
    now[0] += 4.0
    assert budget.remaining() == 6.0
    now[0] += 60.0
    assert budget.remaining() == 0.0
    assert "remaining=0.0s" in repr(budget)


# ---------------------------------------------------------------------------
# find_case_invite_for_actor (#3821): the invitee holds the CASE_MANAGER's
# Invite as intake's ReceivedActivityRecord (CLP-10-017, ADR-0111), or bare
# under the sender's id while the inbox defers it until the case bootstrap.
# ---------------------------------------------------------------------------

_MANAGER = "http://example.com/actors/case-actor"
_INVITE_ID = "http://example.com/activities/invite-1"


def _archived_invite_entry(
    case_id: str = CASE_ID, invitee_id: str = ACTOR_B
) -> tuple[str, dict]:
    """A received Invite as the datalayer router serializes its record."""
    invite = rm_invite_to_case_activity(
        as_Service(id_=invitee_id),
        target=as_VulnerabilityCase(
            id_=case_id, stub_summary="Security issue for test invite"
        ),
        actor=_MANAGER,
        id_=_INVITE_ID,
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=invitee_id)
    record = archive_received(dl, invite)
    return record.id_, record.model_dump(
        mode="json", exclude_none=True, by_alias=True
    )


def _dl_client(entries: dict[str, dict]) -> MagicMock:
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.dl_path.return_value = "/actors/vendor/datalayer/"
    client.get.return_value = entries
    return client


class TestFindCaseInviteForActor:
    def test_returns_the_senders_id_for_the_archived_invite(self):
        record_id, record = _archived_invite_entry()
        client = _dl_client({record_id: record})

        found = find_case_invite_for_actor(
            client, CASE_ID, ACTOR_B, timeout_seconds=1.0, poll_interval=0.01
        )

        assert found == _INVITE_ID
        assert record_id != _INVITE_ID

    @pytest.mark.spec("CM-11-013")
    def test_matches_the_case_the_stub_names_not_the_stub_id(self):
        """The stub's own ID is ``<case-id>/stub``; ``caseId`` names the case."""
        record_id, record = _archived_invite_entry()
        target = record["activity"]["target"]
        assert target["type"] == "VulnerabilityCaseStub"
        assert target["id"] != CASE_ID and target["caseId"] == CASE_ID
        client = _dl_client({record_id: record})

        found = find_case_invite_for_actor(
            client, CASE_ID, ACTOR_B, timeout_seconds=1.0, poll_interval=0.01
        )

        assert found == _INVITE_ID

    def test_finds_the_invite_the_inbox_holds_until_the_case_bootstrap(
        self,
    ):
        """A deferred Invite has not reached intake; the inbox holds it bare."""
        _, record = _archived_invite_entry()
        client = _dl_client({_INVITE_ID: record["activity"]})

        found = find_case_invite_for_actor(
            client, CASE_ID, ACTOR_B, timeout_seconds=1.0, poll_interval=0.01
        )

        assert found == _INVITE_ID

    @pytest.mark.parametrize(
        ("case_id", "invitee_id"),
        [
            ("http://example.com/cases/other", ACTOR_B),
            (CASE_ID, ACTOR_A),
        ],
    )
    def test_an_invite_for_another_case_or_invitee_does_not_match(
        self, case_id, invitee_id
    ):
        record_id, record = _archived_invite_entry(case_id, invitee_id)
        client = _dl_client({record_id: record})

        with pytest.raises(AssertionError):
            find_case_invite_for_actor(
                client,
                CASE_ID,
                ACTOR_B,
                timeout_seconds=0.05,
                poll_interval=0.01,
            )


class TestAssertReceivedFrom:
    @pytest.mark.parametrize("held", ["archived", "deferred"])
    def test_passes_when_the_named_actor_sent_it(self, held):
        record_id, record = _archived_invite_entry()
        entries = (
            {record_id: record}
            if held == "archived"
            else {_INVITE_ID: record["activity"]}
        )

        assert_received_from(
            _dl_client(entries), _INVITE_ID, _MANAGER, "consequence"
        )

    def test_names_the_actual_sender_when_another_actor_sent_it(self):
        record_id, record = _archived_invite_entry()

        with pytest.raises(AssertionError, match=f"emitted as '{_MANAGER}'"):
            assert_received_from(
                _dl_client({record_id: record}),
                _INVITE_ID,
                ACTOR_A,
                "consequence",
            )

    def test_fails_when_the_activity_is_not_held(self):
        with pytest.raises(AssertionError, match="holds no received activity"):
            assert_received_from(
                _dl_client({}), _INVITE_ID, _MANAGER, "consequence"
            )


class TestMalformedReceivedRecord:
    """A record the server returns malformed fails loudly, never matches."""

    def test_a_record_wrapping_no_activity_fails(self):
        with pytest.raises(AssertionError, match="wraps no activity"):
            _received_activity(
                {"type": "ReceivedActivityRecord", "id": "urn:uuid:r"}
            )

    def test_a_record_whose_activity_has_no_id_fails(self):
        with pytest.raises(AssertionError, match="activity with no id"):
            _received_activity_id(
                "urn:uuid:r",
                {
                    "type": "ReceivedActivityRecord",
                    "activity": {"type": "Invite"},
                },
            )

    def test_a_bare_activity_is_known_by_its_storage_id(self):
        assert _received_activity_id("urn:uuid:a", {"type": "Invite"}) == (
            "urn:uuid:a"
        )


# ---------------------------------------------------------------------------
# Embargo polling (#2070): the relayed Invite(EmbargoEvent), the EM state, and
# a participant's consent, each read where the cause commits (EDF-06-002).
# ---------------------------------------------------------------------------

_EMBARGO_ID = f"{CASE_ID}/embargo_events/90d"
_RELAYED_ID = "http://example.com/activities/embargo-invite-1"


def _relayed_embargo_invite(
    invitee_id: str = ACTOR_B, embargo_id: str = _EMBARGO_ID
) -> tuple[str, dict]:
    """The CASE_MANAGER's relayed Invite as the invitee's store holds it."""
    invite = em_propose_embargo_activity(
        as_EmbargoEvent(
            id_=embargo_id,
            context=CASE_ID,
            end_time=datetime.now(UTC) + timedelta(days=90),
        ),
        context=CASE_ID,
        actor=_MANAGER,
        to=[invitee_id],
        id_=_RELAYED_ID,
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=invitee_id)
    record = archive_received(dl, invite)
    return record.id_, record.model_dump(
        mode="json", exclude_none=True, by_alias=True
    )


class TestFindEmbargoInviteForActor:
    @pytest.mark.spec("EP-09-002")
    def test_finds_the_invite_addressed_to_the_invitee(self):
        record_id, record = _relayed_embargo_invite()
        client = _dl_client({record_id: record})

        found = find_embargo_invite_for_actor(
            client,
            _EMBARGO_ID,
            ACTOR_B,
            timeout_seconds=1.0,
            poll_interval=0.01,
        )

        assert found == _RELAYED_ID

    @pytest.mark.spec("EP-09-010")
    @pytest.mark.parametrize(
        ("embargo_id", "invitee_id"),
        [
            (f"{CASE_ID}/embargo_events/other", ACTOR_B),
            (_EMBARGO_ID, ACTOR_A),
        ],
    )
    def test_an_invite_of_another_embargo_or_invitee_does_not_match(
        self, embargo_id, invitee_id
    ):
        record_id, record = _relayed_embargo_invite(invitee_id, embargo_id)
        client = _dl_client({record_id: record})

        with pytest.raises(AssertionError, match="Timed out"):
            find_embargo_invite_for_actor(
                client,
                _EMBARGO_ID,
                ACTOR_B,
                timeout_seconds=0.05,
                poll_interval=0.01,
            )

    def test_a_case_invite_is_not_an_embargo_invite(self):
        record_id, record = _archived_invite_entry()
        client = _dl_client({record_id: record})

        with pytest.raises(AssertionError, match="Timed out"):
            find_embargo_invite_for_actor(
                client,
                CASE_ID,
                ACTOR_B,
                timeout_seconds=0.05,
                poll_interval=0.01,
            )


def _case_client(em: EM, active_embargo_id: str | None) -> MagicMock:
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.actor_id = ACTOR_B
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        active_embargo=active_embargo_id,
        case_statuses=[CaseStatus(em_state=em, context=CASE_ID)],  # type: ignore[arg-type,call-arg]
    )
    client.get.return_value = case.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    return client


class TestWaitForCaseEmState:
    def test_returns_when_em_matches(self):
        wait_for_case_em_state(
            _case_client(EM.ACTIVE, None),
            CASE_ID,
            EM.ACTIVE,
            timeout_seconds=1.0,
            poll_interval=0.01,
        )

    def test_times_out_on_another_state(self):
        with pytest.raises(AssertionError, match="reach REVISE"):
            wait_for_case_em_state(
                _case_client(EM.ACTIVE, None),
                CASE_ID,
                EM.REVISE,
                timeout_seconds=0.05,
                poll_interval=0.01,
            )

    def test_reads_the_named_actors_store(self):
        client = _case_client(EM.ACTIVE, None)
        wait_for_case_em_state(
            client,
            CASE_ID,
            EM.ACTIVE,
            timeout_seconds=1.0,
            dl_actor_id=_MANAGER,
        )
        client.dl_path.assert_called_with(CASE_ID, actor_id=_MANAGER)

    def test_a_stale_active_embargo_does_not_satisfy_the_wait(self):
        """ACTIVE before and after a revision: only the embargo id tells."""
        with pytest.raises(AssertionError, match="active embargo"):
            wait_for_case_em_state(
                _case_client(EM.ACTIVE, "urn:old"),
                CASE_ID,
                EM.ACTIVE,
                timeout_seconds=0.05,
                poll_interval=0.01,
                active_embargo_id="urn:revised",
            )

    def test_the_revised_embargo_satisfies_the_wait(self):
        wait_for_case_em_state(
            _case_client(EM.ACTIVE, "urn:revised"),
            CASE_ID,
            EM.ACTIVE,
            timeout_seconds=1.0,
            poll_interval=0.01,
            active_embargo_id="urn:revised",
        )


class TestWaitForParticipantEmbargoConsent:
    @staticmethod
    def _wait(
        consent: EmbargoConsentState,
        expected: EmbargoConsentState,
        embargo_id: str = "urn:test-embargo",
    ):
        participant = MagicMock()
        participant.consent_for.return_value = consent
        with patch(
            "vultron.demo.helpers.polling._fetch_participant",
            return_value=participant,
        ):
            wait_for_participant_embargo_consent(
                MagicMock(base_url="http://vendor:7999", actor_id=ACTOR_B),
                CASE_ID,
                ACTOR_A,
                embargo_id,
                expected,
                timeout_seconds=0.05,
                poll_interval=0.01,
            )

    def test_returns_when_consent_matches(self):
        self._wait(EmbargoConsentState.ACCEPTED, EmbargoConsentState.ACCEPTED)

    def test_times_out_naming_the_current_consent(self):
        with pytest.raises(AssertionError, match=r"current=.*INVITED"):
            self._wait(
                EmbargoConsentState.INVITED, EmbargoConsentState.ACCEPTED
            )

    def test_times_out_without_a_participant_record(self):
        with patch(
            "vultron.demo.helpers.polling._fetch_participant",
            return_value=None,
        ):
            with pytest.raises(AssertionError, match="no participant record"):
                wait_for_participant_embargo_consent(
                    MagicMock(base_url="http://vendor:7999", actor_id=ACTOR_B),
                    CASE_ID,
                    ACTOR_A,
                    "urn:test-embargo",
                    EmbargoConsentState.ACCEPTED,
                    timeout_seconds=0.05,
                    poll_interval=0.01,
                )

    def test_timeout_names_the_read_error_when_no_poll_completed(self):
        with patch(
            "vultron.demo.helpers.polling._fetch_participant",
            side_effect=ConnectionError("refused"),
        ):
            with pytest.raises(
                AssertionError, match="ConnectionError: refused"
            ):
                wait_for_participant_embargo_consent(
                    MagicMock(base_url="http://vendor:7999", actor_id=ACTOR_B),
                    CASE_ID,
                    ACTOR_A,
                    "urn:test-embargo",
                    EmbargoConsentState.ACCEPTED,
                    timeout_seconds=0.05,
                    poll_interval=0.01,
                )


class TestWaitForParticipantEmbargoAccepted:
    @staticmethod
    def _wait(accepted: bool, embargo_id: str = "urn:revised"):
        participant = MagicMock()
        participant.consent_for.return_value = (
            EmbargoConsentState.ACCEPTED
            if accepted
            else EmbargoConsentState.INVITED
        )
        with patch(
            "vultron.demo.helpers.polling._fetch_participant",
            return_value=participant,
        ):
            wait_for_participant_embargo_accepted(
                MagicMock(base_url="http://vendor:7999", actor_id=ACTOR_B),
                CASE_ID,
                ACTOR_A,
                embargo_id,
                timeout_seconds=0.05,
                poll_interval=0.01,
            )

    def test_returns_when_the_embargo_is_accepted(self):
        self._wait(True)

    def test_times_out_naming_the_accepted_embargoes(self):
        with pytest.raises(AssertionError, match=r"current=.*INVITED"):
            self._wait(False)
