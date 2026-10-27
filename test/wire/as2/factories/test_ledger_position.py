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
"""The factory stamp of a sender's ledger position (SYNC-18-001, SYNC-18-002)."""

import pytest

from vultron.core.models.ledger_position import LedgerPosition
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    add_status_to_participant_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    create_processing_fault_activity,
    ledger_position_case_ids,
    object_states_its_own_position,
    rm_accept_invite_to_case_activity,
    rm_engage_case_activity,
    rm_invite_to_case_activity,
    stamp_ledger_position,
    update_case_activity,
)
from vultron.wire.as2.factories.sync import announce_log_entry_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry
from vultron.wire.as2.vocab.objects.case_status import (
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseStub,
)

_CASE = "https://example.org/cases/stamp"
_ACTOR = "https://example.org/users/vendor"
_TAIL = LedgerPosition(log_index=4, entry_hash="ab" * 32)


def _note():
    return add_note_to_case_activity(
        as_Note(id_=f"{_CASE}/notes/1", content="n", context=_CASE),
        target=_CASE,
        actor=_ACTOR,
    )


@pytest.mark.spec("SYNC-18-002")
def test_the_stamp_is_a_copy_stating_the_position() -> None:
    note = _note()

    stamped = stamp_ledger_position(note, _TAIL)

    assert stamped.ledger_position == _TAIL
    assert note.ledger_position is None
    dumped = stamped.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped["ledgerPosition"] == {"logIndex": 4, "entryHash": "ab" * 32}


@pytest.mark.spec("SYNC-18-002")
def test_a_stamped_activity_keeps_its_first_position() -> None:
    first = stamp_ledger_position(_note(), _TAIL)
    later = LedgerPosition(log_index=9, entry_hash="cd" * 32)

    assert stamp_ledger_position(first, later) is first


@pytest.mark.spec("SYNC-18-001")
def test_the_case_comes_first_from_context_then_target() -> None:
    assert list(ledger_position_case_ids(_note())) == [
        _CASE,
        f"{_CASE}/notes/1",
    ]


@pytest.mark.spec("SYNC-18-001")
def test_a_participant_status_names_its_case_on_the_status() -> None:
    participant_id = f"{_CASE}/participants/vendor"
    add = add_status_to_participant_activity(
        as_ParticipantStatus(id_=f"{participant_id}/s1", context=_CASE),
        target=participant_id,
        actor=_ACTOR,
    )

    assert _CASE in list(ledger_position_case_ids(add))


@pytest.mark.spec("SYNC-18-001")
def test_a_stub_invite_and_its_reply_name_the_case_the_stub_stands_for() -> (
    None
):
    invite = rm_invite_to_case_activity(
        as_Organization(id_="https://example.org/users/invitee"),
        target=as_VulnerabilityCaseStub(case_id=_CASE, summary="a case"),
        actor=_ACTOR,
    )
    reply = rm_accept_invite_to_case_activity(
        invite, actor="https://example.org/users/invitee"
    )

    assert _CASE in list(ledger_position_case_ids(invite))
    assert _CASE in list(ledger_position_case_ids(reply))


@pytest.mark.spec("SYNC-18-001")
@pytest.mark.parametrize(
    "build",
    [
        lambda: announce_log_entry_activity(
            as_CaseLedgerEntry(
                case_id=_CASE,
                log_index=0,
                log_object_id=f"{_CASE}/activities/0",
                semantic_type="create_case",
                payload_snapshot={},
                prev_log_hash="00" * 32,
                entry_hash="11" * 32,
            ),
            actor=_ACTOR,
        ),
        lambda: announce_vulnerability_case_activity(
            as_VulnerabilityCase(id_=_CASE, attributed_to=_ACTOR),
            actor=_ACTOR,
        ),
        lambda: create_case_activity(
            as_VulnerabilityCase(id_=_CASE, attributed_to=_ACTOR),
            actor=_ACTOR,
        ),
        lambda: update_case_activity(
            as_VulnerabilityCase(id_=_CASE, attributed_to=_ACTOR),
            actor=_ACTOR,
        ),
    ],
    ids=["announce-entry", "announce-case", "create-case", "update-case"],
)
def test_an_activity_whose_object_states_its_position_names_no_case(
    build,
) -> None:
    activity = build()

    assert object_states_its_own_position(activity)
    assert list(ledger_position_case_ids(activity)) == []


@pytest.mark.spec("SYNC-18-001")
def test_an_act_on_an_inline_case_names_it_to_be_stamped() -> None:
    join = rm_engage_case_activity(
        as_VulnerabilityCase(id_=_CASE, attributed_to=_ACTOR), actor=_ACTOR
    )

    assert not object_states_its_own_position(join)
    assert list(ledger_position_case_ids(join)) == [_CASE]


@pytest.mark.spec("SYNC-18-001")
def test_a_processing_fault_names_no_case() -> None:
    fault = create_processing_fault_activity(
        actor=_ACTOR,
        fault=as_ProcessingFault(
            failure_class="https://example.org/faults/x",
            in_reply_to=f"{_CASE}/activities/9",
        ),
    )

    assert not object_states_its_own_position(fault)
    assert _CASE not in list(ledger_position_case_ids(fault))


@pytest.mark.spec("SYNC-18-002")
def test_a_stamped_activity_names_no_case_to_stamp_again() -> None:
    stamped = stamp_ledger_position(_note(), _TAIL)

    assert list(ledger_position_case_ids(stamped)) == []
