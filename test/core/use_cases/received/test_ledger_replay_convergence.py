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
"""A replica converges from the ledger alone (#3814 AC-6, convergence half).

Each actor has its own store (TB-06-007).  A participant sends an act to the
CASE_MANAGER; the replica under test never receives that act, only the
CASE_MANAGER's ``Announce(CaseLedgerEntry)`` broadcast, and still reaches the
CASE_MANAGER's state (RSH-08-004, PCR-03-001, ADR-0108).  The replica is
handed the ledger broadcast and nothing else the CASE_MANAGER sends — not the
``Announce(VulnerabilityCase)`` an engage also triggers — so the state it
reaches can only have come from the ledger.

The other half of AC-6 — that a replica receiving the act *directly* writes
nothing before the fan-out — lands with the gating change (RSH-08-003, #3814)
and is exercised below by ``test_*_writes_nothing_at_a_replica``: the activity
is delivered straight to a replica's store, which must change no state because
the state-writing effect now runs only inside the CASE_MANAGER gate.  Every
activity-typed RM move reaches a replica as the status the CASE_MANAGER wrote,
committed as its own entry after the act (CLP-07-013) and copied by the
participant-status slot; engage and defer exercise it end to end, and
``test_rm_verdict_status_entry.py`` pins the status entry itself.
"""

import json
from typing import Any, NoReturn, cast

import pytest
from py_trees.common import Status
from pydantic import BaseModel

from test.support.embargo_register import propose, write_consent_rows
from test.support.failed_teardown import fail_pxa_teardown
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import (
    dump_outbound_body,
    read_sealed_body_dict,
)
from vultron.core.behaviors.case.nodes.stub_reissue import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.embargo.nodes import termination_commit
from vultron.core.models._helpers import _as_id, days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    EmDimension,
    PxaDimension,
    RmDimension,
)
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    ThreatSignal,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.pending_assertion import get_pending_assertion_store
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.case import SvcAddObjectToCaseUseCase
from vultron.core.use_cases.triggers.note import SvcAddNoteToCaseUseCase
from vultron.core.use_cases.triggers.requests import (
    AddNoteToCaseTriggerRequest,
    AddObjectToCaseTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    add_note_to_case_activity,
    add_status_to_case_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    reject_embargo_proposal_activity,
    remove_embargo_from_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork


def _send(net: LedgerNetwork, activity: Any) -> None:
    """Deliver *activity* to the CASE_MANAGER, as its sender's outbox would."""
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(activity)))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


def _replay(net: LedgerNetwork, replica: str) -> list[str]:
    """Hand *replica* the CASE_MANAGER's ledger broadcast, and only that."""
    return net.replay_ledger(replica)


def _ledger(net: LedgerNetwork, actor_id: str) -> list[str]:
    """The ``semantic_type`` of each entry *actor_id*'s store holds, in order."""
    entries = [
        cast(CaseLedgerEntry, e)
        for e in net.stores[actor_id].list_objects("CaseLedgerEntry")
        if getattr(e, "case_id", None) == net.case_id
    ]
    return [
        e.semantic_type for e in sorted(entries, key=lambda e: e.log_index)
    ]


def _register(
    net: LedgerNetwork, actor_id: str
) -> list[tuple[str | None, EmbargoRegisterStatus]]:
    """Each embargo register entry *actor_id*'s case holds, as (id, status)."""
    return [
        (_as_id(entry.embargo), entry.status)
        for entry in net.case(actor_id).embargo_register
    ]


def _embargo(net: LedgerNetwork) -> as_EmbargoEvent:
    embargo = net.stores[OWNER].read(net.initial_embargo_id)
    assert isinstance(embargo, as_EmbargoEvent)
    return embargo


def _owned(net: LedgerNetwork) -> LedgerNetwork:
    """Give OWNER the CASE_OWNER role in every store (EP-09-005, ADR-0115)."""
    for dl in net.stores.values():
        case = cast(VulnerabilityCase, dl.read(net.case_id))
        participant = cast(
            CaseParticipant, dl.read(case.actor_participant_index[OWNER])
        )
        participant.add_role(CVDRole.CASE_OWNER)
        dl.save(participant)
    return net


def _consent(
    net: LedgerNetwork, store_of: str, member: str, embargo_id: str
) -> EmbargoConsentState:
    """*member*'s consent row for *embargo_id* as *store_of* holds it."""
    participant = net.stores[store_of].read(
        net.case(store_of).actor_participant_index[member]
    )
    assert isinstance(participant, CaseParticipant)
    return participant.consent_for(embargo_id)


def _rm(net: LedgerNetwork, store_of: str, member: str) -> RM:
    participant = net.stores[store_of].read(
        net.case(store_of).actor_participant_index[member]
    )
    assert isinstance(participant, CaseParticipant)
    status = participant.participant_status
    assert status is not None
    return status.rm.state


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


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("EMB-18-001")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_owners_embargo_activation():
    """Accept(EmbargoEvent): PROPOSED → ACTIVE in the manager's store and the bystander's.

    The activation is the owner's agreement too (ADR-0122), so the owner's
    row is AGREED in both stores.
    """
    net = _owned(
        LedgerNetwork(
            "https://example.org/cases/replay-activation", em_state=EM.PROPOSED
        )
    )
    _send(
        net,
        activate_embargo_activity(
            _embargo(net), target=net.case_id, actor=OWNER, to=[MANAGER]
        ),
    )

    assert "activate_embargo_on_case" in _replay(net, BYSTANDER)
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.ACTIVE, actor_id
        assert case.active_embargo_id == net.initial_embargo_id, actor_id
        assert _consent(net, actor_id, OWNER, net.initial_embargo_id) == (
            EmbargoConsentState.AGREED
        ), actor_id
    assert _ledger(net, BYSTANDER) == _ledger(net, MANAGER)


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_owners_rejection_of_a_proposal():
    """Reject(EmbargoEvent): PROPOSED → NONE in both stores, no consent written."""
    net = _owned(
        LedgerNetwork(
            "https://example.org/cases/replay-rejection", em_state=EM.PROPOSED
        )
    )
    _send(
        net,
        reject_embargo_proposal_activity(
            _embargo(net), target=net.case_id, actor=OWNER, to=[MANAGER]
        ),
    )

    assert "reject_embargo_proposal_on_case" in _replay(net, BYSTANDER)
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.em_state == EM.NONE, actor_id
        assert case.proposed_embargo_ids == [], actor_id
        assert _consent(net, actor_id, OWNER, net.initial_embargo_id) is (
            EmbargoConsentState.UNINVITED
        ), actor_id
    assert _ledger(net, BYSTANDER) == _ledger(net, MANAGER)


def _report_pxa(
    net: LedgerNetwork, pxa: CS_pxa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case owner reports CS at *pxa*; the CASE_MANAGER adopts and commits it,
    but the teardown the adopted value calls for fails.

    The owner's report is adopted without a call-out (RSH-01-002), and the
    adoption authorizes the teardown, which runs in the same act (ADR-0166).
    A teardown that fails for another reason is the one way the embargo
    stays in force beside P, X or A, the state the EMB-04-002 rejection
    starts from, so the teardown is made to fail for this delivery only.
    Each replica learns *pxa* from the committed entry, as it would in
    production.
    """
    em = net.case(MANAGER).em_state
    with monkeypatch.context() as patch:
        fail_pxa_teardown(patch)
        _send(net, net.pxa_report(OWNER, pxa))
    assert net.case(MANAGER).em_state == em
    assert net.case(MANAGER).current_status.pxa.state == pxa


def _propose_revision_everywhere(
    net: LedgerNetwork, *, days: int
) -> as_EmbargoEvent:
    """Put a revision of the active embargo on every store's register."""
    revision = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/revision",
        context=net.case_id,
        end_time=days_from_now_utc(days),
    )
    for dl in net.stores.values():
        dl.create(revision)
        case = cast(VulnerabilityCase, dl.read(net.case_id))
        propose(case, revision.id_)
        dl.save(case)
        # The UNINVITED rows the proposal writes in production (ADR-0122).
        write_consent_rows(dl, case)
    return revision


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
def test_a_replica_carries_signatories_over_to_a_shorter_activated_revision():
    """The owner activates a shorter revision; the bystander, a signatory of
    the embargo it replaces, is carried over in both stores."""
    net = _owned(LedgerNetwork("https://example.org/cases/replay-revision"))
    revision = _propose_revision_everywhere(net, days=10)

    _send(
        net,
        activate_embargo_activity(
            revision, target=net.case_id, actor=OWNER, to=[MANAGER]
        ),
    )

    assert "activate_embargo_on_case" in _replay(net, BYSTANDER)
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.active_embargo_id == revision.id_, actor_id
        assert case.em_state == EM.ACTIVE, actor_id
        assert _consent(net, actor_id, BYSTANDER, revision.id_) == (
            EmbargoConsentState.AGREED
        ), actor_id


@pytest.mark.spec("EMB-04-002")
@pytest.mark.spec("MSM-07-009")
@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("EMB-13-005")
def test_a_replica_follows_the_owners_rejection_of_a_revision_after_disclosure(
    monkeypatch,
):
    """Reject of the last revision with P set: both registers end the same.

    The CASE_MANAGER records the rejection as decided and then terminates
    the embargo in the same act rather than returning to the prior terms
    (EMB-04-002, MSM-07-009).  The replica copies the reject entry and then
    the termination entry and decides nothing (CM-23-016), so it reaches
    the same register: the revision REJECTED, the embargo TERMINATED with
    the threat signal as its cause, and the same consent rows.
    """
    net = _owned(
        LedgerNetwork("https://example.org/cases/replay-reject-disclosed")
    )
    revision = _propose_revision_everywhere(net, days=120)
    _report_pxa(net, CS_pxa.Pxa, monkeypatch)

    _send(
        net,
        reject_embargo_proposal_activity(
            revision, target=net.case_id, actor=OWNER, to=[MANAGER]
        ),
    )

    # The owner's report, its adopted P, with the CSB-18 note the
    # CASE_MANAGER records when the failed teardown leaves the embargo in
    # force (#4829), then
    # the reject entry, then the termination it forced (EMB-04-002).
    assert _replay(net, BYSTANDER)[:5] == [
        "add_participant_status_to_participant",
        "add_case_status_to_case",
        "add_note_to_case",
        "reject_embargo_proposal_on_case",
        "remove_embargo_event_from_case",
    ]
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.em_state == EM.EXITED, actor_id
        assert case.embargo_register_status(revision.id_) is (
            EmbargoRegisterStatus.REJECTED
        ), actor_id
        assert case.embargo_register_status(net.initial_embargo_id) is (
            EmbargoRegisterStatus.TERMINATED
        ), actor_id
        assert case.embargo_termination == EmbargoTermination.threat(
            [ThreatSignal.P]
        ), actor_id
    assert _register(net, BYSTANDER) == _register(net, MANAGER)
    assert _ledger(net, BYSTANDER) == _ledger(net, MANAGER)
    for embargo_id in (revision.id_, net.initial_embargo_id):
        assert _consent(net, BYSTANDER, BYSTANDER, embargo_id) == _consent(
            net, MANAGER, BYSTANDER, embargo_id
        ), embargo_id


@pytest.mark.spec("MSM-07-009")
@pytest.mark.spec("CLP-07-015")
def test_a_refused_termination_commits_neither_entry(monkeypatch):
    """The rejection and the termination it causes are one act (MSM-07-009).

    The guard's trial passes, but the termination node refuses its step:
    the act fails as a whole, so neither the ``Reject`` entry nor a
    ``Remove`` entry is committed and the revision stays open.
    """
    net = _owned(
        LedgerNetwork("https://example.org/cases/replay-reject-refused")
    )
    revision = _propose_revision_everywhere(net, days=120)
    _report_pxa(net, CS_pxa.Pxa, monkeypatch)
    ledger_before = _ledger(net, MANAGER)

    def _refuse(*_args: object) -> NoReturn:
        raise VultronInvalidStateTransitionError("termination refused")

    monkeypatch.setattr(termination_commit, "decide_termination", _refuse)
    reject = reject_embargo_proposal_activity(
        revision, target=net.case_id, actor=OWNER, to=[MANAGER]
    )
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(reject)))

    assert verdict.disposition is not HandlerDisposition.APPLIED
    assert _ledger(net, MANAGER) == ledger_before
    case = net.case(MANAGER)
    assert case.proposed_embargo_ids == [revision.id_]
    assert case.em_state == EM.REVISE


@pytest.mark.spec("MSM-07-009")
@pytest.mark.spec("CLP-07-015")
def test_a_termination_failing_after_its_remove_commits_neither_entry(
    monkeypatch,
):
    """A failure after the ``Remove`` is committed rolls the whole act back.

    The termination's stub re-issue, which runs after its ``Remove`` entry
    commits, fails: neither the ``Reject`` nor the ``Remove`` entry is kept,
    and the fallback arm does not answer the failure (MSM-07-009).
    """
    net = _owned(
        LedgerNetwork("https://example.org/cases/replay-reject-late-failure")
    )
    revision = _propose_revision_everywhere(net, days=120)
    _report_pxa(net, CS_pxa.Pxa, monkeypatch)
    ledger_before = _ledger(net, MANAGER)

    monkeypatch.setattr(
        ReissueStubInvitesNode, "update", lambda _self: Status.FAILURE
    )
    reject = reject_embargo_proposal_activity(
        revision, target=net.case_id, actor=OWNER, to=[MANAGER]
    )
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(reject)))

    assert verdict.disposition is not HandlerDisposition.APPLIED
    assert _ledger(net, MANAGER) == ledger_before
    case = net.case(MANAGER)
    assert case.proposed_embargo_ids == [revision.id_]
    assert case.active_embargo_id == net.initial_embargo_id
    assert case.em_state == EM.REVISE
    assert not net.queued(MANAGER, to=BYSTANDER, type_="Remove")


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("SYNC-12-001")
def test_a_redelivered_owner_activation_entry_changes_nothing():
    """Replaying the same activation entry twice is a no-op the second time."""
    net = _owned(
        LedgerNetwork(
            "https://example.org/cases/replay-redelivery", em_state=EM.PROPOSED
        )
    )
    _send(
        net,
        activate_embargo_activity(
            _embargo(net), target=net.case_id, actor=OWNER, to=[MANAGER]
        ),
    )
    _replay(net, BYSTANDER)
    before = net.case(BYSTANDER).embargo_register

    for activity in net.queued(MANAGER, to=BYSTANDER, type_="Announce"):
        body = read_sealed_body_dict(net.stores[MANAGER], activity.id_) or {}
        if (body.get("object") or {}).get("semanticType") != (
            "activate_embargo_on_case"
        ):
            continue
        verdict = net.receive(BYSTANDER, body)
        assert verdict.disposition is not HandlerDisposition.REFUSED

    assert net.case(BYSTANDER).embargo_register == before


@pytest.mark.spec("MSM-07-003")
@pytest.mark.spec("RSH-08-004")
def test_the_owners_accept_of_an_invite_is_only_its_own_consent():
    """Accept(Invite(EmbargoEvent)) from the owner records its row; EM stays PROPOSED.

    The owner's decision for the case is a separate activity (ADR-0122).
    """
    net = _owned(
        LedgerNetwork(
            "https://example.org/cases/replay-owner-consent",
            em_state=EM.PROPOSED,
        )
    )
    invite = em_propose_embargo_activity(
        _embargo(net),
        context=net.case_id,
        actor=MANAGER,
        to=[OWNER],
        id_=f"{net.case_id}/embargo_invites/owner",
    )
    net.stores[MANAGER].create(invite)
    _send(
        net,
        em_accept_embargo_activity(
            invite, context=net.case_id, actor=OWNER, to=[MANAGER]
        ),
    )

    assert "accept_invite_to_embargo_on_case" in _replay(net, BYSTANDER)
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.em_state == EM.PROPOSED, actor_id
        assert case.active_embargo_id is None, actor_id
        assert _consent(net, actor_id, OWNER, net.initial_embargo_id) == (
            EmbargoConsentState.AGREED
        ), actor_id


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_owners_embargo_removal():
    """Remove(EmbargoEvent): ACTIVE → EXITED in both stores."""
    net = _owned(LedgerNetwork("https://example.org/cases/replay-removal"))
    _send(
        net,
        remove_embargo_from_case_activity(
            _embargo(net),
            origin=net.case_id,
            actor=OWNER,
            to=[MANAGER],
            reason=TerminationReason.EARLY,
        ),
    )

    assert "remove_embargo_event_from_case" in _replay(net, BYSTANDER)
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.EXITED, actor_id
        assert case.active_embargo_id is None, actor_id


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("RSH-01-003")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_a_participants_adopted_case_status():
    """The owner's P report, adopted by the CASE_MANAGER, reaches the
    bystander's replica as P set (RSH-01-003, #4956)."""
    net = _owned(
        LedgerNetwork(
            "https://example.org/cases/replay-case-status", em_state=EM.NONE
        )
    )
    _send(net, net.pxa_report(OWNER, CS_pxa.Pxa))

    assert "add_case_status_to_case" in _replay(net, BYSTANDER)
    manager, replica = net.case(MANAGER), net.case(BYSTANDER)
    assert manager.current_status.pxa.state == CS_pxa.Pxa
    assert replica.current_status.id_ == manager.current_status.id_
    assert replica.current_status.pxa.state == CS_pxa.Pxa
    assert replica.current_status.em.state == manager.current_status.em.state
    assert [_as_id(s) for s in replica.case_statuses] == [
        _as_id(s) for s in manager.case_statuses
    ]


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("RSH-08-001")
@pytest.mark.spec("TB-06-007")
@pytest.mark.parametrize(
    ("factory", "semantic_type", "target"),
    [
        (rm_engage_case_activity, "engage_case", RM.ACCEPTED),
        (rm_defer_case_activity, "defer_case", RM.DEFERRED),
    ],
    ids=["engage", "defer"],
)
def test_a_replica_follows_a_participants_engagement_decision(
    factory, semantic_type, target
):
    """Join/Ignore(Case) from the bystander moves its RM on the owner's replica."""
    net = LedgerNetwork(
        f"https://example.org/cases/replay-{semantic_type}", em_state=EM.NONE
    )
    _set_rm(net, BYSTANDER, RM.VALID)
    owner_before = {s: _rm(net, s, OWNER) for s in (MANAGER, OWNER)}
    _send(net, factory(net.case(BYSTANDER), actor=BYSTANDER, to=[MANAGER]))

    assert semantic_type in _replay(net, OWNER)
    for store_of in (MANAGER, OWNER):
        # The sender is the subject (RSH-08-001) in every store: the
        # replica's own participant does not move.
        assert _rm(net, store_of, BYSTANDER) == target, store_of
        assert _rm(net, store_of, OWNER) == owner_before[store_of], store_of


def _create_note(net: LedgerNetwork, note_id: str) -> as_Create:
    """A bystander's ``Create(Note)`` to the CASE_MANAGER, naming its case."""
    return as_Create(
        actor=BYSTANDER,
        object_=as_Note(
            id_=note_id, content="A general inquiry", context=net.case_id
        ),
        to=[MANAGER],
    )


@pytest.mark.spec("VAM-01-010", "VAM-01-011", "RSH-08-004")
def test_a_create_note_changes_no_copy_of_the_case():
    """A received Create(Note) naming the case is not a protocol message
    (VAM-01-011): the CASE_MANAGER refuses it as unrecognized, attaches
    nothing and commits nothing, so no replica has an entry to replay (#4707).
    """
    net = LedgerNetwork(
        "https://example.org/cases/replay-create-note", em_state=EM.NONE
    )
    note_id = "https://example.org/notes/replay-create-note"
    manager_notes = list(net.case(MANAGER).notes)
    ledger_before = _ledger(net, MANAGER)

    verdict = net.receive(
        MANAGER, json.loads(dump_outbound_body(_create_note(net, note_id)))
    )

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert _ledger(net, MANAGER) == ledger_before
    assert net.case(MANAGER).notes == manager_notes
    assert note_id not in [_as_id(n) for n in net.case(OWNER).notes]


def _note_entries(net: LedgerNetwork, actor_id: str) -> list[CaseLedgerEntry]:
    """The note entries *actor_id*'s store holds for the case, in order."""
    entries = [
        cast(CaseLedgerEntry, e)
        for e in net.stores[actor_id].list_objects("CaseLedgerEntry")
        if getattr(e, "case_id", None) == net.case_id
        and "note" in cast(CaseLedgerEntry, e).semantic_type
    ]
    return sorted(entries, key=lambda e: e.log_index)


@pytest.mark.spec("CLP-07-002")
@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("SYNC-11-002")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("CM-06-005")
@pytest.mark.spec("CM-13-007")
@pytest.mark.spec("VAM-07-002")
@pytest.mark.spec("VAM-01-010")
def test_add_note_trigger_makes_one_add_note_to_case_entry():
    """The add-note trigger sends one Add(Note) that names the case as its
    target and carries the note inline: the CASE_MANAGER commits exactly one
    ``add_note_to_case`` entry, every other participant's replica attaches
    the note from it and holds the Note object, the entry's Announce clears
    the author's pending assertion, and a redelivered Add commits nothing
    more (#4706 AC-3)."""
    net = LedgerNetwork(
        "https://example.org/cases/trigger-add-note", em_state=EM.NONE
    )
    net.stores[BYSTANDER].create(as_Service(id_=BYSTANDER, name="Vendor B"))

    result = SvcAddNoteToCaseUseCase(
        net.stores[BYSTANDER],
        AddNoteToCaseTriggerRequest(
            actor_id=BYSTANDER,
            case_id=net.case_id,
            note_name="Question",
            note_content="Is there a workaround?",
        ),
        trigger_activity=TriggerActivityAdapter(net.stores[BYSTANDER]),
    ).execute()
    assert result.activity is not None and result.note is not None
    add_id: str = result.activity["id"]
    note_id: str = result.note["id"]

    queued = net.queued(BYSTANDER, to=MANAGER)
    assert [(a.type_, a.id_) for a in queued] == [("Add", add_id)]
    pending = get_pending_assertion_store(BYSTANDER)
    assert pending.is_suppressed(net.case_id, "add_note_to_case", add_id)

    # The Note itself travels inside the Add; the CASE_MANAGER has never
    # seen it before this delivery.
    assert net.stores[MANAGER].read(note_id) is None
    verdicts = net.deliver(BYSTANDER, to=MANAGER)
    assert [(type_, v.disposition) for type_, v in verdicts] == [
        ("Add", HandlerDisposition.APPLIED)
    ]

    entries = _note_entries(net, MANAGER)
    assert [(e.semantic_type, e.log_object_id) for e in entries] == [
        ("add_note_to_case", add_id)
    ]
    assert note_id in [_as_id(n) for n in net.case(MANAGER).notes]
    assert net.stores[MANAGER].read(note_id) is not None

    # Every active participant other than the author receives the note.
    assert _replay(net, OWNER).count("add_note_to_case") == 1
    assert [_as_id(n) for n in net.case(OWNER).notes].count(note_id) == 1
    assert net.stores[OWNER].read(note_id) is not None

    # The author already holds the note; the entry's Announce only clears
    # its pending assertion and attaches nothing twice.
    assert "add_note_to_case" in _replay(net, BYSTANDER)
    assert not pending.is_suppressed(net.case_id, "add_note_to_case", add_id)
    assert [_as_id(n) for n in net.case(BYSTANDER).notes].count(note_id) == 1

    # A redelivered Add commits no second entry and attaches nothing twice.
    body = read_sealed_body_dict(net.stores[BYSTANDER], add_id)
    assert body is not None
    net.receive(MANAGER, body)
    assert [e.log_object_id for e in _note_entries(net, MANAGER)] == [add_id]
    assert [_as_id(n) for n in net.case(MANAGER).notes].count(note_id) == 1


@pytest.mark.spec("SYNC-11-002")
@pytest.mark.spec("SYNC-11-003")
@pytest.mark.spec("TRIG-10-001")
@pytest.mark.parametrize(
    ("sender", "make_object", "semantic_type"),
    [
        pytest.param(
            OWNER,
            lambda: as_VulnerabilityReport(
                id_="https://example.org/reports/trigger-add-object",
                name="Report",
                content="details",
            ),
            "add_report_to_case",
            id="report-from-owner",
        ),
        pytest.param(
            BYSTANDER,
            lambda: as_Note(
                id_="https://example.org/notes/trigger-add-object",
                content="Written here",
                attributed_to=BYSTANDER,
                # A note belongs to the case it is added to (HP-08-007).
                context="https://example.org/cases/trigger-add-object-add_note_to_case",
            ),
            "add_note_to_case",
            id="note-from-author",
        ),
    ],
)
def test_add_object_trigger_pending_entry_clears_on_the_managers_commit(
    sender: str, make_object: Any, semantic_type: str
):
    """The add-object trigger's pending assertion is keyed the way the
    CASE_MANAGER commits the Add, so the commit's Announce clears it and the
    same object may be added again (#4041, #4761)."""
    net = _owned(
        LedgerNetwork(
            f"https://example.org/cases/trigger-add-object-{semantic_type}",
            em_state=EM.NONE,
        )
    )
    dl = net.stores[sender]
    if dl.read(sender) is None:
        dl.create(as_Service(id_=sender, name="Sender"))
    obj = make_object()
    dl.create(obj)

    def _add() -> Any:
        return SvcAddObjectToCaseUseCase(
            dl,
            AddObjectToCaseTriggerRequest(
                actor_id=sender, case_id=net.case_id, object_id=obj.id_
            ),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

    first = _add()
    assert first.activity is not None
    add_id: str = first.activity["id"]
    pending = get_pending_assertion_store(sender)
    assert pending.is_suppressed(net.case_id, semantic_type, add_id)
    assert _add().activity is None  # a repeat while pending is suppressed

    verdicts = net.deliver(sender, to=MANAGER)
    assert [(type_, v.disposition) for type_, v in verdicts] == [
        ("Add", HandlerDisposition.APPLIED)
    ]
    entries = [
        cast(CaseLedgerEntry, e)
        for e in net.stores[MANAGER].list_objects("CaseLedgerEntry")
        if getattr(e, "case_id", None) == net.case_id
        and cast(CaseLedgerEntry, e).semantic_type == semantic_type
    ]
    assert [e.log_object_id for e in entries] == [add_id]

    assert semantic_type in _replay(net, sender)
    assert not pending.is_suppressed(net.case_id, semantic_type, add_id)
    assert _add().activity is not None


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("HP-08-006")
def test_an_add_naming_a_note_the_manager_already_holds_is_refused():
    """An Add(Note, target=Case) naming a note the CASE_MANAGER already
    holds is refused: an Add introduces a new note (a change is an
    Update(Note)), so no ``add_note_to_case`` entry is committed, the case
    does not gain the note and no replica learns of it (#4831)."""
    net = LedgerNetwork(
        "https://example.org/cases/replay-add-existing-note", em_state=EM.NONE
    )
    note = as_Note(
        id_="https://example.org/notes/replay-add-existing-note",
        content="Written elsewhere",
        context=net.case_id,
    )
    net.stores[MANAGER].create(note)

    verdict = net.receive(
        MANAGER,
        json.loads(
            dump_outbound_body(
                add_note_to_case_activity(
                    note, target=net.case_id, actor=BYSTANDER, to=[MANAGER]
                )
            )
        ),
    )

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert _note_entries(net, MANAGER) == []
    assert note.id_ not in [_as_id(n) for n in net.case(MANAGER).notes]
    assert "add_note_to_case" not in _replay(net, OWNER)
    assert net.stores[OWNER].read(note.id_) is None


# ---------------------------------------------------------------------------
# AC-6, "writes nothing" half (RSH-08-003, #3814): an activity delivered
# straight to a replica — not the CASE_MANAGER — changes no participant or
# case state.  The replica archives it and takes the move from the ledger.
# ---------------------------------------------------------------------------
def _deliver_direct(
    net: LedgerNetwork, replica: str, activity: BaseModel
) -> None:
    """Deliver *activity* straight into *replica*'s store (never the manager)."""
    net.receive(replica, json.loads(dump_outbound_body(activity)))


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("TB-06-007")
def test_embargo_activation_writes_nothing_at_a_replica():
    """Accept(EmbargoEvent) delivered straight to a replica leaves EM untouched.

    The owner's activation writes EM state only at the CASE_MANAGER
    (RSH-08-003); a replica takes the change from the ledger, so the same
    activity delivered direct to a replica changes nothing.
    """
    net = _owned(
        LedgerNetwork(
            "https://example.org/cases/writes-nothing-activation",
            em_state=EM.PROPOSED,
        )
    )
    before = net.case(BYSTANDER).current_status.em.state
    _deliver_direct(
        net,
        BYSTANDER,
        activate_embargo_activity(
            _embargo(net), target=net.case_id, actor=OWNER, to=[BYSTANDER]
        ),
    )

    case = net.case(BYSTANDER)
    assert case.current_status.em.state == before
    assert case.active_embargo_id is None


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("TB-06-007")
def test_embargo_removal_writes_nothing_at_an_active_replica():
    """Remove(EmbargoEvent) delivered straight to an active (non-paused) replica
    leaves the embargo in force: it is not awaiting an ending notice, so it
    takes the teardown from the ledger (CM-31-010)."""
    net = _owned(
        LedgerNetwork("https://example.org/cases/writes-nothing-removal")
    )
    before = net.case(BYSTANDER).current_status.em.state
    assert before == EM.ACTIVE
    _deliver_direct(
        net,
        BYSTANDER,
        remove_embargo_from_case_activity(
            _embargo(net),
            origin=net.case_id,
            actor=MANAGER,
            to=[BYSTANDER],
            reason=TerminationReason.EARLY,
        ),
    )

    case = net.case(BYSTANDER)
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == net.initial_embargo_id


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("RSH-09-005")
@pytest.mark.spec("TB-06-007")
def test_case_status_writes_nothing_at_a_replica():
    """The CASE_MANAGER's Add(CaseStatus) delivered straight to a replica,
    the one sender it admits one from (RSH-04-005), appends no status."""
    net = LedgerNetwork(
        "https://example.org/cases/writes-nothing-case-status",
        em_state=EM.NONE,
    )
    before = [_as_id(s) for s in net.case(OWNER).case_statuses]
    status = CaseStatus(
        context=net.case_id,
        attributed_to=MANAGER,
        em=EmDimension(state=EM.NONE),
        pxa=PxaDimension(state=CS_pxa.Pxa),
    )
    activity = add_status_to_case_activity(
        status, target=net.case_id, actor=MANAGER, to=[OWNER]
    )
    verdict = net.receive(OWNER, json.loads(dump_outbound_body(activity)))

    assert verdict.disposition is not HandlerDisposition.REFUSED, (
        verdict.reason
    )

    assert [_as_id(s) for s in net.case(OWNER).case_statuses] == before


# The report-verdict "writes nothing at a replica" half of AC-6
# (TentativeReject / Reject(Offer(Report))) is exercised in
# ``test/core/behaviors/report/test_received_report_trees.py`` (a
# non-CASE_MANAGER receiver archives the activity but the RM write is gated
# out), with the manager-path transition and sender-as-subject covered by
# ``test_report_routing_guard.py`` and ``test_receive_tree_ledger_commit.py``;
# #4304 made those verdicts committed and replayed, so gating them is safe
# (RSH-08-003).
