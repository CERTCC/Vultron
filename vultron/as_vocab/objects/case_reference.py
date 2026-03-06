#!/usr/bin/env python
"""
Provides a CaseReference object for the Vultron ActivityStreams Vocabulary.
"""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from typing import TypeAlias

from pydantic import Field, field_validator

from vultron.as_vocab.base.links import ActivityStreamRef
from vultron.as_vocab.base.registry import activitystreams_object
from vultron.as_vocab.objects.base import VultronObject
from vultron.enums import VultronObjectType as VO_type

# CVE JSON Schema reference tag vocabulary
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


@activitystreams_object
class CaseReference(VultronObject):
    """
    Represents a typed external reference associated with a case.

    A CaseReference links to external resources (e.g., public advisory, patch,
    vendor bulletin, or other vulnerability-related resource) rather than
    embedding their content. The structure aligns with the CVE JSON schema
    reference format.

    Fields:
        url: Required URL reference (must be non-empty string).
        name: Optional human-readable title for the reference.
        tags: Optional array of type descriptors from CVE JSON schema
            vocabulary (e.g., 'patch', 'vendor-advisory', 'exploit', etc.).
    """

    as_type: VO_type = Field(default=VO_type.CASE_REFERENCE, alias="type")

    url: str = Field(
        ...,
        description="URL reference for the external resource",
    )
    name: str | None = Field(
        default=None,
        description="Human-readable title for the reference",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Type descriptors from CVE JSON schema vocabulary",
    )

    @field_validator("url")
    @classmethod
    def validate_url_not_empty(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("url must be a non-empty string")
        return v

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v):
        if v is not None and (not isinstance(v, str) or not v.strip()):
            raise ValueError("name must be either None or a non-empty string")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("tags must be a list or None")
        if not v:
            raise ValueError("tags must have at least one element")
        for tag in v:
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError("All tags must be non-empty strings")
        return v


CaseReferenceRef: TypeAlias = ActivityStreamRef[CaseReference]


def main():
    from vultron.as_vocab.base.objects.actors import as_Actor

    actor = as_Actor()
    obj = CaseReference(
        url="https://example.org/advisory/",
        name="Example Security Advisory",
        tags=["vendor-advisory", "patch"],
        attributed_to=[actor],
    )
    _json = obj.to_json(indent=2)
    print(_json)
    with open("../../../doc/examples/case_reference.json", "w") as fp:
        fp.write(_json)


if __name__ == "__main__":
    main()
