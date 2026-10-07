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
"""Every CASE_MANAGER commit made through the inbox is fanned out (#4113).

The inbox dispatcher builds each received use case with the ports its port
factory returns.  ``OFFER_ACTOR_TO_CASE`` got no ``SyncActivityPort``, so the
receipt commit (``offer_actor_to_case``) and the owner-direct ``Invite`` it
commits (``invite_actor_to_case``) were persisted but never announced to the
participants (SYNC-02-003).  Replicas learned of them only through
``Reject(CaseLedgerEntry)`` catch-up, which made the ``fcv-reject`` demo's
ledger-coverage gate time out.

These tests dispatch through the real :func:`make_dispatcher` wiring, so a
semantic whose factory drops the sync port fails here.
"""

import json
from typing import Any

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi import inbox_handler as ih
from vultron.adapters.outbox_sealed_body import read_sealed_body
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import recommend_actor_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_MANAGER_ID = "https://example.org/actors/case-actor"
_OWNER_ID = "https://example.org/actors/case-owner"
_FINDER_ID = "https://example.org/actors/finder"
_INVITEE_ID = "https://example.org/actors/invitee"
_CASE_ID = "https://example.org/cases/fan-out-wiring-case"


def _seat(
    dl: SqliteDataLayer,
    case: as_VulnerabilityCase,
    actor_id: str,
    slug: str,
    roles: list[CVDRole],
) -> None:
    participant = CaseParticipant(
        id_=f"{_CASE_ID}/participants/{slug}",
        attributed_to=actor_id,
        context=_CASE_ID,
        case_roles=roles,
    )
    dl.create(participant)
    case.case_participants.append(participant.id_)
    case.actor_participant_index[actor_id] = participant.id_


def _case_manager_store() -> SqliteDataLayer:
    """The CASE_MANAGER's store: a case with an owner and a finder seated."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER_ID)
    case = as_VulnerabilityCase(
        id_=_CASE_ID,
        name="FanOutWiring",
        attributed_to=_OWNER_ID,
        stub_summary="Security issue — details shared after acceptance",
    )
    _seat(dl, case, _MANAGER_ID, "case-manager", [CVDRole.CASE_MANAGER])
    _seat(dl, case, _OWNER_ID, "owner", [CVDRole.CASE_OWNER])
    _seat(dl, case, _FINDER_ID, "finder", [CVDRole.FINDER])
    dl.create(case)
    return dl


def _announced(dl: SqliteDataLayer) -> dict[str, set[str]]:
    """Map each announced ledger-entry id to the recipients it was sent to."""
    announced: dict[str, set[str]] = {}
    for item in dl.outbox_list():
        sealed = read_sealed_body(dl, item)
        assert sealed is not None
        body: dict[str, Any] = json.loads(sealed.body)
        if body.get("type") != "Announce":
            continue
        entry = body.get("object")
        if not isinstance(entry, dict) or entry.get("type") != (
            "CaseLedgerEntry"
        ):
            continue
        announced.setdefault(entry["id"], set()).update(body.get("to", []))
    return announced


@pytest.mark.spec("SYNC-02-003")
def test_owner_offer_actor_dispatched_by_inbox_fans_out_every_commit(
    monkeypatch,
):
    """Both commits the owner's Offer(Actor, Case) makes reach the finder.

    The finder is a participant that neither sent the Offer nor holds the
    CASE_MANAGER role, so every entry the CASE_MANAGER commits is announced to
    it (SYNC-02-003, CM-10-004).
    """
    monkeypatch.setattr(
        ih.inbox_port_factories, "_resolve_actor_config", lambda: None
    )
    dl = _case_manager_store()
    activity = recommend_actor_activity(
        as_Actor(id_=_INVITEE_ID),
        target=as_VulnerabilityCase(id_=_CASE_ID, name="FanOutWiring"),
        actor=_OWNER_ID,
        to=[_MANAGER_ID],
        suggested_roles=["vendor"],
    )
    event = extract_event(activity).model_copy(
        update={"receiving_actor_id": _MANAGER_ID}
    )

    result = ih.dispatch(event, dl, dispatcher=ih.make_dispatcher())

    assert result.disposition is HandlerDisposition.APPLIED
    entries = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
    ]
    event_types = {entry.event_type for entry in entries}
    assert {"offer_actor_to_case", "invite_actor_to_case"} <= event_types

    announced = _announced(dl)
    for entry in entries:
        assert _FINDER_ID in announced.get(entry.id_, set()), (
            f"{entry.event_type} entry '{entry.id_}' was committed but never"
            " announced to the finder (SYNC-02-003)"
        )
