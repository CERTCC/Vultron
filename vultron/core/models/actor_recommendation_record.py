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

"""The CASE_MANAGER's record of who recommended an actor to a case.

When the CASE_MANAGER receives an ``Offer(Actor, Case)`` it forwards the
recommendation to the case owner, and once the owner decides it tells the
recommender (CM-16-006, CM-16-007).  The decision arrives naming only the
recommendation, so the CASE_MANAGER keeps this record to find the recommender
again without re-reading the stored wire Offer (ADR-0035 DL-06-002).

This is *case bookkeeping* (CLP-07-014): a working record the CASE_MANAGER
keeps beside the case, like the report offer records, and not part of the case
file.  It is a :class:`~vultron.core.models.base.CoreRecord`, so it has no AS2
spelling and is never rendered into a case snapshot or a ledger entry
(ARCH-20-003), and it lives only in the CASE_MANAGER's own store.

The record is keyed by the case and the recommendation through
:meth:`ActorRecommendationRecord.build_id`, so a decision about one case never
finds a recommendation recorded for another.
"""

import urllib.parse
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import CoreRecord, UriString, with_record_id


class ActorRecommendationRecord(CoreRecord):
    """Who recommended an actor to a case, kept by the CASE_MANAGER.

    Attributes:
        case_id: URI of the case the actor was recommended to.
        recommendation_id: URI of the received ``Offer(Actor, Case)``.
        recommender_id: URI of the participant that made the recommendation,
            the actor the owner's decision is reported back to.
    """

    type_: Literal["ActorRecommendationRecord"] = Field(  # type: ignore[assignment]
        default="ActorRecommendationRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: UriString = Field(
        ..., description="URI of the case the actor was recommended to"
    )
    recommendation_id: UriString = Field(
        ..., description="URI of the received Offer(Actor, Case)"
    )
    recommender_id: UriString = Field(
        ..., description="URI of the participant that made the recommendation"
    )

    @classmethod
    def build_id(cls, case_id: str, recommendation_id: str) -> str:
        """Return the stable DataLayer ID for a recommendation on a case."""
        case_slug = urllib.parse.quote(case_id, safe="")
        recommendation_slug = urllib.parse.quote(recommendation_id, safe="")
        return f"actor-recommendation/{case_slug}/{recommendation_slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from the case and recommendation."""
        if isinstance(data, dict):
            case_id = data.get("case_id")
            recommendation_id = data.get("recommendation_id")
            if case_id is not None and recommendation_id is not None:
                data = with_record_id(
                    data, cls.build_id(case_id, recommendation_id)
                )
        return data


__all__ = ["ActorRecommendationRecord"]
