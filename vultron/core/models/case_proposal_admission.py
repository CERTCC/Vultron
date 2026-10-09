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

"""Durable record that a ``Create(as_CaseProposal)`` was *admitted*.

The mirror image of :class:`~vultron.core.models.case_proposal_decline.CaseProposalDeclineRecord`,
and written for the same reason: the admission decision needs durable evidence
that is keyed on the **proposal**, not on the report.

``main_flow`` writes this as its first step, before the case is created. That
ordering is what the guard on the refusal arm needs, because the accept path
creates the case and commits its ledger entries *before* it emits the
``Accept``. A delivery that fails in that window leaves a case with no stored
``Accept``, and without a proposal-keyed record the only evidence available is
report-keyed — which answers a different question:

- *"has a case been created for this report?"* is true for a proposal this
  service never saw, because ``report_id`` comes from the report the **sender**
  embedded in its proposal (``request.inner_object_id``). Two proposals can name
  one report, so a report-keyed guard reports "already answered" for a proposal
  that was never adjudicated at all — silently skipping the admission call-out
  point and admitting through the duplicate-reuse path.
- *"did this proposal begin the accept path?"* is the question the guard actually
  needs, and only a proposal-keyed record answers it.

Spec: ``specs/case-proposal.yaml`` CP-05-002, CP-05-005, CP-05-006.
"""

import urllib.parse
from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import (
    UriString,
    with_record_id,
)
from vultron.core.models.retired_stored_fields import (
    RetiredFieldsRecord,
    RetiredStoredField,
)


class CaseProposalAdmissionRecord(RetiredFieldsRecord):
    """Durable record that this service admitted a ``CaseProposal``.

    Attributes:
        proposal_id: URI of the ``as_CaseProposal`` that was admitted. Used as
            the stable key component for ``build_id()``.
        case_actor_id: URI of the case actor service that made the decision.
        proposer_uri: URI of the proposing actor owed the ``Accept``.

    A stored record that still carries the retired ``vendor_uri`` key is
    refused on load (#4128); the store must be reset.

    Spec: CP-05-002, CP-05-005, CP-05-006.
    """

    type_: Literal["CaseProposalAdmissionRecord"] = Field(  # type: ignore[assignment]
        default="CaseProposalAdmissionRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    proposal_id: UriString = Field(
        ..., description="URI of the CaseProposal that was admitted"
    )
    case_actor_id: UriString = Field(
        ..., description="URI of the case actor service that admitted it"
    )
    proposer_uri: UriString = Field(
        ..., description="URI of the proposing actor owed the Accept"
    )

    retired_stored_fields: ClassVar[Mapping[str, RetiredStoredField]] = {
        "vendor_uri": RetiredStoredField("proposer_uri", "#4128"),
    }

    @classmethod
    def build_id(cls, proposal_id: str) -> str:
        """Return the stable DataLayer ID for *proposal_id*."""
        slug = urllib.parse.quote(proposal_id, safe="")
        return f"case-proposal-admitted/{slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``proposal_id``."""
        if isinstance(data, dict):
            proposal_id = data.get("proposal_id")
            if proposal_id is not None:
                data = with_record_id(data, cls.build_id(proposal_id))
        return data


__all__ = ["CaseProposalAdmissionRecord"]
