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
"""
Unit tests for vultron.wire.as2.factories.actor.

Spec coverage:
- AF-01-002: Factory functions return plain AS2 base types.
- AF-01-003: Explicit, domain-typed parameters for protocol-significant fields.
- AF-04-001: Factory functions wrap ValidationError in
  VultronActivityConstructionError.
- AF-04-002: All factory functions re-exported from factories/__init__.py.
"""

import pytest

from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    accept_actor_recommendation_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Person

_ACTOR_URI = "https://example.org/actors/alice"
_CASE_URI = "https://example.org/cases/case-001"


@pytest.fixture
def sample_actor() -> as_Person:
    return as_Person(name="Alice", id_=_ACTOR_URI)


@pytest.fixture
def sample_recommendation(sample_actor) -> as_Offer:
    """RecommendActorActivity — used for Accept/Reject tests."""
    return recommend_actor_activity(
        recommended=sample_actor, target=_CASE_URI, actor=_ACTOR_URI
    )


# ---------------------------------------------------------------------------
# recommend_actor_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_recommend_actor_returns_offer(sample_actor):
    result = recommend_actor_activity(
        recommended=sample_actor, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Offer)


def test_recommend_actor_object_is_actor(sample_actor):
    result = recommend_actor_activity(
        recommended=sample_actor, actor=_ACTOR_URI
    )
    assert result.object_ == sample_actor


def test_recommend_actor_target_is_set(sample_actor):
    result = recommend_actor_activity(
        recommended=sample_actor, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_recommend_actor_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        recommend_actor_activity(
            recommended="not-an-actor"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# accept_actor_recommendation_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_accept_actor_recommendation_returns_accept(sample_recommendation):
    result = accept_actor_recommendation_activity(
        offer=sample_recommendation, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Accept)


def test_accept_actor_recommendation_object_is_recommendation(
    sample_recommendation,
):
    result = accept_actor_recommendation_activity(
        offer=sample_recommendation, actor=_ACTOR_URI
    )
    assert result.object_ == sample_recommendation


def test_accept_actor_recommendation_target_is_set(sample_recommendation):
    result = accept_actor_recommendation_activity(
        offer=sample_recommendation, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_accept_actor_recommendation_plain_offer_raises(sample_actor):
    """A plain as_Offer (not from recommend_actor_activity) must fail."""
    plain_offer = as_Offer(actor=_ACTOR_URI, object_=sample_actor)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        accept_actor_recommendation_activity(offer=plain_offer)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# reject_actor_recommendation_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_reject_actor_recommendation_returns_reject(sample_recommendation):
    result = reject_actor_recommendation_activity(
        offer=sample_recommendation, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Reject)


def test_reject_actor_recommendation_object_is_recommendation(
    sample_recommendation,
):
    result = reject_actor_recommendation_activity(
        offer=sample_recommendation, actor=_ACTOR_URI
    )
    assert result.object_ == sample_recommendation


def test_reject_actor_recommendation_target_is_set(sample_recommendation):
    result = reject_actor_recommendation_activity(
        offer=sample_recommendation, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_reject_actor_recommendation_plain_offer_raises(sample_actor):
    plain_offer = as_Offer(actor=_ACTOR_URI, object_=sample_actor)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        reject_actor_recommendation_activity(offer=plain_offer)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# __init__.py re-exports (AF-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-04-002")
def test_all_actor_factories_importable_from_package():
    from vultron.wire.as2.factories import (  # noqa: F401
        accept_actor_recommendation_activity,
        recommend_actor_activity,
        reject_actor_recommendation_activity,
    )
