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

"""The ``Create(CaseProposal)`` envelope carries its proposer inline (CP-01-010).

The CASE_MANAGER reads the CASE_OWNER's actor default only from the profile
the Create carries as its ``actor``.  These tests pin the three parse-edge
refusals, the extractor handing that profile to core, and the factory that
builds the envelope on the sending side.
"""

from datetime import timedelta
from typing import Any

import pytest

from vultron.core.models.actor import CoreActor, VultronOrganization
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.errors import VultronActivityConstructionError
from vultron.semantic_registry import extract_event
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.factories.case import create_case_proposal_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

_VENDOR = "https://example.org/actors/vendor"
_OTHER = "https://example.org/actors/other"
_CASE_ACTOR = "https://example.org/actors/case-actor"
_REPORT = "https://example.org/reports/r-001"
_PUBLISHED = "2026-03-04T05:06:07+00:00"


def _policy(actor_id: str) -> dict[str, Any]:
    return {
        "type": "EmbargoPolicy",
        "id": f"{actor_id}/embargo-policy",
        "actorId": actor_id,
        "inbox": f"{actor_id}/inbox",
        "preferredDuration": "P45D",
    }


def _body(actor: Any, attributed_to: str = _VENDOR) -> dict[str, Any]:
    return {
        "type": "Create",
        "id": "https://example.org/activities/create-proposal-1",
        "actor": actor,
        "published": _PUBLISHED,
        "to": [_CASE_ACTOR],
        "object": {
            "type": "CaseProposal",
            "id": "https://example.org/proposals/p-001",
            "attributedTo": attributed_to,
            "object": _REPORT,
            "target": _CASE_ACTOR,
        },
    }


def _profile(
    actor_id: str = _VENDOR, policy_of: str | None = None
) -> dict[str, Any]:
    profile: dict[str, Any] = {"type": "Organization", "id": actor_id}
    if policy_of is not None:
        profile["embargoPolicy"] = _policy(policy_of)
    return profile


@pytest.mark.spec("CP-01-010")
def test_an_inline_profile_with_its_own_policy_parses():
    activity = parse_activity(_body(_profile(policy_of=_VENDOR)))

    assert isinstance(activity.actor, CoreActor)
    assert activity.actor.embargo_policy is not None
    assert activity.actor.embargo_policy.preferred_duration == timedelta(
        days=45
    )


@pytest.mark.spec("CP-01-010")
@pytest.mark.parametrize(
    "actor",
    [_VENDOR, {"type": "Link", "href": _VENDOR}],
    ids=["bare-uri", "link"],
)
def test_an_actor_named_by_reference_is_refused(actor: Any):
    with pytest.raises(VultronParseValidationError, match="CP-01-010"):
        parse_activity(_body(actor))


@pytest.mark.spec("CP-01-010")
def test_a_profile_that_is_not_the_proposers_is_refused():
    with pytest.raises(VultronParseValidationError, match="attributedTo"):
        parse_activity(_body(_profile(_OTHER, policy_of=_OTHER)))


@pytest.mark.spec("CP-01-010")
@pytest.mark.spec("EP-01-001")
def test_a_profile_carrying_another_actors_policy_is_refused():
    with pytest.raises(VultronParseValidationError, match="actorId"):
        parse_activity(_body(_profile(policy_of=_OTHER)))


@pytest.mark.spec("CP-01-010")
def test_a_create_of_something_else_may_name_its_actor_by_uri():
    """Only the CaseProposal envelope needs the inline profile."""
    body = _body(_VENDOR)
    body["object"] = {
        "type": "Note",
        "id": "https://example.org/notes/n-1",
        "content": "hello",
    }

    assert parse_activity(body).actor is not None


@pytest.mark.spec("CP-01-010")
def test_the_extractor_hands_the_inline_profile_to_core():
    activity = parse_activity(_body(_profile(policy_of=_VENDOR)))

    event = extract_event(activity)

    profile = getattr(event, "proposer_profile", None)
    assert isinstance(profile, CoreActor)
    assert profile.id_ == _VENDOR
    assert profile.embargo_policy is not None
    assert profile.embargo_policy.actor_id == _VENDOR


def _proposal(attributed_to: str = _VENDOR) -> as_CaseProposal:
    return as_CaseProposal(
        id_="https://example.org/proposals/p-002",
        attributed_to=attributed_to,
        object_=_REPORT,
        target=_CASE_ACTOR,
    )


@pytest.mark.spec("CP-01-010")
def test_the_factory_carries_the_senders_profile_inline():
    profile = VultronOrganization(
        id_=_VENDOR,
        embargo_policy=EmbargoPolicy(
            actor_id=_VENDOR,
            inbox=f"{_VENDOR}/inbox",
            preferred_duration=timedelta(days=30),
        ),
    )

    activity = create_case_proposal_activity(
        actor=profile, proposal=_proposal(), to=[_CASE_ACTOR]
    )

    assert activity.actor == profile


@pytest.mark.spec("CP-01-010")
def test_the_factory_refuses_a_profile_that_is_not_the_proposers():
    with pytest.raises(VultronActivityConstructionError, match="CP-01-010"):
        create_case_proposal_activity(
            actor=VultronOrganization(id_=_OTHER),
            proposal=_proposal(),
            to=[_CASE_ACTOR],
        )
