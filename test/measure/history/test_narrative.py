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

"""The case narrative: one line per ledger entry (#6670).

Each line names the entry's two times in their own fields, the actor and
object by display name, the registry phrase, and every state change the
entry caused in RM, EM, VFD and PXA.  A ledger read up to an entry yields
the narrative's lines up to that entry, so a followed case only adds lines.

Spec: CEH-01-006, CEH-01-007, CEH-03-007, CEH-03-008, DRPT-03-004.
"""

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from test.measure.history.builders import (
    CASE,
    CM,
    EMBARGO_2,
    OWNER,
    REPORTER,
    VENDOR,
    Ledger,
    embargo,
    publish,
    seat_vendor,
    stamp,
    status,
)
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.history import (
    StateChange,
    StateMachine,
    case_narrative,
    derive_case_steps,
)
from vultron.measure.ledger import (
    LedgerFile,
    LedgerRow,
    case_ledgers_from_files,
    read_case_ledgers,
    render_event_phrase,
)

_RECORDING = RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"


def _at(second: int) -> datetime:
    return datetime.fromisoformat(stamp(second))


def _change(machine, before, after, participant=None) -> StateChange:
    return StateChange(
        machine=machine, participant=participant, before=before, after=after
    )


def _vendor_case() -> Ledger:
    """Genesis, a seated Vendor, its validation and its fix, a proposal,
    and the case's publication."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.add_status(
        VENDOR, status("v-v", VENDOR, "VALID", vf="Vf", roles=("VENDOR",))
    )
    ledger.add_status(
        VENDOR, status("v-f", VENDOR, "VALID", vf="VF", roles=("VENDOR",))
    )
    ledger.add(
        "invite_to_embargo_on_case", "Invite", REPORTER, embargo(EMBARGO_2)
    )
    publish(ledger, "Pxa")
    return ledger


def test_each_entry_has_one_line_in_log_index_order():
    """AC-1: one line per ledger entry, in log-index order."""
    ledger = _vendor_case()
    lines = case_narrative(ledger.case_ledger())
    assert [line.log_index for line in lines] == list(
        range(len(ledger.entries))
    )


@pytest.mark.spec("CEH-03-007")
@pytest.mark.spec("CEH-03-008")
def test_a_line_keeps_the_claimed_time_and_the_commit_stamp_apart():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add("add_note_to_case", "Add", REPORTER, claimed=stamp(3))
    ledger.add("add_note_to_case", "Add", REPORTER, claimed=None)
    genesis, same, unclaimed = case_narrative(ledger.case_ledger())
    assert (genesis.claimed_at, genesis.committed_at) == (_at(0), _at(1))
    assert genesis.commit_differs
    assert same.claimed_at == same.committed_at == _at(3)
    assert not same.commit_differs
    assert unclaimed.claimed_at is None
    assert unclaimed.committed_at == _at(5)
    assert unclaimed.commit_differs


@pytest.mark.spec("CEH-01-006")
@pytest.mark.spec("CEH-01-007")
@pytest.mark.spec("DRPT-03-004")
def test_a_line_names_the_actor_and_object_and_reads_the_registry_phrase():
    """AC-2: who did what, by display name and registry phrase."""
    ledger = _vendor_case()
    ledger.entries[0]["payloadSnapshot"]["actor"] = {
        "id": CM,
        "type": "Service",
        "name": "Coordination Desk",
    }
    lines = case_narrative(ledger.case_ledger())
    created = lines[0]
    assert created.actor_id == CM
    assert created.actor == "Coordination Desk"
    assert created.semantic_type == "create_case"
    assert created.object == "case"
    assert created.phrase == render_event_phrase(
        "create_case", "Coordination Desk", "case"
    )
    proposal = lines[4]
    assert proposal.actor == "Reporter"
    assert proposal.object == "embargo"
    assert proposal.phrase == "Reporter proposed an embargo"


def test_a_line_lists_every_state_change_its_entry_caused():
    """AC-2: RM, EM, VFD and PXA changes, each on the entry that made it."""
    lines = case_narrative(_vendor_case().case_ledger())
    rm, em, vfd, pxa = (
        StateMachine.RM,
        StateMachine.EM,
        StateMachine.VFD,
        StateMachine.PXA,
    )
    assert lines[0].changes == (
        _change(rm, "START", "ACCEPTED", CM),
        _change(rm, "START", "RECEIVED", OWNER),
        _change(rm, "START", "ACCEPTED", REPORTER),
        _change(em, "NONE", "ACTIVE"),
    )
    assert lines[1].changes == (
        _change(rm, "START", "RECEIVED", VENDOR),
        _change(vfd, "vfd", "Vfd", VENDOR),
    )
    assert lines[2].changes == (_change(rm, "RECEIVED", "VALID", VENDOR),)
    assert lines[3].changes == (_change(vfd, "Vfd", "VFd", VENDOR),)
    assert lines[4].changes == (_change(em, "ACTIVE", "REVISE"),)
    assert lines[5].changes == (_change(pxa, "pxa", "Pxa"),)


@pytest.mark.spec("CEH-04-013")
@pytest.mark.spec("CEH-04-015")
def test_an_entry_that_moves_no_state_forward_lists_no_change():
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "VF")
    ledger.add_status(VENDOR, status("v-again", VENDOR, "RECEIVED", vf="VF"))
    ledger.add_status(VENDOR, status("v-back", VENDOR, "RECEIVED", vf="Vf"))
    ledger.add("add_note_to_case", "Add", REPORTER)
    lines = case_narrative(ledger.case_ledger())
    assert [line.changes for line in lines[2:]] == [(), (), ()]


def test_an_entry_the_walk_cannot_read_keeps_its_line_and_says_why():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add("future_thing", "Note", REPORTER)
    ledger.add("add_note_to_case", "Add", REPORTER)
    del ledger.entries[2]["published"]
    _, future, unstamped = case_narrative(ledger.case_ledger())
    assert future.phrase == "Future thing"
    assert future.changes == ()
    assert future.notes == ("unknown semantic type 'future_thing'",)
    assert unstamped.committed_at is None
    assert not unstamped.commit_differs
    assert unstamped.notes == ("no commit stamp",)


def test_an_entry_with_no_semantic_type_reads_as_an_action():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add("add_note_to_case", "Add", REPORTER)
    del ledger.entries[1]["semanticType"]
    _, untyped = case_narrative(ledger.case_ledger())
    assert untyped.semantic_type is None
    assert untyped.phrase == "Performed an action"
    assert untyped.actor == "Reporter"
    assert untyped.notes


def test_a_register_with_no_em_state_says_so_once_and_changes_no_em():
    ledger = Ledger()
    ledger.standard_genesis()
    broken = {
        "id": CASE,
        "type": "VulnerabilityCase",
        "embargoRegister": [
            {**embargo(), "status": "ACTIVE"},
            {**embargo(EMBARGO_2), "status": "TERMINATED"},
        ],
    }
    ledger.add("announce_vulnerability_case", "Announce", CM, broken)
    ledger.add("announce_vulnerability_case", "Announce", CM, broken)
    _, first, second = case_narrative(ledger.case_ledger())
    (note,) = first.notes
    assert note.startswith("Embargo register breaks its invariants: ")
    assert "ACTIVE" in note and "TERMINATED" in note
    assert first.changes == second.changes == ()
    assert second.notes == ()


def test_a_register_broken_another_way_says_so_again():
    ledger = Ledger()
    ledger.genesis([], with_embargo=False)
    for register in (
        [{**embargo(), "status": "SUPERSEDED"}],
        [
            {**embargo(EMBARGO_2), "status": "PROPOSED"},
            {**embargo("urn:uuid:embargo-3"), "status": "TERMINATED"},
        ],
    ):
        ledger.add(
            "announce_vulnerability_case",
            "Announce",
            CM,
            {
                "id": CASE,
                "type": "VulnerabilityCase",
                "embargoRegister": register,
            },
        )
    _, first, second = case_narrative(ledger.case_ledger())
    (first_note,) = first.notes
    (second_note,) = second.notes
    assert "SUPERSEDED" in first_note
    assert "PROPOSED while another is TERMINATED" in second_note
    assert first.changes == second.changes == ()


def test_a_line_after_a_hole_names_the_entries_missing_before_it():
    ledger = _vendor_case()
    del ledger.entries[2:4]
    case_ledger = ledger.case_ledger()
    assert case_ledger.missing_log_indices == [2, 3]
    lines = case_narrative(case_ledger)
    assert [line.log_index for line in lines] == [0, 1, 4, 5]
    assert lines[2].notes == ("No entry at log indices 2, 3 before this one",)
    assert [line.notes for line in (lines[0], lines[1], lines[3])] == [
        (),
        (),
        (),
    ]


def test_a_line_where_the_copies_disagree_says_so():
    ledger = _vendor_case()
    other = Ledger(entries=[dict(entry) for entry in ledger.entries])
    other.entries[1] = {**other.entries[1], "entryHash": "hash-other"}
    rows = [
        LedgerRow(path=Path(name), line=i + 1, data=entry)
        for name, copy in (("a.jsonl", ledger), ("b.jsonl", other))
        for i, entry in enumerate(copy.entries)
    ]
    files = [
        LedgerFile(
            path=Path(name), rows=[r for r in rows if r.path == Path(name)]
        )
        for name in ("a.jsonl", "b.jsonl")
    ]
    (case_ledger,) = case_ledgers_from_files(files).cases.values()
    assert 1 in case_ledger.conflicting_log_indices
    lines = case_narrative(case_ledger)
    at_one = [line for line in lines if line.log_index == 1]
    assert len(at_one) == 2
    assert all(
        "The ledger's copies disagree at this log index" in line.notes
        for line in at_one
    )


def test_a_line_where_only_one_index_is_missing_names_it():
    ledger = _vendor_case()
    del ledger.entries[3]
    lines = case_narrative(ledger.case_ledger())
    assert lines[3].notes == ("No entry at log index 3 before this one",)


def test_each_hole_is_named_on_the_line_after_it_the_first_one_included():
    """A missing log index 0 is named on the first line, and two holes in one
    ledger are each named once, on the line that follows them."""
    ledger = _vendor_case()
    del ledger.entries[4]
    del ledger.entries[0]
    case_ledger = ledger.case_ledger()
    assert case_ledger.missing_log_indices == [0, 4]
    lines = case_narrative(case_ledger)
    assert [line.log_index for line in lines] == [1, 2, 3, 5]
    assert "No entry at log index 0 before this one" in lines[0].notes
    assert "No entry at log index 4 before this one" in lines[3].notes
    holes = [
        n for line in lines for n in line.notes if n.startswith("No entry")
    ]
    assert holes == [
        "No entry at log index 0 before this one",
        "No entry at log index 4 before this one",
    ]


def test_a_narrative_read_from_a_walk_already_taken_is_the_same():
    case_ledger = _vendor_case().case_ledger()
    derived = derive_case_steps(case_ledger)
    assert case_narrative(case_ledger, derived=derived) == case_narrative(
        case_ledger
    )


def test_an_em_change_after_a_broken_register_reads_from_the_last_em_state():
    ledger = Ledger()
    ledger.genesis([], with_embargo=False)
    ledger.add(
        "announce_vulnerability_case",
        "Announce",
        CM,
        {
            "id": CASE,
            "type": "VulnerabilityCase",
            "embargoRegister": [
                {**embargo(), "status": "SUPERSEDED"},
            ],
        },
    )
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2))
    _, broken, active = case_narrative(ledger.case_ledger())
    assert broken.changes == ()
    assert broken.notes
    assert active.notes == ()
    assert active.changes == (_change(StateMachine.EM, "NONE", "ACTIVE"),)


def test_every_line_up_to_an_entry_is_the_one_its_prefix_reads():
    """AC-3: a ledger read up to an entry reads the same lines, so a
    followed case adds lines and loses none."""
    (ledger,) = read_case_ledgers([_RECORDING]).cases.values()
    full = case_narrative(ledger)
    assert len(full) == len(ledger.rows)
    for end in (1, len(ledger.rows) // 2, len(ledger.rows) - 1):
        rows = [placed.row for placed in ledger.rows[:end]]
        (prefix,) = case_ledgers_from_files(
            [LedgerFile(path=_RECORDING, rows=rows)]
        ).cases.values()
        assert case_narrative(prefix) == full[:end]


def test_a_recorded_case_reads_its_embargo_revisions():
    (ledger,) = read_case_ledgers([_RECORDING]).cases.values()
    em = [
        (change.before, change.after)
        for line in case_narrative(ledger)
        for change in line.changes
        if change.machine is StateMachine.EM
    ]
    assert em == [
        ("NONE", "ACTIVE"),
        ("ACTIVE", "REVISE"),
        ("REVISE", "ACTIVE"),
        ("ACTIVE", "REVISE"),
        ("REVISE", "ACTIVE"),
        ("ACTIVE", "EXITED"),
    ]


@pytest.mark.parametrize(
    ("machine", "participant", "message"),
    [
        (StateMachine.RM, None, "names a participant"),
        (StateMachine.VFD, None, "names a participant"),
        (StateMachine.EM, VENDOR, "belongs to the case"),
        (StateMachine.PXA, VENDOR, "belongs to the case"),
    ],
)
def test_a_change_names_a_participant_exactly_when_its_machine_has_one(
    machine, participant, message
):
    with pytest.raises(ValidationError, match=message):
        _change(machine, "a", "b", participant)


def test_a_state_to_itself_is_no_change():
    with pytest.raises(ValidationError, match="no change"):
        _change(StateMachine.EM, "ACTIVE", "ACTIVE")
