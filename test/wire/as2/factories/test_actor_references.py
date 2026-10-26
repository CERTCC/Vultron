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
"""How an actor named in an activity travels (ADR-0159).

Spec coverage:
- AKM-02-006: an actor given by URI carries no value nobody asserted.
- AKM-05-005: an actor travels as held, or as an id-and-type actor reference.
- VAM-04: each activity dispatches to the same semantic whichever form its
  actor takes.
"""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from vultron.core.models.actor import VultronOrganization
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.ledger_position import LedgerPosition
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    offer_case_ownership_transfer_activity,
    recommend_actor_activity,
    rm_invite_to_case_activity,
    rm_invite_to_full_case_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Actor,
    as_Organization,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseStub,
)

_ACTOR = "https://example.org/actors/coordinator"
_PEER = "https://example.org/actors/vendor"
_CASE = "https://example.org/cases/c1"

#: Fields an actor reference may not carry: each would be a value the sender
#: invented rather than one the actor asserted (AKM-02-006).
_INVENTED = ("published", "updated", "inbox", "outbox")

#: Each factory that takes an actor, built around *peer*, paired with the
#: activity field the actor lands in.
_BUILDERS: dict[
    str,
    tuple[Callable[[as_Actor | VultronOrganization | str], BaseModel], str],
] = {
    "recommend_actor_activity": (
        lambda peer: recommend_actor_activity(
            peer, target=_CASE, actor=_ACTOR, to=[_ACTOR]
        ),
        "object",
    ),
    "rm_invite_to_case_activity": (
        lambda peer: rm_invite_to_case_activity(
            peer,
            target=as_VulnerabilityCaseStub(
                case_id=_CASE, summary="An issue in widget"
            ),
            actor=_ACTOR,
            to=[_PEER],
        ),
        "object",
    ),
    "rm_invite_to_full_case_activity": (
        lambda peer: rm_invite_to_full_case_activity(
            peer,
            _CASE,
            LedgerPosition(log_index=0, entry_hash="0" * 64),
            actor=_ACTOR,
            to=[_PEER],
        ),
        "object",
    ),
    "offer_case_ownership_transfer_activity": (
        lambda peer: offer_case_ownership_transfer_activity(
            as_VulnerabilityCase(
                id_=_CASE, attributed_to=_ACTOR, name="Case c1"
            ),
            target=peer,
            actor=_ACTOR,
            to=[_PEER],
        ),
        "target",
    ),
}


def _carried_actor(
    name: str, peer: as_Actor | VultronOrganization | str
) -> dict[str, Any]:
    """Return the actor as the activity built by *name* carries it."""
    build, field = _BUILDERS[name]
    dumped = build(peer).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    actor = dumped[field]
    assert isinstance(actor, dict), f"{name} carried {field} as {actor!r}"
    return actor


@pytest.mark.spec("AKM-02-006")
@pytest.mark.parametrize("name", sorted(_BUILDERS))
def test_an_actor_given_by_uri_carries_no_invented_field(name: str) -> None:
    actor = _carried_actor(name, _PEER)
    assert [key for key in _INVENTED if key in actor] == []


@pytest.mark.spec("AKM-05-005")
@pytest.mark.parametrize("name", sorted(_BUILDERS))
def test_an_actor_given_by_uri_travels_as_an_actor_reference(
    name: str,
) -> None:
    actor = _carried_actor(name, _PEER)
    actor.pop("@context", None)
    assert actor == {"id": _PEER, "type": "Actor"}


@pytest.mark.spec("AKM-05-005")
@pytest.mark.parametrize("name", sorted(_BUILDERS))
def test_a_held_actor_profile_travels_as_held(name: str) -> None:
    held = as_Organization(id_=_PEER, name="Vendor Co")
    expected = held.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert _carried_actor(name, held) == expected


#: The semantic each actor-naming activity dispatches to.
_SEMANTICS: dict[str, MessageSemantics] = {
    "recommend_actor_activity": MessageSemantics.OFFER_ACTOR_TO_CASE,
    "rm_invite_to_case_activity": MessageSemantics.INVITE_ACTOR_TO_CASE,
    "rm_invite_to_full_case_activity": (
        MessageSemantics.INVITE_ACTOR_TO_FULL_CASE
    ),
    "offer_case_ownership_transfer_activity": (
        MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER
    ),
}

#: A peer record as the address book holds it: only what the peer supplied,
#: so no clock time and no endpoint (AKM-02-006).
_HELD_PEER = VultronOrganization(
    id_=_PEER, name="Vendor Co", published=None, updated=None
)


@pytest.mark.spec("AKM-05-005")
@pytest.mark.spec("AKM-02-006")
@pytest.mark.parametrize("name", sorted(_BUILDERS))
def test_a_held_peer_record_travels_with_nothing_added(name: str) -> None:
    """The core record a sender's store holds is carried as held."""
    carried = _carried_actor(name, _HELD_PEER)
    expected = _HELD_PEER.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    assert carried == expected
    assert [key for key in _INVENTED if key in carried] == []


@pytest.mark.spec("VAM-04-001")
@pytest.mark.spec("VAM-04-004")
@pytest.mark.spec("VAM-04-007")
@pytest.mark.spec("VAM-04-011")
@pytest.mark.parametrize(
    "peer",
    [as_Organization(id_=_PEER, name="Vendor Co"), _HELD_PEER, _PEER],
    ids=["wire-profile", "held-record", "actor-reference"],
)
@pytest.mark.parametrize("name", sorted(_BUILDERS))
def test_the_activity_dispatches_to_the_same_semantic(
    name: str, peer: as_Actor | VultronOrganization | str
) -> None:
    """A held profile and an actor reference both route by the actor's type."""
    build, _ = _BUILDERS[name]
    body = build(peer).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )

    event = extract_event(parse_activity(body))

    assert event.semantic_type is _SEMANTICS[name]
