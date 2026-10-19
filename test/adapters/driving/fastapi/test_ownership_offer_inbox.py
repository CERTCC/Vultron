#!/usr/bin/env python
"""The CASE_MANAGER commits an ownership Offer naming a peer it holds no profile of.

The transferee of an ``Offer(VulnerabilityCase)`` is a *peer*: the
CASE_MANAGER's store need not hold its actor profile, and no handler writes
one.  The ledger commit still needs the transferee inline in the snapshot
(CLP-07-006), so the Offer must carry it inline and storage must keep it so
(DL-08-003).  Before #4843 the sender named the transferee by a bare id and the
commit worked only when an earlier delivery had happened to leave the
transferee's profile in the CASE_MANAGER's store.

These tests drive the real FastAPI ingress and dispatch adapters and the
production dispatcher, from the sealed body the sender's outbox delivers.
"""

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

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.inbox import InboxOutcomeStatus, process_payload
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events import MessageSemantics
from vultron.wire.as2.factories import recommend_actor_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ACTOR_ID = "https://example.org/actors/case-actor-4843"
_VENDOR_ID = "https://example.org/users/vendor-4843"
_COORDINATOR_ID = "https://example.org/users/coordinator-4843"
_CASE_ID = "https://example.org/cases/case-4843"
_OWNERSHIP_EVENT = MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER.value


@pytest.fixture(autouse=True)
def clear_actor_locks() -> Iterator[None]:
    from vultron.adapters.driving.fastapi import inbox_orchestration

    inbox_orchestration._actor_inbox_locks.clear()
    yield
    inbox_orchestration._actor_inbox_locks.clear()


def _case() -> as_VulnerabilityCase:
    return as_VulnerabilityCase(
        id_=_CASE_ID, name="Ownership handoff", attributed_to=_VENDOR_ID
    )


@pytest.fixture
def case_actor_dl() -> Iterator[SqliteDataLayer]:
    """The CASE_MANAGER's store: the case and its roster, no actor profiles."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    case = _case()
    seed_case_manager_participant(dl, case, _CASE_ACTOR_ID)
    seed_case_owner_participant(dl, case, _VENDOR_ID)
    seed_case_participant(dl, case, _COORDINATOR_ID)
    dl.create(case)
    yield dl
    dl.close()


@pytest.fixture
def vendor_dl() -> Iterator[SqliteDataLayer]:
    """The Case Owner's replica, from which the Offer is sent."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_ID)
    dl.create(_case())
    yield dl
    dl.close()


def _ownership_offer_body(vendor_dl: SqliteDataLayer) -> dict[str, Any]:
    """The sealed body the vendor's outbox delivers for the ownership Offer.

    Built by the trigger adapter from a bare transferee id, as the
    ``offer-case-ownership-transfer`` trigger passes it (TRIG-11-001).
    """
    offer_id, _ = TriggerActivityAdapter(
        vendor_dl
    ).offer_case_ownership_transfer(
        case_id=_CASE_ID,
        transferee_id=_COORDINATOR_ID,
        actor=_VENDOR_ID,
        to=[_CASE_ACTOR_ID],
    )
    body = read_sealed_body_dict(vendor_dl, offer_id)
    assert body is not None
    return body


def _deliver(dl: SqliteDataLayer, body: dict[str, Any]):
    return process_payload(
        body,
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_CASE_ACTOR_ID, dispatcher=make_dispatcher()
        ),
    )


def _ownership_entries(dl: SqliteDataLayer) -> list[CaseLedgerEntry]:
    return [
        entry
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
        and entry.semantic_type == _OWNERSHIP_EVENT
    ]


def _assert_committed_with_inline_transferee(dl: SqliteDataLayer) -> None:
    entries = _ownership_entries(dl)
    assert len(entries) == 1, [e.semantic_type for e in entries]
    target = entries[0].payload_snapshot.get("target")
    assert isinstance(target, dict), (
        f"transferee is not inline in the snapshot: {target!r}"
    )
    assert target.get("id") == _COORDINATOR_ID


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("DL-08-003")
def test_ownership_offer_commits_when_the_case_manager_holds_no_transferee_profile(
    case_actor_dl, vendor_dl
):
    assert case_actor_dl.read(_COORDINATOR_ID) is None

    outcome = _deliver(case_actor_dl, _ownership_offer_body(vendor_dl))

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    _assert_committed_with_inline_transferee(case_actor_dl)


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("CM-21-005")
def test_ownership_offer_after_a_recommendation_commits_and_is_forwarded(
    case_actor_dl, vendor_dl
):
    """The rvcv-handoff order: an ``Offer(Actor, Case)`` comes first (#4843).

    The recommendation names the transferee, but the commit of the later
    ownership Offer must not depend on anything that delivery stored.
    """
    recommendation = recommend_actor_activity(
        recommended=_COORDINATOR_ID,
        target=_CASE_ID,
        actor=_VENDOR_ID,
        to=[_CASE_ACTOR_ID],
    )
    _deliver(
        case_actor_dl,
        recommendation.model_dump(
            mode="json", by_alias=True, exclude_none=True
        ),
    )

    outcome = _deliver(case_actor_dl, _ownership_offer_body(vendor_dl))

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    _assert_committed_with_inline_transferee(case_actor_dl)
    # CM-21-005: the CASE_MANAGER forwards the recorded Offer to the
    # transferee, still naming the transferee inline.
    forwards = [
        cast(Any, case_actor_dl.read(activity_id))
        for activity_id in case_actor_dl.outbox_list()
    ]
    forwards = [
        a
        for a in forwards
        if a is not None
        and a.type_ == "Offer"
        and _COORDINATOR_ID in (a.to or [])
    ]
    assert len(forwards) == 1
    forward_body = read_sealed_body_dict(case_actor_dl, forwards[0].id_)
    assert forward_body is not None
    assert isinstance(forward_body.get("target"), dict)
    assert forward_body["target"].get("id") == _COORDINATOR_ID
