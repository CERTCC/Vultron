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

"""Domain representation of a typed external reference on a VulnerabilityCase.

A ``CaseReference`` is an ``as:Object`` with its own id, so it can be offered,
admitted and ledgered (CM-34).  Its ``url`` holds an ``as:Link``
(:class:`CaseReferenceLink`): the Link's ``href`` is the referenced resource,
and its ``rel`` values say what kind of resource it is.  Those values are the
CVE JSON schema reference tags written as RFC 8288 link relation types
(``notes/as2-vocabulary-alignment.md`` § "CaseReference Holds a Link").
"""

import logging
from types import MappingProxyType
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from vultron.core.models.base import (
    CoreObject,
    NonEmptyString,
    ValidatedAssignmentMixin,
)

logger = logging.getLogger(__name__)

#: Where Vultron's extension link relation types live.  RFC 8288 § 2.1.2
#: writes a relation type that IANA has not registered as a URI.
CASE_REFERENCE_REL_NAMESPACE = "https://certcc.github.io/Vultron/ns/rel/"

#: The CVE JSON schema reference tags that IANA registers as link relation
#: types; RFC 8288 § 2.1.1 writes those as their bare name.
_IANA_REGISTERED_CVE_TAGS = frozenset({"related"})

#: The CVE JSON schema reference tag vocabulary.
CVE_REFERENCE_TAGS = frozenset(
    {
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
)

#: Each CVE reference tag and the link relation type it is written as: the
#: bare name when IANA registers it, a URI under
#: :data:`CASE_REFERENCE_REL_NAMESPACE` otherwise (RFC 8288 § 2.1).
CVE_REFERENCE_TAG_RELS: MappingProxyType[str, str] = MappingProxyType(
    {
        tag: (
            tag
            if tag in _IANA_REGISTERED_CVE_TAGS
            else f"{CASE_REFERENCE_REL_NAMESPACE}{tag}"
        )
        for tag in sorted(CVE_REFERENCE_TAGS)
    }
)

#: The ``rel`` values a case reference's Link may carry.
CASE_REFERENCE_REL_VOCABULARY = frozenset(CVE_REFERENCE_TAG_RELS.values())

#: Fields a parsed Link model may have set that say nothing about the
#: reference: the JSON-LD context it arrived with.
_IGNORED_PARSED_LINK_FIELDS = frozenset({"context_"})


def _wire_names(model: type[BaseModel], names: set[str]) -> list[str]:
    """The wire spellings of *model*'s fields *names*, sorted."""
    fields = model.model_fields
    return sorted(
        fields[name].serialization_alias or fields[name].alias or name
        for name in names
    )


class CaseReferenceLink(ValidatedAssignmentMixin, BaseModel):
    """The ``as:Link`` a :class:`CaseReference` holds in its ``url``.

    Link properties describe the reference, not the resource (AS2 Core
    § 4.2), so this is a value with no id of its own.

    Fields:
        href: The referenced resource's URL.
        name: Optional human-readable title for the resource.
        media_type: Optional MIME type of the resource (wire ``mediaType``).
        rel: The link relation types, drawn from
            :data:`CASE_REFERENCE_REL_VOCABULARY`.  AS2 ``rel`` is not
            functional, so it is a list; empty when the kind is unknown.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    type_: Literal["Link"] = Field(
        default="Link",
        validation_alias="type",
        serialization_alias="type",
    )
    href: NonEmptyString = Field(  # pyright: ignore[reportGeneralTypeIssues]
        ...,
        description="URL of the referenced resource",
    )
    name: NonEmptyString | None = Field(
        default=None,
        description="Human-readable title for the referenced resource",
    )
    media_type: NonEmptyString | None = Field(
        default=None,
        description="MIME type of the referenced resource",
    )
    rel: list[NonEmptyString] = Field(
        default_factory=list,
        description="Link relation types: CVE reference tags as RFC 8288 rels",
    )

    @model_validator(mode="before")
    @classmethod
    def _read_parsed_link(cls, data: object) -> object:
        """Read a Link the parse edge already validated into another model.

        The parser turns every inline ``{"type": "Link"}`` into the wire Link
        class before the parent object validates (ISSUE-3217), so a received
        reference's ``url`` arrives here as that model, not as a dict.  Only
        the fields the sender gave are read.  A Link property this class does
        not hold (``hreflang``, ``width``, …) passed the parse edge's
        unknown-key walk, which decides keys against the wire Link; it is set
        aside and reported here, as that walk does for any other unknown key
        (MV-11-003), rather than refusing the whole activity.
        """
        if not isinstance(data, BaseModel) or isinstance(data, cls):
            return data
        given = data.model_fields_set - _IGNORED_PARSED_LINK_FIELDS
        unheld = given - set(cls.model_fields)
        if unheld:
            logger.info(
                "Set aside Link properties %s a case reference's url does not"
                " hold (it holds %s) (MV-11-003)",
                _wire_names(type(data), unheld),
                _wire_names(cls, set(cls.model_fields)),
            )
        return {name: getattr(data, name) for name in given - unheld}

    @field_validator("rel", mode="before")
    @classmethod
    def _rel_as_list(cls, v: object) -> object:
        # AS2 ``rel`` is not functional: a sender may give one value as a
        # bare string or several as an array.  Both read as a list.
        return [v] if isinstance(v, str) else v

    @field_validator("rel")
    @classmethod
    def _validate_rel(cls, v: list[str]) -> list[str]:
        # Each value is already a ``NonEmptyString`` (CS-08-002); only the
        # vocabulary check remains, and every bad value is named (EH-07-001).
        unknown = [
            rel for rel in v if rel not in CASE_REFERENCE_REL_VOCABULARY
        ]
        if unknown:
            raise ValueError(
                f"Invalid rel value(s) {unknown}. Each must be one of: "
                f"{sorted(CASE_REFERENCE_REL_VOCABULARY)}"
            )
        return v


class CaseReference(CoreObject):
    """Domain representation of a typed external reference for a case.

    Links to external resources (e.g., public advisory, patch, vendor
    bulletin) rather than embedding their content.  The reference is an
    object with its own id; what it points at, and what kind of resource
    that is, live on the :class:`CaseReferenceLink` in ``url``.

    ``type_`` is ``"CaseReference"`` so this class auto-registers in
    :data:`CORE_VOCABULARY` and round-trips through the DataLayer.

    Fields:
        url: Required ``as:Link`` to the referenced resource (CM-05-005).
        name: Optional human-readable title for the reference.
    """

    type_: Literal["CaseReference"] = Field(
        default="CaseReference",
        validation_alias="type",
        serialization_alias="type",
    )
    # AS2 ranges ``url`` over a URI or a Link; ``CoreObject`` declares only
    # the URI branch, and a reference narrows it to the Link branch.
    url: CaseReferenceLink = Field(  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]
        ...,
        description="Link to the external resource",
    )
    name: NonEmptyString | None = Field(
        default=None,
        description="Human-readable title for the reference",
    )


__all__ = [
    "CASE_REFERENCE_REL_NAMESPACE",
    "CASE_REFERENCE_REL_VOCABULARY",
    "CVE_REFERENCE_TAGS",
    "CVE_REFERENCE_TAG_RELS",
    "CaseReference",
    "CaseReferenceLink",
]
