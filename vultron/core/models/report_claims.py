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

"""What a document attached to a report claims, read into a format-neutral form.

A sender may attach a structured document to a ``VulnerabilityReport``, such as
a CSAF 2.1 document (CSAF-01-001).  The wire edge reads it (for CSAF,
:mod:`vultron.wire.csaf.reader`) and hands core a :class:`ClaimsReading`:
the schema verdict, the values the document states, and the fields it could
not read.  Core keeps that reading in a :class:`ReportClaimsRecord`, stored
apart from the report, which stays exactly as received (VM-08-002,
CSAF-04-004).

The models name what a value *means* to a case, not where a format keeps it,
so a reader for another format (CVE JSON, OSV) fills the same types.  Every
value here is one the document states: a field the document omits is absent,
never a default its schema declares (CSAF-02-005).  An absent scalar is
``None`` because "not stated" is a different fact from any value; an absent
list is empty.
"""

import urllib.parse
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_serializer,
    model_validator,
)

from vultron.core.models._helpers import (
    format_timestamp,
    now_utc,
    timestamp_serializer,
)
from vultron.core.models.base import (
    CoreRecord,
    NonEmptyString,
    UriString,
    with_record_id,
)


class SchemaVerdict(StrEnum):
    """The result of checking an attached document against its schema.

    A closed set of two (CSAF-04-001).  Neither value says the document is
    valid in its format: a schema leaves most of a format's rules unchecked,
    so a document can pass it and still break them (CSAF-04-002).
    """

    SCHEMA_VALID = "schema-valid"
    SCHEMA_INVALID = "schema-invalid"


class ClaimOutcome(StrEnum):
    """What became of one value a document claimed (CSAF-04-004).

    Every value starts as ``DISPLAY_ONLY``: reading a document changes no case
    data.  Case creation marks a value ``APPLIED`` when it fills a case input,
    or ``OVERRIDDEN`` when a Vultron field states the same thing and wins
    (CSAF-02-003).
    """

    APPLIED = "applied"
    OVERRIDDEN = "overridden"
    DISPLAY_ONLY = "display-only"


class _ClaimsModel(BaseModel):
    """Immutable, closed base for the claims value objects."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SchemaError(_ClaimsModel):
    """One schema error: where in the document, and what the schema refused."""

    path: NonEmptyString
    message: NonEmptyString


class SkippedClaim(_ClaimsModel):
    """A field the reader found in the document but could not read.

    A schema-invalid document is read one field at a time, and each field that
    cannot be read is skipped and named here (CSAF-04-003).
    """

    path: NonEmptyString
    reason: NonEmptyString


class ClaimedReference(_ClaimsModel):
    """A reference the document states: a URL and what it points to.

    ``category`` is ``None`` when the document leaves it out, even where the
    schema declares a default for it (CSAF-02-005).
    """

    url: NonEmptyString
    summary: NonEmptyString | None = None
    category: NonEmptyString | None = None


class ClaimedAcknowledgment(_ClaimsModel):
    """A party the document thanks: its people, organization and why."""

    names: list[NonEmptyString] = Field(default_factory=list)
    organization: NonEmptyString | None = None
    summary: NonEmptyString | None = None

    @model_validator(mode="after")
    def _states_something(self) -> "ClaimedAcknowledgment":
        if not (self.names or self.organization or self.summary):
            raise ValueError("an acknowledgment names no one and says nothing")
        return self


class VulnerabilityClaims(_ClaimsModel):
    """What the document states about one vulnerability.

    ``ids`` lists the vulnerability's identifiers, a CVE ID first when there
    is one.  ``exploitation`` is the SSVC Exploitation value key as written
    (``N``, ``P`` or ``A`` in SSVC v2): the wire edge copies it as a string,
    and core maps it onto its own SSVC type, because wire code may not import
    the scoring package (ARCH-22-001).  ``first_known_exploitation_dates``
    lists the exploitation dates of the document's entries, in order.
    """

    ids: list[NonEmptyString] = Field(default_factory=list)
    title: NonEmptyString | None = None
    disclosure_date: datetime | None = None
    exploitation: NonEmptyString | None = None
    first_known_exploitation_dates: list[datetime] = Field(
        default_factory=list
    )
    references: list[ClaimedReference] = Field(default_factory=list)

    _serialize_disclosure_date = timestamp_serializer("disclosure_date")

    @field_serializer(
        "first_known_exploitation_dates", mode="wrap", when_used="json"
    )
    def _serialize_exploitation_dates(
        self, value: Any, handler: SerializerFunctionWrapHandler
    ) -> Any:
        """Write each date in the one fixed form (CS-13-007)."""
        if isinstance(value, datetime):
            return format_timestamp(value)
        if isinstance(value, list):
            return [format_timestamp(item) for item in value]
        return handler(value)


class ReportClaims(_ClaimsModel):
    """What a document attached to a report states, in format-neutral terms.

    ``name`` and ``summary`` are the document's title and its document-level
    summary (or, lacking one, description) text (CSAF-03-007).
    ``document_category`` is the kind of document the format says it is (for
    CSAF, ``document.category``).  ``known_affected_vendors`` names the vendors
    of the products the document lists as known affected, each once, in the
    order first found (CSAF-04-007).

    ``distribution_label`` (the TLP label), ``acknowledgments`` and
    ``involved_parties`` (the parties the document says are involved) set no
    case input; they are kept so a human who validates the report sees them
    (CSAF-04-004).
    """

    document_category: NonEmptyString | None = None
    name: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    distribution_label: NonEmptyString | None = None
    acknowledgments: list[ClaimedAcknowledgment] = Field(default_factory=list)
    involved_parties: list[NonEmptyString] = Field(default_factory=list)
    references: list[ClaimedReference] = Field(default_factory=list)
    vulnerabilities: list[VulnerabilityClaims] = Field(default_factory=list)
    known_affected_vendors: list[NonEmptyString] = Field(default_factory=list)

    def value_paths(self) -> list[str]:
        """Return the path of every value these claims hold, in field order.

        A path names one claimed value, such as ``name``,
        ``references[0]`` or ``vulnerabilities[1].disclosure_date``; a
        :class:`ReportClaimsRecord` records one outcome per path
        (CSAF-04-004).  A list contributes one path per item.
        """
        paths = _model_value_paths(self, "")
        for index, vul in enumerate(self.vulnerabilities):
            paths.extend(_model_value_paths(vul, f"vulnerabilities[{index}]."))
        return paths


def _model_value_paths(model: BaseModel, prefix: str) -> list[str]:
    """The paths of *model*'s own stated values, nested claims excluded."""
    paths: list[str] = []
    for name in type(model).model_fields:
        value = getattr(model, name)
        if name == "vulnerabilities" or value is None:
            continue
        if isinstance(value, list):
            paths.extend(f"{prefix}{name}[{i}]" for i in range(len(value)))
        else:
            paths.append(f"{prefix}{name}")
    return paths


class ClaimsReading(_ClaimsModel):
    """The wire edge's reading of one document attached to a report.

    ``document_id`` is the attached document's id and ``document_format``
    names the format it was recognized as (``"CSAF 2.1"``).  The verdict and
    its errors agree: ``SCHEMA_VALID`` carries no error and
    ``SCHEMA_INVALID`` at least one (CSAF-04-001).  ``skipped`` names each
    field that was present but could not be read (CSAF-04-003).
    """

    document_id: NonEmptyString
    document_format: NonEmptyString
    schema_verdict: SchemaVerdict
    schema_errors: list[SchemaError] = Field(default_factory=list)
    claims: ReportClaims = Field(default_factory=ReportClaims)
    skipped: list[SkippedClaim] = Field(default_factory=list)

    @model_validator(mode="after")
    def _verdict_matches_errors(self) -> "ClaimsReading":
        if (self.schema_verdict is SchemaVerdict.SCHEMA_VALID) == bool(
            self.schema_errors
        ):
            raise ValueError(
                f"a {self.schema_verdict.value} verdict cannot carry"
                f" {len(self.schema_errors)} schema error(s): schema-valid"
                " carries none and schema-invalid at least one (CSAF-04-001)"
            )
        return self


class ReportClaimsRecord(CoreRecord):
    """The receiver's record of what a report's attached document claimed.

    One per attached document a reader recognized, stored with the report it
    came on and kept apart from it, so the report stays as received
    (VM-08-002).  It holds the reading, the receiver's time of receipt and
    one :class:`ClaimOutcome` for every value read (CSAF-04-004).  It is
    receiver-local and is never sent to another actor (CSAF-04-005).

    ``received_at`` is when the receiver read the document, not the Offer's
    ``published``, which is the sender's claimed time (CLP-15-003); a date the
    document states is compared with it.  The id is derived from the report
    and document ids (:meth:`build_id`), so a resent Offer finds the record it
    already wrote.
    """

    type_: Literal["ReportClaimsRecord"] = Field(
        default="ReportClaimsRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    report_id: UriString
    activity_id: NonEmptyString
    received_at: datetime = Field(default_factory=now_utc)
    reading: ClaimsReading
    outcomes: dict[NonEmptyString, ClaimOutcome] = Field(default_factory=dict)

    _serialize_received_at = timestamp_serializer("received_at")

    @classmethod
    def build_id(cls, report_id: str, document_id: str) -> str:
        """Return the stable DataLayer id for *document_id* on *report_id*."""
        report = urllib.parse.quote(report_id, safe="")
        document = urllib.parse.quote(document_id, safe="")
        return f"report-claims/{report}/{document}"

    @model_validator(mode="before")
    @classmethod
    def _derive_id_and_outcomes(cls, data: Any) -> Any:
        """Derive the id, and give every value read an outcome.

        The id comes from the report and document ids.  A value the document
        claimed with no outcome given starts ``DISPLAY_ONLY``, and an outcome
        for a path the document claimed nothing at is refused (CSAF-04-004).
        Both are derived before validation, so a validated assignment never
        re-enters them (ARCH-21-004).
        """
        if not isinstance(data, dict) or "reading" not in data:
            return data
        reading = ClaimsReading.model_validate(data["reading"])
        data = dict(data)
        report_id = data.get("report_id")
        if isinstance(report_id, str):
            data = with_record_id(
                data, cls.build_id(report_id, reading.document_id)
            )
        given = data.get("outcomes") or {}
        if not isinstance(given, dict):
            return data
        paths = reading.claims.value_paths()
        unknown = sorted(set(given) - set(paths))
        if unknown:
            raise ValueError(
                f"outcomes name values the document did not claim: {unknown}"
                " (CSAF-04-004)"
            )
        data["outcomes"] = {
            path: given.get(path, ClaimOutcome.DISPLAY_ONLY) for path in paths
        }
        return data

    def with_outcome(
        self, path: str, outcome: ClaimOutcome
    ) -> "ReportClaimsRecord":
        """Return a copy recording *outcome* for the value at *path*."""
        if path not in self.outcomes:
            raise KeyError(
                f"'{path}' names no value the document claimed (CSAF-04-004)"
            )
        return self.model_validate(
            {
                **self.model_dump(),
                "outcomes": {**self.outcomes, path: outcome},
            }
        )


__all__ = [
    "ClaimOutcome",
    "ClaimedAcknowledgment",
    "ClaimedReference",
    "ClaimsReading",
    "ReportClaims",
    "ReportClaimsRecord",
    "SchemaError",
    "SchemaVerdict",
    "SkippedClaim",
    "VulnerabilityClaims",
]
