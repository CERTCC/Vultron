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

"""A forward stands for its recorded Offer however its issuer is spelled."""

from types import SimpleNamespace
from typing import Any, cast

import pytest

from vultron.core.participants.offer_forward import forwarded_offer_entry

CASE_ID = "https://example.org/cases/c1"
MANAGER_ID = "https://example.org/actors/case-manager"
TARGET_ID = "https://example.org/actors/vendor"
OFFER_ID = "https://example.org/activities/role-offer"
FORWARD_ID = "https://example.org/activities/role-offer/forward"


class _Store:
    """Holds one stored activity, the forward."""

    def __init__(self, forward: object) -> None:
        self._forward = forward

    def read(self, object_id: str) -> object | None:
        return self._forward if object_id == FORWARD_ID else None


def _entry() -> Any:
    """The ledgered Offer the forward names in ``inReplyTo``."""
    return SimpleNamespace(
        log_object_id=OFFER_ID, payload_snapshot={"target": TARGET_ID}
    )


@pytest.mark.spec("OID-01-006", "CLP-10-021")
@pytest.mark.parametrize(
    ("forward_actor", "issuer_id"),
    [
        (f"{MANAGER_ID}/", MANAGER_ID),
        (MANAGER_ID, f"{MANAGER_ID}/"),
    ],
    ids=["slash-on-forward-actor", "slash-on-issuer"],
)
def test_a_forward_is_the_issuers_in_either_spelling(
    forward_actor: str, issuer_id: str
) -> None:
    """The issuer test answers as the ``target`` test beside it does (#5901).

    The stored Offer's ``actor`` keeps its writer's spelling, so an exact
    comparison would make a forward stand for no recorded Offer, and the
    answer to it would close nothing (#4565).
    """
    forward = SimpleNamespace(
        type_="Offer",
        actor=forward_actor,
        context=CASE_ID,
        target=TARGET_ID,
        in_reply_to=OFFER_ID,
    )
    entry = _entry()

    found = forwarded_offer_entry(
        cast(Any, _Store(forward)),
        case_id=CASE_ID,
        forward_id=FORWARD_ID,
        issuer_id=issuer_id,
        entries=[entry],
        case_field="context",
    )

    assert found is entry


@pytest.mark.spec("CLP-10-021")
def test_a_forward_from_another_actor_stands_for_nothing() -> None:
    """Tolerance is for the spelling, not for the actor."""
    forward = SimpleNamespace(
        type_="Offer",
        actor="https://example.org/actors/stranger/",
        context=CASE_ID,
        target=TARGET_ID,
        in_reply_to=OFFER_ID,
    )

    assert (
        forwarded_offer_entry(
            cast(Any, _Store(forward)),
            case_id=CASE_ID,
            forward_id=FORWARD_ID,
            issuer_id=MANAGER_ID,
            entries=[_entry()],
            case_field="context",
        )
        is None
    )
