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

from test.support.ledger import committed_event_types, fail_commits
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
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
from vultron.core.models.embargo_consent_event_types import (
    UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
)
from vultron.core.models.ledger_gap_buffer import get_ledger_gap_buffer
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import VultronEntryRefusedError

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


def _rows(record: CaseParticipant) -> list[dict[str, Any]]:
    return [row.model_dump(mode="json") for row in record.embargo_consents]


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

        The replica's row has diverged from the CASE_MANAGER's (it already
        reads ``DECLINED``), so the entry moving ``AGREED`` to ``DECLINED``
        does not start where this replica's case is.
        """
        net = _net("cc-gap")
        replica = net.stores[BYSTANDER]
        diverged = _record(net, BYSTANDER, BYSTANDER)
        diverged.copy_consent_row(_row_change(net, BYSTANDER, _S.DECLINED).row)
        replica.save(diverged)
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
