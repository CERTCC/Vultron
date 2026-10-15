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

"""Termination commits first and replays by copying (#4714, ADR-0124).

The CASE_MANAGER decides a termination, commits the ``Remove(EmbargoEvent)``
entry that carries the ``TERMINATE`` step, and only then applies it through
the one apply function.  The ``Remove`` entry is the whole step, the
``CANCEL`` of every open proposal included (EP-08-004, ADR-0122), so no other
embargo or consent entry follows it.  A replica copies the entry through the
same function and reaches the CASE_MANAGER's register and rows.  Each actor
has its own store (TB-06-007); a replica is handed the CASE_MANAGER's ledger
broadcast and nothing else.
"""

from datetime import timedelta
from typing import Any, cast

import py_trees
import pytest

from test.support.embargo_register import propose, write_consent_rows
from test.support.ledger import committed_event_types, fail_commits
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.end_time_tree import (
    end_embargo_if_end_time_passed,
)
from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_EVENT_TYPE
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models._helpers import now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent_event_types import CONSENT_ROW_VERBS
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationCauseKind,
    ThreatSignal,
    ThreatSignalTermination,
)
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

_REPLICAS = (OWNER, BYSTANDER)


def _net(name: str) -> LedgerNetwork:
    """An embargoed case with one open revision, the same in every store.

    The revision makes the termination's ``CANCEL`` part of the step under
    test (EP-08-004).
    """
    net = LedgerNetwork(f"https://example.org/cases/{name}")
    revision = f"{net.case_id}/embargo_events/revision"
    for dl in net.stores.values():
        case = cast(VulnerabilityCase, dl.read(net.case_id))
        propose(case, revision)
        dl.save(case)
        write_consent_rows(dl, case)
    assert net.case(MANAGER).em_state is EM.REVISE
    return net


def _end_time_passed(net: LedgerNetwork) -> None:
    """Move the embargo in force's end time an hour into the past, in every
    store."""
    for dl in net.stores.values():
        dl.save(
            as_EmbargoEvent(
                id_=net.initial_embargo_id,
                context=net.case_id,
                end_time=now_utc() - timedelta(hours=1),
            )
        )


def _bridge(net: LedgerNetwork) -> BTBridge:
    dl = net.stores[MANAGER]
    return BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )


def _cascade(
    net: LedgerNetwork,
    termination: Any = None,
) -> py_trees.common.Status:
    """The CASE_MANAGER's cascade termination: no use case builds the
    ``Remove``."""
    result = _bridge(net).execute_with_setup(
        terminate_embargo_bt(
            case_id=net.case_id,
            result_out={},
            termination=termination
            or ThreatSignalTermination(signals=[ThreatSignal.X]),
        ),
        actor_id=MANAGER,
    )
    return result.status


def _trigger(net: LedgerNetwork) -> py_trees.common.Status:
    """The CASE_MANAGER's own terminate trigger: an early end, its ``Remove``
    built by the trigger's builder, as ``SvcTerminateEmbargoUseCase``
    builds it."""
    factory = TriggerActivityAdapter(net.stores[MANAGER])

    def _builder(to: list[str] | None) -> tuple[str, str]:
        return factory.terminate_embargo(
            embargo_id=net.initial_embargo_id,
            case_id=net.case_id,
            actor=MANAGER,
            reason=TerminationReason.EARLY,
            to=to,
        )

    result = _bridge(net).execute_with_setup(
        terminate_embargo_bt(
            case_id=net.case_id,
            result_out={},
            termination=EmbargoTermination.early(),
            activity_builder=_builder,
        ),
        actor_id=MANAGER,
    )
    return result.status


def _lazy_end_time_check(net: LedgerNetwork) -> None:
    dl = net.stores[MANAGER]
    end_embargo_if_end_time_passed(
        datalayer=dl,
        case_id=net.case_id,
        actor_id=MANAGER,
        now=now_utc(),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    )


def _register(net: LedgerNetwork, holder: str) -> list[dict[str, Any]]:
    return [
        entry.model_dump(mode="json")
        for entry in net.case(holder).embargo_register
    ]


def _rows(net: LedgerNetwork, holder: str) -> dict[str, list[dict]]:
    """Every participant's consent rows in *holder*'s store, by actor."""
    case = net.case(holder)
    rows = {}
    for actor_id, participant_id in case.actor_participant_index.items():
        record = cast(CaseParticipant, net.stores[holder].read(participant_id))
        rows[actor_id] = [
            row.model_dump(mode="json") for row in record.embargo_consents
        ]
    return rows


def _queued_removes(net: LedgerNetwork) -> list[str]:
    dl = net.stores[MANAGER]
    return [
        activity_id
        for activity_id in dl.outbox_list()
        if cast(VultronActivity, dl.read(activity_id)).type_ == "Remove"
    ]


def _embargo_entry_types(net: LedgerNetwork, since: int) -> list[str]:
    """The embargo and consent event types committed after the first
    *since* entries."""
    embargo_types = {EMBARGO_TEARDOWN_EVENT_TYPE, *CONSENT_ROW_VERBS}
    return [
        event_type
        for event_type in committed_event_types(
            net.stores[MANAGER], net.case_id
        )[since:]
        if event_type in embargo_types
    ]


class TestCaseManagerCommitsFirst:
    """AC-1: decide → trial apply → commit the ``Remove`` → apply."""

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.spec("EP-08-004")
    @pytest.mark.parametrize("path", ["trigger", "cascade"])
    def test_the_remove_is_committed_before_the_case_changes(
        self, monkeypatch, path
    ):
        """At the commit the embargo is still in force; afterwards it is
        ended, every open proposal cancelled, by that one entry."""
        net = _net(f"tc-order-{path}")
        before = len(committed_event_types(net.stores[MANAGER], net.case_id))
        em_at_commit: list[EM] = []

        def _record(kwargs: dict[str, Any]) -> bool:
            if kwargs["event_type"] == EMBARGO_TEARDOWN_EVENT_TYPE:
                em_at_commit.append(net.case(MANAGER).em_state)
            return False  # observe only; every commit runs

        fail_commits(monkeypatch, commit_tree, when=_record)
        run = _trigger if path == "trigger" else _cascade
        assert run(net) == py_trees.common.Status.SUCCESS

        assert em_at_commit == [EM.REVISE]
        ended = net.case(MANAGER)
        assert ended.em_state is EM.EXITED
        assert {e.embargo_id: e.status for e in ended.embargo_register} == {
            net.initial_embargo_id: EmbargoRegisterStatus.TERMINATED,
            f"{net.case_id}/embargo_events/revision": (
                EmbargoRegisterStatus.CANCELLED
            ),
        }
        # One activity/object pair, one entry: no cancel or consent entry.
        assert _embargo_entry_types(net, before) == [
            EMBARGO_TEARDOWN_EVENT_TYPE
        ]

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.spec("SYNC-09-002")
    @pytest.mark.parametrize("path", ["trigger", "cascade"])
    def test_a_failed_commit_leaves_the_case_file_and_outbox_unchanged(
        self, monkeypatch, path
    ):
        """The #4653 defect: a teardown whose commit fails used to end the
        embargo locally with no entry.  Now nothing changes, and a retry can
        still end it."""
        net = _net(f"tc-fail-{path}")
        register, rows = _register(net, MANAGER), _rows(net, MANAGER)
        failed = fail_commits(
            monkeypatch,
            commit_tree,
            when=lambda kw: kw["event_type"] == EMBARGO_TEARDOWN_EVENT_TYPE,
        )

        run = _trigger if path == "trigger" else _cascade
        assert run(net) == py_trees.common.Status.FAILURE

        assert len(failed) == 1, "the teardown was never committed"
        assert net.case(MANAGER).em_state is EM.REVISE
        assert _register(net, MANAGER) == register
        assert _rows(net, MANAGER) == rows
        assert _queued_removes(net) == [], "an unrecorded Remove was queued"
        assert EMBARGO_TEARDOWN_EVENT_TYPE not in committed_event_types(
            net.stores[MANAGER], net.case_id
        )

        monkeypatch.undo()
        assert _cascade(net) == py_trees.common.Status.SUCCESS
        assert net.case(MANAGER).em_state is EM.EXITED

    @pytest.mark.spec("CLP-07-013")
    def test_a_refused_decision_commits_nothing(self):
        """A threat termination with no threat signal set is refused before
        any entry is committed."""
        net = _net("tc-refused")
        before = committed_event_types(net.stores[MANAGER], net.case_id)
        register = _register(net, MANAGER)

        status = _cascade(net, ThreatSignalTermination())

        assert status == py_trees.common.Status.FAILURE
        assert committed_event_types(net.stores[MANAGER], net.case_id) == (
            before
        )
        assert _register(net, MANAGER) == register
        assert _queued_removes(net) == []

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.spec("EMB-18-006")
    def test_a_step_the_trial_refuses_commits_nothing(self, monkeypatch):
        """The trial apply runs before the commit: a step the apply function
        refuses stops the act with nothing committed or written."""
        from vultron.core.behaviors.embargo.nodes import termination_commit
        from vultron.errors import VultronEntryRefusedError

        def _refuse(*_args: Any, **_kwargs: Any) -> Any:
            raise VultronEntryRefusedError("the step does not apply")

        monkeypatch.setattr(termination_commit, "trial_apply", _refuse)
        net = _net("tc-trial")
        before = committed_event_types(net.stores[MANAGER], net.case_id)
        register = _register(net, MANAGER)

        assert _cascade(net) == py_trees.common.Status.FAILURE

        assert committed_event_types(net.stores[MANAGER], net.case_id) == (
            before
        )
        assert _register(net, MANAGER) == register
        assert _queued_removes(net) == []


def _without_cause(register: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """*register* with each termination's cause removed.

    The ``Remove`` carries only the what, so a replica's ``TERMINATED`` entry
    records no cause; copying the why is #4748 (blocked by #4609).
    """
    stripped = []
    for entry in register:
        termination = entry.get("termination")
        stripped.append(
            entry
            if termination is None
            else {**entry, "termination": {**termination, "cause": None}}
        )
    return stripped


class TestReplicaCopiesTheTermination:
    """AC-2 and AC-4: a replica's register and rows equal the CASE_MANAGER's."""

    @staticmethod
    def _replay_and_compare(
        net: LedgerNetwork, *, drop_cause: bool = False
    ) -> None:
        manager_register = _register(net, MANAGER)
        if drop_cause:
            manager_register = _without_cause(manager_register)
        for replica in _REPLICAS:
            assert EMBARGO_TEARDOWN_EVENT_TYPE in net.replay_ledger(replica)
            assert net.case(replica).em_state is EM.EXITED
            assert _register(net, replica) == manager_register, replica
            assert _rows(net, replica) == _rows(net, MANAGER), replica

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("CLP-07-013")
    def test_an_early_termination(self):
        net = _net("tc-early")
        assert _trigger(net) == py_trees.common.Status.SUCCESS

        assert net.case(MANAGER).embargo_termination == (
            EmbargoTermination.early()
        )
        self._replay_and_compare(net)

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("EMB-13-003")
    def test_an_end_time_termination(self):
        net = _net("tc-end-time")
        _end_time_passed(net)
        _lazy_end_time_check(net)

        assert net.case(MANAGER).embargo_termination == (
            EmbargoTermination.end_time_reached()
        )
        self._replay_and_compare(net)

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("EMB-13-004")
    def test_a_threat_termination(self):
        """The what is copied; the why is the CASE_MANAGER's alone.

        Copying the cause (``THREAT_SIGNAL`` with ``X``) to replicas is
        #4748, so the comparison leaves the cause out.
        """
        net = _net("tc-threat")
        assert _cascade(net) == py_trees.common.Status.SUCCESS
        recorded = net.case(MANAGER).embargo_termination
        assert recorded is not None
        assert recorded.reason is TerminationReason.EARLY
        assert recorded.cause is not None
        assert recorded.cause.kind is TerminationCauseKind.THREAT_SIGNAL

        # #4748: the Remove does not carry the why, so drop it here.
        self._replay_and_compare(net, drop_cause=True)
        for replica in _REPLICAS:
            assert net.case(replica).embargo_termination == (
                EmbargoTermination.early()
            )
