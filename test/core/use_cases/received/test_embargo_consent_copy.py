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

from typing import Any, cast

import pytest

from test.support.ledger import committed_semantic_types, fail_commits
from test.support.ledger_rebuild import received_event
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.embargo import copy_commit
from vultron.core.behaviors.embargo.copy_commit import (
    PlannedEmbargoEntry,
    commit_and_apply_embargo_entries,
    consent_row_entry,
)
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models import ledger_gap_buffer
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_consent_semantic_types import (
    UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
)
from vultron.core.models.ledger_gap_buffer import get_ledger_gap_buffer
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import VultronEntryRefusedError
from vultron.wire.as2.factories import announce_vulnerability_case_activity

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

_S = EmbargoConsentState
_CAUSE = "https://example.org/activities/the-act"


@pytest.fixture(autouse=True)
def _own_gap_buffers(monkeypatch):
    """Each test gets its own per-actor gap buffers (process-global)."""
    monkeypatch.setattr(ledger_gap_buffer, "_BUFFERS", {})


def _net(name: str) -> LedgerNetwork:
    return LedgerNetwork(f"https://example.org/cases/{name}")


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


class TestCaseManagerCommitsThenApplies:
    """Decide → trial apply → commit → apply, as one transaction."""

    @pytest.mark.spec("CLP-07-013")
    def test_each_changed_row_is_its_own_entry_and_is_applied(self):
        net = _net("cc-commit")
        entries = [
            _entry(net, _row_change(net, BYSTANDER, _S.DECLINED)),
            _entry(net, _row_change(net, OWNER, _S.DECLINED)),
        ]
        before = committed_semantic_types(net.stores[MANAGER], net.case_id)

        commit_and_apply_embargo_entries(
            net.stores[MANAGER], net.case_id, entries
        )

        after = committed_semantic_types(net.stores[MANAGER], net.case_id)
        assert (
            after[len(before) :] == [UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE] * 2
        )
        for actor_id in (BYSTANDER, OWNER):
            record = _record(net, MANAGER, actor_id)
            assert record.consent_for(net.initial_embargo_id) == _S.DECLINED

    @pytest.mark.spec("CLP-07-013")
    def test_a_refused_trial_commits_nothing_and_changes_nothing(self):
        net = _net("cc-trial")
        dl = net.stores[MANAGER]
        held = _rows(_record(net, MANAGER, BYSTANDER))
        before = committed_semantic_types(dl, net.case_id)
        entries = [
            _entry(net, _row_change(net, OWNER, _S.DECLINED)),
            # AGREED → TIMED_OUT is no consent transition, so the trial
            # refuses the act before its first entry is committed.
            _entry(net, _row_change(net, BYSTANDER, _S.TIMED_OUT)),
        ]

        with pytest.raises(VultronEntryRefusedError):
            commit_and_apply_embargo_entries(dl, net.case_id, entries)

        assert committed_semantic_types(dl, net.case_id) == before
        assert _rows(_record(net, MANAGER, BYSTANDER)) == held
        owner = _record(net, MANAGER, OWNER)
        assert owner.consent_for(net.initial_embargo_id) == _S.AGREED

    @pytest.mark.spec("CLP-07-015")
    def test_a_commit_failing_part_way_leaves_no_entry_and_no_row_change(
        self, monkeypatch
    ):
        """The second row's commit fails: the first row's entry, its
        activity and announcements, and both rows' changes are all undone
        (ADR-0146)."""
        net = _net("cc-fail")
        dl = net.stores[MANAGER]
        held = {a: _rows(_record(net, MANAGER, a)) for a in (BYSTANDER, OWNER)}
        before = committed_semantic_types(dl, net.case_id)
        queued = dl.outbox_list()
        failed = fail_commits(
            monkeypatch,
            commit_tree,
            allowed=1,
            when=lambda kw: (
                kw["semantic_type"] == UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE
            ),
        )
        entries = [
            _entry(net, _row_change(net, BYSTANDER, _S.DECLINED)),
            _entry(net, _row_change(net, OWNER, _S.DECLINED)),
        ]

        with pytest.raises(RuntimeError):
            commit_and_apply_embargo_entries(dl, net.case_id, entries)

        assert len(failed) == 2, (
            "the first commit ran before the second failed"
        )
        assert committed_semantic_types(dl, net.case_id) == before
        assert dl.outbox_list() == queued
        for activity_id in failed:
            assert dl.read(activity_id) is None
        for actor_id, rows in held.items():
            assert _rows(_record(net, MANAGER, actor_id)) == rows

    @pytest.mark.spec("CLP-07-015")
    def test_a_save_that_fails_after_the_commits_keeps_no_entry(
        self, monkeypatch
    ):
        """The entries and the case-file changes they carry are one
        transaction: a failed save undoes the committed entries too."""
        net = _net("cc-fail-save")
        dl = net.stores[MANAGER]
        held = _rows(_record(net, MANAGER, BYSTANDER))
        before = committed_semantic_types(dl, net.case_id)

        def _fail(*_args: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(copy_commit, "save_case_file", _fail)

        with pytest.raises(OSError, match="disk full"):
            commit_and_apply_embargo_entries(
                dl,
                net.case_id,
                [_entry(net, _row_change(net, BYSTANDER, _S.DECLINED))],
            )

        assert committed_semantic_types(dl, net.case_id) == before
        assert _rows(_record(net, MANAGER, BYSTANDER)) == held

    @pytest.mark.spec("CLP-07-015")
    @pytest.mark.spec("CM-23-016")
    def test_on_success_a_replica_holds_the_case_managers_rows(self):
        """Both entries commit and are announced; a replica that copies them
        holds every row the CASE_MANAGER holds."""
        net = _net("cc-whole")
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [
                _entry(net, _row_change(net, BYSTANDER, _S.DECLINED)),
                _entry(net, _row_change(net, OWNER, _S.DECLINED)),
            ],
        )
        bodies = _announcements(net, BYSTANDER)
        assert len(bodies) == 2

        for body in bodies:
            verdict = net.receive(BYSTANDER, body)
            assert verdict.disposition is HandlerDisposition.APPLIED, (
                verdict.reason
            )

        for actor_id in (BYSTANDER, OWNER):
            replica_rows = _rows(_record(net, BYSTANDER, actor_id))
            assert replica_rows == _rows(_record(net, MANAGER, actor_id))
            assert (
                _record(net, BYSTANDER, actor_id).consent_for(
                    net.initial_embargo_id
                )
                == _S.DECLINED
            )

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
