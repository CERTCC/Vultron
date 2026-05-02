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
Unit tests for vultron.wire.as2.factories.embargo.

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
    activate_embargo_activity,
    add_embargo_to_case_activity,
    announce_embargo_activity,
    choose_preferred_embargo_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.intransitive import (
    as_Question,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Invite,
    as_Reject,
    as_Remove,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

_ACTOR_URI = "https://example.org/actors/alice"
_CASE_URI = "https://example.org/cases/case-001"


@pytest.fixture
def sample_embargo() -> EmbargoEvent:
    return EmbargoEvent()


@pytest.fixture
def sample_proposal(sample_embargo) -> as_Invite:
    """EmProposeEmbargoActivity — used for Accept/Reject tests."""
    return em_propose_embargo_activity(
        embargo=sample_embargo, context=_CASE_URI, actor=_ACTOR_URI
    )


# ---------------------------------------------------------------------------
# em_propose_embargo_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_em_propose_embargo_returns_invite(sample_embargo):
    result = em_propose_embargo_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Invite)


def test_em_propose_embargo_object_is_embargo(sample_embargo):
    result = em_propose_embargo_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert result.object_ == sample_embargo


def test_em_propose_embargo_context_is_set(sample_embargo):
    result = em_propose_embargo_activity(
        embargo=sample_embargo, context=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.context == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_em_propose_embargo_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        em_propose_embargo_activity(
            embargo="not-an-embargo"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# em_accept_embargo_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_em_accept_embargo_returns_accept(sample_proposal):
    result = em_accept_embargo_activity(
        proposal=sample_proposal, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Accept)


def test_em_accept_embargo_object_is_proposal(sample_proposal):
    result = em_accept_embargo_activity(
        proposal=sample_proposal, actor=_ACTOR_URI
    )
    assert result.object_ == sample_proposal


def test_em_accept_embargo_context_is_set(sample_proposal):
    result = em_accept_embargo_activity(
        proposal=sample_proposal, context=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.context == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_em_accept_embargo_plain_invite_raises(sample_embargo):
    """A plain as_Invite (not from em_propose_embargo_activity) must fail."""
    plain_invite = as_Invite(actor=_ACTOR_URI, object_=sample_embargo)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        em_accept_embargo_activity(proposal=plain_invite)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# em_reject_embargo_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_em_reject_embargo_returns_reject(sample_proposal):
    result = em_reject_embargo_activity(
        proposal=sample_proposal, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Reject)


def test_em_reject_embargo_object_is_proposal(sample_proposal):
    result = em_reject_embargo_activity(
        proposal=sample_proposal, actor=_ACTOR_URI
    )
    assert result.object_ == sample_proposal


def test_em_reject_embargo_context_is_set(sample_proposal):
    result = em_reject_embargo_activity(
        proposal=sample_proposal, context=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.context == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_em_reject_embargo_plain_invite_raises(sample_embargo):
    plain_invite = as_Invite(actor=_ACTOR_URI, object_=sample_embargo)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        em_reject_embargo_activity(proposal=plain_invite)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# choose_preferred_embargo_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_choose_preferred_embargo_returns_question():
    result = choose_preferred_embargo_activity(actor=_ACTOR_URI)
    assert isinstance(result, as_Question)


def test_choose_preferred_embargo_any_of_is_set(sample_embargo):
    result = choose_preferred_embargo_activity(
        any_of=[sample_embargo], actor=_ACTOR_URI
    )
    assert isinstance(result, as_Question)
    assert getattr(result, "any_of") == [sample_embargo]


def test_choose_preferred_embargo_one_of_is_set(sample_embargo):
    result = choose_preferred_embargo_activity(
        one_of=[sample_embargo], actor=_ACTOR_URI
    )
    assert isinstance(result, as_Question)
    assert getattr(result, "one_of") == [sample_embargo]


def test_choose_preferred_embargo_no_options_creates_empty():
    """Neither any_of nor one_of — should create a valid but empty Question."""
    result = choose_preferred_embargo_activity(actor=_ACTOR_URI)
    assert isinstance(result, as_Question)
    assert getattr(result, "any_of") is None
    assert getattr(result, "one_of") is None


# ---------------------------------------------------------------------------
# activate_embargo_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_activate_embargo_returns_add(sample_embargo):
    result = activate_embargo_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Add)


def test_activate_embargo_object_is_embargo(sample_embargo):
    result = activate_embargo_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert result.object_ == sample_embargo


def test_activate_embargo_target_is_set(sample_embargo):
    result = activate_embargo_activity(
        embargo=sample_embargo, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


def test_activate_embargo_in_reply_to_is_set(sample_embargo, sample_proposal):
    result = activate_embargo_activity(
        embargo=sample_embargo, in_reply_to=sample_proposal, actor=_ACTOR_URI
    )
    assert result.in_reply_to == sample_proposal


@pytest.mark.spec("AF-04-001")
def test_activate_embargo_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        activate_embargo_activity(
            embargo="not-an-embargo"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# add_embargo_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_embargo_to_case_returns_add(sample_embargo):
    result = add_embargo_to_case_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Add)


def test_add_embargo_to_case_object_is_embargo(sample_embargo):
    result = add_embargo_to_case_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert result.object_ == sample_embargo


def test_add_embargo_to_case_target_is_set(sample_embargo):
    result = add_embargo_to_case_activity(
        embargo=sample_embargo, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_add_embargo_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_embargo_to_case_activity(
            embargo="not-an-embargo"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# announce_embargo_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_announce_embargo_returns_announce(sample_embargo):
    result = announce_embargo_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Announce)


def test_announce_embargo_object_is_embargo(sample_embargo):
    result = announce_embargo_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert result.object_ == sample_embargo


def test_announce_embargo_context_is_set(sample_embargo):
    result = announce_embargo_activity(
        embargo=sample_embargo, context=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.context == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_announce_embargo_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        announce_embargo_activity(
            embargo="not-an-embargo"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# remove_embargo_from_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_remove_embargo_from_case_returns_remove(sample_embargo):
    result = remove_embargo_from_case_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Remove)


def test_remove_embargo_from_case_object_is_embargo(sample_embargo):
    result = remove_embargo_from_case_activity(
        embargo=sample_embargo, actor=_ACTOR_URI
    )
    assert result.object_ == sample_embargo


def test_remove_embargo_from_case_origin_is_set(sample_embargo):
    """Uses ``origin`` (not ``target``) for the case reference."""
    result = remove_embargo_from_case_activity(
        embargo=sample_embargo, origin=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.origin == _CASE_URI


def test_remove_embargo_from_case_target_not_used(sample_embargo):
    """Confirm target is NOT set (origin is the correct field)."""
    result = remove_embargo_from_case_activity(
        embargo=sample_embargo, origin=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target is None


@pytest.mark.spec("AF-04-001")
def test_remove_embargo_from_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        remove_embargo_from_case_activity(
            embargo="not-an-embargo"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# __init__.py re-exports (AF-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-04-002")
def test_all_embargo_factories_importable_from_package():
    from vultron.wire.as2.factories import (  # noqa: F401
        activate_embargo_activity,
        add_embargo_to_case_activity,
        announce_embargo_activity,
        choose_preferred_embargo_activity,
        em_accept_embargo_activity,
        em_propose_embargo_activity,
        em_reject_embargo_activity,
        remove_embargo_from_case_activity,
    )
