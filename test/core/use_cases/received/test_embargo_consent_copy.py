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
goes to gap handling and is never patched over (ADR-0124), and the replica
reports the divergence to the CASE_MANAGER (SYNC-16-001).
"""

from typing import Any

import pytest

from test.support.inbox_replay import held_depth
from test.support.ledger import committed_semantic_types, fail_commits
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.embargo import copy_commit
from vultron.core.behaviors.embargo.copy_commit import (
    commit_and_apply_embargo_entries,
)
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent_semantic_types import (
    UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import (
    VultronBTInternalError,
    VultronEntryRefusedError,
    VultronValidationError,
)

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

_S = EmbargoConsentState
_CAUSE = "https://example.org/activities/the-act"
_CASE_DIVERGED = VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED


def _net(name: str) -> LedgerNetwork:
    return LedgerNetwork(f"https://example.org/cases/{name}")


def _rows(record: CaseParticipant) -> list[dict[str, Any]]:
    return [row.model_dump(mode="json") for row in record.embargo_consents]


class TestCaseManagerCommitsThenApplies:
    """Decide → trial apply → commit → apply, as one transaction."""

    @pytest.mark.spec("CLP-07-013")
    def test_each_changed_row_is_its_own_entry_and_is_applied(self):
        net = _net("cc-commit")
        entries = [
            net.planned_consent_entry(
                net.consent_row_change(BYSTANDER, _S.DECLINED), _CAUSE
            ),
            net.planned_consent_entry(
                net.consent_row_change(OWNER, _S.DECLINED), _CAUSE
            ),
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
            record = net.record(MANAGER, actor_id)
            assert record.consent_for(net.initial_embargo_id) == _S.DECLINED

    @pytest.mark.spec("CLP-07-013")
    def test_a_refused_trial_commits_nothing_and_changes_nothing(self):
        net = _net("cc-trial")
        dl = net.stores[MANAGER]
        held = _rows(net.record(MANAGER, BYSTANDER))
        before = committed_semantic_types(dl, net.case_id)
        entries = [
            net.planned_consent_entry(
                net.consent_row_change(OWNER, _S.DECLINED), _CAUSE
            ),
            # AGREED → TIMED_OUT is no consent transition, so the trial
            # refuses the act before its first entry is committed.
            net.planned_consent_entry(
                net.consent_row_change(BYSTANDER, _S.TIMED_OUT), _CAUSE
            ),
        ]

        with pytest.raises(VultronEntryRefusedError):
            commit_and_apply_embargo_entries(dl, net.case_id, entries)

        assert committed_semantic_types(dl, net.case_id) == before
        assert _rows(net.record(MANAGER, BYSTANDER)) == held
        owner = net.record(MANAGER, OWNER)
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
        held = {a: _rows(net.record(MANAGER, a)) for a in (BYSTANDER, OWNER)}
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
            net.planned_consent_entry(
                net.consent_row_change(BYSTANDER, _S.DECLINED), _CAUSE
            ),
            net.planned_consent_entry(
                net.consent_row_change(OWNER, _S.DECLINED), _CAUSE
            ),
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
            assert _rows(net.record(MANAGER, actor_id)) == rows

    @pytest.mark.spec("CLP-07-015")
    def test_a_save_that_fails_after_the_commits_keeps_no_entry(
        self, monkeypatch
    ):
        """The entries and the case-file changes they carry are one
        transaction: a failed save undoes the committed entries too."""
        net = _net("cc-fail-save")
        dl = net.stores[MANAGER]
        held = _rows(net.record(MANAGER, BYSTANDER))
        before = committed_semantic_types(dl, net.case_id)

        def _fail(*_args: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(copy_commit, "save_case_file", _fail)

        with pytest.raises(OSError, match="disk full"):
            commit_and_apply_embargo_entries(
                dl,
                net.case_id,
                [
                    net.planned_consent_entry(
                        net.consent_row_change(BYSTANDER, _S.DECLINED), _CAUSE
                    )
                ],
            )

        assert committed_semantic_types(dl, net.case_id) == before
        assert _rows(net.record(MANAGER, BYSTANDER)) == held

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
                net.planned_consent_entry(
                    net.consent_row_change(BYSTANDER, _S.DECLINED), _CAUSE
                ),
                net.planned_consent_entry(
                    net.consent_row_change(OWNER, _S.DECLINED), _CAUSE
                ),
            ],
        )
        bodies = net.ledger_announcements(BYSTANDER)
        assert len(bodies) == 2

        for body in bodies:
            verdict = net.receive(BYSTANDER, body)
            assert verdict.disposition is HandlerDisposition.APPLIED, (
                verdict.reason
            )

        for actor_id in (BYSTANDER, OWNER):
            replica_rows = _rows(net.record(BYSTANDER, actor_id))
            assert replica_rows == _rows(net.record(MANAGER, actor_id))
            assert (
                net.record(BYSTANDER, actor_id).consent_for(
                    net.initial_embargo_id
                )
                == _S.DECLINED
            )

    def test_a_first_commit_that_fails_changes_nothing(self, monkeypatch):
        net = _net("cc-fail-first")
        dl = net.stores[MANAGER]
        held = _rows(net.record(MANAGER, BYSTANDER))
        fail_commits(monkeypatch, commit_tree)

        with pytest.raises(RuntimeError):
            commit_and_apply_embargo_entries(
                dl,
                net.case_id,
                [
                    net.planned_consent_entry(
                        net.consent_row_change(BYSTANDER, _S.DECLINED), _CAUSE
                    )
                ],
            )

        assert _rows(net.record(MANAGER, BYSTANDER)) == held


class TestReplicaCopies:
    """A replica copies each row entry through the same apply function."""

    @pytest.mark.spec("CM-23-016")
    def test_the_replica_holds_the_case_managers_rows(self):
        net = _net("cc-copy")
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [
                net.planned_consent_entry(
                    net.consent_row_change(BYSTANDER, _S.DECLINED), _CAUSE
                )
            ],
        )

        for body in net.ledger_announcements(BYSTANDER):
            verdict = net.receive(BYSTANDER, body)
            assert verdict.disposition is HandlerDisposition.APPLIED, (
                verdict.reason
            )

        assert _rows(net.record(BYSTANDER, BYSTANDER)) == _rows(
            net.record(MANAGER, BYSTANDER)
        )

    @pytest.mark.spec("CM-23-016")
    def test_an_entry_that_does_not_apply_is_held_for_gap_handling(self):
        """AC-4: its received Announce is held, never patched over.

        The replica's record has diverged from the CASE_MANAGER's (it lost
        its row), so the entry updating that row does not start where this
        replica's case is.
        """
        net = _net("cc-gap")
        replica = net.stores[BYSTANDER]
        net.drop_consent_row(BYSTANDER, BYSTANDER)
        diverged = net.record(BYSTANDER, BYSTANDER)
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [
                net.planned_consent_entry(
                    net.consent_row_change(BYSTANDER, _S.DECLINED), _CAUSE
                )
            ],
        )
        (body,) = net.ledger_announcements(BYSTANDER)
        entry_id = body["object"]["id"]

        verdict = net.receive(BYSTANDER, body)

        assert verdict.disposition is HandlerDisposition.DEFERRED
        assert "its Announce is held" in verdict.reason
        assert replica.read(entry_id) is None, "a refused entry is not stored"
        assert held_depth(replica, net.case_id) == 1
        assert _rows(net.record(BYSTANDER, BYSTANDER)) == _rows(diverged)

    @pytest.mark.spec("SYNC-16-001")
    @pytest.mark.spec("ASK-07-004")
    @pytest.mark.spec("ID-04-004")
    def test_a_diverged_replica_tells_the_case_manager_and_no_one_else(self):
        """The refusal of an entry that extends the chain is a divergence.

        The replica queues one ``LedgerEntryRefused/CaseDiverged`` fault,
        naming the refused ``Announce`` by reference, to the CASE_MANAGER
        alone; the entry stays held and the announce is still deferred.  A
        redelivery of the same ``Announce`` names the same fault.
        """
        net = _net("cc-diverged")
        replica = net.stores[BYSTANDER]
        body = net.diverged_announcement(BYSTANDER, BYSTANDER, _CAUSE)

        verdict = net.receive(BYSTANDER, body)

        assert verdict.disposition is HandlerDisposition.DEFERRED
        assert held_depth(replica, net.case_id) == 1
        assert replica.read(body["object"]["id"]) is None
        (fault,) = net.processing_faults(BYSTANDER)
        assert fault["id"] == derived_activity_id(
            "processing-fault", BYSTANDER, body["id"], _CASE_DIVERGED
        )
        assert fault["to"] == [MANAGER]
        assert not any(fault.get(k) for k in ("cc", "bto", "bcc"))
        assert fault["object"]["failureClass"] == _CASE_DIVERGED
        assert fault["object"]["inReplyTo"] == body["id"]

        net.receive(BYSTANDER, body)

        assert [f["id"] for f in net.processing_faults(BYSTANDER)] == [
            fault["id"]
        ]

    @pytest.mark.spec("SYNC-16-001")
    @pytest.mark.spec("SYNC-14-006")
    def test_a_divergence_the_bound_cannot_hold_is_still_reported(
        self, monkeypatch
    ):
        """A full holding area drops the Announce, not the fault."""
        from vultron.core.services import held_ledger_announces

        monkeypatch.setattr(
            held_ledger_announces, "DEFAULT_HELD_LEDGER_ANNOUNCES_MAX", 0
        )
        net = _net("cc-diverged-full")
        body = net.diverged_announcement(BYSTANDER, BYSTANDER, _CAUSE)

        verdict = net.receive(BYSTANDER, body)

        assert verdict.disposition is HandlerDisposition.REFUSED
        assert held_depth(net.stores[BYSTANDER], net.case_id) == 0
        (fault,) = net.processing_faults(BYSTANDER)
        assert fault["object"]["failureClass"] == _CASE_DIVERGED

    @pytest.mark.spec("SYNC-16-001")
    def test_a_divergence_without_a_trigger_port_is_a_wiring_fault(self):
        """No port is a composition fault, raised, never a silent hold.

        The hold shares the fault's transaction, so it is rolled back with
        it: no ``Announce`` stays held without its fault (ASK-07-010), and
        a redelivery to a correctly wired replica runs the act again.
        """
        net = _net("cc-diverged-no-port")
        body = net.diverged_announcement(BYSTANDER, BYSTANDER, _CAUSE)

        with pytest.raises(VultronBTInternalError):
            net.receive(
                BYSTANDER, body, without=frozenset({"trigger_activity"})
            )

        assert net.processing_faults(BYSTANDER) == []
        assert held_depth(net.stores[BYSTANDER], net.case_id) == 0

    @pytest.mark.spec("SYNC-16-001")
    @pytest.mark.spec("ASK-07-010")
    def test_a_fault_that_cannot_be_queued_rolls_back_the_hold(
        self, monkeypatch
    ):
        """A port that fails to queue the fault is an internal error.

        The refusal is not reported as handled with its fault lost: the use
        case raises, and the held ``Announce`` is rolled back with the
        failed fault.  A redelivery once the port works holds it and
        reports it.
        """

        def _fail(*args: Any, **kwargs: Any) -> None:
            raise VultronValidationError("the outbox refused the fault")

        net = _net("cc-diverged-port-fails")
        body = net.diverged_announcement(BYSTANDER, BYSTANDER, _CAUSE)
        with monkeypatch.context() as patched:
            patched.setattr(
                TriggerActivityAdapter, "emit_processing_fault", _fail
            )
            with pytest.raises(VultronBTInternalError):
                net.receive(BYSTANDER, body)

        assert net.processing_faults(BYSTANDER) == []
        assert held_depth(net.stores[BYSTANDER], net.case_id) == 0

        verdict = net.receive(BYSTANDER, body)

        assert verdict.disposition is HandlerDisposition.DEFERRED
        assert held_depth(net.stores[BYSTANDER], net.case_id) == 1
        (fault,) = net.processing_faults(BYSTANDER)
        assert fault["object"]["failureClass"] == _CASE_DIVERGED

    @pytest.mark.spec("SYNC-16-002")
    @pytest.mark.spec("CLP-04-007")
    def test_no_case_ledger_gains_an_entry_for_a_divergence_fault(self):
        """Neither the replica sending the fault nor the CASE_MANAGER
        receiving it commits it to a case ledger, though the CASE_MANAGER
        answers it with a fresh case copy (SYNC-16-003)."""
        net = _net("cc-diverged-unledgered")
        # The owner's row diverges, so the bystander stays an active
        # participant and the CASE_MANAGER re-seeds it (SYNC-16-003).
        body = net.diverged_announcement(BYSTANDER, OWNER, _CAUSE)
        manager_before = committed_semantic_types(
            net.stores[MANAGER], net.case_id
        )
        replica_before = committed_semantic_types(
            net.stores[BYSTANDER], net.case_id
        )

        net.receive(BYSTANDER, body)
        verdicts = net.deliver(BYSTANDER, to=MANAGER, type_="Create")

        ((_, verdict),) = verdicts
        assert verdict.disposition is HandlerDisposition.APPLIED
        assert (
            committed_semantic_types(net.stores[MANAGER], net.case_id)
            == manager_before
        )
        assert (
            committed_semantic_types(net.stores[BYSTANDER], net.case_id)
            == replica_before
        )

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("SYNC-14-006")
    def test_a_refused_entry_the_bound_cannot_hold_is_refused(
        self, monkeypatch
    ):
        """With the holding area full, a refused entry's Announce is not
        held: the entry is still never patched over or stored, and the
        delivery reports a refusal, not a deferral."""
        from vultron.core.services import held_ledger_announces

        monkeypatch.setattr(
            held_ledger_announces, "DEFAULT_HELD_LEDGER_ANNOUNCES_MAX", 0
        )
        net = _net("cc-gap-full")
        replica = net.stores[BYSTANDER]
        net.drop_consent_row(BYSTANDER, BYSTANDER)
        diverged = net.record(BYSTANDER, BYSTANDER)
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [
                net.planned_consent_entry(
                    net.consent_row_change(BYSTANDER, _S.DECLINED), _CAUSE
                )
            ],
        )
        (body,) = net.ledger_announcements(BYSTANDER)

        verdict = net.receive(BYSTANDER, body)

        assert verdict.disposition is HandlerDisposition.REFUSED
        assert replica.read(body["object"]["id"]) is None
        assert held_depth(replica, net.case_id) == 0
        assert _rows(net.record(BYSTANDER, BYSTANDER)) == _rows(diverged)

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("SYNC-16-007")
    def test_a_held_entry_is_stored_once_a_fresh_copy_reflects_it(self):
        """A refused entry's held Announce is retried; it is never dropped.

        The CASE_MANAGER's fresh ``Announce(VulnerabilityCase)`` names its
        tail, the refused entry, so it replaces the diverged case
        (SYNC-16-006).  Its tree replays the held Announce through the inbox,
        and that delivery stores the entry as the no-op the copy already
        reflects, so the replica's rows match the CASE_MANAGER's
        (SYNC-14-009, SYNC-16-007).
        """
        net = _net("cc-gap-retry")
        replica = net.stores[BYSTANDER]
        net.drop_consent_row(BYSTANDER, BYSTANDER)
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [
                net.planned_consent_entry(
                    net.consent_row_change(BYSTANDER, _S.DECLINED), _CAUSE
                )
            ],
        )
        (body,) = net.ledger_announcements(BYSTANDER)
        entry_id = body["object"]["id"]
        assert (
            net.receive(BYSTANDER, body).disposition
            is HandlerDisposition.DEFERRED
        )

        # The CASE_MANAGER's copy names its tail, the entry the replica
        # holds (SYNC-16-005), so it replaces the case and the held entry is
        # stored as the no-op the copy already reflects (SYNC-16-007).
        seed_id = TriggerActivityAdapter(
            net.stores[MANAGER]
        ).announce_vulnerability_case(
            case_id=net.case_id,
            actor=MANAGER,
            context_id=net.case_id,
            to=[BYSTANDER],
        )
        seed = read_sealed_body_dict(net.stores[MANAGER], seed_id)
        assert seed is not None
        assert net.receive(BYSTANDER, seed).disposition is (
            HandlerDisposition.APPLIED
        )

        assert replica.read(entry_id) is not None
        assert _rows(net.record(BYSTANDER, BYSTANDER)) == _rows(
            net.record(MANAGER, BYSTANDER)
        )
        assert held_depth(replica, net.case_id) == 0

    @pytest.mark.spec("CM-23-016")
    def test_an_entry_already_in_place_is_an_idempotent_no_op(self):
        """A re-applied entry is stored, not refused.

        The replica saved the row but stopped before it stored the entry,
        so the re-delivered entry finds its own result in place.
        """
        net = _net("cc-replay")
        replica = net.stores[BYSTANDER]
        change = net.consent_row_change(BYSTANDER, _S.DECLINED)
        applied = net.record(BYSTANDER, BYSTANDER)
        applied.copy_consent_row(change.row)
        replica.save(applied)
        commit_and_apply_embargo_entries(
            net.stores[MANAGER],
            net.case_id,
            [net.planned_consent_entry(change, _CAUSE)],
        )
        (body,) = net.ledger_announcements(BYSTANDER)

        verdict = net.receive(BYSTANDER, body)

        assert verdict.disposition is HandlerDisposition.APPLIED, (
            verdict.reason
        )
        assert replica.read(body["object"]["id"]) is not None
        assert held_depth(replica, net.case_id) == 0
        assert _rows(net.record(BYSTANDER, BYSTANDER)) == _rows(
            net.record(MANAGER, BYSTANDER)
        )
