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

"""Domain representation of a vulnerability report."""

from typing import Annotated, Any, Literal

from pydantic import AfterValidator, Field, field_validator

from vultron.core.models.attached_document import (
    ATTACHED_FILE_TYPES,
    AttachedFile,
)
from vultron.core.models.base import CoreObject


def _not_a_file(value: Any) -> Any:
    """Refuse a file-typed attachment that its own file class refused.

    Without this, a ``Document`` that fails :class:`AttachedDocument` would
    be kept untyped as an :data:`OtherAttachment` instead of failing fast.
    """
    if isinstance(value, dict) and value.get("type") in ATTACHED_FILE_TYPES:
        raise ValueError(
            f"a {value['type']!r} attachment must be a valid "
            f"{ATTACHED_FILE_TYPES[value['type']].__name__}"
        )
    return value


#: An attachment that is no file: a ``Note``, a ``Link``, a bare URI, or any
#: other AS2 object or link, which AS2 allows in ``attachment``.  The report
#: keeps it as received and nothing reads it, because a report is never
#: refused over the form of an attachment (CSAF-02-006, ADR-0184).  It is
#: untyped, like the other open AS2 slots of :class:`CoreObject`.
OtherAttachment = Annotated[Any, AfterValidator(_not_a_file)]

#: One entry of a report's ``attachment`` list: a typed file when it is one,
#: else carried as received.  Left to right, so a file is never kept untyped.
ReportAttachment = Annotated[
    AttachedFile | OtherAttachment, Field(union_mode="left_to_right")
]


class VulnerabilityReport(CoreObject):
    """Domain representation of a vulnerability report.

    Canonical core type for the Vultron ``VulnerabilityReport`` object.
    ``type_`` is ``"VulnerabilityReport"`` to match the wire value and to
    auto-register this class in :data:`CORE_VOCABULARY`.

    Policy implementations receive this type when evaluating credibility
    and validity.  The wire name ``as_VulnerabilityReport`` in
    ``vultron.wire.as2.vocab.objects.vulnerability_report`` is an alias of
    this class (ARCH-25-003, ADR-0099): a ``by_alias`` dump is its AS2 form
    (ARCH-12-013), and there is no separate wire class or projection step.

    ``attachment`` holds what the report carries, a CSAF document among
    them (CSAF-01-001).  A file is a core ``Document``, ``Image``, ``Audio``
    or ``Video`` object
    (:data:`~vultron.core.models.attached_document.AttachedFile`); anything
    else AS2 allows there is kept as received (:data:`OtherAttachment`), so
    no attachment refuses the report (CSAF-02-006).  A single attachment
    sent without a list is read as a list of one, its JSON-LD equivalent.
    It stays ``None`` when the report carries none, because the AS2 form
    omits an absent ``attachment`` and an empty list would be a key the
    sender never sent.
    """

    type_: Literal["VulnerabilityReport"] = Field(
        default="VulnerabilityReport",
        validation_alias="type",
        serialization_alias="type",
    )
    attachment: list[ReportAttachment] | None = None

    @field_validator("attachment", mode="before")
    @classmethod
    def _one_attachment_is_a_list_of_one(cls, value: Any) -> Any:
        """Read a single attachment as a list of one (AS2 allows either)."""
        if value is None or isinstance(value, list):
            return value
        return [value]


__all__ = ["OtherAttachment", "ReportAttachment", "VulnerabilityReport"]
