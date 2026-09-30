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

"""The factory completes ``context`` for case-scoped activities (#2654 AC-2).

A canonical ledger entry's snapshot must carry ``context`` equal to the case
URI (CLP-07-007), and the snapshot is the factory's exact blob (VM-08-003).
So the factory, not the emitting node, fills ``context`` in.
"""

import pytest

from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    accept_case_participant_role_activity,
    add_participant_to_case_activity,
    offer_case_participant_activity,
    offer_case_participant_role_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
    reject_case_participant_role_activity,
    remove_participant_from_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.factories._context import (
    case_target_ref,
    case_uri_of,
    with_case_context,
)
from vultron.wire.as2.factories.actor import (
    accept_case_participant_offer_activity,
    reject_case_participant_offer_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseStub,
)

_ACTOR = "https://example.org/actors/coordinator"
_VENDOR = "https://example.org/actors/vendor"
_CASE_ID = "https://example.org/cases/case-ctx"


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------


def test_case_uri_of_reads_a_string_or_an_object_id():
    assert case_uri_of(_CASE_ID) == _CASE_ID
    assert case_uri_of(as_VulnerabilityCase(id_=_CASE_ID)) == _CASE_ID
    assert case_uri_of("") is None
    assert case_uri_of(None) is None


def test_with_case_context_fills_only_a_missing_context():
    assert with_case_context({}, _CASE_ID) == {"context": _CASE_ID}
    assert with_case_context({"context": "urn:x"}, _CASE_ID) == {
        "context": "urn:x"
    }
    assert with_case_context({}, None) == {}


# ---------------------------------------------------------------------------
# The factories
# ---------------------------------------------------------------------------


def _participant() -> as_CaseParticipant:
    return as_CaseParticipant(attributed_to=_VENDOR, context=_CASE_ID)


def _recommendation():
    return recommend_actor_activity(
        recommended=as_Actor(id_=_VENDOR), target=_CASE_ID, actor=_ACTOR
    )


def _cp_offer():
    return offer_case_participant_activity(
        recommended=_VENDOR, target=_CASE_ID, actor=_ACTOR
    )


def _role_offer():
    return offer_case_participant_role_activity(
        role=CVDRole.CASE_MANAGER,
        target_actor=as_Actor(id_=_VENDOR),
        case=as_VulnerabilityCase(id_=_CASE_ID, name="x"),
        actor=_ACTOR,
    )


@pytest.mark.spec("CLP-07-007")
@pytest.mark.spec("VM-08-003")
@pytest.mark.parametrize(
    "build",
    [
        pytest.param(
            lambda: rm_invite_to_case_activity(
                invitee=_VENDOR,
                target=as_VulnerabilityCase(id_=_CASE_ID, name="x"),
                actor=_ACTOR,
            ),
            id="invite_actor_to_case",
        ),
        pytest.param(
            lambda: rm_invite_to_case_activity(
                invitee=_VENDOR, target=_CASE_ID, actor=_ACTOR
            ),
            id="invite_actor_to_case-bare-target",
        ),
        pytest.param(_recommendation, id="recommend_actor"),
        pytest.param(
            lambda: accept_actor_recommendation_activity(
                offer=_recommendation(), target=_CASE_ID, actor=_ACTOR
            ),
            id="accept_actor_recommendation",
        ),
        pytest.param(
            lambda: reject_actor_recommendation_activity(
                offer=_recommendation(), target=_CASE_ID, actor=_ACTOR
            ),
            id="reject_actor_recommendation",
        ),
        pytest.param(_cp_offer, id="offer_case_participant"),
        pytest.param(
            lambda: accept_case_participant_offer_activity(
                offer=_cp_offer(), target=_CASE_ID, actor=_ACTOR
            ),
            id="accept_case_participant_offer",
        ),
        pytest.param(
            lambda: reject_case_participant_offer_activity(
                offer=_cp_offer(), target=_CASE_ID, actor=_ACTOR
            ),
            id="reject_case_participant_offer",
        ),
        pytest.param(
            lambda: add_participant_to_case_activity(
                participant=_participant(), target=_CASE_ID, actor=_ACTOR
            ),
            id="add_participant_to_case",
        ),
        pytest.param(
            lambda: remove_participant_from_case_activity(
                participant=_participant(), target=_CASE_ID, actor=_ACTOR
            ),
            id="remove_participant_from_case",
        ),
        pytest.param(
            lambda: accept_case_participant_role_activity(
                offer=_role_offer(), actor=_VENDOR
            ),
            id="accept_case_participant_role",
        ),
        pytest.param(
            lambda: reject_case_participant_role_activity(
                offer=_role_offer(), actor=_VENDOR
            ),
            id="reject_case_participant_role",
        ),
    ],
)
def test_case_scoped_factories_default_context_to_the_case_uri(build):
    activity = build()
    assert case_uri_of(activity.context) == _CASE_ID


def test_an_explicit_context_is_left_alone():
    activity = add_participant_to_case_activity(
        participant=_participant(),
        target=_CASE_ID,
        actor=_ACTOR,
        context="https://example.org/cases/explicit",
    )
    assert activity.context == "https://example.org/cases/explicit"


def test_no_case_means_no_context():
    activity = offer_case_participant_activity(
        recommended=_VENDOR, actor=_ACTOR
    )
    assert activity.context is None


# ---------------------------------------------------------------------------
# A full case never travels in ``target`` (MV-10-001, AKM-02-003)
# ---------------------------------------------------------------------------


def test_case_target_ref_reduces_a_full_case_to_its_uri():
    case = as_VulnerabilityCase(id_=_CASE_ID, name="full")
    assert case_target_ref(case) == _CASE_ID


def test_case_target_ref_leaves_a_uri_a_stub_and_none_alone():
    stub = as_VulnerabilityCaseStub(id_=_CASE_ID)
    assert case_target_ref(_CASE_ID) == _CASE_ID
    assert case_target_ref(stub) is stub
    assert case_target_ref(None) is None


@pytest.mark.spec("AKM-02-003")
def test_factories_given_a_full_case_target_send_its_uri():
    case = as_VulnerabilityCase(id_=_CASE_ID, name="full")
    activity = add_participant_to_case_activity(
        participant=_participant(), target=case, actor=_ACTOR
    )
    dumped = activity.model_dump(by_alias=True, exclude_none=True)
    assert dumped["target"] == _CASE_ID
    assert dumped["context"] == _CASE_ID
