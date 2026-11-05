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
from vultron.adapters.driven.sender_sequence_stamp import with_outbound_stamps
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.sender_sequence import SenderSequenceCounter
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
