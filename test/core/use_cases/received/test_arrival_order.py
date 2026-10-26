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
"""No coordination decision may depend on arrival order (SYNC-19, ADR-0161).

The transport promises no order (ADR-0037), so a message the CASE_MANAGER
sends outside the ledger can reach a participant before, between or after
the ledger entries it relates to.  ``TestRevisionInvitePermutations``
delivers one such scenario in every order and asserts one final case file.
Each ``xfail(strict=True)`` test below reproduces an order dependency the
arrival-order audit found; it passes, and so fails loudly, once its Bug is
fixed.
"""

import itertools
import json
from typing import Any, cast

import pytest

from test.core.use_cases.received import (
    test_embargo_ending_notices as notices,
)
from test.support.embargo_register import activate, propose
from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import case_file_differences
from test.support.relayed_invite import (
    INVITEE,
    answers_in_outbox,
    deliver_relayed_invite,
    seed_invitee_case,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import (
    dump_outbound_body,
    read_sealed_body_dict,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.held_ledger_announces import held_ledger_announces
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    announce_embargo_activity,
    remove_embargo_from_case_activity,
    rm_close_case_activity,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._ledger_network import BYSTANDER, MANAGER, LedgerNetwork
from .test_embargo_activation_copy import _propose
from .test_embargo_answer_idempotency import _answer_body, _invited

_PROPOSAL_TYPE = "invite_to_embargo_on_case"


def _bodies_for(net: LedgerNetwork, recipient: str) -> list[dict[str, Any]]:
    """The sealed bodies the CASE_MANAGER queued for *recipient*, in order."""
    return [
        cast(dict[str, Any], read_sealed_body_dict(net.stores[MANAGER], a.id_))
        for a in net.queued(MANAGER, to=recipient)
    ]


def _entry(body: dict[str, Any]) -> dict[str, Any]:
    """The ``CaseLedgerEntry`` an ``Announce`` carries, or ``{}``."""
    obj = body.get("object")
    if body.get("type") != "Announce" or not isinstance(obj, dict):
        return {}
    return obj if obj.get("type") == "CaseLedgerEntry" else {}


def _answers(net: LedgerNetwork, actor: str, invite_id: str) -> list[str]:
    """The types of *actor*'s queued answers to *invite_id*.

    A gap ``Reject(CaseLedgerEntry)`` the replica sends on an entry that
    overtook its predecessor is replication signalling, not an answer.
    """
    answers = []
    for activity in net.queued(actor, to=MANAGER):
        body = read_sealed_body_dict(net.stores[actor], activity.id_) or {}
        obj = body.get("object")
        obj_id = obj.get("id") if isinstance(obj, dict) else obj
        if obj_id == invite_id:
            answers.append(str(body.get("type")))
    return answers


def _addressed_to(entry: dict[str, Any], actor: str) -> bool:
    """Whether the activity *entry* records was sent to *actor*."""
    snapshot = entry.get("payloadSnapshot") or {}
    recipients = snapshot.get("to") or []
    if isinstance(recipients, str):
        recipients = [recipients]
    return actor in recipients


def _stored_hashes(net: LedgerNetwork, actor: str) -> set[str]:
    """The hashes of the entries *actor*'s replica has stored."""
    return {
        e.entry_hash for e in ledger_entries(net.stores[actor], net.case_id)
    }


def _held_hashes(net: LedgerNetwork, actor: str) -> set[str]:
    """The hashes of the entries *actor*'s replica holds out of order."""
    return {
        h.entry_hash
        for h in held_ledger_announces(net.stores[actor], net.case_id)
    }


class TestRevisionInvitePermutations:
    """The revision Invite races its own ledger entries (EP-09-002, SYNC-19).

    A revision proposal reaches a participant as three related units: the
    ``Announce`` of the proposal entry (its ``PROPOSE`` register step); the
    relayed ``Invite(EmbargoEvent)``; and the rest of the act's entries in
    chain order, which end with the entry recording the Invite's emission to
    that participant.  Each of the six orders of the three is delivered, and
    the test first checks that the order really happened.  When the entries
    arrive, the replica holds them out of order if the proposal has not come
    yet, and stores them if it has.  When the Invite arrives, the replica
    has stored the proposal entry only if the proposal came first, has stored
    the emission entry only if both entry units did, and holds it only if the
    entries came first and the proposal last.  Every order
    must leave the participant with the CASE_MANAGER's case file, the relayed
    Invite indexed as the proposal it answers, and one answer.
    """

    @pytest.mark.spec("SYNC-19-001")
    @pytest.mark.spec("SYNC-19-002")
    @pytest.mark.spec("SYNC-19-003")
    @pytest.mark.parametrize(
        "order",
        list(itertools.permutations(range(3))),
        ids=lambda order: "-".join(
            ("proposal", "entries", "invite")[i] for i in order
        ),
    )
    def test_every_order_reaches_one_case_file(
        self, order: tuple[int, ...]
    ) -> None:
        net = LedgerNetwork(
            "https://example.org/cases/perm-" + "".join(map(str, order))
        )
        revision_id = _propose(net, "shorter", 20)
        bodies = _bodies_for(net, BYSTANDER)
        announces = [b for b in bodies if _entry(b)]
        invites = [b for b in bodies if b.get("type") == "Invite"]
        assert len(invites) == 1, [b.get("type") for b in bodies]
        proposal, *entries = announces
        assert _entry(proposal)["semanticType"] == _PROPOSAL_TYPE
        (emission,) = [
            b
            for b in entries
            if _entry(b)["semanticType"] == _PROPOSAL_TYPE
            and _addressed_to(_entry(b), BYSTANDER)
        ]
        units: tuple[list[dict[str, Any]], ...] = (
            [proposal],
            entries,
            [invites[0]],
        )

        emission_hash = _entry(emission)["entryHash"]
        stored_at_invite: set[str] = set()
        held_at_invite: set[str] = set()
        emission_held_on_arrival = False
        for unit in order:
            if unit == 2:
                stored_at_invite = _stored_hashes(net, BYSTANDER)
                held_at_invite = _held_hashes(net, BYSTANDER)
            for body in units[unit]:
                net.receive(BYSTANDER, body)
            if unit == 1:
                emission_held_on_arrival = emission_hash in _held_hashes(
                    net, BYSTANDER
                )

        # The order was realized, not undone by holding (SYNC-14): these
        # observations differ for each of the six orders.
        proposal_before_invite = order.index(0) < order.index(2)
        entries_before_invite = order.index(1) < order.index(2)
        entries_before_proposal = order.index(1) < order.index(0)
        assert emission_held_on_arrival is entries_before_proposal
        assert (_entry(proposal)["entryHash"] in stored_at_invite) is (
            proposal_before_invite
        )
        assert (emission_hash in stored_at_invite) is (
            proposal_before_invite and entries_before_invite
        )
        assert (emission_hash in held_at_invite) is (
            entries_before_invite and not proposal_before_invite
        )
        assert (
            case_file_differences(
                net.stores[MANAGER], net.stores[BYSTANDER], net.case_id
            )
            == []
        )
        replica = net.case(BYSTANDER)
        assert (
            replica.pending_embargo_proposal_index[revision_id]
            == (invites[0]["id"])
        )
        assert _answers(net, BYSTANDER, invites[0]["id"]) == ["Accept"]


# -- order dependencies the audit found (SYNC-19-001) ------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SYNC-19-001: the owner's auto-accept of a relayed first-proposal"
        " Invite reads EM NONE, which the proposal's own PROPOSE entry"
        " changes. Tracked by #5199."
    ),
)
@pytest.mark.spec("SYNC-19-001")
def test_owner_answer_to_first_proposal_does_not_depend_on_its_entry(
    make_payload,
) -> None:
    """The owner's answer is the same whether the PROPOSE entry came first."""
    answers = {}
    for entry_first in (False, True):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE)
        case, embargo = seed_invitee_case(
            dl,
            f"https://example.org/cases/owner-first-{entry_first}",
            em_state=EM.NONE,
            roles=[CVDRole.CASE_OWNER],
            proposal_days=10,
            policy_days=30,
        )
        if entry_first:
            # The proposal's ledger entry is its PROPOSE register step.
            propose(case, embargo.id_)
            dl.save(case)
        deliver_relayed_invite(dl, case, embargo, make_payload)
        answers[entry_first] = answers_in_outbox(dl, INVITEE)
        # One in-memory store per actor id: close it before the next order.
        dl.close()

    # Which answer is right is not decided yet (#5199), so only agreement
    # is asserted; the fix must also pin the decided answer here.
    assert answers[False] == answers[True]


def _apply_decision(dl: Any, case_id: str, embargo_id: str) -> None:
    """Apply the PROPOSE and ACTIVATE entries for *embargo_id* to a replica."""
    stored = dl.read_case(case_id)
    assert stored is not None
    propose(stored, embargo_id)
    activate(stored, embargo_id)
    dl.save(stored)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SYNC-19-001, EP-08-003: a relayed Invite that arrives after its"
        " proposal was decided indexes a decided proposal as open. Tracked"
        " by #5200."
    ),
)
@pytest.mark.spec("SYNC-19-001")
def test_late_relayed_invite_leaves_the_same_proposal_index(
    make_payload,
) -> None:
    """The proposal index ends the same whether the Invite came first."""
    indexes = {}
    for invite_first in (True, False):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE)
        case, embargo = seed_invitee_case(
            dl,
            f"https://example.org/cases/late-invite-{invite_first}",
            em_state=EM.NONE,
            roles=[CVDRole.VENDOR],
            proposal_days=10,
            policy_days=30,
        )
        if invite_first:
            deliver_relayed_invite(dl, case, embargo, make_payload)
            _apply_decision(dl, case.id_, embargo.id_)
        else:
            _apply_decision(dl, case.id_, embargo.id_)
            stored = dl.read_case(case.id_)
            assert stored is not None
            deliver_relayed_invite(dl, stored, embargo, make_payload)
        final = dl.read_case(case.id_)
        assert final is not None
        indexes[invite_first] = dict(final.pending_embargo_proposal_index)
        dl.close()

    # A decided proposal is not pending (EP-08-003), in either order.
    assert indexes[True] == {}
    assert indexes[True] == indexes[False]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SYNC-19-001: a paused signatory applies the Remove of a revision"
        " only while that revision is in force, so a Remove that overtakes"
        " its Announce is skipped and the revision is left ACTIVE. Tracked"
        " by #5201."
    ),
)
@pytest.mark.spec("SYNC-19-001")
@pytest.mark.spec("SYNC-19-002")
def test_paused_signatory_ending_notices_converge_in_either_order() -> None:
    """``Announce(R1)`` then ``Remove(R1)`` ends the same in either order."""
    outcomes = {}
    for announce_first in (True, False):
        replica = notices._Replica(notices.REMOVED)
        revision = as_EmbargoEvent(
            id_=notices.REVISION_ID,
            context=notices.CASE_ID,
            end_time=days_from_now_utc(30),
        )
        announce = announce_embargo_activity(
            revision,
            context=notices.CASE_ID,
            actor=notices.MANAGER,
            to=[replica.actor_id],
        )
        remove = remove_embargo_from_case_activity(
            revision,
            origin=notices.CASE_ID,
            context=notices.CASE_ID,
            actor=notices.MANAGER,
            to=[replica.actor_id],
            reason=TerminationReason.EARLY,
        )
        for activity in (
            (announce, remove) if announce_first else (remove, announce)
        ):
            replica.receive(activity)
        case = replica.case()
        outcomes[announce_first] = (
            case.current_status.em.state,
            case.active_embargo_id,
        )
        replica.dl.close()

    # The Remove ends the revision, in either order.
    assert outcomes[True] == (EM.EXITED, None)
    assert outcomes[True] == outcomes[False]


def _consent(net: LedgerNetwork, actor: str, embargo_id: str) -> str:
    case = net.case(MANAGER)
    participant = net.stores[MANAGER].read(case.actor_participant_index[actor])
    assert isinstance(participant, CaseParticipant)
    return str(participant.consent_for(embargo_id))


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SYNC-19-001: a participant's Accept and Reject of one Invite, sent"
        " back to back, are recorded in the order they arrive, so the last to"
        " arrive decides its consent. Tracked by #5202."
    ),
)
@pytest.mark.spec("SYNC-19-001")
def test_same_sender_answers_record_one_consent_in_either_order() -> None:
    """An Accept then a Reject of one Invite record one consent in any order."""
    consents = {}
    # Each order runs in a network of its own case. The actors' in-memory
    # stores are shared by actor id, so every id an order mints names its
    # order, and nothing one order receives is a repeat of the other's.
    for send_order in (True, False):
        net = LedgerNetwork(
            f"https://example.org/cases/two-answers-{send_order}"
        )
        embargo_id, invite_id = _invited(net, BYSTANDER, "two-answers")
        accept = _answer_body(
            net, BYSTANDER, invite_id, accept=True, tag=f"accept-{send_order}"
        )
        reject = _answer_body(
            net, BYSTANDER, invite_id, accept=False, tag=f"reject-{send_order}"
        )
        for body in (accept, reject) if send_order else (reject, accept):
            net.receive(MANAGER, body)
        consents[send_order] = _consent(net, BYSTANDER, embargo_id)

    # Which answer should stand is not decided yet (#5202), so only agreement
    # is asserted; the fix must also pin the decided consent here.
    assert consents[True] == consents[False]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SYNC-19-001: a note sent before its sender's Leave(VulnerabilityCase)"
        " is refused, with no notice, when the Leave overtakes it. Tracked by"
        " #5203."
    ),
)
@pytest.mark.spec("SYNC-19-001")
def test_note_sent_before_leave_is_kept_in_either_order() -> None:
    """``Add(Note)`` then ``Leave(Case)`` keep the note in either order."""
    kept = {}
    # One case per order; the note's id carries its case, so neither order's
    # note is a repeat of the other's, and each order checks its own note.
    for send_order in (True, False):
        net = LedgerNetwork(
            f"https://example.org/cases/note-leave-{send_order}"
        )
        case = net.case(BYSTANDER)
        note = as_Note(
            id_=f"{net.case_id}/notes/before-leave",
            content="Sent before leaving",
            context=net.case_id,
            attributed_to=BYSTANDER,
        )
        add = add_note_to_case_activity(
            note, target=case, actor=BYSTANDER, to=[MANAGER]
        )
        leave = rm_close_case_activity(case, actor=BYSTANDER, to=[MANAGER])
        for activity in (add, leave) if send_order else (leave, add):
            body = json.loads(dump_outbound_body(activity))
            net.receive(MANAGER, body)
        notes = [str(n) for n in net.case(MANAGER).notes]
        kept[send_order] = notes == [note.id_]

    # The note was sent while its sender was a participant, so it is kept.
    assert kept[True]
    assert kept[True] == kept[False]
