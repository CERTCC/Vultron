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
"""The object-fetch record and reference (AKM-05-007)."""

import json

import pytest
from pydantic import ValidationError

from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchState,
    ObjectFetchUse,
    ObjectReference,
    PendingObjectFetch,
)

_OBJECT = "urn:uuid:embargo-1"
_HOST = "https://example.org/actors/case-actor"
_CASE = "https://example.org/cases/c-1"

_REF = ObjectReference(
    object_id=_OBJECT,
    source=ObjectFetchSource.CASE_HOST,
    host_actor_id=_HOST,
    case_id=_CASE,
    use=ObjectFetchUse.STORE,
)


def test_one_record_per_object_keyed_on_its_id():
    record = PendingObjectFetch.for_reference(_REF)

    assert record.id_ == PendingObjectFetch.build_id(_OBJECT)
    assert record.state is ObjectFetchState.PENDING
    assert record.waiting_activity_ids == []
    assert record.reference == _REF


def test_a_case_host_reference_must_name_its_case():
    with pytest.raises(ValidationError, match="names no case"):
        ObjectReference(
            object_id=_OBJECT,
            source=ObjectFetchSource.CASE_HOST,
            host_actor_id=_HOST,
            use=ObjectFetchUse.STORE,
        )


def test_a_profile_reference_needs_no_case():
    reference = ObjectReference(
        object_id=_HOST,
        source=ObjectFetchSource.ACTOR_PROFILE,
        host_actor_id=_HOST,
        use=ObjectFetchUse.HAND_OFF,
    )

    assert reference.case_id is None


def test_a_fetched_record_must_carry_its_body():
    with pytest.raises(ValidationError, match="carries the fetched body"):
        PendingObjectFetch.model_validate(
            {
                **PendingObjectFetch.for_reference(_REF).model_dump(),
                "use": ObjectFetchUse.HAND_OFF,
                "state": ObjectFetchState.FETCHED,
            }
        )


def test_only_a_hand_off_fetch_keeps_its_body():
    with pytest.raises(ValidationError, match="only a HAND_OFF"):
        PendingObjectFetch.model_validate(
            {
                **PendingObjectFetch.for_reference(_REF).model_dump(),
                "state": ObjectFetchState.FETCHED,
                "fetched_body": json.dumps({"id": _OBJECT}),
            }
        )


def test_a_failed_record_must_say_why():
    with pytest.raises(ValidationError, match="failure reason"):
        PendingObjectFetch.model_validate(
            {
                **PendingObjectFetch.for_reference(_REF).model_dump(),
                "state": ObjectFetchState.FAILED,
            }
        )


def test_a_fetched_body_must_be_a_json_object():
    with pytest.raises(ValidationError):
        PendingObjectFetch.model_validate(
            {
                **PendingObjectFetch.for_reference(_REF).model_dump(),
                "use": ObjectFetchUse.HAND_OFF,
                "state": ObjectFetchState.FETCHED,
                "fetched_body": "[1, 2]",
            }
        )


def test_attempts_are_never_negative():
    with pytest.raises(ValidationError):
        PendingObjectFetch.model_validate(
            {
                **PendingObjectFetch.for_reference(_REF).model_dump(),
                "attempts": -1,
            }
        )
