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

"""The CASE_MANAGER-gated P/X/A abandonment of open proposals (#4131).

``reject_proposed_embargo_bt`` abandons every open proposal once P/X/A is
set while EM is ``PROPOSED`` (EMB-16-001).  The EM write and the commit run
only as the CASE_MANAGER (EP-09-008, BT-17-001); any other participant
writes nothing and sends nothing (EMB-16-002, #4148).  Each test runs in the
executing actor's own store (BT-05-005).
"""

from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    OTHER_PARTICIPANT_ACTOR,
    make_case_with_manager,
    setup_blackboard,
)
from test.support.embargo_register import propose, write_consent_rows
from test.support.ledger import committed_semantic_types, fail_commits
from test.support.received import archive_received
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes import (
    ABANDONED_PROPOSALS_KEY,
    ReadOpenEmbargoProposalsNode,
)
from vultron.core.behaviors.embargo.trigger_tree import (
    reject_proposed_embargo_bt,
)
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent


def _proposed_case(
    suffix: str,
    days: tuple[int, ...] = (60, 15),
    *,
    indexed: bool = True,
    consent: EmbargoConsentState = EmbargoConsentState.AGREED,
) -> tuple[VulnerabilityCase, SqliteDataLayer, dict[str, str]]:
    """A PROPOSED case in the CASE_MANAGER's store with open proposals.

    Returns the case, the store and ``{embargo_id: invite_id}`` in record
    order.  With *indexed* false no proposal names its Invite.  Every
    participant holds a *consent* row.
    """
    case, _cm, dl = make_case_with_manager(
        suffix, em_state=EM.NONE, other_consent=consent
    )
    case = cast(VulnerabilityCase, dl.read(case.id_))
    proposals: dict[str, str] = {}
    for d in days:
        embargo = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/{d}d",
            context=case.id_,
            end_time=days_from_now_utc(d),
        )
        invite = em_propose_embargo_activity(
            embargo,
            context=case.id_,
            actor=OTHER_PARTICIPANT_ACTOR,
            to=[CASE_MANAGER_ACTOR],
            id_=f"{case.id_}/embargo_proposals/{d}d",
        )
        dl.create(embargo)
        # The participant's Invite, held as the CASE_MANAGER's intake
        # archived it, never under the id its sender chose (DL-06-006).
        archive_received(dl, invite)
        propose(case, embargo.id_)
        proposals[embargo.id_] = invite.id_
    if indexed:
        case.pending_embargo_proposal_index = dict(proposals)
    dl.save(case)
    write_consent_rows(dl, case)
    return case, dl, proposals


_REJECT = MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value
_UNDO = MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE.value
_ABANDONMENT_TYPES = frozenset({_REJECT, _UNDO})
_RELAY_INVITEE = "https://example.org/actors/coordinator"


def _relay(dl: SqliteDataLayer, case_id: str, embargo_id: str) -> str:
    """Send and commit the CASE_MANAGER's relay of *embargo_id*; its id.

    ``actor`` is the CASE_MANAGER and ``attributedTo`` the proposer, as
    ``RelayEmbargoInviteToEachNode`` builds it (EP-09-002).
    """
    invite_id, blob = TriggerActivityAdapter(dl).propose_embargo(
        embargo_id=embargo_id,
        case_id=case_id,
        actor=CASE_MANAGER_ACTOR,
        to=[_RELAY_INVITEE],
        attributed_to=OTHER_PARTICIPANT_ACTOR,
    )
    commit_emitted_activity(
        datalayer=dl,
        actor_id=CASE_MANAGER_ACTOR,
        case_id=case_id,
        activity_id=invite_id,
        activity_blob=blob,
        semantic_type=MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value,
        sync_port=SyncActivityAdapter(dl),
    )
    return invite_id


def _own_proposal_case(
    suffix: str,
) -> tuple[VulnerabilityCase, SqliteDataLayer, str, str]:
    """A PROPOSED case whose one open proposal the CASE_MANAGER sent itself.

    Returns the case, the store, the embargo and the proposal's Invite, held
    under its own id as an activity this actor sent.
    """
    case, _cm, dl = make_case_with_manager(suffix, em_state=EM.NONE)
    case = cast(VulnerabilityCase, dl.read(case.id_))
    embargo = as_EmbargoEvent(
        id_=f"{case.id_}/embargo_events/own",
        context=case.id_,
        end_time=days_from_now_utc(45),
    )
    dl.create(embargo)
    invite_id, _blob = TriggerActivityAdapter(dl).propose_embargo(
        embargo_id=embargo.id_, case_id=case.id_, actor=CASE_MANAGER_ACTOR
    )
    propose(case, embargo.id_)
    case.pending_embargo_proposal_index = {embargo.id_: invite_id}
    dl.save(case)
    write_consent_rows(dl, case)
    return case, dl, embargo.id_, invite_id


def _replica_of(
    manager_dl: SqliteDataLayer,
    case: VulnerabilityCase,
    proposals: dict[str, str],
    actor_id: str,
) -> SqliteDataLayer:
    """Copy the case and everything it names into *actor_id*'s own store."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    stored = cast(VulnerabilityCase, manager_dl.read(case.id_))
    obj_ids = [
        stored.id_,
        *stored.actor_participant_index.values(),
        *proposals,
        *(ReceivedActivityRecord.build_id(i) for i in proposals.values()),
    ]
    for obj_id in obj_ids:
        obj = manager_dl.read(obj_id)
        assert obj is not None, obj_id
        dl.create(obj)
    return dl


def _run(dl: SqliteDataLayer, case_id: str, actor_id: str) -> Status:
    bridge = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )
    tree = reject_proposed_embargo_bt(case_id=case_id, result_out={})
    return bridge.execute_with_setup(tree, actor_id=actor_id).status


def _queued(dl: SqliteDataLayer) -> list[VultronActivity]:
    return [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]


def _abandonment_entries(
    dl: SqliteDataLayer, case_id: str
) -> list[CaseLedgerEntry]:
    return [
        entry
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
        and entry.case_id == case_id
        and str(entry.semantic_type) in _ABANDONMENT_TYPES
    ]


@pytest.mark.spec("EMB-16-001")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("BT-17-001")
@pytest.mark.spec("MSM-02-006")
def test_the_manager_abandons_every_open_proposal_and_commits_each():
    case, dl, proposals = _proposed_case("abandon-mgr")

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.SUCCESS

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.NONE
    assert updated.proposed_embargo_ids == []
    assert updated.pending_embargo_proposal_index == {}
    entries = _abandonment_entries(dl, case.id_)
    assert sorted(
        e.payload_snapshot["object"]["id"] for e in entries
    ) == sorted(proposals.values())
    for entry in entries:
        snapshot = entry.payload_snapshot
        # The CASE_MANAGER declines the proposal it received (ADR-0152).
        assert str(entry.semantic_type) == _REJECT
        assert snapshot["type"] == "Reject"
        assert snapshot["actor"] == CASE_MANAGER_ACTOR


@pytest.mark.spec("EMB-16-001")
@pytest.mark.spec("CLP-07-015")
def test_the_manager_withdraws_each_invite_it_relayed_after_the_reject():
    """The Reject cancels the proposal; one Undo per relayed Invite follows.

    Only the proposal the Undo relays were for gets them, and the other
    proposal, never relayed, is still cancelled (ADR-0152).
    """
    case, dl, proposals = _proposed_case("abandon-relayed")
    relayed, unrelayed = proposals
    relays = [_relay(dl, case.id_, relayed) for _ in range(2)]
    before = len(committed_semantic_types(dl, case.id_))

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.SUCCESS

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.proposed_embargo_ids == []
    assert updated.current_status.em.state == EM.NONE
    added = committed_semantic_types(dl, case.id_)[before:]
    assert added[:4] == [_REJECT, _UNDO, _UNDO, _REJECT]
    undos = [
        e
        for e in _abandonment_entries(dl, case.id_)
        if str(e.semantic_type) == _UNDO
    ]
    assert sorted(e.payload_snapshot["object"]["id"] for e in undos) == sorted(
        relays
    )
    for entry in undos:
        assert entry.payload_snapshot["type"] == "Undo"
        assert entry.payload_snapshot["actor"] == CASE_MANAGER_ACTOR
        assert entry.payload_snapshot["object"]["object"]["id"] == relayed
    assert unrelayed not in updated.proposed_embargo_ids


@pytest.mark.spec("EMB-16-001")
def test_the_manager_withdraws_its_own_proposal_with_an_undo():
    """An Invite one sent is withdrawn, not declined (ADR-0152): the Undo of
    the CASE_MANAGER's own proposal carries the cancel."""
    case, dl, embargo_id, invite_id = _own_proposal_case("abandon-own")

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.SUCCESS

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.proposed_embargo_ids == []
    assert updated.current_status.em.state == EM.NONE
    (entry,) = _abandonment_entries(dl, case.id_)
    assert str(entry.semantic_type) == _UNDO
    assert entry.payload_snapshot["type"] == "Undo"
    assert entry.payload_snapshot["object"]["id"] == invite_id
    assert entry.payload_snapshot["object"]["object"]["id"] == embargo_id


@pytest.mark.spec("CLP-10-001", "CLP-10-027")
def test_the_manager_queues_nothing_to_itself():
    """Every replica learns the abandonment from the entry; the ER itself is
    addressed to nobody, and nothing the manager queues names it."""
    case, dl, _proposals = _proposed_case("abandon-self")

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.SUCCESS

    queued = _queued(dl)
    assert not any(a.type_ in ("Reject", "Undo") for a in queued)
    assert not any(
        CASE_MANAGER_ACTOR in [*(a.to or []), *(a.cc or [])] for a in queued
    )


def _consents(
    dl: SqliteDataLayer, case_id: str
) -> dict[str, list[EmbargoConsent]]:
    stored = cast(VulnerabilityCase, dl.read(case_id))
    return {
        actor: cast(CaseParticipant, dl.read(pid)).embargo_consents
        for actor, pid in stored.actor_participant_index.items()
    }


@pytest.mark.spec("EMB-16-002")
@pytest.mark.spec("EP-09-008")
@pytest.mark.parametrize("indexed", [True, False])
def test_a_non_manager_neither_writes_nor_asks(indexed: bool):
    """The manager abandons on its own P/X/A detection (#4148).

    Not even an unanswerable proposal (no indexed Invite) fails the arm:
    only the manager reads the proposals, because only it answers them.
    """
    case, manager_dl, proposals = _proposed_case(
        f"abandon-quiet-{indexed}", indexed=indexed
    )
    dl = _replica_of(manager_dl, case, proposals, OTHER_PARTICIPANT_ACTOR)

    assert _run(dl, case.id_, OTHER_PARTICIPANT_ACTOR) == Status.SUCCESS

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.PROPOSED
    assert updated.proposed_embargo_ids == list(proposals)
    assert _queued(dl) == []
    assert committed_semantic_types(dl, case.id_) == []


@pytest.mark.spec("CM-18-005")
@pytest.mark.spec("MSM-07-004")
def test_the_managers_abandonment_changes_no_consent():
    """The abandonment declines nobody: no participant's consent moves.

    The non-manager side sends no ``Reject`` at all
    (``test_a_non_manager_neither_writes_nor_asks``); the replica side is
    pinned in ``test_embargo_abandonment_replay.py``.
    """
    case, dl, _proposals = _proposed_case(
        "abandon-consent", consent=EmbargoConsentState.INVITED
    )
    before = _consents(dl, case.id_)
    assert all(before.values())

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.SUCCESS

    assert _consents(dl, case.id_) == before


@pytest.mark.spec("EMB-18-003")
def test_a_proposal_naming_no_invite_fails_before_anything_moves():
    """No ER can answer a proposal with no Invite (MSM-02-006)."""
    case, dl, proposals = _proposed_case("abandon-unindexed", indexed=False)

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.FAILURE

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.PROPOSED
    assert updated.proposed_embargo_ids == list(proposals)
    assert committed_semantic_types(dl, case.id_) == []
    assert _queued(dl) == []


@pytest.mark.spec("EMB-16-001")
@pytest.mark.spec("MSM-02-006")
def test_an_unreadable_invite_fails_before_anything_moves():
    """An indexed Invite missing from the store fails the read, not the
    commit: failing after the EM write would leave the manager at NONE with
    no entry for any replica."""
    case, dl, proposals = _proposed_case("abandon-unreadable")
    missing = next(iter(proposals.values()))
    _drop(dl, missing)

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.FAILURE

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.PROPOSED
    assert updated.proposed_embargo_ids == list(proposals)
    assert committed_semantic_types(dl, case.id_) == []
    assert _queued(dl) == []


def _fail_commits_after(monkeypatch: pytest.MonkeyPatch, allowed: int) -> None:
    """Let the first *allowed* abandonment commits through, then fail each.

    The stand-in is the commit tree itself, so the real
    ``commit_emitted_activity`` sees a failed commit and raises.
    """
    from vultron.core.behaviors.sync import commit_tree

    fail_commits(
        monkeypatch,
        commit_tree,
        allowed=allowed,
        when=lambda kw: kw.get("semantic_type") in _ABANDONMENT_TYPES,
    )


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("EMB-16-001")
def test_a_failed_commit_leaves_the_case_unchanged(monkeypatch):
    """AC-3: no ER commits, so no proposal is cancelled (#4442)."""
    case, dl, proposals = _proposed_case("abandon-commit-fails")
    before = cast(VulnerabilityCase, dl.read(case.id_)).model_dump(mode="json")
    _fail_commits_after(monkeypatch, allowed=0)

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.FAILURE

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.model_dump(mode="json") == before
    assert updated.current_status.em.state == EM.PROPOSED
    assert updated.proposed_embargo_ids == list(proposals)
    assert _abandonment_entries(dl, case.id_) == []


@pytest.mark.spec("CLP-07-015")
@pytest.mark.spec("EP-09-007")
def test_a_later_failed_commit_abandons_no_proposal(monkeypatch):
    """The first ER commits and the second fails: the abandonment is one
    transaction (ADR-0146), so neither ER, nor the stored rejection, nor any
    cancel is kept, and the CASE_MANAGER holds what it held before.
    """
    case, dl, proposals = _proposed_case("abandon-second-fails")
    before = cast(VulnerabilityCase, dl.read(case.id_)).model_dump(mode="json")
    stored = {a.id_ for a in dl.list_objects("Reject")}
    _fail_commits_after(monkeypatch, allowed=1)

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.FAILURE

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.model_dump(mode="json") == before
    assert updated.proposed_embargo_ids == list(proposals)
    assert _abandonment_entries(dl, case.id_) == []
    assert {a.id_ for a in dl.list_objects("Reject")} == stored


@pytest.mark.spec("CLP-07-015")
@pytest.mark.spec("EMB-16-001")
def test_a_failed_undo_keeps_no_part_of_the_abandonment(monkeypatch):
    """The Reject commits and the Undo of a relayed Invite fails: the
    abandonment is one transaction (ADR-0146), so neither is kept."""
    case, dl, proposals = _proposed_case("abandon-undo-fails", days=(60,))
    (embargo_id,) = proposals
    _relay(dl, case.id_, embargo_id)
    before = cast(VulnerabilityCase, dl.read(case.id_)).model_dump(mode="json")
    _fail_commits_after(monkeypatch, allowed=1)

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.FAILURE

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.model_dump(mode="json") == before
    assert updated.proposed_embargo_ids == [embargo_id]
    assert _abandonment_entries(dl, case.id_) == []
    assert dl.list_objects("Undo") == []


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("EMB-18-001")
def test_a_cancel_the_register_refuses_commits_no_entry(monkeypatch):
    """The pre-check runs the register's own rule, not a copy of it.

    A register that would refuse the second proposal's cancel step refuses
    it before the first ER is committed, so no entry records an abandonment
    the case never applies (CLP-07-013).
    """
    from vultron.errors import VultronInvalidStateTransitionError

    case, dl, proposals = _proposed_case("abandon-register-refuses")
    _first, second = proposals
    before = cast(VulnerabilityCase, dl.read(case.id_)).model_dump(mode="json")
    original = VulnerabilityCase.apply_embargo_register_step

    def _refuse_second(self, changes, **kwargs):
        if any(change.embargo_id == second for change in changes):
            raise VultronInvalidStateTransitionError("simulated refusal")
        return original(self, changes, **kwargs)

    monkeypatch.setattr(
        VulnerabilityCase, "apply_embargo_register_step", _refuse_second
    )

    assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.FAILURE

    assert _abandonment_entries(dl, case.id_) == []
    assert (
        cast(VulnerabilityCase, dl.read(case.id_)).model_dump(mode="json")
        == before
    )


@pytest.mark.spec("CLP-07-013")
def test_each_cancel_follows_its_own_entry():
    """Commit, then write, per proposal: the ledger holds each ER before the
    cancel it records is in the case (CLP-07-013)."""
    from vultron.core.behaviors.embargo import copy_commit

    case, dl, _proposals = _proposed_case("abandon-order", days=(60, 15, 30))
    order: list[tuple[str, object]] = []
    original = copy_commit.save_case_file

    def _spy(datalayer, before, after):
        order.append(("cancel", len(_abandonment_entries(dl, case.id_))))
        return original(datalayer, before, after)

    with pytest.MonkeyPatch.context() as patch:
        # The write: each cancel is copied from its committed entry (ADR-0124).
        patch.setattr(copy_commit, "save_case_file", _spy)
        assert _run(dl, case.id_, CASE_MANAGER_ACTOR) == Status.SUCCESS

    assert order == [("cancel", 1), ("cancel", 2), ("cancel", 3)]
    assert (
        cast(VulnerabilityCase, dl.read(case.id_)).proposed_embargo_ids == []
    )


def _drop(dl: SqliteDataLayer, invite_id: str) -> None:
    """Drop the archived Invite *invite_id* from the store."""
    record_id = ReceivedActivityRecord.build_id(invite_id)
    record = dl.read(record_id)
    assert record is not None
    assert dl.delete(str(record.type_), record_id)
    assert dl.read(record_id) is None


# ---------------------------------------------------------------------------
# ReadOpenEmbargoProposalsNode
# ---------------------------------------------------------------------------


def _tick(node: ReadOpenEmbargoProposalsNode) -> Status:
    bt = py_trees.trees.BehaviourTree(root=node)
    bt.setup()
    bt.tick()
    return node.status


def _read_back() -> dict[str, str]:
    return cast(
        dict[str, str],
        py_trees.blackboard.Blackboard.get(f"/{ABANDONED_PROPOSALS_KEY}"),
    )


def test_read_maps_every_open_proposal_to_its_invite_in_record_order():
    case, dl, proposals = _proposed_case("abandon-read", days=(60, 15, 30))
    setup_blackboard(dl, actor_id=CASE_MANAGER_ACTOR)

    node = ReadOpenEmbargoProposalsNode(case_id=case.id_)
    assert _tick(node) == Status.SUCCESS
    assert list(_read_back().items()) == list(proposals.items())


def test_read_fails_and_clears_the_key_when_nothing_is_open():
    case, dl, _proposals = _proposed_case("abandon-none", days=())
    setup_blackboard(dl, actor_id=CASE_MANAGER_ACTOR)
    py_trees.blackboard.Blackboard.set(
        f"/{ABANDONED_PROPOSALS_KEY}", {"stale": "value"}
    )

    node = ReadOpenEmbargoProposalsNode(case_id=case.id_)
    assert _tick(node) == Status.FAILURE
    assert "no open embargo proposal" in node.feedback_message
    assert _read_back() == {}


def test_read_names_the_proposal_with_no_invite():
    case, dl, proposals = _proposed_case("abandon-ghost", indexed=False)
    setup_blackboard(dl, actor_id=CASE_MANAGER_ACTOR)

    node = ReadOpenEmbargoProposalsNode(case_id=case.id_)
    assert _tick(node) == Status.FAILURE
    for embargo_id in proposals:
        assert embargo_id in node.feedback_message


def test_read_names_the_invite_it_cannot_read():
    case, dl, proposals = _proposed_case("abandon-unread")
    missing = list(proposals.values())[-1]
    _drop(dl, missing)
    setup_blackboard(dl, actor_id=CASE_MANAGER_ACTOR)

    node = ReadOpenEmbargoProposalsNode(case_id=case.id_)
    assert _tick(node) == Status.FAILURE
    assert missing in node.feedback_message
    assert _read_back() == {}
