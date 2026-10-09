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

"""The one derivation of the recommend-actor roles key (CONCERN-1335)."""

import pytest

from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
    EvaluateDefaultRolesNode,
)
from vultron.core.behaviors.case.nodes.participant.roles import (
    suggested_roles_key,
)


@pytest.mark.parametrize(
    "recommendation_id, key",
    [
        ("https://example.org/activities/offer-1", "suggested_roles_offer-1"),
        ("urn:uuid:abc", "suggested_roles_urn:uuid:abc"),
    ],
)
def test_key_is_namespaced_by_the_last_path_segment(recommendation_id, key):
    assert suggested_roles_key(recommendation_id) == key


def test_the_writer_and_the_invite_reader_agree_on_the_key():
    offer_id = "https://example.org/activities/offer-2"
    writer = EvaluateDefaultRolesNode(
        suggested_actor_id="https://example.org/actors/v",
        case_id="https://example.org/cases/c",
        recommendation_id=offer_id,
    )
    reader = EmitInviteActorToCaseNode(
        invitee_id="https://example.org/actors/v",
        case_id="https://example.org/cases/c",
        recommendation_id=offer_id,
    )
    assert writer._roles_key == suggested_roles_key(offer_id)
    assert reader._roles_key == f"/{suggested_roles_key(offer_id)}"
