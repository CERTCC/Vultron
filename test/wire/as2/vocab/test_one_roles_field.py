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
"""An Invite and an Offer carry the roles they propose under one wire field.

The recommend-actor ``Offer(Actor)`` and the case ``Invite`` both name an
actor and the CVD roles proposed for it.  ``as_Offer`` declares the one
``roles`` field and ``as_Invite`` inherits it, so the two activities carry
the roles under one name with one definition (VM-10-012, #6417).
"""

import json
from typing import Any, cast

import pytest

from test.support.objects import authored_at, make
from test.support.received import extract_stamped
from vultron.adapters.driven.db_record.record import (
    object_to_record,
    record_to_object,
)
from vultron.core.models.activity import VultronActivity
from vultron.wire.as2.factories import (
    recommend_actor_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Invite,
    as_Offer,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ID = "https://example.org/cases/one-roles-field"
_OWNER_ID = "https://example.org/actors/owner"
_INVITEE_ID = "https://example.org/actors/invitee"
_ROLES = ["vendor", "deployer"]


def _recommend_actor_offer() -> as_Offer:
    return recommend_actor_activity(
        make(as_Actor, id_=_INVITEE_ID),
        target=_CASE_ID,
        roles=list(_ROLES),
        actor=_OWNER_ID,
        at=authored_at(),
    )


def _case_invite() -> as_Invite:
    case = make(
        as_VulnerabilityCase,
        id_=_CASE_ID,
        name="One roles field",
        stub_summary="A case to join",
        attributed_to=_OWNER_ID,
    )
    return rm_invite_to_case_activity(
        invitee=make(as_Actor, id_=_INVITEE_ID),
        case=case,
        roles=list(_ROLES),
        actor=_OWNER_ID,
        at=authored_at(),
    )


_BUILDERS = pytest.mark.parametrize(
    "build",
    [_recommend_actor_offer, _case_invite],
    ids=["recommend-actor-offer", "case-invite"],
)


@pytest.mark.spec("VM-10-012")
def test_offer_declares_the_one_roles_field_and_invite_inherits_it():
    assert "roles" in as_Offer.model_fields
    assert "suggested_roles" not in as_Offer.model_fields
    assert "suggested_roles" not in as_Invite.model_fields
    # Inherited, not redeclared: one declaration means one definition.
    assert "roles" not in as_Invite.__annotations__
    assert (
        as_Invite.model_fields["roles"].json_schema_extra
        == as_Offer.model_fields["roles"].json_schema_extra
    )


@pytest.mark.spec("VM-10-012")
def test_core_activity_has_no_second_roles_field():
    assert "roles" in VultronActivity.model_fields
    assert "suggested_roles" not in VultronActivity.model_fields


@pytest.mark.spec("VM-10-012")
@pytest.mark.spec("CM-17-003")
@_BUILDERS
def test_wire_form_carries_the_roles_as_roles(build):
    body = json.loads(build().to_json())

    assert body["roles"] == _ROLES
    assert "suggestedRoles" not in body


@pytest.mark.spec("CM-16-003")
@pytest.mark.spec("CM-17-003")
@_BUILDERS
def test_roles_arrive_through_the_parse_edge_and_extraction(build):
    """A received activity's roles reach the core activity a use case reads."""
    received = parse_activity(json.loads(build().to_json()))
    assert received.roles == _ROLES

    event = cast(Any, extract_stamped(received))
    assert event.activity.roles == _ROLES


@pytest.mark.spec("CM-16-003")
@pytest.mark.spec("CM-17-003")
@_BUILDERS
def test_roles_survive_the_data_layer_round_trip(build):
    """A stored Offer or Invite reads back with its roles (#1990)."""
    back = record_to_object(object_to_record(cast(Any, build())))

    assert getattr(back, "roles", None) == _ROLES
