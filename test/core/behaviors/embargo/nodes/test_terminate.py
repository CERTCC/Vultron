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

"""Tests for the cascades' embargo teardown ask (``terminate.py``).

Covers BTND-03-011 (required port reads raise NoDataAvailable when the
blackboard key is absent, AC-4 #1885), the ask's addressing (PCR-08-001), and
its pending assertion (EP-09-008, SYNC-11-002, SYNC-11-004; #4147).
"""

from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    EMBARGO_TEARDOWN_EVENT_TYPE,
)
from vultron.core.behaviors.embargo.nodes.terminate import (
    SendTerminateEmbargoActivityNode,
    TeardownAskPendingNode,
    ask_case_manager_to_terminate_once,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.pending_assertion import (
    _STORES,
    PendingAssertion,
    PendingAssertionStore,
    get_pending_assertion_store,
    record_pending_assertion,
)
from vultron.errors import VultronWiringError

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"

_MANAGER_ID = "https://example.org/actors/case-actor-emb19"
_VENDOR_ID = "https://example.org/actors/vendor-emb19"
_FINDER_ID = "https://example.org/actors/finder-emb19"
_EMBARGO_ID = "https://example.org/embargoes/emb-19-001"
_ASK_ID = "https://example.org/activities/remove-emb-19"
_EARLIER_ASK_ID = "https://example.org/activities/earlier-ask"


def _seed_case_with_manager(dl: SqliteDataLayer) -> None:
    """Seed a case whose CASE_MANAGER is *_MANAGER_ID*, plus two participants."""
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.core.models.embargo_event import EmbargoEvent
    from vultron.core.states.participant_embargo_consent import PEC
    from vultron.enums.roles import CVDRole

    parts = []
    for actor_id, roles in (
        (_MANAGER_ID, [CVDRole.CASE_MANAGER]),
        (_VENDOR_ID, [CVDRole.CASE_OWNER, CVDRole.VENDOR]),
        (_FINDER_ID, [CVDRole.REPORTER]),
    ):
        p = CaseParticipant(
            id_=f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}",
            # `attributed_to` is what `add_participant` keys the
            # actor→participant index on.
            attributed_to=actor_id,
            context=CASE_ID,
            case_roles=roles,
            embargo_consent_state=PEC.SIGNATORY,
        )
        dl.create(p)
        parts.append(p)

    dl.create(
        EmbargoEvent(
            id_=_EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(45)
        )
    )
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="Teardown ask",
        attributed_to=_VENDOR_ID,
        active_embargo=_EMBARGO_ID,
    )
    for p in parts:
        case.add_participant(p)
    dl.create(case)


def _seed_ask_blackboard() -> None:
    py_trees.blackboard.Blackboard.storage.clear()
    py_trees.blackboard.Blackboard.storage["/embargo_id"] = _EMBARGO_ID
    py_trees.blackboard.Blackboard.storage["/case_manager_id"] = _MANAGER_ID


def _factory() -> MagicMock:
    factory = MagicMock()
    factory.terminate_embargo.return_value = (_ASK_ID, {})
    return factory


def _pending_ask(actor_id: str) -> PendingAssertion | None:
    return get_pending_assertion_store(actor_id).pending_for_subject(
        CASE_ID, EMBARGO_TEARDOWN_EVENT_TYPE, _EMBARGO_ID
    )


def _record_earlier_ask(subject_id: str = _EMBARGO_ID) -> None:
    record_pending_assertion(
        _VENDOR_ID,
        CASE_ID,
        EMBARGO_TEARDOWN_EVENT_TYPE,
        _EARLIER_ASK_ID,
        subject_id=subject_id,
    )


def _run(
    tree: py_trees.behaviour.Behaviour,
    actor_id: str,
    factory: MagicMock | None,
) -> tuple[SqliteDataLayer, BTExecutionResult]:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    _seed_case_with_manager(dl)
    _seed_ask_blackboard()
    result = BTBridge(
        datalayer=dl, trigger_activity=factory
    ).execute_with_setup(tree=tree, actor_id=actor_id)
    return dl, result


class TestSendTerminateEmbargoActivityNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = SendTerminateEmbargoActivityNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_embargo_id_raises_no_data_available(self) -> None:
        node = SendTerminateEmbargoActivityNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("embargo_id")

    def test_missing_case_manager_id_raises_no_data_available(self) -> None:
        node = SendTerminateEmbargoActivityNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("case_manager_id")

    def test_failure_when_embargo_absent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Ports supplied but no embargo seeded — the factory call fails.

        Formerly named ``test_failure_when_factory_unavailable``, which it never
        tested: ``BTTestScenario`` always wires
        ``trigger_activity=TriggerActivityAdapter(dl)``, so
        ``_on_factory_unavailable()`` is unreachable from this harness; that
        branch is covered by ``test_failure_when_factory_unavailable`` below,
        which builds its own bridge (CONCERN-3019).
        """
        result = bt_scenario.run(
            SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            actor_id=ACTOR_ID,
            embargo_id="https://example.org/embargoes/emb-001",
            case_manager_id=_MANAGER_ID,
        )
        bt_scenario.assert_failure(result, reason="EmbargoEvent")

    @pytest.mark.spec("BT-14-001")
    def test_failure_when_factory_unavailable(self) -> None:
        """No trigger-activity port: FAILURE, nothing queued or recorded."""
        dl, result = _run(
            SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            _VENDOR_ID,
            factory=None,
        )

        assert result.status == Status.FAILURE
        assert dl.outbox_list() == []
        assert _pending_ask(_VENDOR_ID) is None


class TestTeardownAsk:
    """A participant that is not the CASE_MANAGER *requests* the teardown."""

    @pytest.mark.spec("EP-09-008")
    def test_non_manager_asks_the_manager(self) -> None:
        factory = _factory()

        _run(
            SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            _VENDOR_ID,
            factory,
        )

        to = factory.terminate_embargo.call_args.kwargs["to"]
        assert to == [_MANAGER_ID], (
            "a participant that is not the manager is *requesting* the"
            f" teardown, so the manager is the only addressee; got to={to!r}"
        )

    @pytest.mark.spec("EP-09-008")
    @pytest.mark.spec("SYNC-11-002")
    def test_queued_ask_is_recorded_keyed_by_the_ended_embargo(self) -> None:
        dl, result = _run(
            SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            _VENDOR_ID,
            _factory(),
        )

        assert result.status == Status.SUCCESS
        assert dl.outbox_list() == [_ASK_ID]
        pending = _pending_ask(_VENDOR_ID)
        assert pending is not None
        assert pending.object_id == _ASK_ID
        assert pending.subject_id == _EMBARGO_ID

    @pytest.mark.spec("SYNC-11-002")
    def test_failed_outbox_write_records_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only a *successfully enqueued* ask is recorded (SYNC-11-002)."""

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("outbox down")

        monkeypatch.setattr(
            "vultron.core.behaviors.embargo.nodes.emit.add_activity_to_outbox",
            _boom,
        )
        _, result = _run(
            SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            _VENDOR_ID,
            _factory(),
        )

        assert result.status == Status.FAILURE
        assert _pending_ask(_VENDOR_ID) is None

    @pytest.mark.spec("SYNC-11-004")
    def test_the_manager_reaching_the_ask_is_a_wiring_fault(self) -> None:
        """The manager's arm commits the teardown itself: it never asks
        itself, and it keeps no pending assertion."""
        factory = _factory()

        dl, result = _run(
            SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            _MANAGER_ID,
            factory,
        )

        assert result.status == Status.FAILURE
        assert "VultronWiringError" in result.feedback_message
        factory.terminate_embargo.assert_not_called()
        assert dl.outbox_list() == []
        assert _pending_ask(_MANAGER_ID) is None


class TestAskCaseManagerToTerminateOnce:
    """A repeat inside the pending window queues no second ask (#4147)."""

    @pytest.mark.spec("SYNC-11-002")
    def test_a_pending_ask_suppresses_the_repeat(self) -> None:
        _record_earlier_ask()
        factory = _factory()

        dl, result = _run(
            ask_case_manager_to_terminate_once(CASE_ID), _VENDOR_ID, factory
        )

        assert result.status == Status.SUCCESS
        factory.terminate_embargo.assert_not_called()
        assert dl.outbox_list() == []

    @pytest.mark.spec("SYNC-11-002")
    def test_an_ask_about_another_embargo_does_not_suppress(self) -> None:
        _record_earlier_ask(subject_id="https://example.org/embargoes/other")

        dl, _ = _run(
            ask_case_manager_to_terminate_once(CASE_ID),
            _VENDOR_ID,
            _factory(),
        )

        assert dl.outbox_list() == [_ASK_ID]

    @pytest.mark.spec("SYNC-11-003")
    def test_a_cleared_ask_no_longer_suppresses(self) -> None:
        _record_earlier_ask()
        get_pending_assertion_store(_VENDOR_ID).clear(
            CASE_ID, EMBARGO_TEARDOWN_EVENT_TYPE, _EARLIER_ASK_ID
        )

        dl, _ = _run(
            ask_case_manager_to_terminate_once(CASE_ID),
            _VENDOR_ID,
            _factory(),
        )

        assert dl.outbox_list() == [_ASK_ID]

    @pytest.mark.spec("SYNC-11-001")
    def test_zero_window_disables_suppression(self) -> None:
        _STORES[_VENDOR_ID] = PendingAssertionStore(timeout_seconds=0)
        _record_earlier_ask()

        dl, _ = _run(
            ask_case_manager_to_terminate_once(CASE_ID),
            _VENDOR_ID,
            _factory(),
        )

        assert dl.outbox_list() == [_ASK_ID]

    @pytest.mark.spec("BT-14-001")
    def test_a_failed_send_still_fails_the_ask(self) -> None:
        factory = MagicMock()
        factory.terminate_embargo.side_effect = RuntimeError("factory down")

        _, result = _run(
            ask_case_manager_to_terminate_once(CASE_ID), _VENDOR_ID, factory
        )

        assert result.status == Status.FAILURE
        assert _pending_ask(_VENDOR_ID) is None

    def test_pending_guard_without_an_actor_is_a_wiring_fault(self) -> None:
        """A FAILURE here would read as "not pending" and send the ask."""
        node = TeardownAskPendingNode(case_id=CASE_ID)
        node.actor_id = None
        node.embargo_id = _EMBARGO_ID

        with pytest.raises(VultronWiringError):
            node.update()
