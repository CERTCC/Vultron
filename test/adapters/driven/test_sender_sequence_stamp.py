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
"""A participant numbers its case activities to the CASE_MANAGER (SYNC-21).

The sender's side of ADR-0178: which activities its adapter numbers, that a
number is used exactly when the body carrying it is sealed, and that a
refusal notice naming an expected number moves the count up.  The
CASE_MANAGER's side is in
``test/core/use_cases/received/test_sender_sequence.py``.
"""

import json
from typing import Any

import pytest

from test.core.use_cases.received._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    LedgerNetwork,
)
from test.support.signing import resigned
from vultron.adapters.driven.sender_sequence_stamp import with_outbound_stamps
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.sender_sequence import SenderSequenceCounter
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.sync_helpers import (
    allocate_sender_sequence,
    resume_sender_sequence_at,
)
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    refusal_notice_activity,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note


class _Abort(Exception):
    """Stands in for a failure after the number is allocated."""


def _network(tag: str) -> LedgerNetwork:
    return LedgerNetwork(f"https://example.org/cases/sender-stamp-{tag}")


def _note_body(
    net: LedgerNetwork, tag: str, *, actor: str = OWNER, to: str = MANAGER
) -> dict[str, Any]:
    dl = net.stores[actor]
    note_id = f"{net.case_id}/notes/{tag}"
    dl.create(as_Note(id_=note_id, content=tag, context=net.case_id))
    _activity_id, body = TriggerActivityAdapter(dl).add_note_to_case(
        note_id=note_id, case_id=net.case_id, actor=actor, to=[to]
    )
    decoded: dict[str, Any] = json.loads(body)
    return decoded


@pytest.mark.spec("SYNC-21-001")
def test_an_activity_not_sent_to_the_case_manager_takes_no_number() -> None:
    net = _network("not-to-manager")

    body = _note_body(net, "aside", to=BYSTANDER)

    assert "ledgerPosition" in body
    assert "senderSequence" not in body
    assert _note_body(net, "to-manager")["senderSequence"] == 1


@pytest.mark.spec("SYNC-21-002")
def test_each_sender_counts_on_its_own() -> None:
    net = _network("per-sender")
    _note_body(net, "owner-1")
    _note_body(net, "owner-2")

    first = _note_body(net, "bystander-1", actor=BYSTANDER)

    assert first["senderSequence"] == 1


@pytest.mark.spec("SYNC-21-003")
@pytest.mark.spec("SYNC-21-020")
def test_a_number_whose_body_is_never_sealed_is_given_back() -> None:
    net = _network("rollback")
    dl = net.stores[OWNER]
    note = add_note_to_case_activity(
        as_Note(id_=f"{net.case_id}/notes/lost", context=net.case_id),
        target=net.case_id,
        actor=OWNER,
        to=[MANAGER],
    )

    with pytest.raises(_Abort):
        with dl.transaction():
            assert with_outbound_stamps(dl, note).sender_sequence == 1
            raise _Abort

    assert dl.read(SenderSequenceCounter.build_id(net.case_id, OWNER)) is None
    assert _note_body(net, "sealed")["senderSequence"] == 1


@pytest.mark.spec("SYNC-21-020")
def test_the_count_is_a_stored_record() -> None:
    net = _network("record")
    _note_body(net, "one")
    _note_body(net, "two")

    stored = net.stores[OWNER].read(
        SenderSequenceCounter.build_id(net.case_id, OWNER)
    )

    assert isinstance(stored, SenderSequenceCounter)
    assert stored.last_used == 2


@pytest.mark.spec("SYNC-21-007")
def test_a_refusal_notice_moves_the_count_up_to_the_expected_number() -> None:
    net = _network("notice")
    refused = _note_body(net, "refused")
    notice = refusal_notice_activity(
        refused,
        "senderSequence 1 is below the next expected number 7",
        actor=MANAGER,
        to=[OWNER],
        id_=derived_activity_id("refusal-notice", MANAGER, refused["id"]),
        context=net.case_id,
        expected_sender_sequence=7,
    )
    body = json.loads(notice.model_dump_json(by_alias=True, exclude_none=True))
    assert body["expectedSenderSequence"] == 7

    net.receive(OWNER, body)

    assert _note_body(net, "resumed")["senderSequence"] == 7


@pytest.mark.spec("SYNC-21-007")
def test_a_stale_expected_number_never_moves_the_count_down() -> None:
    net = _network("stale")
    dl = net.stores[OWNER]
    for _ in range(3):
        allocate_sender_sequence(dl, net.case_id, OWNER)

    assert not resume_sender_sequence_at(dl, net.case_id, OWNER, 2)
    assert allocate_sender_sequence(dl, net.case_id, OWNER) == 4


def _bare_note(net: LedgerNetwork, tag: str, *, to: object) -> Any:
    return add_note_to_case_activity(
        as_Note(id_=f"{net.case_id}/notes/{tag}", context=net.case_id),
        target=net.case_id,
        actor=OWNER,
        to=[MANAGER],
    ).model_copy(update={"to": to})


@pytest.mark.spec("SYNC-21-001")
def test_a_single_recipient_to_is_numbered() -> None:
    net = _network("string-to")
    dl = net.stores[OWNER]

    with dl.transaction():
        stamped = with_outbound_stamps(dl, _bare_note(net, "one", to=MANAGER))

    assert stamped.sender_sequence == 1


@pytest.mark.spec("SYNC-21-001")
def test_an_activity_to_the_participants_collection_is_numbered() -> None:
    net = _network("collection-to")
    dl = net.stores[OWNER]
    note = _bare_note(net, "all", to=[f"{net.case_id}/participants"])

    with dl.transaction():
        stamped = with_outbound_stamps(dl, note)

    assert stamped.sender_sequence == 1


@pytest.mark.spec("SYNC-21-003")
def test_a_trigger_whose_seal_fails_gives_its_number_back(monkeypatch) -> None:
    net = _network("seal-fails")

    def _fail(*_args: object, **_kwargs: object) -> str:
        raise _Abort

    with monkeypatch.context() as patch:
        patch.setattr(
            "vultron.adapters.driven.trigger_activity_adapter._base"
            ".seal_outbound_body",
            _fail,
        )
        with pytest.raises(_Abort):
            _note_body(net, "lost")

    stored = net.stores[OWNER].read(
        SenderSequenceCounter.build_id(net.case_id, OWNER)
    )
    assert stored is None
    assert _note_body(net, "sealed")["senderSequence"] == 1


@pytest.mark.spec("SYNC-21-007")
def test_a_resume_under_another_spelling_of_the_sender_is_the_same_count() -> (
    None
):
    net = _network("spelling")
    dl = net.stores[OWNER]

    assert resume_sender_sequence_at(dl, net.case_id, f"{OWNER}/", 4)
    assert allocate_sender_sequence(dl, net.case_id, OWNER) == 4


def _notice_body(
    net: LedgerNetwork, refused: dict[str, Any], expected: int
) -> dict[str, Any]:
    notice = refusal_notice_activity(
        refused,
        f"senderSequence is below the next expected number {expected}",
        actor=MANAGER,
        to=[OWNER],
        id_=derived_activity_id("refusal-notice", MANAGER, refused["id"]),
        context=net.case_id,
        expected_sender_sequence=expected,
    )
    decoded: dict[str, Any] = json.loads(
        notice.model_dump_json(by_alias=True, exclude_none=True)
    )
    return decoded


@pytest.mark.spec("SYNC-21-007")
def test_a_notice_that_only_moves_the_count_is_applied() -> None:
    net = _network("notice-applied")
    # An id with no pending assertion, so only the count can move.
    refused = resigned(
        _note_body(net, "refused"), id=f"{net.case_id}/unpending"
    )

    result = net.receive(OWNER, _notice_body(net, refused, 7))

    assert result.disposition is HandlerDisposition.APPLIED


@pytest.mark.spec("SYNC-21-007")
def test_a_stale_notice_with_nothing_to_close_is_skipped() -> None:
    net = _network("notice-stale")
    refused = resigned(
        _note_body(net, "refused"), id=f"{net.case_id}/unpending"
    )
    for _ in range(3):
        allocate_sender_sequence(net.stores[OWNER], net.case_id, OWNER)

    result = net.receive(OWNER, _notice_body(net, refused, 2))

    assert result.disposition is HandlerDisposition.SKIPPED
