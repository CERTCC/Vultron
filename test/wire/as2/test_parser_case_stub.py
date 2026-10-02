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

"""A case stub is recognised by its ``type`` alone (CM-11-013, #4045).

The parser used to recognise a stub as a ``VulnerabilityCase`` whose keys all
fell in a list derived from the stub class (#2624), so a sparse full case and
a stub had the same shape.  The stub now names itself
``VulnerabilityCaseStub``, carries the case in ``caseId`` and has the ID
``<case-id>/stub``; a ``VulnerabilityCase`` is a case however few keys it has.
"""

import json

import pytest
from pydantic import ValidationError

from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.unknown_keys import (
    resolve_inline_class as _inline_vocab_class,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseStub,
    case_stub_id,
)

_CASE_ID = "https://example.org/cases/case-stub"
_STUB_ID = f"{_CASE_ID}/stub"
_ACTOR = "https://example.org/actors/coordinator"
_INVITEE = "https://example.org/actors/vendor"


def _enriched_stub() -> dict:
    return {
        "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
        "type": "VulnerabilityCaseStub",
        "id": _STUB_ID,
        "caseId": _CASE_ID,
        "activeEmbargo": {
            "type": "EmbargoEvent",
            "id": f"{_CASE_ID}/embargoes/e0",
            "context": _CASE_ID,
            "endTime": days_from_now_utc(30).isoformat(),
        },
        "caseStatus": {
            "type": "CaseStatus",
            "context": _CASE_ID,
            "em": "ACTIVE",
        },
    }


@pytest.mark.spec("CM-11-013")
def test_a_stub_is_recognised_by_its_type():
    assert (
        _inline_vocab_class(
            {"type": "VulnerabilityCaseStub", "caseId": _CASE_ID}
        )
        is as_VulnerabilityCaseStub
    )


@pytest.mark.spec("CM-11-013")
def test_an_enriched_stub_is_a_stub():
    assert _inline_vocab_class(_enriched_stub()) is as_VulnerabilityCaseStub


@pytest.mark.spec("CM-11-013")
def test_a_sparse_case_is_a_case_not_a_stub():
    """Only ``id`` and ``type``: still a case, because the type says so."""
    resolved = _inline_vocab_class(
        {"type": "VulnerabilityCase", "id": _CASE_ID}
    )
    assert resolved is VulnerabilityCase


@pytest.mark.spec("CM-11-013")
def test_a_sparse_case_validates_as_a_case():
    case = VulnerabilityCase.model_validate(
        {"type": "VulnerabilityCase", "id": _CASE_ID}
    )
    assert case.id_ == _CASE_ID


@pytest.mark.spec("CM-11-013")
def test_the_stub_id_is_derived_from_the_case_it_names():
    stub = as_VulnerabilityCaseStub(case_id=_CASE_ID)
    assert stub.id_ == _STUB_ID == case_stub_id(_CASE_ID)
    assert stub.case_id == _CASE_ID
    assert stub.type_ == "VulnerabilityCaseStub"


@pytest.mark.spec("CM-11-013")
def test_the_stub_serialises_its_type_id_and_case():
    wire = json.loads(
        as_VulnerabilityCaseStub(case_id=_CASE_ID).model_dump_json(
            by_alias=True, exclude_none=True
        )
    )
    assert wire["type"] == "VulnerabilityCaseStub"
    assert wire["id"] == _STUB_ID
    assert wire["caseId"] == _CASE_ID


@pytest.mark.spec("CM-11-013")
@pytest.mark.parametrize(
    "data",
    [
        {"caseId": _CASE_ID, "id": _STUB_ID},
        {"case_id": _CASE_ID, "id_": _STUB_ID},
        {"case_id": _CASE_ID},
    ],
    ids=["wire", "field-names", "derived"],
)
def test_a_stub_validates_from_either_spelling(data):
    assert as_VulnerabilityCaseStub.model_validate(data).id_ == _STUB_ID


@pytest.mark.spec("CM-11-013")
@pytest.mark.parametrize(
    "stub_id",
    [_CASE_ID, "https://example.org/cases/other/stub"],
    ids=["the-case-id", "another-cases-stub"],
)
def test_a_stub_whose_id_disagrees_with_its_case_is_refused(stub_id):
    with pytest.raises(ValidationError, match="CM-11-013"):
        as_VulnerabilityCaseStub.model_validate(
            {"caseId": _CASE_ID, "id": stub_id}
        )


@pytest.mark.spec("CM-11-013")
def test_a_stub_without_its_case_is_refused():
    with pytest.raises(ValidationError, match="caseId"):
        as_VulnerabilityCaseStub.model_validate({"id": _STUB_ID})


def _invite(target: object) -> dict:
    return {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Invite",
        "id": "urn:uuid:invite-enriched",
        "actor": _ACTOR,
        "to": [_INVITEE],
        "published": days_from_now_utc(0).isoformat(),
        "object": {"type": "Organization", "id": _INVITEE},
        "target": target,
        "context": _CASE_ID,
    }


def test_an_invite_with_an_enriched_stub_target_parses():
    """The invitee receives the embargo terms it is asked to consent to."""
    activity = parse_activity(
        json.loads(json.dumps(_invite(_enriched_stub())))
    )
    target = activity.target
    assert isinstance(target, as_VulnerabilityCaseStub)
    assert target.case_id == _CASE_ID
    assert target.active_embargo is not None
    assert target.case_status is not None


@pytest.mark.spec("CM-11-013")
def test_an_invite_whose_target_is_a_sparse_case_parses_it_as_a_case():
    activity = parse_activity(
        _invite({"type": "VulnerabilityCase", "id": _CASE_ID})
    )
    assert isinstance(activity.target, VulnerabilityCase)
    assert not isinstance(activity.target, as_VulnerabilityCaseStub)
