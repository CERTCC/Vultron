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
"""Persisted mapping from a vulnerability report to its case replica."""

from __future__ import annotations

import urllib.parse
from typing import Any, Literal

from pydantic import AliasChoices, Field, model_validator

from vultron.core.models.base import CoreRecord, NonEmptyString, UriString
from vultron.core.states.rm import RM

# Keys a link was stored under before #4020 renamed the two actor-id fields.
# CodeQL's ``py/clear-text-logging-sensitive-data`` heuristic reads any name
# containing "trusted" as a secret, so every log line printing an actor id
# resolved through those attributes was flagged.  The old keys stay readable
# as validation aliases so a link persisted before the rename still loads;
# a dump writes only the new field names, so a re-saved row migrates itself.
# The aliases are load-bearing: ``CoreRecord`` does not forbid extras, so
# without them an old key would be ignored and the CBT-01-006 trust anchors
# would silently read back as ``None``.  If a row somehow carries both
# spellings, the new name wins (it is listed first) — the old key can only
# be stale, since nothing writes it after the rename.
_LEGACY_CASE_CREATOR_FIELD = "trusted_case_creator_id"
_LEGACY_CASE_MANAGER_FIELD = "trusted_case_actor_id"


class VultronReportCaseLink(CoreRecord):
    """Track the case associated with a submitted vulnerability report.

    The DataLayer id is derived from ``report_id`` alone (:meth:`build_id`), so
    a store holds exactly **one** link per report.  ``rm_state`` is therefore
    report-scoped *per store*, not per actor.

    That is not an isolation gap, because ADR-0073 gives every hosted actor its
    own store and forbids two actors sharing one DataLayer (a shared
    multi-tenant store is the anti-pattern that decision removes; PCR-01-003).
    Under per-actor isolation "one link per report per store" already means
    "one link per report per actor", so each coordinator progresses its own
    report RM state independently.

    Co-locating two distinct coordinators in a **single** DataLayer is
    unsupported: they would collide on this one record and one actor's advance
    would block the other's (issue #3266).  Coordinators that must both handle a
    report run as separate actors with separate stores and exchange state only
    through protocol messages (PCR-01-003), never a shared link.
    """

    type_: Literal["ReportCaseLink"] = Field(  # type: ignore[assignment]
        default="ReportCaseLink",
        validation_alias="type",
        serialization_alias="type",
    )
    report_id: UriString = Field(..., description="URI of the linked report")
    case_id: UriString | None = Field(
        default=None,
        description="URI of the linked case replica, once known",
    )
    case_creator_id: UriString | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "case_creator_id", _LEGACY_CASE_CREATOR_FIELD
        ),
        description=(
            "URI of the actor that the reporter sent the original report offer "
            "to.  Set at submission time; validated against the bootstrap "
            "Create(VulnerabilityCase) sender (CBT-01-005, CBT-01-006)."
        ),
    )
    case_manager_id: UriString | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "case_manager_id", _LEGACY_CASE_MANAGER_FIELD
        ),
        description=(
            "URI of the case's CASE_MANAGER, recorded after bootstrap "
            "validation (ADR-0088).  Extracted from the CASE_MANAGER "
            "participant in the bootstrap snapshot; used to validate subsequent "
            "Announce(VulnerabilityCase) senders (CBT-01-006)."
        ),
    )
    proposal_rejected: bool = Field(
        default=False,
        description=(
            "True when the case-actor service rejected the CaseProposal "
            "for this report (CP-06-004)."
        ),
    )
    rejection_reason: NonEmptyString | None = Field(
        default=None,
        description=(
            "Human-readable reason provided by the case-actor service when "
            "rejecting the CaseProposal (CP-06-004).  None when not provided "
            "or when the proposal was accepted."
        ),
    )
    rm_state: RM = Field(
        default=RM.RECEIVED,
        description=(
            "RM state for this report before a case is established. "
            "Replaces the report-phase ParticipantStatus latch pattern "
            "(BTND-10-006, ADR-0089)."
        ),
    )

    @classmethod
    def build_id(cls, report_id: str) -> str:
        """Return the stable DataLayer ID for *report_id*."""
        slug = urllib.parse.quote(report_id, safe="")
        return f"report-case-link/{slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``report_id``."""
        if isinstance(data, dict):
            report_id = data.get("report_id")
            if report_id is not None:
                data = dict(data)
                data["id"] = cls.build_id(report_id)
        return data
