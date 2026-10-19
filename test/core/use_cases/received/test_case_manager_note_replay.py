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

"""A note the CASE_MANAGER writes for one participant reaches its replica (#4829).

The CASE_MANAGER's own notes — the RSH-06-004 RM-anomaly clarification, the
CSB-18 diagnostic and the CM-16-016 reinforcing-suggestion note — are case
content: the CASE_MANAGER attaches each to its case and commits it as an
``add_note_to_case`` entry, and the participant it is for learns of it from
the ``Announce(CaseLedgerEntry)`` fan-out (SYNC-02-002, CLP-10-001).  No
direct ``Add(Note)`` goes to a participant, whose note handler refuses any
``Add(Note)`` it is not the CASE_MANAGER for (HP-01-005).

Each test moves activities between the actors' stores only as delivered
sealed bodies (TB-06-007), so it runs the emitter and the participant's
receive path together.
"""

import json
from typing import Any, cast

import pytest

from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    EmDimension,
    PxaDimension,
    RmDimension,
)
from vultron.core.models.note import VultronNote
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.wire.as2.factories import (
    add_status_to_case_activity,
    add_status_to_participant_activity,
    recommend_actor_activity,
    rm_engage_case_activity,
)

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)

RECOMMENDED = "https://example.org/users/vendor-c"


def _set_rm(net: LedgerNetwork, member: str, rm: RM) -> None:
    """Record *member* at *rm* in every store, as the ledger already had it."""
    for dl in net.stores.values():
        case = cast(VulnerabilityCase, dl.read(net.case_id))
        participant = cast(
            CaseParticipant, dl.read(case.actor_participant_index[member])
        )
        participant.add_participant_status(
            ParticipantStatus(
                context=net.case_id,
                attributed_to=member,
                rm=RmDimension(state=rm),
            )
        )
        dl.save(participant)


def _to_manager(net: LedgerNetwork, activity: Any):
    """Deliver *activity* to the CASE_MANAGER, as its sender's outbox would."""
    return net.receive(MANAGER, json.loads(dump_outbound_body(activity)))


def _declare_rm(net: LedgerNetwork, member: str, rm: RM):
    participant = net.stores[MANAGER].read(
        net.case(MANAGER).actor_participant_index[member]
    )
    assert isinstance(participant, CaseParticipant)
    status = ParticipantStatus(
        context=net.case_id, attributed_to=member, rm=RmDimension(state=rm)
    )
    return _to_manager(
        net,
        add_status_to_participant_activity(
            status, target=participant, actor=member, to=[MANAGER]
        ),
    )


def _notes(net: LedgerNetwork, actor_id: str) -> list[VultronNote]:
    """The notes *actor_id*'s copy of the case lists, as that store holds them."""
    dl = net.stores[actor_id]
    notes = [dl.read(str(_as_id(n))) for n in net.case(actor_id).notes]
    assert all(isinstance(n, VultronNote) for n in notes), notes
    return cast(list[VultronNote], notes)


def _assert_note_reaches(
    net: LedgerNetwork, recipient: str, *phrases: str
) -> VultronNote:
    """Deliver everything the CASE_MANAGER queued for *recipient* and check it.

    Nothing the recipient receives is refused, and its replica lists the
    CASE_MANAGER's note — the same note the CASE_MANAGER's case lists —
    whose content holds each of *phrases*.
    """
    verdicts = net.deliver(MANAGER, to=recipient)
    refused = [
        (type_, v.reason)
        for type_, v in verdicts
        if v.disposition is HandlerDisposition.REFUSED
    ]
    assert not refused, refused
    matching = [
        n
        for n in _notes(net, recipient)
        if all(p in (n.content or "") for p in phrases)
    ]
    assert len(matching) == 1, [n.content for n in _notes(net, recipient)]
    note = matching[0]
    assert note.id_ in [n.id_ for n in _notes(net, MANAGER)]
    assert _as_id(note.attributed_to) == MANAGER
    return note


@pytest.mark.spec("RSH-06-004", "RSH-06-005", "SYNC-02-002", "CLP-10-001")
def test_rm_gap_note_reaches_the_declaring_participants_replica():
    """Join(Case) from RECEIVED, an accepted non-adjacent RM jump: the
    clarification note replicates."""
    net = LedgerNetwork(
        "https://example.org/cases/manager-note-rm-gap", em_state=EM.NONE
    )
    _set_rm(net, BYSTANDER, RM.RECEIVED)

    verdict = _to_manager(
        net,
        rm_engage_case_activity(
            net.case(BYSTANDER), actor=BYSTANDER, to=[MANAGER]
        ),
    )

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    _assert_note_reaches(net, BYSTANDER, BYSTANDER, "non-adjacent forward")


@pytest.mark.spec("RSH-06-004", "CLP-10-022", "SYNC-02-002")
def test_rm_regression_note_reaches_the_declaring_participants_replica():
    """A wholly refused RM regression: the note still replicates, the
    declaration does not (CLP-10-022)."""
    net = LedgerNetwork(
        "https://example.org/cases/manager-note-rm-regression",
        em_state=EM.NONE,
    )
    _set_rm(net, BYSTANDER, RM.ACCEPTED)

    verdict = _declare_rm(net, BYSTANDER, RM.VALID)

    assert verdict.disposition is HandlerDisposition.REFUSED
    _assert_note_reaches(net, BYSTANDER, BYSTANDER, "backward")
    for actor_id in (MANAGER, BYSTANDER):
        participant = cast(
            CaseParticipant,
            net.stores[actor_id].read(
                net.case(actor_id).actor_participant_index[BYSTANDER]
            ),
        )
        assert participant.participant_status is not None
        assert participant.participant_status.rm.state == RM.ACCEPTED


@pytest.mark.spec("CSB-18-002", "SYNC-02-002", "CLP-10-001")
def test_cs_diagnostic_note_reaches_the_declaring_participants_replica():
    """P declared under an active embargo the gate keeps: the CSB-18 note
    replicates to the participant that declared it."""
    net = LedgerNetwork(
        "https://example.org/cases/manager-note-csb-18", em_state=EM.ACTIVE
    )
    status = CaseStatus(
        context=net.case_id,
        attributed_to=BYSTANDER,
        em=EmDimension(state=EM.ACTIVE),
        pxa=PxaDimension(state=CS_pxa.Pxa),
    )

    verdict = _to_manager(
        net,
        add_status_to_case_activity(
            status, target=net.case_id, actor=BYSTANDER, to=[MANAGER]
        ),
    )

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert net.case(MANAGER).em_state == EM.ACTIVE
    _assert_note_reaches(net, BYSTANDER, "Cross-machine entailment violated")


@pytest.mark.spec("CM-16-016", "CM-16-017", "SYNC-02-002", "CLP-10-001")
def test_reinforcing_suggestion_note_reaches_the_case_owners_replica():
    """A second recommendation of an actor already offered to the owner:
    the reinforcing-suggestion note replicates to the Case Owner."""
    net = LedgerNetwork(
        "https://example.org/cases/manager-note-reinforcing", em_state=EM.NONE
    )
    for recommender in (PROPOSER, BYSTANDER):
        verdict = _to_manager(
            net,
            recommend_actor_activity(
                RECOMMENDED,
                target=net.case_id,
                actor=recommender,
                to=[MANAGER],
                content=f"{recommender} vouches for them",
            ),
        )
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            verdict.reason
        )

    # The second recommendation is noted, not offered again (CM-16-017,
    # #4903).
    assert len(net.queued(MANAGER, to=OWNER, type_="Offer")) == 1
    _assert_note_reaches(
        net, OWNER, "Duplicate actor recommendation", BYSTANDER
    )
