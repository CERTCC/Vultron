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
"""A participant replica takes Offer(Actor) and Add(ParticipantStatus) from
the CASE_MANAGER alone (PCR-03-001, #4646).

Each test runs the real received use case in the replica holder's own store:
the case lists the CASE_MANAGER, a vendor and the replica holder.  A copy sent
by the vendor is refused on the sender check; the same copy sent by the
CASE_MANAGER passes it, and is then refused because the replica is not the
CASE_MANAGER the message is for (HP-01-005).
"""

from collections.abc import Callable

import py_trees
import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_participant,
)
from test.support.case_owner import CASE_OWNER_ID
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases.received.actor.suggest import (
    OfferActorToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_status_to_participant_activity,
    recommend_actor_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/replica-sender-rule"
MANAGER_ID = "https://example.org/actors/case-actor"
VENDOR_ID = "https://example.org/actors/vendor"
REPLICA_ID = "https://example.org/actors/finder"
RECOMMENDED_ID = "https://example.org/actors/vendor-new"


def _replica_store(
    with_manager: bool = True,
) -> tuple[SqliteDataLayer, CaseParticipant]:
    """The replica holder's own store, holding the case it replicates.

    With *with_manager* false the case names no CASE_MANAGER.  Returns the
    store and the vendor's participant record.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=REPLICA_ID)
    dl.create(as_Actor(id_=REPLICA_ID))  # type: ignore[arg-type]
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="ReplicaSenderRule", attributed_to=VENDOR_ID
    )
    if with_manager:
        seed_case_manager_participant(dl, case, MANAGER_ID)
    vendor = seed_case_participant(dl, case, VENDOR_ID)
    seed_case_participant(dl, case, REPLICA_ID)
    dl.create(case)
    return dl, vendor


def _deliver_offer_actor(
    dl: SqliteDataLayer, make_payload: Callable[..., object], sender_id: str
) -> HandlerResult:
    activity = recommend_actor_activity(
        as_Actor(id_=RECOMMENDED_ID),
        target=as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="ReplicaSenderRule"
        ),
        actor=sender_id,
        to=[REPLICA_ID],
    )
    event = make_payload(activity, receiving_actor_id=REPLICA_ID, at=dl)
    return OfferActorToCaseReceivedUseCase(
        dl,
        event,  # type: ignore[arg-type]
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()


def _deliver_participant_status(
    dl: SqliteDataLayer, make_payload: Callable[..., object], sender_id: str
) -> HandlerResult:
    vendor = dl.read(f"{CASE_ID}/participants/vendor")
    assert isinstance(vendor, CaseParticipant)
    status = as_ParticipantStatus(
        id_=f"{CASE_ID}/participants/vendor/statuses/s1", context=CASE_ID
    )
    dl.create(status)
    activity = add_status_to_participant_activity(
        status,
        target=vendor,
        actor=sender_id,
        context=as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="ReplicaSenderRule"
        ),
        to=[REPLICA_ID],
    )
    event = make_payload(activity, receiving_actor_id=REPLICA_ID, at=dl)
    return AddParticipantStatusToParticipantReceivedUseCase(
        dl,
        event,  # type: ignore[arg-type]
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


DELIVERIES = [
    pytest.param(_deliver_offer_actor, id="offer-actor"),
    pytest.param(_deliver_participant_status, id="add-participant-status"),
]


def _sender_guard(
    tree: py_trees.behaviour.Behaviour,
) -> py_trees.common.Status:
    """The status of the tree's composed sender guard."""
    guards = [n for n in tree.iterate() if n.name == "SenderRuleGuard"]
    assert len(guards) == 1, "the tree composes exactly one sender guard"
    return guards[0].status


@pytest.mark.spec("PCR-03-001")
@pytest.mark.parametrize("deliver", DELIVERIES)
def test_replica_refuses_a_listed_non_manager(
    deliver, make_payload, tree_runs
) -> None:
    """The vendor is on the case, but a replica refuses its copy."""
    dl, vendor = _replica_store()

    result = deliver(dl, make_payload, VENDOR_ID)

    assert result.disposition is HandlerDisposition.REFUSED
    assert VENDOR_ID in (result.reason or "")
    assert "is not the CASE_MANAGER" in (result.reason or "")
    assert len(tree_runs) == 1
    assert _sender_guard(tree_runs[0]) is py_trees.common.Status.FAILURE
    stored = dl.read(vendor.id_)
    assert isinstance(stored, CaseParticipant)
    assert stored.participant_statuses == vendor.participant_statuses
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []


@pytest.mark.spec("PCR-03-001")
@pytest.mark.spec("HP-01-005")
@pytest.mark.parametrize("deliver", DELIVERIES)
def test_replica_admits_the_case_manager(
    deliver, make_payload, tree_runs
) -> None:
    """The same copy from the CASE_MANAGER passes the sender check.

    The replica is still not the CASE_MANAGER the message is for, so the gated
    work does not run and the copy is refused for that, not for its sender.
    """
    dl, _ = _replica_store()

    result = deliver(dl, make_payload, MANAGER_ID)

    assert len(tree_runs) == 1
    assert _sender_guard(tree_runs[0]) is py_trees.common.Status.SUCCESS
    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason == f"not the CASE_MANAGER of case '{CASE_ID}'"
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []


@pytest.mark.spec("PCR-03-001")
@pytest.mark.parametrize("deliver", DELIVERIES)
def test_replica_with_no_case_manager_refuses_a_listed_participant(
    deliver, make_payload, tree_runs
) -> None:
    """A replica whose case names no CASE_MANAGER has no sender to admit.

    The CASE_MANAGER check does not pass a sender through when there is no
    CASE_MANAGER to compare with, so the vendor is still refused.
    """
    dl, _ = _replica_store(with_manager=False)

    result = deliver(dl, make_payload, VENDOR_ID)

    assert result.disposition is HandlerDisposition.REFUSED
    assert _sender_guard(tree_runs[0]) is py_trees.common.Status.FAILURE
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []
