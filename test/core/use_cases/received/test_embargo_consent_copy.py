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

"""Consent rows committed by the CASE_MANAGER and copied by a replica (#4713).

The CASE_MANAGER decides, trial-applies, commits, then applies
(``commit_and_apply_embargo_entries``); each changed consent row is its own
``Create``/``Update(EmbargoConsent)`` entry, and a replica copies it through
the same apply function.  An entry that does not apply to a replica's case
goes to gap handling and is never patched over (ADR-0124).
"""

import json
from typing import Any, cast

import pytest
from py_trees.common import Status

from test.support.ledger import (
    committed_event_types,
    fail_commits,
    ledger_entries,
)
from test.support.ledger_rebuild import received_event
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo import copy_commit
from vultron.core.behaviors.embargo.copy_commit import (
    PlannedEmbargoEntry,
    commit_and_apply_embargo_entries,
    consent_row_entry,
    open_embargo_plans,
)
from vultron.core.behaviors.embargo.nodes.finish_owed import (
    FinishOwedEmbargoEntriesNode,
)
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models import ledger_gap_buffer
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_consent_event_types import (
    CREATE_EMBARGO_CONSENT_EVENT_TYPE,
    UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
)
from vultron.core.models.ledger_gap_buffer import get_ledger_gap_buffer
from vultron.core.models.pending_embargo_entries import PendingEmbargoEntries
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcProposeEmbargoRevisionUseCase,
    SvcProposeEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
)
from vultron.errors import VultronBTInternalError, VultronEntryRefusedError
from vultron.wire.as2.factories import announce_vulnerability_case_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)

_S = EmbargoConsentState
_CAUSE = "https://example.org/activities/the-act"


@pytest.fixture(autouse=True)
def _own_gap_buffers(monkeypatch):
    """Each test gets its own per-actor gap buffers (process-global)."""
    monkeypatch.setattr(ledger_gap_buffer, "_BUFFERS", {})


def _net(name: str, **kwargs: Any) -> LedgerNetwork:
    net = LedgerNetwork(f"https://example.org/cases/{name}", **kwargs)
    # The CASE_MANAGER acts by trigger in a next run, so it has an actor.
    net.stores[MANAGER].create(as_Service(id_=MANAGER, name="Coordinator"))
    return net


def _leave_owner_row_owed(
    net: LedgerNetwork, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Commit the bystander's row and fail the owner's: a plan owes it."""
    failing = [True]
    fail_commits(
        monkeypatch,
        commit_tree,
        allowed=1,
        when=lambda kw: (
            failing[0]
            and kw["event_type"] == UPDATE_EMBARGO_CONSENT_EVENT_TYPE
        ),
    )
    with pytest.raises(RuntimeError):
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [
                _entry(net, _row_change(net, BYSTANDER, _S.DECLINED)),
                _entry(net, _row_change(net, OWNER, _S.DECLINED)),
            ],
        )
    failing[0] = False


def _plan_rows(net: LedgerNetwork) -> None:
    """Store a plan owing the owner's row, with nothing committed."""
    dl = net.stores[MANAGER]
    owed = _entry(net, _row_change(net, OWNER, _S.DECLINED))
    assert owed.record is not None
    dl.save(
        PendingEmbargoEntries(
            case_id=net.case_id,
            act_id=_CAUSE,
            author_id=MANAGER,
            entries=[owed.record().planned(owed.change)],
        )
    )


def _trigger(net: LedgerNetwork, use_case: Any, request: Any) -> Any:
    """Run the CASE_MANAGER's trigger *use_case* on *request*."""
    dl = net.stores[MANAGER]
    return use_case(
        dl,
        request,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


def _propose(net: LedgerNetwork) -> Any:
    """The managing owner proposes an embargo by trigger."""
    return _trigger(
        net,
        SvcProposeEmbargoUseCase,
        ProposeEmbargoTriggerRequest(
            actor_id=MANAGER,
            case_id=net.case_id,
            end_time=days_from_now_utc(30),
        ),
    )


def _next_embargo_run(net: LedgerNetwork) -> None:
    """The next CASE_MANAGER embargo tree for the case: a revision proposal.

    Any embargo tree runs the finishing step first (CLP-07-015); this one
    commits nothing that updates a consent row of the initial embargo.
    """
    _trigger(
        net,
        SvcProposeEmbargoRevisionUseCase,
        ProposeEmbargoRevisionTriggerRequest(
            actor_id=MANAGER,
            case_id=net.case_id,
            end_time=days_from_now_utc(60),
        ),
    )


def _record(net: LedgerNetwork, holder: str, actor_id: str) -> CaseParticipant:
    case = net.case(holder)
    return cast(
        CaseParticipant,
        net.stores[holder].read(case.actor_participant_index[actor_id]),
    )


def _row_change(
    net: LedgerNetwork, actor_id: str, state: EmbargoConsentState
) -> ConsentRowChange:
    return ConsentRowChange(
        verb=ConsentRowVerb.UPDATE,
        row=EmbargoConsent(
            embargo_id=net.initial_embargo_id,
            state=state,
            attributed_to=actor_id,
        ),
    )


def _entry(
    net: LedgerNetwork, change: ConsentRowChange
) -> PlannedEmbargoEntry:
    dl = net.stores[MANAGER]
    return consent_row_entry(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        actor_id=MANAGER,
        case_id=net.case_id,
        change=change,
        cause_id=_CAUSE,
        sync_port=SyncActivityAdapter(dl),
    )


def _announcements(net: LedgerNetwork, replica: str) -> list[dict[str, Any]]:
    """The ``Announce(CaseLedgerEntry)`` bodies queued for *replica*."""
    bodies = []
    for activity in net.queued(MANAGER, to=replica, type_="Announce"):
        body = read_sealed_body_dict(net.stores[MANAGER], activity.id_)
        if ((body or {}).get("object") or {}).get("type") == "CaseLedgerEntry":
            bodies.append(cast(dict[str, Any], body))
    return bodies


def _drop_row(net: LedgerNetwork, holder: str, actor_id: str) -> None:
    """Make *holder*'s copy of *actor_id*'s record lose its consent row.

    A diverged replica: an ``Update`` of that row then has no row to start
    from, whatever state it carries.
    """
    record = _record(net, holder, actor_id)
    record.embargo_consents = [
        row
        for row in record.embargo_consents
        if row.embargo_id != net.initial_embargo_id
    ]
    net.stores[holder].save(record)


def _rows(record: CaseParticipant) -> list[dict[str, Any]]:
    return [row.model_dump(mode="json") for row in record.embargo_consents]


def _initial_row(net: LedgerNetwork, holder: str, actor_id: str) -> Any:
    """*holder*'s copy of *actor_id*'s row for the initial embargo."""
    row = _record(net, holder, actor_id).held_row(net.initial_embargo_id)
    assert row is not None, (holder, actor_id)
    return row.model_dump(mode="json")


class TestCaseManagerCommitsThenApplies:
    """AC-3: decide → trial apply → commit → apply."""

    @pytest.mark.spec("CLP-07-013")
    def test_each_changed_row_is_its_own_entry_and_is_applied(self):
        net = _net("cc-commit")
        entries = [
            _entry(net, _row_change(net, BYSTANDER, _S.DECLINED)),
            _entry(net, _row_change(net, OWNER, _S.DECLINED)),
        ]
        before = committed_event_types(net.stores[MANAGER], net.case_id)

        commit_and_apply_embargo_entries(
            net.stores[MANAGER], net.case_id, entries
        )

        after = committed_event_types(net.stores[MANAGER], net.case_id)
        assert after[len(before) :] == [UPDATE_EMBARGO_CONSENT_EVENT_TYPE] * 2
        for actor_id in (BYSTANDER, OWNER):
            record = _record(net, MANAGER, actor_id)
            assert record.consent_for(net.initial_embargo_id) == _S.DECLINED

    @pytest.mark.spec("CLP-07-013")
    def test_a_refused_trial_commits_nothing_and_changes_nothing(self):
        net = _net("cc-trial")
        dl = net.stores[MANAGER]
        held = _rows(_record(net, MANAGER, BYSTANDER))
        before = committed_event_types(dl, net.case_id)
        entries = [
            _entry(net, _row_change(net, OWNER, _S.DECLINED)),
            # AGREED → TIMED_OUT is no consent transition, so the trial
            # refuses the act before its first entry is committed.
            _entry(net, _row_change(net, BYSTANDER, _S.TIMED_OUT)),
        ]

        with pytest.raises(VultronEntryRefusedError):
            commit_and_apply_embargo_entries(dl, net.case_id, entries)

        assert committed_event_types(dl, net.case_id) == before
        assert _rows(_record(net, MANAGER, BYSTANDER)) == held
        owner = _record(net, MANAGER, OWNER)
        assert owner.consent_for(net.initial_embargo_id) == _S.AGREED

    @pytest.mark.spec("CLP-07-013")
    def test_a_failed_commit_makes_only_the_changes_already_committed(
        self, monkeypatch
    ):
        net = _net("cc-fail")
        dl = net.stores[MANAGER]
        fail_commits(
            monkeypatch,
            commit_tree,
            allowed=1,
            when=lambda kw: (
                kw["event_type"] == UPDATE_EMBARGO_CONSENT_EVENT_TYPE
            ),
        )
        entries = [
            _entry(net, _row_change(net, BYSTANDER, _S.DECLINED)),
            _entry(net, _row_change(net, OWNER, _S.DECLINED)),
        ]

        with pytest.raises(RuntimeError):
            commit_and_apply_embargo_entries(dl, net.case_id, entries)

        assert (
            committed_event_types(dl, net.case_id).count(
                UPDATE_EMBARGO_CONSENT_EVENT_TYPE
            )
            == 1
        )
        bystander = _record(net, MANAGER, BYSTANDER)
        assert bystander.consent_for(net.initial_embargo_id) == _S.DECLINED
        owner = _record(net, MANAGER, OWNER)
        assert owner.consent_for(net.initial_embargo_id) == _S.AGREED

    @pytest.mark.spec("CLP-07-015")
    @pytest.mark.spec("CM-23-016")
    def test_the_next_run_commits_the_entries_a_failed_commit_left_owed(
        self, monkeypatch
    ):
        """The managing owner's proposal committed with only its first
        ``Create(EmbargoConsent)``: the next CASE_MANAGER embargo tree, a
        second proposal, commits the rows the first owes, unchanged and in
        order, before its own act, and every replica copies them
        (ADR-0146)."""
        net = _net("cc-finish", owner=MANAGER, em_state=EM.NONE)
        dl = net.stores[MANAGER]
        failing = [True]
        fail_commits(
            monkeypatch,
            commit_tree,
            allowed=1,
            when=lambda kw: (
                failing[0]
                and kw["event_type"] == CREATE_EMBARGO_CONSENT_EVENT_TYPE
            ),
        )
        with pytest.raises(VultronBTInternalError, match="commit failed"):
            _propose(net)
        failing[0] = False
        (plan,) = open_embargo_plans(dl, net.case_id)
        owed_ids = [owed.activity_id for owed in plan.entries]
        assert len(owed_ids) >= 2, "the proposal owes more than one row"
        (embargo_id,) = net.case(MANAGER).proposed_embargo_ids
        assert _record(net, MANAGER, BYSTANDER).held_row(embargo_id) is None
        before = len(ledger_entries(dl, net.case_id))

        _propose(net)

        new = ledger_entries(dl, net.case_id)[before:]
        # The plan names every row after the act; the first committed.  The
        # rest come first, as planned, then the new proposal.
        assert [e.log_object_id for e in new[: len(owed_ids) - 1]] == (
            owed_ids[1:]
        )
        assert [e.payload_snapshot for e in new[: len(owed_ids) - 1]] == [
            json.loads(cast(str, owed.activity_json))
            for owed in plan.entries[1:]
        ]
        assert new[len(owed_ids) - 1].event_type == "invite_to_embargo_on_case"
        assert open_embargo_plans(dl, net.case_id) == []
        for actor_id in (MANAGER, BYSTANDER, PROPOSER):
            assert _record(net, MANAGER, actor_id).held_row(embargo_id)
        net.replay_ledger(BYSTANDER)
        for actor_id in (MANAGER, BYSTANDER, PROPOSER):
            assert _rows(_record(net, BYSTANDER, actor_id)) == _rows(
                _record(net, MANAGER, actor_id)
            ), actor_id

    @pytest.mark.spec("CLP-07-015")
    def test_the_next_run_commits_nothing_for_an_act_that_never_committed(
        self, monkeypatch
    ):
        """The act's own entry failed: its stored plan owes nothing, and the
        next CASE_MANAGER embargo tree discards it (ADR-0146)."""
        net = _net("cc-discard")
        dl = net.stores[MANAGER]
        held = {
            actor_id: _initial_row(net, MANAGER, actor_id)
            for actor_id in (BYSTANDER, OWNER)
        }
        failing = [True]
        fail_commits(monkeypatch, commit_tree, when=lambda kw: failing[0])
        with pytest.raises(RuntimeError):
            commit_and_apply_embargo_entries(
                dl,
                net.case_id,
                [
                    _entry(net, _row_change(net, BYSTANDER, _S.DECLINED)),
                    _entry(net, _row_change(net, OWNER, _S.DECLINED)),
                ],
            )
        failing[0] = False
        (plan,) = open_embargo_plans(dl, net.case_id)

        _next_embargo_run(net)

        recorded = {e.log_object_id for e in ledger_entries(dl, net.case_id)}
        assert not {owed.activity_id for owed in plan.entries} & recorded
        assert open_embargo_plans(dl, net.case_id) == []
        for actor_id, row in held.items():
            assert _initial_row(net, MANAGER, actor_id) == row

    @pytest.mark.spec("CLP-07-015")
    @pytest.mark.spec("CLP-07-014")
    def test_a_stored_plan_is_bookkeeping_and_leaves_once_finished(self):
        """The plan is stored before the first commit, is no ledger entry,
        and is removed once the last entry commits (CLP-07-014)."""
        net = _net("cc-plan")
        dl = net.stores[MANAGER]
        seen: list[list[PendingEmbargoEntries]] = []
        entries = [
            _entry(net, _row_change(net, BYSTANDER, _S.DECLINED)),
            _entry(net, _row_change(net, OWNER, _S.DECLINED)),
        ]
        first = entries[0]
        assert first.commit is not None

        def _observe_then_commit() -> Any:
            seen.append(open_embargo_plans(dl, net.case_id))
            assert first.commit is not None
            return first.commit()

        commit_and_apply_embargo_entries(
            dl,
            net.case_id,
            [
                PlannedEmbargoEntry(
                    change=first.change,
                    commit=_observe_then_commit,
                    record=first.record,
                ),
                entries[1],
            ],
        )

        ((plan,),) = seen
        (owed,) = plan.entries
        assert owed.change == _row_change(net, OWNER, _S.DECLINED)
        assert plan.author_id == MANAGER
        assert open_embargo_plans(dl, net.case_id) == []
        assert all(
            "PendingEmbargoEntries" not in json.dumps(entry.payload_snapshot)
            for entry in ledger_entries(dl, net.case_id)
        )

    @pytest.mark.spec("CLP-07-015")
    def test_a_single_entry_act_stores_no_plan(self, monkeypatch):
        """An act with one entry owes nothing after it, so no plan is stored
        and a failed commit leaves none behind."""
        net = _net("cc-single")
        dl = net.stores[MANAGER]
        fail_commits(monkeypatch, commit_tree)

        with pytest.raises(RuntimeError):
            commit_and_apply_embargo_entries(
                dl,
                net.case_id,
                [_entry(net, _row_change(net, BYSTANDER, _S.DECLINED))],
            )

        assert open_embargo_plans(dl, net.case_id) == []

    @pytest.mark.spec("CLP-07-015")
    def test_an_owed_entry_with_no_record_activity_is_refused_first(self):
        """An entry after the act's own that no later run could commit is a
        fault in the caller: nothing is committed, stored or saved."""
        net = _net("cc-no-record")
        dl = net.stores[MANAGER]
        before = committed_event_types(dl, net.case_id)
        row = _entry(net, _row_change(net, BYSTANDER, _S.DECLINED))

        with pytest.raises(VultronBTInternalError, match="no record"):
            commit_and_apply_embargo_entries(
                dl,
                net.case_id,
                [
                    _entry(net, _row_change(net, OWNER, _S.DECLINED)),
                    PlannedEmbargoEntry(change=row.change, commit=row.commit),
                ],
            )

        assert committed_event_types(dl, net.case_id) == before
        assert open_embargo_plans(dl, net.case_id) == []

    @pytest.mark.spec("CLP-07-015")
    def test_an_owed_entry_that_no_longer_applies_keeps_the_plan(
        self, monkeypatch
    ):
        """A plan whose owed row no longer applies is a fault in the
        CASE_MANAGER's own store: the finish raises and keeps the plan."""
        net = _net("cc-stale")
        dl = net.stores[MANAGER]
        _leave_owner_row_owed(net, monkeypatch)
        _drop_row(net, MANAGER, OWNER)
        net.bypass_ledger()

        with pytest.raises(VultronBTInternalError, match="no longer apply"):
            copy_commit.finish_owed_embargo_entries(dl, net.case_id, MANAGER)

        assert open_embargo_plans(dl, net.case_id) != []

    @pytest.mark.spec("CLP-07-015")
    def test_a_plan_another_actor_authored_is_refused(self, monkeypatch):
        """Only the CASE_MANAGER that authored a plan finishes it."""
        net = _net("cc-author")
        dl = net.stores[MANAGER]
        _leave_owner_row_owed(net, monkeypatch)

        with pytest.raises(VultronBTInternalError, match="authored by"):
            copy_commit.finish_owed_embargo_entries(
                dl, net.case_id, "https://example.org/users/someone-else"
            )

        assert open_embargo_plans(dl, net.case_id) != []

    @pytest.mark.spec("CLP-07-015")
    def test_a_committed_entry_whose_save_failed_is_applied_not_recommitted(
        self, monkeypatch
    ):
        """Every entry committed but the case file was not saved: the finish
        applies the changes and commits nothing again."""
        net = _net("cc-save")
        dl = net.stores[MANAGER]
        real_save = copy_commit.save_case_file
        failing = [True]

        def _save(*args: Any, **kwargs: Any) -> None:
            if failing[0]:
                raise RuntimeError("save failed")
            real_save(*args, **kwargs)

        monkeypatch.setattr(copy_commit, "save_case_file", _save)
        with pytest.raises(RuntimeError, match="save failed"):
            commit_and_apply_embargo_entries(
                dl,
                net.case_id,
                [
                    _entry(net, _row_change(net, BYSTANDER, _S.DECLINED)),
                    _entry(net, _row_change(net, OWNER, _S.DECLINED)),
                ],
            )
        failing[0] = False
        before = committed_event_types(dl, net.case_id)
        assert _record(net, MANAGER, OWNER).consent_for(
            net.initial_embargo_id
        ) == (_S.AGREED)

        copy_commit.finish_owed_embargo_entries(dl, net.case_id, MANAGER)

        assert committed_event_types(dl, net.case_id) == before
        owner = _record(net, MANAGER, OWNER)
        assert owner.consent_for(net.initial_embargo_id) == _S.DECLINED
        assert open_embargo_plans(dl, net.case_id) == []

    @pytest.mark.spec("CLP-07-015")
    def test_the_finishing_node_with_no_case_does_nothing(self):
        """A tree that learns its case at tick time and has none finishes
        nothing."""
        net = _net("cc-no-case")
        dl = net.stores[MANAGER]
        _plan_rows(net)

        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=FinishOwedEmbargoEntriesNode(), actor_id=MANAGER
        )

        assert result.status is Status.SUCCESS
        assert open_embargo_plans(dl, net.case_id) != []

    def test_a_first_commit_that_fails_changes_nothing(self, monkeypatch):
        net = _net("cc-fail-first")
        dl = net.stores[MANAGER]
        held = _rows(_record(net, MANAGER, BYSTANDER))
        fail_commits(monkeypatch, commit_tree)

        with pytest.raises(RuntimeError):
            commit_and_apply_embargo_entries(
                dl,
                net.case_id,
                [_entry(net, _row_change(net, BYSTANDER, _S.DECLINED))],
            )

        assert _rows(_record(net, MANAGER, BYSTANDER)) == held


class TestReplicaCopies:
    """A replica copies each row entry through the same apply function."""

    @pytest.mark.spec("CM-23-016")
    def test_the_replica_holds_the_case_managers_rows(self):
        net = _net("cc-copy")
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [_entry(net, _row_change(net, BYSTANDER, _S.DECLINED))],
        )

        for body in _announcements(net, BYSTANDER):
            verdict = net.receive(BYSTANDER, body)
            assert verdict.disposition is HandlerDisposition.APPLIED, (
                verdict.reason
            )

        assert _rows(_record(net, BYSTANDER, BYSTANDER)) == _rows(
            _record(net, MANAGER, BYSTANDER)
        )

    @pytest.mark.spec("CM-23-016")
    def test_an_entry_that_does_not_apply_is_held_for_gap_handling(self):
        """AC-4: refused into ``LedgerGapBuffer``, never patched over.

        The replica's record has diverged from the CASE_MANAGER's (it lost
        its row), so the entry updating that row does not start where this
        replica's case is.
        """
        net = _net("cc-gap")
        replica = net.stores[BYSTANDER]
        _drop_row(net, BYSTANDER, BYSTANDER)
        diverged = _record(net, BYSTANDER, BYSTANDER)
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [_entry(net, _row_change(net, BYSTANDER, _S.DECLINED))],
        )
        (body,) = _announcements(net, BYSTANDER)
        entry_id = body["object"]["id"]

        verdict = net.receive(BYSTANDER, body)

        assert verdict.disposition is HandlerDisposition.DEFERRED
        assert "gap buffer" in verdict.reason
        assert replica.read(entry_id) is None, "a refused entry is not stored"
        assert get_ledger_gap_buffer(BYSTANDER).depth(net.case_id) == 1
        assert _rows(_record(net, BYSTANDER, BYSTANDER)) == _rows(diverged)

    @pytest.mark.spec("CM-23-016")
    def test_a_held_entry_applies_once_the_case_reaches_its_start(self):
        """The gap buffer retries a refused entry; it is never dropped.

        Once this replica's case is where the entry starts (here the
        diverged row is put back), the CASE_MANAGER's fresh
        ``Announce(VulnerabilityCase)`` (SYNC-16) seeds nothing new, but its
        tree hands the held entry back to the inbox, and that delivery applies
        and stores it (SYNC-14-009, SYNC-16-007).
        """
        net = _net("cc-gap-retry")
        replica = net.stores[BYSTANDER]
        agreed = _rows(_record(net, BYSTANDER, BYSTANDER))
        _drop_row(net, BYSTANDER, BYSTANDER)
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [_entry(net, _row_change(net, BYSTANDER, _S.DECLINED))],
        )
        (body,) = _announcements(net, BYSTANDER)
        entry_id = body["object"]["id"]
        assert (
            net.receive(BYSTANDER, body).disposition
            is HandlerDisposition.DEFERRED
        )

        restored = _record(net, BYSTANDER, BYSTANDER)
        restored.copy_consent_row(_row_change(net, BYSTANDER, _S.AGREED).row)
        replica.save(restored)
        assert _rows(restored) == agreed
        seed = announce_vulnerability_case_activity(
            net.case(MANAGER), actor=MANAGER, to=[BYSTANDER]
        )
        assert (
            net.receive_event(
                BYSTANDER,
                received_event(seed, BYSTANDER),
            ).disposition
            is HandlerDisposition.APPLIED
        )

        assert replica.read(entry_id) is not None
        assert _rows(_record(net, BYSTANDER, BYSTANDER)) == _rows(
            _record(net, MANAGER, BYSTANDER)
        )
        assert get_ledger_gap_buffer(BYSTANDER).depth(net.case_id) == 0

    @pytest.mark.spec("CM-23-016")
    def test_an_entry_already_in_place_is_an_idempotent_no_op(self):
        """A re-applied entry is stored, not refused.

        The replica saved the row but stopped before it stored the entry,
        so the re-delivered entry finds its own result in place.
        """
        net = _net("cc-replay")
        replica = net.stores[BYSTANDER]
        change = _row_change(net, BYSTANDER, _S.DECLINED)
        applied = _record(net, BYSTANDER, BYSTANDER)
        applied.copy_consent_row(change.row)
        replica.save(applied)
        commit_and_apply_embargo_entries(
            net.stores[MANAGER], net.case_id, [_entry(net, change)]
        )
        (body,) = _announcements(net, BYSTANDER)

        verdict = net.receive(BYSTANDER, body)

        assert verdict.disposition is HandlerDisposition.APPLIED, (
            verdict.reason
        )
        assert replica.read(body["object"]["id"]) is not None
        assert get_ledger_gap_buffer(BYSTANDER).depth(net.case_id) == 0
        assert _rows(_record(net, BYSTANDER, BYSTANDER)) == _rows(
            _record(net, MANAGER, BYSTANDER)
        )
