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
"""Who recommended whom is case bookkeeping, not part of the case (#4448)."""

import pytest
from pydantic import ValidationError

from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.actor_recommendation_record import (
    ActorRecommendationRecord,
)
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.errors import VultronValidationError

CASE_ID = "https://example.org/cases/c-1"
RECOMMENDATION_ID = "https://example.org/activities/offer-1"
RECOMMENDER_ID = "https://example.org/actors/finder"


def _record(case_id: str = CASE_ID) -> ActorRecommendationRecord:
    return ActorRecommendationRecord(
        case_id=case_id,
        recommendation_id=RECOMMENDATION_ID,
        recommender_id=RECOMMENDER_ID,
    )


def test_the_id_is_derived_from_the_case_and_the_recommendation() -> None:
    record = _record()

    assert record.id_ == ActorRecommendationRecord.build_id(
        CASE_ID, RECOMMENDATION_ID
    )
    assert ActorRecommendationRecord.model_validate(record.model_dump()) == (
        record
    )


def test_the_same_recommendation_on_two_cases_is_two_records() -> None:
    assert _record().id_ != _record("https://example.org/cases/c-2").id_


@pytest.mark.parametrize(
    "field", ["case_id", "recommendation_id", "recommender_id"]
)
def test_every_field_is_required_and_non_empty(field: str) -> None:
    data = {
        "case_id": CASE_ID,
        "recommendation_id": RECOMMENDATION_ID,
        "recommender_id": RECOMMENDER_ID,
    }
    with pytest.raises(ValidationError):
        ActorRecommendationRecord.model_validate({**data, field: ""})
    del data[field]
    with pytest.raises(ValidationError):
        ActorRecommendationRecord.model_validate(data)


@pytest.mark.spec("CLP-07-014")
def test_the_record_is_not_part_of_the_case() -> None:
    assert "recommendation_recommender_index" not in (
        VulnerabilityCase.model_fields
    )
    assert not any(
        "recommend" in name for name in VulnerabilityCase.model_fields
    )


@pytest.mark.spec("CLP-07-014")
@pytest.mark.spec("ARCH-20-003")
def test_the_record_has_no_wire_rendering() -> None:
    """A record with no AS2 spelling cannot enter a snapshot or ledger entry."""
    assert not isinstance(_record(), CoreObject)
    with pytest.raises(VultronValidationError, match="not a CoreObject"):
        As2WireRenderAdapter().render(_record())
