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

"""Typed-Ports isolation tests for SendTerminateEmbargoActivityNode (AC-4, #1885).

Covers BTND-03-011: required port reads raise NoDataAvailable when the
blackboard key is absent.
"""

import pytest
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.embargo.nodes.terminate import (
    SendTerminateEmbargoActivityNode,
)
from test.core.behaviors.bt_harness import BTTestScenario

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"


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

    def test_failure_when_factory_unavailable(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)


# ---------------------------------------------------------------------------
# EMB-19-001: whom the teardown is addressed to
# ---------------------------------------------------------------------------

_MANAGER_ID = "https://example.org/actors/case-actor-emb19"
_VENDOR_ID = "https://example.org/actors/vendor-emb19"
_FINDER_ID = "https://example.org/actors/finder-emb19"
_EMBARGO_ID = "https://example.org/embargoes/emb-19-001"


def _seed_case_with_manager(dl, executing_actor_id: str):
    """Seed a case whose CASE_MANAGER is *_MANAGER_ID*, plus two participants."""
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.core.models.embargo_event import EmbargoEvent
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
        )
        dl.create(p)
        parts.append(p)

    embargo = EmbargoEvent(id_=_EMBARGO_ID, context=CASE_ID)
    dl.create(embargo)

    case = VulnerabilityCase(
        id_=CASE_ID,
        name="EMB-19-001",
        attributed_to=_VENDOR_ID,
        active_embargo=_EMBARGO_ID,
    )
    for p in parts:
        case.add_participant(p)
    dl.create(case)
    return case


def _seed_manager_only_case(dl):
    """Seed a case whose only participant is the CASE_MANAGER."""
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.core.models.embargo_event import EmbargoEvent
    from vultron.enums.roles import CVDRole

    participant = CaseParticipant(
        id_=f"{CASE_ID}/participants/manager",
        attributed_to=_MANAGER_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(participant)
    dl.create(EmbargoEvent(id_=_EMBARGO_ID, context=CASE_ID))

    case = VulnerabilityCase(
        id_=CASE_ID,
        name="EMB-19-002",
        attributed_to=_MANAGER_ID,
        active_embargo=_EMBARGO_ID,
    )
    case.add_participant(participant)
    dl.create(case)
    return case


@pytest.mark.spec("EMB-19-001")
@pytest.mark.spec("EMB-19-002")
class TestTeardownRecipients:
    """EMB-19-001: the teardown must not be addressed to its own author.

    The cascade path (``PublicDisclosureBranchNode`` → ``terminate_embargo_bt``)
    runs as the CASE_MANAGER, because that is who the received tree's ledger
    commit is gated on. Addressing the resulting ``Remove(EmbargoEvent, Case)``
    to ``case_manager_id`` therefore addressed it to the sender, delivery
    discarded it, and every other participant's replica kept an embargo the
    manager had already torn down — EM stayed ACTIVE for everyone but the
    manager, with nothing raised anywhere.
    """

    def test_manager_addresses_the_other_participants(self) -> None:
        from unittest.mock import MagicMock

        import py_trees

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.bridge import BTBridge

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER_ID)
        _seed_case_with_manager(dl, _MANAGER_ID)

        factory = MagicMock()
        factory.terminate_embargo.return_value = (
            "https://example.org/activities/remove-emb-19",
            {},
        )
        py_trees.blackboard.Blackboard.storage.clear()
        py_trees.blackboard.Blackboard.storage["/embargo_id"] = _EMBARGO_ID
        py_trees.blackboard.Blackboard.storage["/case_manager_id"] = (
            _MANAGER_ID
        )

        BTBridge(datalayer=dl, trigger_activity=factory).execute_with_setup(
            tree=SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            actor_id=_MANAGER_ID,
        )

        factory.terminate_embargo.assert_called_once()
        to = factory.terminate_embargo.call_args.kwargs["to"]
        assert _MANAGER_ID not in to, (
            "the manager must not address its own teardown to itself"
            f" (EMB-19-001); got to={to!r}"
        )
        assert set(to) == {_VENDOR_ID, _FINDER_ID}, (
            "every other participant holds a replica carrying the embargo and"
            f" must be told it is gone; got to={to!r}"
        )

    def test_non_manager_still_asks_the_manager(self) -> None:
        from unittest.mock import MagicMock

        import py_trees

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.bridge import BTBridge

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_ID)
        _seed_case_with_manager(dl, _VENDOR_ID)

        factory = MagicMock()
        factory.terminate_embargo.return_value = (
            "https://example.org/activities/remove-emb-19b",
            {},
        )
        py_trees.blackboard.Blackboard.storage.clear()
        py_trees.blackboard.Blackboard.storage["/embargo_id"] = _EMBARGO_ID
        py_trees.blackboard.Blackboard.storage["/case_manager_id"] = (
            _MANAGER_ID
        )

        BTBridge(datalayer=dl, trigger_activity=factory).execute_with_setup(
            tree=SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            actor_id=_VENDOR_ID,
        )

        to = factory.terminate_embargo.call_args.kwargs["to"]
        assert to == [_MANAGER_ID], (
            "a participant that is not the manager is *requesting* the"
            f" teardown, so the manager is the right addressee; got to={to!r}"
        )

    def test_a_manager_with_no_audience_emits_nothing(self) -> None:
        """EMB-19-002: skipped, not emitted with an empty ``to``.

        The node used to log "nothing to tell" and then build the activity
        anyway. An activity addressed to nobody is undeliverable and delivery
        discards it, so the only lasting effect was an outbox entry that could
        never resolve. SUCCESS because the teardown itself already happened —
        there is simply no one to tell.
        """
        from unittest.mock import MagicMock

        import py_trees

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.bridge import BTBridge

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER_ID)
        _seed_manager_only_case(dl)

        factory = MagicMock()
        py_trees.blackboard.Blackboard.storage.clear()
        py_trees.blackboard.Blackboard.storage["/embargo_id"] = _EMBARGO_ID
        py_trees.blackboard.Blackboard.storage["/case_manager_id"] = (
            _MANAGER_ID
        )

        result = BTBridge(
            datalayer=dl, trigger_activity=factory
        ).execute_with_setup(
            tree=SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            actor_id=_MANAGER_ID,
        )

        assert result.status == py_trees.common.Status.SUCCESS
        factory.terminate_embargo.assert_not_called()
        assert dl.outbox_list() == []
