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

"""Proposals and answers commit first and replay by copying (#4715).

The CASE_MANAGER decides an embargo act on a staged store, commits the act's
entry (carrying any register step), then one ``Create`` or
``Update(EmbargoConsent)`` entry per consent row the act changes, and only
then applies them by copying (ADR-0124, CLP-07-013).  A replica copies the
same entries through the same apply function, so its register and rows equal
the CASE_MANAGER's (CM-23-016).  Each test runs one store per actor
(``LedgerNetwork``, TB-06-007).
"""

import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any, cast

import pytest

from test.support.ledger import committed_semantic_types, fail_commits
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models._helpers import days_from_now_utc, now_utc
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent_semantic_types import (
    CREATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
    UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
    SvcProposeEmbargoUseCase,
    SvcRejectEmbargoUseCase,
    SvcWithdrawEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
    WithdrawEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    withdraw_from_embargo_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)

_S = EmbargoConsentState


def _net(name: str, *, owner: str = OWNER, **kwargs: Any) -> LedgerNetwork:
    """A network whose CASE_MANAGER can act by trigger (it has an actor)."""
    net = LedgerNetwork(
        f"https://example.org/cases/copy-{name}", owner=owner, **kwargs
    )
    net.stores[MANAGER].create(as_Service(id_=MANAGER, name="Coordinator"))
    return net


def _ports(net: LedgerNetwork) -> dict[str, Any]:
    dl = net.stores[MANAGER]
    return {
        "trigger_activity": TriggerActivityAdapter(dl),
        "sync_port": SyncActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
    }


def _case_file(net: LedgerNetwork, holder: str) -> dict[str, Any]:
    """*holder*'s embargo register and every participant's consent rows."""
    case = net.case(holder)
    rows: dict[str, Any] = {}
    for actor_id, participant_id in case.actor_participant_index.items():
        record = net.stores[holder].read(participant_id)
        assert isinstance(record, CaseParticipant), (holder, actor_id)
        rows[actor_id] = [
            row.model_dump(mode="json") for row in record.embargo_consents
        ]
    return {
        "register": [
            entry.model_dump(mode="json") for entry in case.embargo_register
        ],
        "em": case.em_state,
        "rows": rows,
    }


def _row(
    net: LedgerNetwork, holder: str, actor_id: str, embargo_id: str
) -> EmbargoConsentState | None:
    record = net.stores[holder].read(
        net.case(holder).actor_participant_index[actor_id]
    )
    assert isinstance(record, CaseParticipant)
    held = record.held_row(embargo_id)
    return None if held is None else held.state


def _assert_replica_copies(net: LedgerNetwork, replica: str) -> None:
    """*replica* takes the ledger broadcast alone and holds the same case file."""
    net.replay_ledger(replica)
    assert _case_file(net, replica) == _case_file(net, MANAGER)


#: The trigger arms' ``Add(CaseStatus)`` declaration (RSH-04-002); not an
#: embargo entry.
_STATUS_DECLARATION = "add_case_status_to_case"


def _new_entries(net: LedgerNetwork, act: Callable[[], object]) -> list[str]:
    """The embargo semantic types the CASE_MANAGER commits while *act* runs."""
    before = committed_semantic_types(net.stores[MANAGER], net.case_id)
    act()
    return [
        semantic_type
        for semantic_type in committed_semantic_types(
            net.stores[MANAGER], net.case_id
        )[len(before) :]
        if semantic_type != _STATUS_DECLARATION
    ]


def _propose(net: LedgerNetwork, days: int = 30) -> Any:
    """The CASE_MANAGER proposes terms by trigger; the use case result."""
    request_type, use_case_type = (
        (
            ProposeEmbargoRevisionTriggerRequest,
            SvcProposeEmbargoRevisionUseCase,
        )
        if net.case(MANAGER).embargo_in_force
        else (ProposeEmbargoTriggerRequest, SvcProposeEmbargoUseCase)
    )
    return use_case_type(
        net.stores[MANAGER],
        request_type(
            actor_id=MANAGER,
            case_id=net.case_id,
            end_time=days_from_now_utc(days),
        ),
        **_ports(net),
    ).execute()


def _accept(net: LedgerNetwork) -> Any:
    return SvcAcceptEmbargoUseCase(
        net.stores[MANAGER],
        AcceptEmbargoTriggerRequest(actor_id=MANAGER, case_id=net.case_id),
        **_ports(net),
    ).execute()


def _reject(net: LedgerNetwork) -> Any:
    return SvcRejectEmbargoUseCase(
        net.stores[MANAGER],
        RejectEmbargoTriggerRequest(actor_id=MANAGER, case_id=net.case_id),
        **_ports(net),
    ).execute()


def _participant_proposes(net: LedgerNetwork, suffix: str, days: int) -> str:
    """PROPOSER sends terms to the CASE_MANAGER only (EP-09-001)."""
    revision = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/{suffix}",
        context=net.case_id,
        end_time=days_from_now_utc(days),
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=net.case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{net.case_id}/embargo_proposals/{suffix}",
    )
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(proposal)))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    return revision.id_


def _participant_answers(
    net: LedgerNetwork, actor: str, *, accept: bool
) -> None:
    """*actor* gets its relayed Invite and answers it to the CASE_MANAGER."""
    for _type, verdict in net.deliver(MANAGER, to=actor, type_="Invite"):
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            verdict.reason
        )
    (invite,) = net.queued(MANAGER, to=actor, type_="Invite")
    adapter = TriggerActivityAdapter(net.stores[actor])
    build = adapter.accept_embargo if accept else adapter.reject_embargo
    _, sealed = build(
        proposal_id=invite.id_, case_id=net.case_id, actor=actor, to=[MANAGER]
    )
    verdict = net.receive(MANAGER, json.loads(sealed))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


def _seat_manager_stake(net: LedgerNetwork, *roles: CVDRole) -> None:
    """Give the CASE_MANAGER's record *roles*, an embargo stake (EP-09-002)."""
    dl = net.stores[MANAGER]
    record = dl.read(net.case(MANAGER).actor_participant_index[MANAGER])
    assert isinstance(record, CaseParticipant)
    for role in roles:
        record.add_role(role)
    dl.save(record)


# ---------------------------------------------------------------------------
# AC-1: the propose and answer arms commit before they write
# ---------------------------------------------------------------------------


def _owner_manager_with_revision(name: str) -> tuple[LedgerNetwork, str]:
    net = _net(name, owner=MANAGER)
    _propose(net)
    (revision_id,) = net.case(MANAGER).proposed_embargo_ids
    return net, revision_id


def _manager_with_participants_revision(
    name: str,
) -> tuple[LedgerNetwork, str]:
    """A CASE_MANAGER that is a stakeholder but not the owner, and a revision
    it holds a row for: its Accept/Reject is its own consent (ADR-0122)."""
    net = _net(name)
    revision_id = _participant_proposes(net, "consent", 30)
    return net, revision_id


def _withdraw(net: LedgerNetwork) -> Any:
    """The CASE_MANAGER, a signatory and not the owner, leaves the embargo."""
    return SvcWithdrawEmbargoUseCase(
        net.stores[MANAGER],
        WithdrawEmbargoTriggerRequest(actor_id=MANAGER, case_id=net.case_id),
        **_ports(net),
    ).execute()


_ARMS: dict[
    str, tuple[Callable[[str], Any], Callable[[LedgerNetwork], Any]]
] = {
    "propose": (lambda name: (_net(name), None), _propose),
    "accept": (_manager_with_participants_revision, _accept),
    "reject": (_manager_with_participants_revision, _reject),
    "activate": (_owner_manager_with_revision, _accept),
    "reject-proposal": (_owner_manager_with_revision, _reject),
    # The withdraw trigger shares _answer_arms (MSM-07-010).
    "withdraw": (lambda name: (_net(name), None), _withdraw),
}


def _embargo_records(net: LedgerNetwork) -> set[str]:
    return {
        str(obj.id_)
        for obj in net.stores[MANAGER].list_objects("EmbargoEvent")
    }


@pytest.mark.spec("CLP-07-013")
@pytest.mark.parametrize("arm", list(_ARMS))
def test_a_forced_commit_failure_leaves_no_write_behind(arm, monkeypatch):
    """The act's commit fails: no register step and no row is written."""
    setup, act = _ARMS[arm]
    net, _ = setup(f"fail-{arm}")
    before_file = _case_file(net, MANAGER)
    before_entries = committed_semantic_types(net.stores[MANAGER], net.case_id)
    before_embargoes = _embargo_records(net)

    with pytest.MonkeyPatch.context() as patch:
        fail_commits(patch, commit_tree)
        with pytest.raises(VultronBTInternalError, match="commit failed"):
            act(net)

    assert _case_file(net, MANAGER) == before_file
    assert (
        committed_semantic_types(net.stores[MANAGER], net.case_id)
        == before_entries
    )
    # A failed proposal leaves no orphan EmbargoEvent behind either.
    assert _embargo_records(net) == before_embargoes


@pytest.mark.spec("CLP-07-013")
@pytest.mark.parametrize("arm", [a for a in _ARMS if a != "reject"])
def test_the_act_entry_comes_first(arm):
    """The act's entry is committed before every entry it causes."""
    setup, act = _ARMS[arm]
    net, _ = setup(f"order-{arm}")

    entries = _new_entries(net, lambda: act(net))

    assert entries, "the act committed nothing"
    assert entries[0] not in {
        CREATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
        UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
    }, entries


@pytest.mark.spec("CLP-07-015")
def test_a_row_commit_that_fails_leaves_no_write_behind():
    """The act committed and its first row did not: neither is kept.

    The managing owner's proposal commits its ``Invite(EmbargoEvent)``
    entry; the first ``Create(EmbargoConsent)`` then fails.  The act and its
    rows are one transaction (ADR-0146), so the proposal's entry, its
    ``PROPOSE`` step and its embargo are all undone with the row.
    """
    net = _net("fail-row", owner=MANAGER, em_state=EM.NONE)
    before_file = _case_file(net, MANAGER)
    before_entries = committed_semantic_types(net.stores[MANAGER], net.case_id)
    before_embargoes = _embargo_records(net)
    before_invites = {
        str(a.id_) for a in net.stores[MANAGER].list_objects("Invite")
    }

    with pytest.MonkeyPatch.context() as patch:
        failed = fail_commits(
            patch,
            commit_tree,
            when=lambda kw: (
                kw["semantic_type"] == CREATE_EMBARGO_CONSENT_SEMANTIC_TYPE
            ),
        )
        with pytest.raises(VultronBTInternalError, match="commit failed"):
            _propose(net)

    assert failed, "the act's own entry committed before the row's failed"
    assert net.case(MANAGER).proposed_embargo_ids == []
    assert _case_file(net, MANAGER) == before_file
    assert (
        committed_semantic_types(net.stores[MANAGER], net.case_id)
        == before_entries
    )
    assert _embargo_records(net) == before_embargoes
    assert {
        str(a.id_) for a in net.stores[MANAGER].list_objects("Invite")
    } == before_invites, "the proposal's Invite is not left stored"


@pytest.mark.spec("CLP-07-013")
def test_the_managers_own_accept_is_its_rows_entry():
    """An answer's entry carries the row it states; no second entry follows
    (ADR-0122)."""
    setup, act = _ARMS["accept"]
    net, revision_id = setup("own-answer-accept")

    entries = _new_entries(net, lambda: act(net))

    assert entries == ["accept_invite_to_embargo_on_case"]
    assert _row(net, MANAGER, MANAGER, revision_id) is _S.AGREED


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_the_managers_own_reject_is_its_update_of_the_row():
    """The CASE_MANAGER declines as its own ``Update(EmbargoConsent)``.

    A CASE_MANAGER with an embargo stake (EP-09-002) commits no
    ``Reject(Invite(EmbargoEvent))``: that shape from the CASE_MANAGER is its
    abandonment of the proposal (EMB-16-001, ADR-0152).  Its own consent is
    its row's entry, and the replica copies the ``DECLINED`` row from it and
    keeps the proposal open.
    """
    setup, act = _ARMS["reject"]
    net, revision_id = setup("own-answer-reject")

    entries = _new_entries(net, lambda: act(net))

    assert entries == [UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE]
    assert _row(net, MANAGER, MANAGER, revision_id) is _S.DECLINED
    _assert_replica_copies(net, BYSTANDER)
    assert _row(net, BYSTANDER, MANAGER, revision_id) is _S.DECLINED
    assert revision_id in net.case(BYSTANDER).proposed_embargo_ids


@pytest.mark.spec("CLP-07-013")
def test_the_managers_withdrawal_commits_each_declined_row_after_the_leave():
    """The Leave first, then the CASE_MANAGER's declined row as its own
    entry (MSM-07-010, ADR-0124)."""
    net = _net("withdraw-order")

    entries = _new_entries(net, lambda: _withdraw(net))

    assert entries[0] == "withdraw_from_embargo_on_case"
    assert entries[1:] == [UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE]
    assert _row(net, MANAGER, MANAGER, net.initial_embargo_id) is _S.DECLINED


# ---------------------------------------------------------------------------
# AC-2: the UNINVITED rows a proposal creates are CASE_MANAGER entries
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_the_managers_proposal_commits_one_row_per_participant_and_copies():
    """``Invite(EmbargoEvent)`` is the PROPOSE step; each new row follows.

    The managing owner proposes: its own row is ``AGREED`` (proposing is
    consenting, ADR-0093) and every other participant's ``UNINVITED``, each a
    ``Create(EmbargoConsent)``.  Each relayed Invite is followed by its
    invitee's ``Update(EmbargoConsent)``.  The bystander's replica copies
    them all.
    """
    net = _net("propose", owner=MANAGER, em_state=EM.NONE)
    participants = len(net.case(MANAGER).actor_participant_index)

    entries = _new_entries(net, lambda: _propose(net))

    (embargo_id,) = net.case(MANAGER).proposed_embargo_ids
    assert entries[0] == "invite_to_embargo_on_case"
    assert entries[1 : 1 + participants] == (
        [CREATE_EMBARGO_CONSENT_SEMANTIC_TYPE] * participants
    )
    assert _row(net, MANAGER, MANAGER, embargo_id) is _S.AGREED
    assert _row(net, MANAGER, BYSTANDER, embargo_id) is _S.INVITED
    _assert_replica_copies(net, BYSTANDER)
    assert net.case(BYSTANDER).em_state == EM.PROPOSED


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_a_received_proposal_commits_one_row_per_participant_and_copies():
    """A participant's proposal: the guarded commit commits it, its rows follow."""
    net = _net("received-propose")
    participants = len(net.case(MANAGER).actor_participant_index)

    entries = _new_entries(
        net, lambda: _participant_proposes(net, "received", 30)
    )

    assert entries[0] == "invite_to_embargo_on_case"
    assert entries[1 : 1 + participants] == (
        [CREATE_EMBARGO_CONSENT_SEMANTIC_TYPE] * participants
    )
    _assert_replica_copies(net, BYSTANDER)
    _assert_replica_copies(net, OWNER)
    assert net.case(BYSTANDER).em_state == EM.REVISE


# ---------------------------------------------------------------------------
# AC-3: the CASE_MANAGER's policy consent is its own entry
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-09-002")
@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_the_managers_policy_consent_is_its_own_entry_and_is_copied():
    """A stakeholder manager answers on its row with no Invite (EP-09-002).

    Its policy decision is a decision taken from local policy, so it is the
    CASE_MANAGER's own ``Update(EmbargoConsent)`` entry, and every replica
    copies it.
    """
    net = _net("policy")
    _seat_manager_stake(net, CVDRole.VENDOR)

    entries = _new_entries(
        net, lambda: _participant_proposes(net, "policy", 30)
    )

    embargo_id = net.case(MANAGER).proposed_embargo_ids[-1]
    assert _row(net, MANAGER, MANAGER, embargo_id) is _S.AGREED
    assert entries[-1] == UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE
    _assert_replica_copies(net, BYSTANDER)
    assert _row(net, BYSTANDER, MANAGER, embargo_id) is _S.AGREED


# ---------------------------------------------------------------------------
# AC-6: CASE_MANAGER and replica agree after each answer
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("MSM-07-003")
@pytest.mark.spec("MSM-07-004")
@pytest.mark.parametrize("accept", [True, False], ids=["accept", "reject"])
def test_a_participants_answer_is_copied_by_every_replica(accept):
    """The answer's entry is the answerer's row's entry, and the owner's
    replica copies the row from it (ADR-0122)."""
    net = _net(f"answer-{'accept' if accept else 'reject'}")
    embargo_id = _participant_proposes(net, "answered", 30)

    entries = _new_entries(
        net, lambda: _participant_answers(net, BYSTANDER, accept=accept)
    )

    expected = _S.AGREED if accept else _S.DECLINED
    assert entries == [
        "accept_invite_to_embargo_on_case"
        if accept
        else "reject_invite_to_embargo_on_case"
    ]
    assert _row(net, MANAGER, BYSTANDER, embargo_id) is expected
    _assert_replica_copies(net, OWNER)
    assert _row(net, OWNER, BYSTANDER, embargo_id) is expected


@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize(
    "arm", ["accept", "reject", "activate", "reject-proposal", "withdraw"]
)
def test_the_managers_own_answer_is_copied_by_the_replica(arm):
    """Each trigger answer arm: the replica equals the CASE_MANAGER after."""
    setup, act = _ARMS[arm]
    net, _ = setup(f"replica-{arm}")

    act(net)

    _assert_replica_copies(net, BYSTANDER)


def _reseed(net: LedgerNetwork, replica: str) -> None:
    """Give *replica* a fresh store seeded with the CASE_MANAGER's case now."""
    case = net.case(MANAGER)
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=replica)
    for obj_id in (
        case.id_,
        *(str(p) for p in case.actor_participant_index.values()),
        *(entry.embargo_id for entry in case.embargo_register),
    ):
        obj = net.stores[MANAGER].read(obj_id)
        assert obj is not None, obj_id
        store.save(obj)
    net.stores[replica] = store


@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize(
    "history", ["proposal", "answered-revision", "two-revisions"]
)
def test_a_replica_seeded_after_the_entries_replays_them_as_no_ops(history):
    """A joiner's seed is ahead of the ledger it replays from genesis.

    Each copied entry the seed is already past is a no-op, so the replay
    reaches the tail and the replica equals the CASE_MANAGER (ADR-0114).
    """
    net = _net(f"seeded-{history}", owner=MANAGER)
    if history == "answered-revision":
        _participant_proposes(net, "seeded", 30)
        _participant_answers(net, BYSTANDER, accept=True)
    else:
        _propose(net)
    _accept(net)
    if history == "two-revisions":
        _propose(net, 40)
        _accept(net)

    _reseed(net, BYSTANDER)

    _assert_replica_copies(net, BYSTANDER)


# ---------------------------------------------------------------------------
# AC-5 (reworded, #4715): a re-issued stub Invite invites to the embargo in
# force, with the replacement's deadline, under the copy model
# ---------------------------------------------------------------------------

INVITEE = "https://example.org/users/stub-invitee"


def _stub_network(name: str) -> LedgerNetwork:
    net = _net(name, owner=MANAGER)
    dl = net.stores[MANAGER]
    dl.create(as_Service(id_=INVITEE, name="Invitee"))
    # A stub Invite carries the case's summary (CM-17-010).
    case = net.case(MANAGER)
    case.stub_summary = "Summary shared before acceptance"
    dl.save(case)
    return net


def _send_stub(net: LedgerNetwork) -> str:
    from test.core.use_cases.triggers.test_case_joining_trigger import (
        _send_stub_invite,
    )

    return str(
        _send_stub_invite(net.stores[MANAGER], MANAGER, net.case_id, INVITEE)[
            "id"
        ]
    )


def _replacement(net: LedgerNetwork, original_id: str) -> Any:
    from test.core.use_cases.triggers.test_case_joining_trigger import (
        _invites_to,
    )

    (replacement,) = [
        i
        for i in _invites_to(net.stores[MANAGER], INVITEE)
        if i.in_reply_to == original_id
    ]
    return replacement


def _later_stamps(patch: pytest.MonkeyPatch) -> None:
    """Stamp the replacement two minutes after the relayed Invite was.

    Deadlines are second-resolution, so a re-issue in the same second as the
    relay would carry the very deadline the row already holds.  Two minutes
    stays inside the ledger's future tolerance (CLP-14-007).
    """
    from vultron.core.behaviors.embargo import rsvp_stamp

    later = now_utc() + timedelta(minutes=2)
    patch.setattr(rsvp_stamp, "now_utc", lambda: later)


def _invitee_row(net: LedgerNetwork, holder: str, embargo_id: str) -> Any:
    record = net.stores[holder].read(
        net.case(holder).actor_participant_index[INVITEE]
    )
    assert isinstance(record, CaseParticipant)
    return record.held_row(embargo_id)


@pytest.mark.spec("CM-11-016")
@pytest.mark.spec("CM-28-013")
@pytest.mark.spec("CLP-07-013")
@pytest.mark.parametrize(
    "stub_first", [True, False], ids=["from-invited", "from-uninvited"]
)
def test_a_re_issued_stub_invites_to_the_embargo_in_force(stub_first):
    """The replacement's deadline goes on the invitee's row for the new terms.

    From ``INVITED`` (the stub went out before the revision was proposed, so
    the relay invited the inert invitee) the state stays and only the
    deadline is replaced; from ``UNINVITED`` (the invitee was invited after
    the relay) the row moves to ``INVITED``.  Either way the row change is
    the CASE_MANAGER's own ``Update(EmbargoConsent)`` entry after the
    replacement's, and the replica copies it.
    """
    net = _stub_network(f"reissue-{'first' if stub_first else 'after'}")
    if stub_first:
        original_id = _send_stub(net)
        _propose(net)
    else:
        _propose(net)
        original_id = _send_stub(net)
    (revision_id,) = net.case(MANAGER).proposed_embargo_ids
    start = _invitee_row(net, MANAGER, revision_id)
    assert start is not None
    assert start.state is (_S.INVITED if stub_first else _S.UNINVITED)

    with pytest.MonkeyPatch.context() as patch:
        _later_stamps(patch)
        entries = _new_entries(net, lambda: _accept(net))

    assert net.case(MANAGER).active_embargo_id == revision_id
    replacement = _replacement(net, original_id)
    row = _invitee_row(net, MANAGER, revision_id)
    assert row.state is _S.INVITED
    assert row.rsvp_deadline == replacement.end_time
    stub_entry = entries.index("invite_actor_to_case")
    assert entries[stub_entry + 1] == UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE
    _assert_replica_copies(net, BYSTANDER)


@pytest.mark.spec("CM-11-016")
def test_a_re_issue_with_no_embargo_in_force_writes_no_row():
    """After a termination nothing is in force, so the replacement asks the
    invitee to join only, and no consent row changes."""
    from vultron.core.use_cases.triggers.embargo import (
        SvcTerminateEmbargoUseCase,
    )
    from vultron.core.use_cases.triggers.requests import (
        TerminateEmbargoTriggerRequest,
    )

    net = _stub_network("reissue-terminated")
    original_id = _send_stub(net)
    before = _case_file(net, MANAGER)["rows"][INVITEE]

    entries = _new_entries(
        net,
        lambda: SvcTerminateEmbargoUseCase(
            net.stores[MANAGER],
            TerminateEmbargoTriggerRequest(
                actor_id=MANAGER, case_id=net.case_id
            ),
            **_ports(net),
        ).execute(),
    )

    assert net.case(MANAGER).active_embargo_id is None
    assert _replacement(net, original_id) is not None
    stub_entry = entries.index("invite_actor_to_case")
    assert UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE not in entries[stub_entry:]
    assert _case_file(net, MANAGER)["rows"][INVITEE] == before


def _is_invitee_row_update(kwargs: dict[str, Any]) -> bool:
    snapshot = kwargs.get("payload_snapshot") or {}
    row = snapshot.get("object") or {}
    return (
        kwargs["semantic_type"] == UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE
        and row.get("attributedTo") == INVITEE
    )


@pytest.mark.spec("CM-11-016")
@pytest.mark.spec("CLP-07-015")
def test_an_accept_whose_re_issued_row_did_not_commit_is_not_kept():
    """The replacement's row commit fails: the Accept that staled the stub
    is undone with the replacement, and nothing is left for a later run.

    The Accept, the replacement and its invitee's row are one act
    (ADR-0146), so the failure leaves the revision still proposed, the
    original embargo in force, and no replacement stored, queued or
    committed.  The stub is not stale, so a re-issue run sends nothing.
    """
    from test.core.use_cases.triggers.test_case_joining_trigger import (
        _invites_to,
    )
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter as _Sync,
    )
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.nodes.stub_reissue import (
        ReissueStubInvitesNode,
    )

    net = _stub_network("reissue-row-fails")
    original_id = _send_stub(net)
    _propose(net)
    (revision_id,) = net.case(MANAGER).proposed_embargo_ids
    dl = net.stores[MANAGER]
    in_force = net.case(MANAGER).active_embargo_id
    committed_before = committed_semantic_types(dl, net.case_id)
    outbox_before = list(dl.outbox_list())
    row_before = _invitee_row(net, MANAGER, revision_id)
    with pytest.MonkeyPatch.context() as patch:
        _later_stamps(patch)
        failed = fail_commits(patch, commit_tree, when=_is_invitee_row_update)
        with pytest.raises(VultronBTInternalError, match="commit failed"):
            _accept(net)
    assert len(failed) == 1

    assert net.case(MANAGER).active_embargo_id == in_force
    assert net.case(MANAGER).proposed_embargo_ids == [revision_id]
    assert committed_semantic_types(dl, net.case_id) == committed_before
    assert list(dl.outbox_list()) == outbox_before
    assert _invitee_row(net, MANAGER, revision_id) == row_before
    assert [
        i for i in _invites_to(dl, INVITEE) if i.in_reply_to == original_id
    ] == [], "the replacement is not stored"
    assert (
        _new_entries(
            net,
            lambda: BTBridge(
                datalayer=dl,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=_Sync(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute_with_setup(
                tree=ReissueStubInvitesNode(case_id=net.case_id),
                actor_id=MANAGER,
            ),
        )
        == []
    ), "nothing is stale, so nothing is left to re-issue"


# ---------------------------------------------------------------------------
# A received answer that would record nothing is refused before its commit
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("SYNC-12-001")
def test_an_answer_that_records_nothing_is_refused_before_it_is_committed():
    """An Accept of an embargo the register does not hold states a row no
    node can write, so it is refused and nothing is committed (ADR-0122,
    CM-18-003)."""
    net = _net("answer-nothing")
    stranger = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/stranger",
        context=net.case_id,
        end_time=days_from_now_utc(30),
    )
    invite = em_propose_embargo_activity(
        stranger,
        context=net.case_id,
        actor=MANAGER,
        to=[BYSTANDER],
        id_=f"{net.case_id}/invites/stranger",
    )
    # The CASE_MANAGER sent it, so the sender guard finds its invitee.
    net.stores[MANAGER].create(invite)
    accept = json.loads(
        dump_outbound_body(
            em_accept_embargo_activity(
                invite, context=net.case_id, actor=BYSTANDER, to=[MANAGER]
            )
        )
    )
    before = committed_semantic_types(net.stores[MANAGER], net.case_id)

    verdict = net.receive(MANAGER, accept)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "nothing to accept (CM-18-003)" in (verdict.reason or "")
    assert committed_semantic_types(net.stores[MANAGER], net.case_id) == before


# ---------------------------------------------------------------------------
# #4717: withdrawal commits each declined row and replays by copying
# ---------------------------------------------------------------------------

_LEAVE = "withdraw_from_embargo_on_case"


def _bystander_agreed_to_a_revision(name: str) -> tuple[LedgerNetwork, str]:
    """BYSTANDER is AGREED on the embargo in force and on an open revision."""
    net = _net(name)
    revision_id = _participant_proposes(net, "withdrawn", 30)
    _participant_answers(net, BYSTANDER, accept=True)
    assert _row(net, MANAGER, BYSTANDER, revision_id) is _S.AGREED
    return net, revision_id


def _bystander_leaves(net: LedgerNetwork) -> Any:
    """BYSTANDER sends ``Leave(EmbargoEvent)`` to the CASE_MANAGER only."""
    embargo = cast(
        as_EmbargoEvent, net.stores[BYSTANDER].read(net.initial_embargo_id)
    )
    leave = withdraw_from_embargo_activity(
        embargo, context=net.case_id, actor=BYSTANDER, to=[MANAGER]
    )
    return net.receive(MANAGER, json.loads(dump_outbound_body(leave)))


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("MSM-07-010")
def test_a_received_withdrawal_commits_the_leave_then_each_declined_row():
    """The Leave, then one CASE_MANAGER entry per row it declines: the
    sender's row for the embargo in force and the revision it had agreed to
    (ADR-0124)."""
    net, revision_id = _bystander_agreed_to_a_revision("received-withdraw")
    register_before = _case_file(net, MANAGER)["register"]

    verdict: list[Any] = []
    entries = _new_entries(net, lambda: verdict.append(_bystander_leaves(net)))

    assert verdict[0].disposition is HandlerDisposition.APPLIED, verdict[
        0
    ].reason
    assert entries == [
        _LEAVE,
        UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
        UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
    ]
    assert _row(net, MANAGER, BYSTANDER, net.initial_embargo_id) is (
        _S.DECLINED
    )
    assert _row(net, MANAGER, BYSTANDER, revision_id) is _S.DECLINED
    # The embargo stays in force for everyone else (VP-13-017).
    assert _row(net, MANAGER, OWNER, net.initial_embargo_id) is _S.AGREED
    assert _case_file(net, MANAGER)["register"] == register_before


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("MSM-07-010")
@pytest.mark.parametrize(
    "replica", [OWNER, BYSTANDER], ids=["bystander", "withdrawers-own"]
)
def test_a_received_withdrawal_is_copied_by_every_replica(replica):
    """Every replica, the withdrawer's own included, ends equal to the
    CASE_MANAGER: the row entries are committed before the rows make the
    withdrawer inactive, so it is sent each of them."""
    net, revision_id = _bystander_agreed_to_a_revision(f"copy-{replica}")
    assert _bystander_leaves(net).disposition is HandlerDisposition.APPLIED

    _assert_replica_copies(net, replica)
    assert _row(net, replica, BYSTANDER, net.initial_embargo_id) is (
        _S.DECLINED
    )
    assert _row(net, replica, BYSTANDER, revision_id) is _S.DECLINED


@pytest.mark.spec("CLP-07-013")
def test_a_received_withdrawal_whose_row_commit_fails_writes_no_row():
    """A row commit that fails saves no row, and the Leave's own entry is
    gone with it: they commit in one transaction (ADR-0151)."""
    net, revision_id = _bystander_agreed_to_a_revision("withdraw-row-fails")

    with pytest.MonkeyPatch.context() as patch:
        fail_commits(patch, commit_tree)
        with pytest.raises(VultronBTInternalError, match="commit failed"):
            _bystander_leaves(net)

    assert _row(net, MANAGER, BYSTANDER, net.initial_embargo_id) is (_S.AGREED)
    assert _row(net, MANAGER, BYSTANDER, revision_id) is _S.AGREED
    assert _LEAVE not in committed_semantic_types(
        net.stores[MANAGER], net.case_id
    )


@pytest.mark.spec("CLP-07-015")
def test_a_received_act_whose_consequence_fails_keeps_no_entry_for_it():
    """A received act and its consequences succeed or fail as one: when a
    row commit fails, the Leave's own entry is not kept either, nor the
    ``Announce(CaseLedgerEntry)`` its commit queued for each participant, so
    no replica is sent an entry the CASE_MANAGER does not hold."""
    net, _revision_id = _bystander_agreed_to_a_revision("withdraw-atomic")
    dl = net.stores[MANAGER]
    before = committed_semantic_types(dl, net.case_id)
    outbox_before = list(dl.outbox_list())

    with pytest.MonkeyPatch.context() as patch:
        failed = fail_commits(patch, commit_tree)
        with pytest.raises(VultronBTInternalError, match="commit failed"):
            _bystander_leaves(net)
    assert failed, "the fault came after the Leave's own commit"

    assert committed_semantic_types(dl, net.case_id) == before
    assert list(dl.outbox_list()) == outbox_before


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("SYNC-12-001")
def test_a_withdrawal_whose_decision_fails_is_refused_before_its_commit(
    monkeypatch,
):
    """The decision runs among the guards (ADR-0122): a Leave the lifecycle
    refuses is refused uncommitted even past the read-only guard."""
    from vultron.core.behaviors.embargo.nodes import withdrawal

    net, _ = _bystander_agreed_to_a_revision("withdraw-decision")
    monkeypatch.setattr(
        withdrawal, "embargo_withdrawal_refusal", lambda *_a, **_k: None
    )
    _set_bystander_row(net, _S.INVITED)
    before = committed_semantic_types(net.stores[MANAGER], net.case_id)

    verdict = _bystander_leaves(net)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "records nothing" in (verdict.reason or "")
    assert committed_semantic_types(net.stores[MANAGER], net.case_id) == before


def _set_bystander_row(net: LedgerNetwork, state: EmbargoConsentState) -> None:
    """Seed BYSTANDER's row for the embargo in force (test setup only).

    The row is written outside the ledger, so no rebuild can reach it.
    """
    net.bypass_ledger()
    dl = net.stores[MANAGER]
    record = dl.read(net.case(MANAGER).actor_participant_index[BYSTANDER])
    assert isinstance(record, CaseParticipant)
    held = record.held_row(net.initial_embargo_id)
    assert held is not None
    record.embargo_consents = [
        row.model_copy(update={"state": state})
        if row.embargo_id == net.initial_embargo_id
        else row
        for row in record.embargo_consents
    ]
    dl.save(record)


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_the_managers_withdrawal_declines_the_revision_it_agreed_to():
    """By trigger: the CASE_MANAGER's agreed revision row is declined as its
    own entry too, and a replica copies both rows."""
    net, revision_id = _manager_with_participants_revision("withdraw-agreed")
    _accept(net)
    assert _row(net, MANAGER, MANAGER, revision_id) is _S.AGREED

    entries = _new_entries(net, lambda: _withdraw(net))

    assert entries == [
        _LEAVE,
        UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
        UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
    ]
    assert _row(net, MANAGER, MANAGER, revision_id) is _S.DECLINED
    _assert_replica_copies(net, BYSTANDER)
