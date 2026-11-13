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

"""The states a ledger has reached at its last entry (``derive_case``)."""

import pytest

from test.measure.history.builders import (
    CM,
    EMBARGO,
    EMBARGO_2,
    INVITEE,
    OWNER,
    REPORTER,
    VENDOR,
    Ledger,
    embargo,
    participant,
    publish,
    seat_vendor,
    status,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.rm import RM
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.history import (
    RM_EVENT_KINDS,
    ReachedParticipant,
    ReachedState,
    derive_case,
)

_S = EmbargoRegisterStatus


def _reached(ledger: Ledger) -> ReachedState:
    return derive_case(ledger.case_ledger())[1]


def _propose(ledger: Ledger, embargo_id: str = EMBARGO_2) -> int:
    return ledger.add(
        "invite_to_embargo_on_case", "Invite", REPORTER, embargo(embargo_id)
    )


def test_a_joined_participant_reaches_the_state_of_its_last_rm_event():
    """The reached state and the events come from one walk, so they agree."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.add_status(
        VENDOR, status("v-v", VENDOR, "VALID", vf="Vf", roles=("VENDOR",))
    )
    history, reached = derive_case(ledger.case_ledger())
    by_kind = {kind: rm for rm, kind in RM_EVENT_KINDS.items()}
    for reached_one in reached.participants:
        rm_events = [
            e
            for e in history.for_participant(reached_one.participant)
            if e.kind in by_kind
        ]
        assert reached_one.rm is by_kind[rm_events[-1].kind]


def test_each_participant_keeps_the_last_state_it_reached():
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.add_status(
        VENDOR, status("v-v", VENDOR, "VALID", vf="Vf", roles=("VENDOR",))
    )
    reached = _reached(ledger)
    assert [p.participant for p in reached.participants] == [
        CM,
        OWNER,
        REPORTER,
        VENDOR,
    ]
    vendor = reached.for_participant(VENDOR)
    assert vendor == ReachedParticipant(
        participant=VENDOR, rm=RM.VALID, roles=("VENDOR",), joined=True
    )
    assert reached.for_participant(CM).rm is RM.ACCEPTED
    assert reached.for_participant("urn:unknown") is None


@pytest.mark.spec("CEH-04-015")
def test_a_state_behind_the_one_reached_is_not_reached():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    ledger.add_status(OWNER, status("owner-r2", OWNER, "RECEIVED"))
    assert _reached(ledger).for_participant(OWNER).rm is RM.VALID


@pytest.mark.spec("CEH-04-010")
def test_an_inert_invitee_reaches_its_state_without_a_case_event():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.seat(
        participant(
            INVITEE,
            [status("inv-r", INVITEE, "RECEIVED")],
            roles=("VENDOR",),
            joined=False,
        )
    )
    ledger.add_status(INVITEE, status("inv-c", INVITEE, "CLOSED"))
    history, reached = derive_case(ledger.case_ledger())
    assert history.for_participant(INVITEE) == []
    invitee = reached.for_participant(INVITEE)
    assert (invitee.rm, invitee.joined) == (RM.CLOSED, False)


def test_the_case_reaches_the_public_state_it_adopts():
    ledger = Ledger()
    ledger.standard_genesis()
    publish(ledger, "Pxa")
    reached = _reached(ledger)
    assert reached.pxa is CS_pxa.Pxa
    assert reached.model_dump(mode="json")["pxa"] == "Pxa"


def test_the_genesis_register_is_carried():
    ledger = Ledger()
    ledger.standard_genesis()
    reached = _reached(ledger)
    assert reached.embargo_register == {EMBARGO: _S.ACTIVE}
    assert reached.em() is EM.ACTIVE


def test_no_embargo_is_em_none():
    ledger = Ledger()
    ledger.genesis([], with_embargo=False)
    assert _reached(ledger).em() is EM.NONE


def test_a_proposal_with_no_embargo_in_force_is_proposed():
    ledger = Ledger()
    ledger.genesis([], with_embargo=False)
    _propose(ledger)
    _propose(ledger)  # the CASE_MANAGER's fan-out of the one proposal
    reached = _reached(ledger)
    assert reached.embargo_register == {EMBARGO_2: _S.PROPOSED}
    assert reached.em() is EM.PROPOSED


def test_a_proposal_beside_the_embargo_in_force_is_revise():
    ledger = Ledger()
    ledger.standard_genesis()
    _propose(ledger)
    assert _reached(ledger).em() is EM.REVISE


def test_an_activation_supersedes_the_embargo_in_force():
    ledger = Ledger()
    ledger.standard_genesis()
    _propose(ledger)
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2))
    reached = _reached(ledger)
    assert reached.embargo_register == {
        EMBARGO: _S.SUPERSEDED,
        EMBARGO_2: _S.ACTIVE,
    }
    assert reached.em() is EM.ACTIVE


def test_the_owners_rejection_closes_a_proposal():
    ledger = Ledger()
    ledger.genesis([], with_embargo=False)
    _propose(ledger)
    ledger.add(
        "reject_embargo_proposal_on_case", "Reject", OWNER, embargo(EMBARGO_2)
    )
    reached = _reached(ledger)
    assert reached.embargo_register == {EMBARGO_2: _S.REJECTED}
    assert reached.em() is EM.NONE


def test_an_undone_invitation_cancels_its_proposal():
    ledger = Ledger()
    ledger.standard_genesis()
    _propose(ledger)
    ledger.add(
        "undo_invite_to_embargo_on_case",
        "Undo",
        CM,
        {"id": "urn:uuid:invite-2", "type": "Invite", "object": EMBARGO_2},
    )
    reached = _reached(ledger)
    assert reached.embargo_register[EMBARGO_2] is _S.CANCELLED
    assert reached.em() is EM.ACTIVE


def test_closing_an_unknown_or_settled_proposal_changes_nothing():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add(
        "reject_embargo_proposal_on_case", "Reject", OWNER, embargo(EMBARGO)
    )
    ledger.add(
        "reject_embargo_proposal_on_case", "Reject", OWNER, embargo(EMBARGO_2)
    )
    assert _reached(ledger).embargo_register == {EMBARGO: _S.ACTIVE}


@pytest.mark.spec("CEH-04-005")
def test_a_termination_exits_and_cancels_every_open_proposal():
    """EP-08-004: termination cancels every proposal in the same step."""
    ledger = Ledger()
    ledger.standard_genesis()
    _propose(ledger)
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(),
        content="EARLY",
    )
    reached = _reached(ledger)
    assert reached.embargo_register == {
        EMBARGO: _S.TERMINATED,
        EMBARGO_2: _S.CANCELLED,
    }
    assert reached.em() is EM.EXITED


def test_a_carried_register_never_reopens_a_final_entry():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(),
        content="EARLY",
    )
    ledger.add(
        "announce_vulnerability_case",
        "Announce",
        CM,
        {
            "id": "urn:uuid:case-1",
            "type": "VulnerabilityCase",
            "embargoRegister": [
                {"embargo": embargo(), "status": "PROPOSED"},
                {"embargo": embargo(EMBARGO_2), "status": "PROPOSED"},
            ],
        },
    )
    assert _reached(ledger).embargo_register == {
        EMBARGO: _S.TERMINATED,
        EMBARGO_2: _S.PROPOSED,
    }


def test_a_register_breaking_its_invariants_has_no_em():
    reached = ReachedState(
        embargo_register={EMBARGO: _S.ACTIVE, EMBARGO_2: _S.TERMINATED}
    )
    with pytest.raises(VultronInvalidStateTransitionError):
        reached.em()


def test_a_participant_is_listed_once():
    with pytest.raises(ValueError, match="more than once"):
        ReachedState(
            participants=[
                ReachedParticipant(participant=VENDOR),
                ReachedParticipant(participant=VENDOR),
            ]
        )


def test_roles_are_sorted_and_listed_once():
    with pytest.raises(ValueError, match="sorted"):
        ReachedParticipant(participant=VENDOR, roles=("VENDOR", "DEPLOYER"))


def test_a_stale_carried_status_never_moves_an_entry_back():
    """A later snapshot still listing the embargo as proposed."""
    ledger = Ledger()
    ledger.standard_genesis()
    _propose(ledger)
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2))
    ledger.add(
        "announce_vulnerability_case",
        "Announce",
        CM,
        {
            "id": "urn:uuid:case-1",
            "type": "VulnerabilityCase",
            "embargoRegister": [
                {"embargo": embargo(), "status": "ACTIVE"},
                {"embargo": embargo(EMBARGO_2), "status": "PROPOSED"},
            ],
        },
    )
    reached = _reached(ledger)
    assert reached.embargo_register == {
        EMBARGO: _S.SUPERSEDED,
        EMBARGO_2: _S.ACTIVE,
    }
    assert reached.em() is EM.ACTIVE


def test_an_activation_never_reopens_a_rejected_proposal():
    ledger = Ledger()
    ledger.standard_genesis()
    _propose(ledger)
    ledger.add(
        "reject_embargo_proposal_on_case", "Reject", OWNER, embargo(EMBARGO_2)
    )
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2))
    reached = _reached(ledger)
    assert reached.embargo_register == {
        EMBARGO: _S.ACTIVE,
        EMBARGO_2: _S.REJECTED,
    }


def test_a_termination_of_an_unrecorded_embargo_records_it_ended():
    """A merge missing the activation still ends the embargo."""
    ledger = Ledger()
    ledger.genesis([], with_embargo=False)
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(EMBARGO_2),
        content="EARLY",
    )
    assert _reached(ledger).embargo_register == {EMBARGO_2: _S.TERMINATED}
