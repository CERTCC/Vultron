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
"""A participant numbers its case activities, and the CASE_MANAGER judges
each sender's activities in that order (SYNC-21, ADR-0178).

A hold that ends on its wait is ended by the hold timer the app runs
(``LedgerNetwork.end_expired_holds`` ticks it once), and a released activity
is replayed as a delivery of its own, as the inbox replays it.

A test that checks the sender's numbering builds its activities through the
sender's own adapter, as its outbox sends them.  A test that checks the
CASE_MANAGER's ordering sets each body's ``senderSequence`` itself, so it
states exactly which numbers arrive, in which order.
"""

import json
from datetime import timedelta
from typing import Any, cast

import pytest

from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import rebuild_from_ledger, replay_inbox
from test.support.refusal_notice import (
    assert_no_refusal_notice,
    assert_refusal_notice,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.config.ledger import LedgerConfig
from vultron.core.behaviors.case.nodes.delegation import (
    GrantCaseParticipantRoleNode,
)
from vultron.core.behaviors.case.role_offer_answer_tree import (
    create_accept_case_participant_role_tree,
)
from vultron.core.behaviors.sync.nodes.sender_sequence_drain import (
    DrainSequenceHoldsNode,
)
from vultron.core.models._helpers import clock as helpers_clock, now_utc
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.sender_sequence import SenderSequenceOrder
from vultron.core.services.sender_sequence_order import (
    end_case_sender_sequence_holds,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.sync_helpers import ledger_tail_position
from vultron.core.use_cases.received.actor.accept_reject_case_participant_role import (
    AcceptCaseParticipantRoleReceivedUseCase,
)
from vultron.demo.determinism import SteppingClock
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork
from .test_embargo_answer_idempotency import _answer_body, _invited

#: The default hold wait and per-sender cap (SYNC-21-021, ADR-0178).
DEFAULT_WAIT = timedelta(seconds=120)
DEFAULT_CAP = 16


def _network(tag: str) -> LedgerNetwork:
    """A network of its own case, so no id one test mints repeats another's."""
    return LedgerNetwork(f"https://example.org/cases/sender-sequence-{tag}")


def _note_body_in(
    dl: SqliteDataLayer, case_id: str, note_id: str, *, actor: str, to: str
) -> dict[str, Any]:
    """The sealed body *actor*'s adapter builds for a note on *case_id*."""
    if dl.read(note_id) is None:
        dl.create(as_Note(id_=note_id, content="numbered", context=case_id))
    _activity_id, body = TriggerActivityAdapter(dl).add_note_to_case(
        note_id=note_id, case_id=case_id, actor=actor, to=[to]
    )
    return cast(dict[str, Any], json.loads(body))


def _note_body(
    net: LedgerNetwork, tag: str, *, actor: str = OWNER, to: str = MANAGER
) -> dict[str, Any]:
    """*actor*'s outbox body for a new note on the network's case."""
    return _note_body_in(
        net.stores[actor],
        net.case_id,
        f"{net.case_id}/notes/{tag}",
        actor=actor,
        to=to,
    )


def _numbered(body: dict[str, Any], number: int) -> dict[str, Any]:
    """*body* carrying *number* as its ``senderSequence``."""
    return {**body, "senderSequence": number}


def _note_of(body: dict[str, Any]) -> str:
    obj = body["object"]
    return str(obj["id"] if isinstance(obj, dict) else obj)


def _committed_notes(net: LedgerNetwork) -> list[str]:
    """The ids of the notes the CASE_MANAGER's ledger records, in order."""
    notes = []
    for entry in ledger_entries(net.stores[MANAGER], net.case_id):
        if entry.semantic_type == "add_note_to_case":
            notes.append(_note_of(entry.payload_snapshot))
    return notes


def _wait_out_holds(
    net: LedgerNetwork, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Move the clock past the default wait and tick the hold timer once.

    Nothing else arrives: the timer alone ends the holds (SYNC-21-011).
    """
    later = now_utc() + DEFAULT_WAIT + timedelta(seconds=1)
    monkeypatch.setattr(
        helpers_clock, "datetime", SteppingClock(later, step=timedelta(0))
    )
    net.end_expired_holds(MANAGER)


def _forget_sequence_state(net: LedgerNetwork, actor: str) -> None:
    """*actor* keeps the case ledger but none of its sequence state.

    A new CASE_MANAGER holds the case ledger it inherited and none of the old
    one's next expected numbers or holds (ADR-0178), so the test reaches the
    ledger-derived start (SYNC-21-009).
    """
    dl = net.stores[actor]
    for order in dl.list_objects(SenderSequenceOrder.__name__):
        assert isinstance(order, SenderSequenceOrder)
        if order.case_id == net.case_id:
            dl.delete(SenderSequenceOrder.__name__, order.id_)


def _hand_over_case_manager(net: LedgerNetwork) -> None:
    """The outgoing CASE_MANAGER's drain as its role passes (SYNC-21-025).

    The role passes when the CASE_MANAGER commits the acceptance of a
    ``CASE_MANAGER`` role delegation (CM-02-016), and that tree drains the
    holds first (``DrainSequenceHoldsNode``, pinned in
    ``test_the_case_manager_role_grant_drains_first``).  This network drives
    no delegation, so the helper runs the node's drain and the replay that
    follows the delivery.
    """
    dl = net.stores[MANAGER]
    end_case_sender_sequence_holds(dl, net.case_id)
    replay_inbox(dl, MANAGER)


def _consent(net: LedgerNetwork, actor: str, embargo_id: str) -> Any:
    case = net.case(MANAGER)
    participant = net.stores[MANAGER].read(case.actor_participant_index[actor])
    assert isinstance(participant, CaseParticipant)
    return participant.consent_for(embargo_id)


# ---------------------------------------------------------------------------
# The sender numbers its activities
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-21-004")
@pytest.mark.spec("SYNC-21-002")
@pytest.mark.spec("SYNC-21-001")
def test_each_activity_to_the_case_manager_is_numbered_one_up() -> None:
    net = _network("numbered")
    dl = net.stores[OWNER]
    first = _note_body(net, "first")
    net.receive(MANAGER, first)
    net.deliver(MANAGER, to=OWNER, type_="Announce")
    SyncActivityAdapter(dl).send_read_ledger_entry(
        net.case_id, ledger_tail_position(net.case_id, dl), OWNER, [MANAGER]
    )
    [read] = net.queued(OWNER, to=MANAGER, type_="Read")
    read_body = read_sealed_body_dict(dl, read.id_)
    assert read_body is not None
    replica_entry = ledger_entries(dl, net.case_id)[-1]
    SyncActivityAdapter(dl).send_reject_log_entry(
        replica_entry, replica_entry.entry_hash, OWNER, [MANAGER]
    )
    [reject] = net.queued(OWNER, to=MANAGER, type_="Reject")
    reject_body = read_sealed_body_dict(dl, reject.id_)
    assert reject_body is not None

    second = _note_body(net, "second")
    from_manager = _note_body(net, "manager", actor=MANAGER, to=OWNER)

    # The Read and the Reject are about the ledger, so they use no number.
    assert "senderSequence" not in read_body
    assert "senderSequence" not in reject_body
    assert (first.get("senderSequence"), second.get("senderSequence")) == (
        1,
        2,
    )
    # The CASE_MANAGER's own activities are ordered by its ledger.
    assert "senderSequence" not in from_manager


@pytest.mark.spec("SYNC-21-003")
def test_a_rebuilt_activity_keeps_its_number() -> None:
    net = _network("rebuilt")
    first = _note_body(net, "kept")
    _note_body(net, "later")

    again = _note_body(net, "kept")

    assert again["senderSequence"] == first["senderSequence"] == 1


@pytest.mark.spec("SYNC-21-005")
def test_the_entry_records_the_received_number() -> None:
    net = _network("entry")
    body = _numbered(_note_body(net, "recorded"), 1)

    net.receive(MANAGER, body)

    [entry] = [
        e
        for e in ledger_entries(net.stores[MANAGER], net.case_id)
        if e.semantic_type == "add_note_to_case"
    ]
    assert entry.payload_snapshot["senderSequence"] == 1


@pytest.mark.spec("SYNC-21-006")
def test_a_sender_rebuilt_from_the_ledger_resumes_past_its_own_numbers() -> (
    None
):
    net = _network("resume-ledger")
    for tag in ("one", "two"):
        net.receive(MANAGER, _note_body(net, tag))
    assert len(_committed_notes(net)) == 2

    rebuilt = rebuild_from_ledger(
        net.stores[MANAGER],
        net.case_id,
        as_actor=OWNER,
        seed=net.rebuild_seed,
    )
    try:
        body = _note_body_in(
            rebuilt,
            net.case_id,
            f"{net.case_id}/notes/after-rebuild",
            actor=OWNER,
            to=MANAGER,
        )
    finally:
        rebuilt.close()

    assert body["senderSequence"] == 3


@pytest.mark.spec("SYNC-21-019")
@pytest.mark.spec("SYNC-21-007")
def test_a_refused_sender_resumes_at_the_expected_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    net = _network("resume-notice")
    # The CASE_MANAGER is told number 10 first, so after the hold ends it
    # expects 11 while OWNER's own count is far behind.
    net.receive(MANAGER, _numbered(_note_body(net, "ahead"), 10))
    _wait_out_holds(net, monkeypatch)
    behind = _note_body(net, "behind")
    net.receive(MANAGER, behind)
    notice = assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=behind["id"],
        asserter=OWNER,
        reason="",
        case_id=net.case_id,
    )
    assert notice["expectedSenderSequence"] == 11
    net.deliver(MANAGER, to=OWNER, type_="Reject")

    again = _note_body(net, "behind-again")
    net.receive(MANAGER, again)

    assert again["senderSequence"] >= 11
    assert _note_of(again) in _committed_notes(net)


# ---------------------------------------------------------------------------
# The CASE_MANAGER judges each sender's activities in number order
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-21-016")
@pytest.mark.spec("SYNC-21-010")
@pytest.mark.spec("SYNC-21-009")
@pytest.mark.spec("SYNC-21-008")
def test_an_activity_past_a_gap_is_held_until_the_gap_fills() -> None:
    net = _network("gap")
    first = _numbered(_note_body(net, "first"), 1)
    second = _numbered(_note_body(net, "second"), 2)

    net.receive(MANAGER, second)
    assert _committed_notes(net) == []
    assert_no_refusal_notice(
        net.stores[MANAGER], manager=MANAGER, refused_id=second["id"]
    )

    net.receive(MANAGER, first)
    assert _committed_notes(net) == [_note_of(first), _note_of(second)]


@pytest.mark.spec("SYNC-21-008")
def test_an_accept_then_a_reject_decide_as_sent_in_either_order() -> None:
    consents = {}
    for send_order in (True, False):
        net = _network(f"answers-{send_order}")
        embargo_id, invite_id = _invited(net, BYSTANDER, f"seq-{send_order}")
        accept = _answer_body(
            net, BYSTANDER, invite_id, accept=True, tag=f"seq-a-{send_order}"
        )
        reject = _answer_body(
            net, BYSTANDER, invite_id, accept=False, tag=f"seq-r-{send_order}"
        )
        sent = (_numbered(accept, 1), _numbered(reject, 2))
        for body in sent if send_order else reversed(sent):
            net.receive(MANAGER, body)
        consents[send_order] = _consent(net, BYSTANDER, embargo_id)

    # The Reject was sent last, so it decides (#5202, ADR-0178).
    assert consents == {
        True: EmbargoConsentState.DECLINED,
        False: EmbargoConsentState.DECLINED,
    }


@pytest.mark.spec("SYNC-21-008")
def test_a_note_numbered_before_leave_is_kept_in_either_order() -> None:
    kept = {}
    for send_order in (True, False):
        net = _network(f"note-leave-{send_order}")
        dl = net.stores[BYSTANDER]
        note = _numbered(_note_body(net, "before-leave", actor=BYSTANDER), 1)
        _leave_id, leave_text = TriggerActivityAdapter(dl).close_case(
            case_id=net.case_id, actor=BYSTANDER, to=[MANAGER]
        )
        leave = _numbered(json.loads(leave_text), 2)
        for body in (note, leave) if send_order else (leave, note):
            net.receive(MANAGER, body)
        kept[send_order] = _committed_notes(net) == [_note_of(note)]

    # The note was sent while its sender was active, so it is kept (#5203).
    assert kept == {True: True, False: True}


@pytest.mark.spec("SYNC-21-016")
@pytest.mark.spec("SYNC-21-013")
@pytest.mark.spec("SYNC-21-011")
def test_a_hold_ends_when_its_wait_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    net = _network("wait")
    _note_body(net, "lost")
    held = [_numbered(_note_body(net, f"held-{n}"), n) for n in (2, 3)]
    for body in reversed(held):
        net.receive(MANAGER, body)
    assert _committed_notes(net) == []

    # OWNER sends nothing more, and nothing else arrives.
    _wait_out_holds(net, monkeypatch)

    assert _committed_notes(net) == [_note_of(b) for b in held]
    for body in held:
        assert_no_refusal_notice(
            net.stores[MANAGER], manager=MANAGER, refused_id=body["id"]
        )


@pytest.mark.spec("SYNC-21-013")
@pytest.mark.spec("SYNC-21-012")
def test_a_hold_ends_when_the_sender_reaches_the_cap() -> None:
    net = _network("cap")
    _note_body(net, "lost")
    held = [
        _numbered(_note_body(net, f"held-{n}"), n)
        for n in range(2, 2 + DEFAULT_CAP)
    ]
    *before_cap, at_cap = held

    for body in before_cap:
        net.receive(MANAGER, body)
    assert _committed_notes(net) == []

    net.receive(MANAGER, at_cap)
    assert _committed_notes(net) == [_note_of(b) for b in held]


@pytest.mark.spec("SYNC-21-015")
@pytest.mark.spec("SYNC-21-014")
@pytest.mark.spec("SYNC-21-009")
def test_a_late_or_reused_number_is_refused_with_a_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    net = _network("late")
    late = _numbered(_note_body(net, "late"), 1)
    held = _numbered(_note_body(net, "held"), 2)
    reused = _numbered(_note_body(net, "reused"), 2)
    manager_dl = net.stores[MANAGER]

    net.receive(MANAGER, held)
    net.receive(MANAGER, reused)
    reused_notice = assert_refusal_notice(
        manager_dl,
        manager=MANAGER,
        refused_id=reused["id"],
        asserter=OWNER,
        reason="",
        case_id=net.case_id,
    )
    assert reused_notice["expectedSenderSequence"] == 1

    _wait_out_holds(net, monkeypatch)
    net.receive(MANAGER, late)

    late_notice = assert_refusal_notice(
        manager_dl,
        manager=MANAGER,
        refused_id=late["id"],
        asserter=OWNER,
        reason="",
        case_id=net.case_id,
    )
    assert late_notice["expectedSenderSequence"] == 3
    assert _committed_notes(net) == [_note_of(held)]


@pytest.mark.spec("SYNC-21-015")
@pytest.mark.spec("SYNC-21-017")
def test_an_unnumbered_activity_is_refused_with_a_notice() -> None:
    net = _network("unnumbered")
    unnumbered = _note_body(net, "unnumbered")
    unnumbered.pop("senderSequence", None)
    malformed = {**_note_body(net, "malformed"), "senderSequence": "two"}

    for body in (unnumbered, malformed):
        net.receive(MANAGER, body)

    assert _committed_notes(net) == []
    for body in (unnumbered, malformed):
        notice = assert_refusal_notice(
            net.stores[MANAGER],
            manager=MANAGER,
            refused_id=body["id"],
            asserter=OWNER,
            reason="",
            case_id=net.case_id,
        )
        assert notice["expectedSenderSequence"] == 1


@pytest.mark.spec("SYNC-21-017")
@pytest.mark.parametrize("value", [0, -1, True, 2.5, "1", None, [1]])
def test_a_number_that_is_not_a_positive_integer_draws_a_notice(
    value: object,
) -> None:
    """The parse edge sets a malformed number aside, so the CASE_MANAGER
    refuses it after its guards, with the notice, and the entry it never
    commits would have kept the value as it arrived (VM-08-002)."""
    net = _network(f"malformed-{type(value).__name__}-{value}")
    body = {**_note_body(net, "malformed"), "senderSequence": value}

    net.receive(MANAGER, body)

    assert _committed_notes(net) == []
    notice = assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=body["id"],
        asserter=OWNER,
        reason="SYNC-21-017",
        case_id=net.case_id,
    )
    assert notice["expectedSenderSequence"] == 1
    assert notice["object"]["senderSequence"] == value


@pytest.mark.spec("SYNC-21-022")
def test_each_skipped_number_is_logged_at_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    net = _network("skip-log")
    held = _numbered(_note_body(net, "held"), 3)
    net.receive(MANAGER, held)

    with caplog.at_level("WARNING"):
        _wait_out_holds(net, monkeypatch)

    skipped = [
        r
        for r in caplog.records
        if r.levelname == "WARNING" and "skipped number" in r.getMessage()
    ]
    assert [r.args[0] for r in skipped] == [1, 2]  # type: ignore[index]
    for record in skipped:
        assert OWNER in record.getMessage()
        assert net.case_id in record.getMessage()
    assert _committed_notes(net) == [_note_of(held)]


@pytest.mark.spec("SYNC-21-021")
def test_the_hold_defaults_are_the_documented_ones() -> None:
    ledger = LedgerConfig()
    assert ledger.sender_sequence_hold == DEFAULT_WAIT
    assert ledger.sender_sequence_hold_cap == DEFAULT_CAP


@pytest.mark.spec("SYNC-21-025")
def test_the_case_manager_role_grant_drains_first() -> None:
    """The tree that commits a CASE_MANAGER delegation's acceptance ends the
    holds before the grant (CM-02-016); any other role's grant does not."""

    def _grant_steps(role: CVDRole) -> list[str]:
        tree = create_accept_case_participant_role_tree(
            "https://example.org/cases/drain",
            "https://example.org/offers/1",
            BYSTANDER,
            "https://example.org/answers/1",
            role,
            BYSTANDER,
            sender_rule=AcceptCaseParticipantRoleReceivedUseCase.sender_entitlement,
        )
        names = [
            type(n).__name__
            for n in tree.iterate()
            if isinstance(
                n, (DrainSequenceHoldsNode, GrantCaseParticipantRoleNode)
            )
        ]
        return names

    assert _grant_steps(CVDRole.CASE_MANAGER) == [
        "DrainSequenceHoldsNode",
        "GrantCaseParticipantRoleNode",
    ]
    assert _grant_steps(CVDRole.COORDINATOR) == [
        "GrantCaseParticipantRoleNode"
    ]


@pytest.mark.spec("SYNC-21-023")
def test_a_closed_senders_late_number_draws_no_notice() -> None:
    net = _network("closed-late")
    dl = net.stores[BYSTANDER]
    note = _numbered(_note_body(net, "after-leave", actor=BYSTANDER), 1)
    _leave_id, leave_text = TriggerActivityAdapter(dl).close_case(
        case_id=net.case_id, actor=BYSTANDER, to=[MANAGER]
    )
    net.receive(MANAGER, _numbered(json.loads(leave_text), 1))

    # The note reuses the judged Leave's number, but its sender has left, so
    # the closed-sender door refuses it first, with no notice (CLP-02-005).
    net.receive(MANAGER, note)

    assert _committed_notes(net) == []
    assert_no_refusal_notice(
        net.stores[MANAGER], manager=MANAGER, refused_id=note["id"]
    )


@pytest.mark.spec("SYNC-21-024")
@pytest.mark.spec("SYNC-21-015")
@pytest.mark.spec("SYNC-21-014")
def test_a_late_answer_never_overrides_the_later_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    net = _network("late-answer")
    embargo_id, invite_id = _invited(net, BYSTANDER, "late-answer")
    first = _numbered(_note_body(net, "first", actor=BYSTANDER), 1)
    accept = _numbered(
        _answer_body(net, BYSTANDER, invite_id, accept=True, tag="late-a"), 2
    )
    reject = _numbered(
        _answer_body(net, BYSTANDER, invite_id, accept=False, tag="late-r"), 3
    )
    net.receive(MANAGER, first)

    # The Accept (#2) is lost; the Reject (#3) waits, then the gap is skipped.
    net.receive(MANAGER, reject)
    _wait_out_holds(net, monkeypatch)
    assert _consent(net, BYSTANDER, embargo_id) is EmbargoConsentState.DECLINED
    entries_before = len(ledger_entries(net.stores[MANAGER], net.case_id))

    # The Accept arrives late: the later Reject has countermanded it.
    net.receive(MANAGER, accept)

    assert _consent(net, BYSTANDER, embargo_id) is EmbargoConsentState.DECLINED
    assert (
        len(ledger_entries(net.stores[MANAGER], net.case_id)) == entries_before
    )
    notice = assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=accept["id"],
        asserter=BYSTANDER,
        reason="",
        case_id=net.case_id,
    )
    assert notice["expectedSenderSequence"] == 4


@pytest.mark.spec("SYNC-21-009")
def test_a_new_case_manager_starts_from_the_ledger() -> None:
    net = _network("handover")
    earlier = [_numbered(_note_body(net, f"earlier-{n}"), n) for n in (1, 2)]
    for body in earlier:
        net.receive(MANAGER, body)
    _forget_sequence_state(net, MANAGER)
    third = _numbered(_note_body(net, "third"), 3)
    reused = _numbered(_note_body(net, "reused"), 2)

    # The ledger records numbers 1 and 2, so 3 is judged on arrival.
    net.receive(MANAGER, third)
    assert _committed_notes(net) == [_note_of(b) for b in (*earlier, third)]

    net.receive(MANAGER, reused)
    notice = assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=reused["id"],
        asserter=OWNER,
        reason="",
        case_id=net.case_id,
    )
    assert notice["expectedSenderSequence"] == 4


@pytest.mark.spec("SYNC-21-025")
def test_an_outgoing_case_manager_drains_its_holds() -> None:
    net = _network("drain")
    _note_body(net, "lost")
    held = [_numbered(_note_body(net, f"held-{n}"), n) for n in (2, 3)]
    for body in reversed(held):
        net.receive(MANAGER, body)
    assert _committed_notes(net) == []

    # The wait has not passed; the handover ends it early.
    _hand_over_case_manager(net)

    assert _committed_notes(net) == [_note_of(b) for b in held]
    for body in held:
        assert_no_refusal_notice(
            net.stores[MANAGER], manager=MANAGER, refused_id=body["id"]
        )


@pytest.mark.spec("SYNC-21-018")
def test_a_repeat_is_found_by_id_before_its_number() -> None:
    net = _network("repeat")
    first = _numbered(_note_body(net, "first"), 1)
    second = _numbered(_note_body(net, "second"), 2)

    for body in (second, second, first, first):
        net.receive(MANAGER, body)

    assert _committed_notes(net) == [_note_of(first), _note_of(second)]
    for body in (first, second):
        assert_no_refusal_notice(
            net.stores[MANAGER], manager=MANAGER, refused_id=body["id"]
        )


@pytest.mark.spec("SYNC-21-020")
def test_sequence_state_lives_in_the_datalayer() -> None:
    net = _network("stored")
    first = _note_body(net, "first")
    net.reopen(OWNER)
    second = _note_body(net, "second")
    assert (first["senderSequence"], second["senderSequence"]) == (1, 2)

    net.receive(MANAGER, second)
    net.reopen(MANAGER)
    net.receive(MANAGER, first)

    assert _committed_notes(net) == [_note_of(first), _note_of(second)]
