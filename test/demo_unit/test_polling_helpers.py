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
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from test.support.embargo_register import register
from test.support.received import archive_received
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.demo.helpers.polling import (
    CROSS_CONTAINER_TIMEOUT,
    LATE_JOINER_REPLICA_TIMEOUT,
    LATE_JOINER_TIMEOUT,
    PARTICIPANT_JOIN_TIMEOUT,
    _received_activity_id,
    _wait_for_participant_status_field,
    assert_received_from,
    case_manager_store,
    find_case_invite_for_actor,
    find_cp_offer_for_case,
    find_embargo_invite_for_actor,
    find_full_case_invite_for_actor,
    find_ownership_transfer_offer_for_actor,
    wait_for_case_attributed_to,
    wait_for_case_em_state,
    wait_for_case_participants,
    wait_for_embargo_proposal_indexed,
    wait_for_ledger_event,
    wait_for_participant_embargo_accepted,
    wait_for_participant_embargo_consent,
    wait_for_pending_inbox_quiescent,
)
from vultron.demo.utils import received_activity_in
from vultron.wire.as2.factories.actor import offer_case_participant_activity
from vultron.wire.as2.factories.case import (
    rm_invite_to_case_activity,
    rm_invite_to_full_case_activity,
)
from vultron.wire.as2.factories.embargo import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "http://example.com/cases/case-123"
ACTOR_A = "http://example.com/actors/reporter"
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
    "semantic_type": "close_case",
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
        semantic_type="close_case",
        timeout_seconds=1.0,
    )


def test_wait_for_ledger_event_keyed_by_object_id():
    client = _make_ledger_client([_LEDGER_ENTRY])
    wait_for_ledger_event(
        client=client,
        case_id=CASE_ID,
        semantic_type="close_case",
        log_object_id=CASE_ID,
        timeout_seconds=1.0,
    )


def test_wait_for_ledger_event_keyed_by_min_log_index():
    client = _make_ledger_client([_LEDGER_ENTRY])
    wait_for_ledger_event(
        client=client,
        case_id=CASE_ID,
        semantic_type="close_case",
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
            semantic_type="close_case",
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
            semantic_type="close_case",
            min_log_index=6,
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_ledger_event_wrong_semantic_type_then_timeout():
    client = _make_ledger_client([_LEDGER_ENTRY])
    with pytest.raises(
        AssertionError, match="Timed out waiting for ledger event"
    ):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            semantic_type="open_case",
            timeout_seconds=0,
            poll_interval=0.01,
        )


def test_wait_for_ledger_event_empty_ledger_then_timeout():
    client = _make_ledger_client([])
    with pytest.raises(AssertionError):
        wait_for_ledger_event(
            client=client,
            case_id=CASE_ID,
            semantic_type="close_case",
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


class TestCaseManagerStore:
    """Where a helper reads the CASE_MANAGER's store from (#1876).

    A dedicated case-actor container is read as-is; without one the reading
    participant's container is scoped to a CaseActor it co-hosts.
    """

    def test_a_dedicated_case_manager_client_is_read_unscoped(self):
        participant, manager = MagicMock(), MagicMock()
        with patch(
            "vultron.demo.helpers.polling.resolve_case_actor_store_id"
        ) as resolve:
            client, dl_actor_id = case_manager_store(
                participant, "urn:uuid:case", manager
            )
        assert client is manager
        assert dl_actor_id is None
        resolve.assert_not_called()

    def test_without_one_the_participant_client_is_scoped(self):
        participant = MagicMock()
        with patch(
            "vultron.demo.helpers.polling.resolve_case_actor_store_id",
            return_value="http://vendor.test/api/v2/actors/case-actor",
        ) as resolve:
            client, dl_actor_id = case_manager_store(
                participant, "urn:uuid:case"
            )
        assert client is participant
        assert dl_actor_id == "http://vendor.test/api/v2/actors/case-actor"
        resolve.assert_called_once_with(participant, "urn:uuid:case")


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
                "http://reporter.test/api/v2/actors/reporter": "urn:uuid:p3",
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
                "http://reporter.test/api/v2/actors/reporter": "urn:uuid:p2",
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
        "wait_for_semantic_type_in_ledger",
        lambda **kwargs: seen.update(kwargs),
    )

    polling.wait_for_case_actor_ledger_event(
        client=client,
        case_id="urn:test:case",
        semantic_type="accept_case_ownership_transfer",
        timeout_seconds=7.0,
    )

    assert seen["client"] is client
    assert seen["dl_actor_id"] == "urn:test:case-actor"
    assert seen["semantic_type"] == "accept_case_ownership_transfer"
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
# Invite as intake's ReceivedActivityRecord of the body that arrived
# (CLP-10-017, ADR-0149), archived on arrival (PCR-06-005); a row under the
# sender's id is never read (DL-06-006).
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
        target = json.loads(record["received_body"])["target"]
        assert target["type"] == "VulnerabilityCaseStub"
        assert target["id"] != CASE_ID and target["caseId"] == CASE_ID
        client = _dl_client({record_id: record})

        found = find_case_invite_for_actor(
            client, CASE_ID, ACTOR_B, timeout_seconds=1.0, poll_interval=0.01
        )

        assert found == _INVITE_ID

    @pytest.mark.spec("DL-06-006")
    def test_an_invite_held_only_under_the_senders_id_is_not_found(self):
        """A bare row is not a received activity, even a stub Invite (#4871)."""
        _, record = _archived_invite_entry()
        client = _dl_client({_INVITE_ID: json.loads(record["received_body"])})

        with pytest.raises(AssertionError, match="Timed out"):
            find_case_invite_for_actor(
                client,
                CASE_ID,
                ACTOR_B,
                timeout_seconds=0.05,
                poll_interval=0.01,
            )

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


def _archived_full_case_invite_entry() -> tuple[str, dict]:
    """A received full-case Invite as the datalayer router serializes its record."""
    invite = rm_invite_to_full_case_activity(
        ACTOR_B,
        CASE_ID,
        LedgerPosition(log_index=3, entry_hash="ab" * 32),
        actor=_MANAGER,
        id_="http://example.com/activities/full-invite-1",
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_B)
    record = archive_received(dl, invite)
    return record.id_, record.model_dump(
        mode="json", exclude_none=True, by_alias=True
    )


class TestFindFullCaseInviteForActor:
    """The stub Invite and the full-case Invite are told apart by their target."""

    @pytest.mark.spec("CM-11-010")
    def test_finds_the_full_case_invite_and_not_the_stub_invite(self):
        stub_id, stub = _archived_invite_entry()
        full_id, full = _archived_full_case_invite_entry()
        client = _dl_client({stub_id: stub, full_id: full})

        found = find_full_case_invite_for_actor(
            client, CASE_ID, ACTOR_B, timeout_seconds=1.0, poll_interval=0.01
        )

        assert found == "http://example.com/activities/full-invite-1"

    def test_times_out_when_only_the_stub_invite_is_held(self):
        stub_id, stub = _archived_invite_entry()
        client = _dl_client({stub_id: stub})

        with pytest.raises(AssertionError):
            find_full_case_invite_for_actor(
                client,
                CASE_ID,
                ACTOR_B,
                timeout_seconds=0.05,
                poll_interval=0.01,
            )


class TestAssertReceivedFrom:
    def test_passes_when_the_named_actor_sent_it(self):
        record_id, record = _archived_invite_entry()

        assert_received_from(
            _dl_client({record_id: record}),
            _INVITE_ID,
            _MANAGER,
            "consequence",
        )

    @pytest.mark.spec("DL-06-006")
    def test_a_row_under_the_senders_id_is_not_a_received_activity(self):
        _, record = _archived_invite_entry()
        client = _dl_client({_INVITE_ID: json.loads(record["received_body"])})

        with pytest.raises(AssertionError, match="holds no received activity"):
            assert_received_from(client, _INVITE_ID, _MANAGER, "consequence")

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


class TestFindCpOfferForCase:
    """The participant is inline only in intake's archive record (IO-03-004)."""

    def test_returns_the_senders_id_for_the_archived_offer(self):
        offer = offer_case_participant_activity(
            recommended=as_Service(id_=ACTOR_B),
            target=CASE_ID,
            actor=_MANAGER,
        )
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_B)
        record = archive_received(dl, offer)
        client = _dl_client(
            {
                record.id_: record.model_dump(
                    mode="json", exclude_none=True, by_alias=True
                )
            }
        )

        found = find_cp_offer_for_case(
            client, CASE_ID, timeout_seconds=1.0, poll_interval=0.01
        )

        assert found == offer.id_

    def test_a_bare_offer_naming_its_participant_by_id_does_not_match(self):
        bare = {
            "type": "Offer",
            "target": CASE_ID,
            "object": f"{ACTOR_B}#participant",
        }

        with pytest.raises(AssertionError, match="Timed out"):
            find_cp_offer_for_case(
                _dl_client({"urn:uuid:o": bare}),
                CASE_ID,
                timeout_seconds=0.05,
                poll_interval=0.01,
            )


class TestMalformedReceivedRecord:
    """A record the server returns malformed fails loudly, never matches."""

    def test_a_record_wrapping_no_activity_fails(self):
        with pytest.raises(AssertionError, match="holds no received body"):
            received_activity_in(
                {"type": "ReceivedActivityRecord", "id": "urn:uuid:r"}
            )

    def test_a_record_whose_activity_has_no_id_fails(self):
        with pytest.raises(AssertionError, match="activity with no id"):
            _received_activity_id(
                "urn:uuid:r",
                {
                    "type": "ReceivedActivityRecord",
                    "received_body": json.dumps({"type": "Invite"}),
                },
            )

    @pytest.mark.spec("DL-06-006")
    def test_a_bare_activity_is_not_a_received_one(self):
        with pytest.raises(AssertionError, match="holds no received body"):
            _received_activity_id("urn:uuid:a", {"type": "Invite"})


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
    """A client whose case is ACTIVE under *active_embargo_id* (ADR-0122)."""
    assert em is EM.ACTIVE  # the only state these tests serve
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    client.actor_id = ACTOR_B
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        embargo_register=register(active=active_embargo_id or "urn:embargo"),
        case_statuses=[CaseStatus(context=CASE_ID)],  # type: ignore[call-arg]
    )
    client.get.return_value = case.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    return client


def _indexed_client(index: dict[str, str]) -> MagicMock:
    client = MagicMock()
    client.base_url = "http://vendor:7999"
    case = as_VulnerabilityCase(
        id_=CASE_ID, pending_embargo_proposal_index=index
    )
    client.get.return_value = case.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    return client


class TestWaitForEmbargoProposalIndexed:
    def test_returns_when_the_index_names_the_invite(self):
        wait_for_embargo_proposal_indexed(
            _indexed_client({"urn:embargo": "urn:invite"}),
            CASE_ID,
            "urn:embargo",
            "urn:invite",
            timeout_seconds=1.0,
            poll_interval=0.01,
        )

    @pytest.mark.parametrize(
        "index",
        [{}, {"urn:embargo": "urn:proposer-proposal"}],
        ids=["not-yet-indexed", "indexed-to-another-proposal"],
    )
    def test_times_out_when_the_invite_is_not_the_indexed_proposal(
        self, index
    ):
        with pytest.raises(AssertionError, match="index Invite"):
            wait_for_embargo_proposal_indexed(
                _indexed_client(index),
                CASE_ID,
                "urn:embargo",
                "urn:invite",
                timeout_seconds=0.05,
                poll_interval=0.01,
            )


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
        self._wait(EmbargoConsentState.AGREED, EmbargoConsentState.AGREED)

    def test_times_out_naming_the_current_consent(self):
        with pytest.raises(AssertionError, match=r"current=.*INVITED"):
            self._wait(EmbargoConsentState.INVITED, EmbargoConsentState.AGREED)

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
                    EmbargoConsentState.AGREED,
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
                    EmbargoConsentState.AGREED,
                    timeout_seconds=0.05,
                    poll_interval=0.01,
                )


class TestWaitForParticipantEmbargoAccepted:
    @staticmethod
    def _wait(accepted: bool, embargo_id: str = "urn:revised"):
        participant = MagicMock()
        participant.consent_for.return_value = (
            EmbargoConsentState.AGREED
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


# ---------------------------------------------------------------------------
# Store-scan finders read only the types the awaited object is stored as
# (#4600): the whole-store dump rehydrated and serialized every object on the
# container being polled — a late joiner applying its backfill — twice a
# second, at a cost that grew with the store.
# ---------------------------------------------------------------------------

_RECEIVED_TYPES = ["ReceivedActivityRecord"]

_STORE_SCAN_FINDERS = [
    pytest.param(
        lambda c, **kw: find_case_invite_for_actor(c, CASE_ID, ACTOR_B, **kw),
        _RECEIVED_TYPES,
        id="case-invite",
    ),
    pytest.param(
        lambda c, **kw: find_full_case_invite_for_actor(
            c, CASE_ID, ACTOR_B, **kw
        ),
        _RECEIVED_TYPES,
        id="full-case-invite",
    ),
    pytest.param(
        lambda c, **kw: find_embargo_invite_for_actor(
            c, "http://example.com/embargoes/e1", ACTOR_B, **kw
        ),
        _RECEIVED_TYPES,
        id="embargo-invite",
    ),
    pytest.param(
        lambda c, **kw: find_ownership_transfer_offer_for_actor(
            c, CASE_ID, ACTOR_B, **kw
        ),
        _RECEIVED_TYPES,
        id="ownership-transfer-offer",
    ),
    pytest.param(
        lambda c, **kw: find_cp_offer_for_case(c, CASE_ID, **kw),
        _RECEIVED_TYPES,
        id="case-participant-offer",
    ),
]


class TestStoreScanFindersReadOnlyTheirTypes:
    @staticmethod
    def _recording_client() -> MagicMock:
        client = MagicMock()
        client.base_url = "http://vendor:7999"
        client.dl_path.side_effect = lambda key="", actor_id=None: (
            f"/actors/vendor/datalayer/{key}"
        )
        client.get.return_value = {}
        return client

    @pytest.mark.parametrize(("finder", "types"), _STORE_SCAN_FINDERS)
    def test_never_reads_the_whole_store(self, finder, types):
        client = self._recording_client()

        with pytest.raises(AssertionError):
            finder(client, timeout_seconds=0.05, poll_interval=0.01)

        assert client.get.call_args_list, "the finder never read the store"
        for call in client.get.call_args_list:
            path = call.args[0]
            if path == "/actors/vendor/datalayer/":
                assert call.kwargs.get("params") == {"type": types}, call
            else:
                # Only a typed collection may be read unfiltered.
                assert path.endswith("s/"), call


# ---------------------------------------------------------------------------
# wait_for_reporter_introduction (#4675)
# ---------------------------------------------------------------------------

_INTRO_NODE = "http://node.test/api/v2"
_INTRO_REPORTER = f"{_INTRO_NODE}/actors/reporter"
_INTRO_RECEIVER = f"{_INTRO_NODE}/actors/vendor"
_INTRO_REPORT = "urn:uuid:44444444-4444-4444-4444-444444444444"
_INTRO_CASE = "urn:uuid:55555555-5555-5555-5555-555555555555"


def _served_link(report_id: str = _INTRO_REPORT, **fields) -> dict:
    """A ReportCaseLink as the datalayer list route serializes it."""
    from vultron.core.models.report_case_link import VultronReportCaseLink

    link = VultronReportCaseLink(report_id=report_id, **fields)
    return {
        link.id_: link.model_dump(
            mode="json", exclude_none=True, by_alias=True
        )
    }


def _wait_for_introduction(served: dict, **kwargs):
    from vultron.demo.helpers.polling import wait_for_reporter_introduction
    from vultron.demo.utils import DataLayerClient

    seen: dict = {}

    def _get(self, path, **get_kwargs):
        seen["path"] = path
        seen["params"] = get_kwargs.get("params")
        return served

    with patch.object(DataLayerClient, "get", _get):
        result = wait_for_reporter_introduction(
            DataLayerClient(base_url=_INTRO_NODE, actor_id=_INTRO_RECEIVER),
            _INTRO_REPORTER,
            _INTRO_RECEIVER,
            _INTRO_REPORT,
            **kwargs,
        )
    return result, seen


@pytest.mark.spec("CBT-01-005")
def test_wait_for_reporter_introduction_returns_the_bound_case():
    """A link the receiver's introduction bound answers with its case."""
    case_id, seen = _wait_for_introduction(
        _served_link(case_id=_INTRO_CASE, case_creator_id=_INTRO_RECEIVER)
    )
    assert case_id == _INTRO_CASE
    # It reads the reporter's own store, not the client's bound actor.
    assert "/actors/reporter/" in seen["path"]
    assert seen["params"] == {"type": ["ReportCaseLink"]}


@pytest.mark.parametrize(
    "fields",
    [
        # Pending: the trigger wrote the anchor, no introduction bound it.
        {"case_creator_id": _INTRO_RECEIVER},
        # Bound, but by an actor the report was not sent to.
        {"case_id": _INTRO_CASE, "case_creator_id": f"{_INTRO_NODE}/actors/x"},
    ],
    ids=["pending", "other_introducer"],
)
def test_wait_for_reporter_introduction_times_out_without_a_trusted_one(
    fields,
):
    """No bound link naming the receiver: the wait raises."""
    with pytest.raises(AssertionError, match="CBT-01-011"):
        _wait_for_introduction(
            _served_link(**fields), timeout_seconds=0.05, poll_interval=0.01
        )


def test_wait_for_reporter_introduction_ignores_another_reports_link():
    """A bound link for a different report does not answer the wait."""
    with pytest.raises(AssertionError, match="CBT-01-011"):
        _wait_for_introduction(
            _served_link(
                report_id="urn:uuid:66666666-6666-6666-6666-666666666666",
                case_id=_INTRO_CASE,
                case_creator_id=_INTRO_RECEIVER,
            ),
            timeout_seconds=0.05,
            poll_interval=0.01,
        )


def test_wait_for_reporter_introduction_matches_the_expected_case():
    """With *case_id* given, the link must be bound to that case."""
    served = _served_link(case_id=_INTRO_CASE, case_creator_id=_INTRO_RECEIVER)

    case_id, _seen = _wait_for_introduction(served, case_id=_INTRO_CASE)
    assert case_id == _INTRO_CASE

    with pytest.raises(AssertionError, match="of case 'urn:uuid:7777"):
        _wait_for_introduction(
            served,
            case_id="urn:uuid:77777777-7777-7777-7777-777777777777",
            timeout_seconds=0.05,
            poll_interval=0.01,
        )


@pytest.mark.parametrize("dimension", ["vf_state", "rm_state", "rmState", "x"])
def test_participant_status_poll_refuses_unknown_dimension(dimension):
    """A misspelled dimension raises at once rather than polling to timeout."""
    client = MagicMock()
    with patch("vultron.demo.helpers.polling._fetch_participant") as fetch:
        with pytest.raises(ValueError, match="Unknown participant status"):
            _wait_for_participant_status_field(
                client,
                CASE_ID,
                ACTOR_A,
                dimension,  # type: ignore[arg-type]
                {"anything"},
                timeout_seconds=5.0,
                poll_interval=0.01,
            )
    fetch.assert_not_called()
