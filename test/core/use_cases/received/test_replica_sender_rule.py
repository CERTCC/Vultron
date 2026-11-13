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
"""A participant replica refuses every Offer(Actor) and every
Add(ParticipantStatus) at its path stage (HP-01-039).

Each test runs the real received use case in the replica holder's own store:
the case lists the CASE_MANAGER, a vendor and the replica holder.  Both
messages are addressed to the CASE_MANAGER alone (PCR-08-001), and a replica
takes what they change from the ledger (RSH-08-003, PCR-03-001), so each
tree declares the manager path only: the path stage refuses a copy from any
sender before the sender check runs (HP-01-005).  A replica whose case names
no CASE_MANAGER is told the case has none (CM-02-014).
"""

from collections.abc import Callable

import py_trees
import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_participant,
)
from test.support.act_runner import run_in_act
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import authored_at, make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.sender_guard import is_composed_sender_guard
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
    dl.create(make(as_Actor, id_=REPLICA_ID))  # type: ignore[arg-type]
    case = make(
        as_VulnerabilityCase,
        id_=CASE_ID,
        name="ReplicaSenderRule",
        attributed_to=VENDOR_ID,
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
        make(as_Actor, id_=RECOMMENDED_ID),
        target=make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_=CASE_ID,
            name="ReplicaSenderRule",
        ),
        actor=sender_id,
        to=[REPLICA_ID],
        at=authored_at(),
    )
    event = make_payload(activity, receiving_actor_id=REPLICA_ID, at=dl)
    return run_in_act(
        OfferActorToCaseReceivedUseCase(
            dl,
            event,  # type: ignore[arg-type]
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
    )


def _deliver_participant_status(
    dl: SqliteDataLayer, make_payload: Callable[..., object], sender_id: str
) -> HandlerResult:
    vendor = dl.read(f"{CASE_ID}/participants/vendor")
    assert isinstance(vendor, CaseParticipant)
    status = make(
        as_ParticipantStatus,
        id_=f"{CASE_ID}/participants/vendor/statuses/s1",
        context=CASE_ID,
    )
    dl.create(status)
    activity = add_status_to_participant_activity(
        status,
        target=vendor,
        actor=sender_id,
        context=make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_=CASE_ID,
            name="ReplicaSenderRule",
        ),
        to=[REPLICA_ID],
        at=authored_at(),
    )
    event = make_payload(activity, receiving_actor_id=REPLICA_ID, at=dl)
    return run_in_act(
        AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,  # type: ignore[arg-type]
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        )
    )


DELIVERIES = [
    pytest.param(_deliver_offer_actor, id="offer-actor"),
    pytest.param(_deliver_participant_status, id="participant-status"),
]


@pytest.mark.spec("PCR-03-001", "RSH-08-003", "HP-01-039")
@pytest.mark.parametrize("deliver", DELIVERIES)
@pytest.mark.parametrize("sender_id", [VENDOR_ID, MANAGER_ID])
def test_replica_refuses_every_copy_at_the_path_stage(
    deliver, sender_id: str, make_payload, tree_runs
) -> None:
    """A replica takes the change from the ledger, never from the message,
    so the path stage refuses it whoever sent it, and the sender guard never
    runs."""
    dl, vendor = _replica_store()

    result = deliver(dl, make_payload, sender_id)

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason == f"not the CASE_MANAGER of case '{CASE_ID}'"
    assert len(tree_runs) == 1
    (guard,) = [
        n for n in tree_runs[0].iterate() if is_composed_sender_guard(n)
    ]
    assert guard.status is py_trees.common.Status.INVALID
    stored = dl.read(vendor.id_)
    assert isinstance(stored, CaseParticipant)
    assert stored.participant_statuses == vendor.participant_statuses
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []


@pytest.mark.spec("CM-02-014", "HP-01-039")
@pytest.mark.parametrize("deliver", DELIVERIES)
def test_replica_with_no_case_manager_says_the_case_has_none(
    deliver, make_payload, tree_runs
) -> None:
    """A replica whose case names no CASE_MANAGER is on the replica path,
    and the path stage's reason says the case has none (CM-02-014)."""
    dl, _ = _replica_store(with_manager=False)

    result = deliver(dl, make_payload, VENDOR_ID)

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason == f"case '{CASE_ID}' has no CASE_MANAGER"
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []
