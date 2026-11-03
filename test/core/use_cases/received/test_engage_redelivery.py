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
"""A redelivered ``Join(VulnerabilityCase)`` changes nothing (ID-02-001, #5006).

The CASE_MANAGER answers an engage by recording the sender's RM move to
``ACCEPTED`` and announcing the case to every eligible participant.  A second
delivery of the same ``Join`` has no move left to record, so it has nothing to
announce either: the store and the outbox stand as the first delivery left
them and the handler reports ``SKIPPED`` (ID-02-001, ID-05-003, HP-01-003).

The sweep in ``test/adapters/driving/fastapi/test_inbox_redelivery.py`` cannot
see this: its examples run against a store that holds no case, so the engage
tree is refused before it reaches its CASE_MANAGER effects.  These tests run
against a case-holding CASE_MANAGER store instead.
"""

import copy
from typing import Any, cast

import pytest

from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import run_use_case
from test.support.received import delivered_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import prepare_for_dispatch
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.rm import RM
from vultron.wire.as2.factories import rm_engage_case_activity

from ._ledger_network import BYSTANDER, MANAGER, LedgerNetwork

CASE_ID = "https://example.org/cases/case-engage-redelivery"


def _engage_body(net: LedgerNetwork, sender: str) -> dict[str, Any]:
    """The body *sender*'s outbox delivers for its ``Join`` of the case."""
    return delivered_body(
        rm_engage_case_activity(net.case(MANAGER), actor=sender, to=[MANAGER]),
        at=net.stores[MANAGER],
    )


def _deliver(net: LedgerNetwork, body: dict[str, Any]) -> HandlerResult:
    """Route *body* to the CASE_MANAGER through the inbox's own parse edge.

    Every delivery is parsed and rehydrated again, so the second one is
    routed as the inbox routes a redelivery: against the archived copy of
    the first (IE-10-001).
    """
    dl = net.stores[MANAGER]
    ingress = FastAPIIngressAdapter(dl)
    artifact = ingress.parse(copy.deepcopy(body))
    assert artifact is not None
    event = prepare_for_dispatch(ingress.rehydrate(artifact)).model_copy(
        update={"receiving_actor_id": MANAGER}
    )
    return cast(HandlerResult, run_use_case(dl, event))


def _snapshot(dl: SqliteDataLayer) -> dict[str, Any]:
    """The store's object ids and its outbox, as compared across deliveries."""
    return {
        "object_ids": frozenset(cast(dict[str, Any], dl.all())),
        "outbox": tuple(dl.outbox_list()),
    }


def _case_announces(net: LedgerNetwork) -> list[dict[str, Any]]:
    """The ``Announce(VulnerabilityCase)`` bodies queued for the bystander.

    The ledger fan-out announces every committed entry too (SYNC-02-003);
    only the case broadcast is counted here.
    """
    return net.sealed_bodies(
        MANAGER,
        to=BYSTANDER,
        type_="Announce",
        object_type="VulnerabilityCase",
    )


@pytest.mark.spec("ID-02-001")
@pytest.mark.spec("ID-05-003")
@pytest.mark.spec("HP-01-003")
def test_a_redelivered_engage_queues_no_second_case_announce():
    """The second ``Join`` adds no outbox item and no object (#5006 AC-1).

    The first delivery records the sender's ``ACCEPTED`` and announces the
    case; the second finds that state already recorded, so the whole act is
    a no-op and the CASE_MANAGER announces nothing again.
    """
    net = LedgerNetwork(CASE_ID)
    dl = net.stores[MANAGER]
    body = _engage_body(net, BYSTANDER)

    first = _deliver(net, body)
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    after_first = _snapshot(dl)
    entries_after_first = [e.id_ for e in ledger_entries(dl, CASE_ID)]
    # Preconditions: the first delivery did reach the CASE_MANAGER's effects.
    status = net.record(MANAGER, BYSTANDER).participant_status
    assert status is not None and status.rm.state is RM.ACCEPTED
    assert _case_announces(net), "precondition: the first delivery announced"

    second = _deliver(net, body)
    after_second = _snapshot(dl)

    assert after_second["outbox"] == after_first["outbox"], (
        "the redelivered Join queued another activity: "
        f"{set(after_second['outbox']) - set(after_first['outbox'])}"
    )
    assert after_second["object_ids"] == after_first["object_ids"], (
        "the redelivered Join stored new objects: "
        f"{after_second['object_ids'] - after_first['object_ids']}"
    )
    assert [e.id_ for e in ledger_entries(dl, CASE_ID)] == entries_after_first
    assert second.disposition in (
        HandlerDisposition.SKIPPED,
        first.disposition,
    ), second.reason
