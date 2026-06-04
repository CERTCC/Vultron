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

"""Domain representation of a typed external reference on a VulnerabilityCase."""

from typing import Literal

from pydantic import Field, field_validator

from vultron.core.models.base import CoreObject, NonEmptyString

# CVE JSON Schema reference tag vocabulary (mirrors wire layer)
CASE_REFERENCE_TAG_VOCABULARY = {
    "broken-link",
    "customer-entitlement",
    "exploit",
    "government-resource",
    "issue-tracking",
    "mailing-list",
    "mitigation",
    "not-applicable",
    "patch",
    "permissions-required",
    "media-coverage",
    "product",
    "related",
    "release-notes",
    "signature",
    "technical-description",
    "third-party-advisory",
    "vendor-advisory",
    "vdb-entry",
}


class CaseReference(CoreObject):
    """Domain representation of a typed external reference for a case.

    Links to external resources (e.g., public advisory, patch, vendor
    bulletin) rather than embedding their content.  Aligns with the CVE
    JSON schema reference format.

    ``type_`` is ``"CaseReference"`` so this class auto-registers in
    :data:`CORE_VOCABULARY` and round-trips through the DataLayer.

    Fields:
        url: Required URL reference (must be non-empty string).
        name: Optional human-readable title for the reference.
        tags: Optional list of type descriptors from the CVE JSON schema
            vocabulary (e.g. ``"patch"``, ``"vendor-advisory"``).
    """

    type_: Literal["CaseReference"] = Field(
        default="CaseReference",
        validation_alias="type",
        serialization_alias="type",
    )
    url: NonEmptyString = Field(  # pyright: ignore[reportGeneralTypeIssues]
        ...,
        description="URL reference for the external resource",
    )
    name: NonEmptyString | None = Field(
        default=None,
        description="Human-readable title for the reference",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Type descriptors from CVE JSON schema vocabulary",
    )

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if not v:
            raise ValueError("tags must have at least one element")
        for tag in v:
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError("All tags must be non-empty strings")
            if tag not in CASE_REFERENCE_TAG_VOCABULARY:
                raise ValueError(
                    f"Invalid tag '{tag}'. Must be one of: "
                    f"{sorted(CASE_REFERENCE_TAG_VOCABULARY)}"
                )
        return v
