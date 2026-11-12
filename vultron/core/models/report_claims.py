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

import json
import urllib.parse
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_serializer,
    model_validator,
)

from vultron.core.models._helpers import (
    format_timestamp,
    timestamp_serializer,
)
from vultron.core.models.attached_document import AttachedDocument
from vultron.core.models.base import (
    CoreRecord,
    NonEmptyString,
    UriString,
    ValidatedAssignmentMixin,
    with_record_id,
)
from vultron.core.models.vulnerability_item import CveId, NoteCategory
from vultron.errors import VultronValidationError


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


class _ClaimsModel(ValidatedAssignmentMixin):
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
    def _states_something(self) -> ClaimedAcknowledgment:
        if not (self.names or self.organization or self.summary):
            raise ValueError("an acknowledgment names no one and says nothing")
        return self


class ClaimedVulnerabilityId(_ClaimsModel):
    """One tracking ID the document states: a named system and its label.

    ``text`` is copied as written and never parsed (CM-05-008).
    """

    system_name: NonEmptyString
    text: NonEmptyString


class ClaimedNote(_ClaimsModel):
    """A note the document states about one vulnerability.

    ``category`` is one of the note categories CSAF 2.1 allows; the reader
    skips a note of any other (CSAF-04-003).
    """

    category: NoteCategory
    text: NonEmptyString
    title: NonEmptyString | None = None
    audience: NonEmptyString | None = None


class VulnerabilityClaims(_ClaimsModel):
    """What the document states about one vulnerability.

    ``cve``, ``ids``, ``title``, ``notes`` and ``references`` are the
    vulnerability's identity fields, the ones a vulnerability item takes
    (CM-05-018, CSAF-03-008): ``cve`` is its CVE ID, in the format CSAF
    gives it (CM-05-019), and ``ids`` its other tracking IDs, each with the
    system that names it.  ``exploitation`` is the SSVC Exploitation value
    key as written (``N``, ``P`` or ``A`` in SSVC v2): the wire edge copies
    it as a string, and core maps it onto its own SSVC type, because wire
    code may not import the scoring package (ARCH-22-001).
    ``first_known_exploitation_dates`` lists the exploitation dates of the
    document's entries, in order.
    """

    cve: CveId | None = None
    ids: list[ClaimedVulnerabilityId] = Field(default_factory=list)
    title: NonEmptyString | None = None
    notes: list[ClaimedNote] = Field(default_factory=list)
    disclosure_date: AwareDatetime | None = None
    exploitation: NonEmptyString | None = None
    first_known_exploitation_dates: list[AwareDatetime] = Field(
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
        # A lone datetime reaches here only through ``model_construct``, as
        # the CS-13-007 ratchet builds one; validated data is always a list.
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


class CaseSplitDifference(StrEnum):
    """One way in which a document's vulnerabilities disagree (CSAF-04-006)."""

    PUBLIC_STATUS = "public-status"
    EXPLOIT_PUBLIC = "exploit-public"
    ATTACKS_OBSERVED = "attacks-observed"
    FUTURE_DISCLOSURE_DATE = "future-disclosure-date"


class CaseSplitSignal(_ClaimsModel):
    """The document's vulnerabilities may need cases of their own.

    One case takes the most cautious value of its vulnerabilities
    (CSAF-03-002 to CSAF-03-005), which can hold back one whose state
    differs.  The signal names each way they differ, in a fixed order
    (CSAF-04-006).  It only shows that a split may be needed: nothing splits
    a case because of it (CSAF-04-008).
    """

    differs_in: list[CaseSplitDifference] = Field(min_length=1)


class CandidatePartiesSignal(_ClaimsModel):
    """The document names vendors the case may need as parties.

    ``vendors`` are the vendors of the products the document lists as known
    affected, other than the receiving actor itself, each once, in the order
    first found (CSAF-04-007).  It only shows that a party may be needed:
    nothing suggests or invites an actor because of it (CSAF-04-008).
    """

    vendors: list[NonEmptyString] = Field(min_length=1)


class ClaimsReading(_ClaimsModel):
    """The wire edge's reading of one document attached to a report.

    ``document_id`` is the attached document's id and ``document_format``
    names the format it was recognized as (``"CSAF 2.1"``).
    ``document_digest`` is the SHA-256 of the document's content as received:
    a ``Document`` its sender gave no id gets a fresh one at every parse, so
    the content, not the id, is what names the document across a resend.  The verdict and
    its errors agree: ``SCHEMA_VALID`` carries no error and
    ``SCHEMA_INVALID`` at least one (CSAF-04-001).  ``skipped`` names each
    field that was present but could not be read (CSAF-04-003).
    """

    document_id: NonEmptyString
    document_digest: NonEmptyString
    document_format: NonEmptyString
    schema_verdict: SchemaVerdict
    schema_errors: list[SchemaError] = Field(default_factory=list)
    claims: ReportClaims = Field(default_factory=ReportClaims)
    skipped: list[SkippedClaim] = Field(default_factory=list)

    @model_validator(mode="after")
    def _verdict_matches_errors(self) -> ClaimsReading:
        if (self.schema_verdict is SchemaVerdict.SCHEMA_VALID) == bool(
            self.schema_errors
        ):
            raise ValueError(
                f"a {self.schema_verdict.value} verdict cannot carry"
                f" {len(self.schema_errors)} schema error(s): schema-valid"
                " carries none and schema-invalid at least one (CSAF-04-001)"
            )
        return self


#: The largest attachment content, in characters, that a reader parses as a
#: document's claims.  Every received report's attachments are parsed and
#: schema-checked, so an unbounded one would let one Offer occupy the
#: receiver; a larger one is kept with the report and not read.  A sender
#: that attaches a larger one sends a document no receiver reads.  The
#: inbox-wide body limit is #4596 (IE-03-002).
MAX_CSAF_CONTENT_CHARS = 8 * 1024 * 1024


def csaf_document_text(document: Mapping[str, object]) -> str:
    """The JSON text a submitted CSAF document is attached as (CSAF-01-001).

    The one place that text is made, so what the trigger checks is what it
    sends.  It is checked before the document is parsed as CSAF, so an
    oversized one is never parsed.

    Raises:
        VultronValidationError: the text is not valid Unicode (a lone
            surrogate, which no UTF-8 body can carry), or it is longer than
            the :data:`MAX_CSAF_CONTENT_CHARS` a receiver reads, so no
            receiver would read the document (CSAF-04-009).  The message
            never repeats the text, so the 422 that reports it can always
            be written.
    """
    text = json.dumps(document, ensure_ascii=False)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise VultronValidationError(
            "csaf_document holds text that is not valid Unicode"
            f" ({exc.reason}), so it cannot be sent as UTF-8 JSON"
            " (CSAF-04-009)"
        ) from exc
    if len(text) > MAX_CSAF_CONTENT_CHARS:
        raise VultronValidationError(
            f"csaf_document is {len(text)} characters as JSON text, more than"
            f" the {MAX_CSAF_CONTENT_CHARS} a receiver reads as CSAF"
            " (CSAF-04-009)"
        )
    return text


class SubmittedCsafDocument(_ClaimsModel):
    """A CSAF document a Reporter asks the submit-report trigger to attach.

    The trigger's edge reads the JSON object the request carries:
    ``attachment`` is the ``Document`` that would carry it, its JSON text as
    ``content`` and ``application/json`` as ``media_type`` (CSAF-01-001,
    CSAF-01-002), and ``reading`` is the schema check and the claims of that
    same text, naming that same attachment.  Nothing here judges the
    document: the trigger refuses one that a receiver would not take as the
    sender's statement (CSAF-04-009), so this model carries an invalid one
    as faithfully as a valid one.  Only content no receiver would read at
    all, longer than :data:`MAX_CSAF_CONTENT_CHARS`, is refused here.
    """

    attachment: AttachedDocument
    reading: ClaimsReading

    @model_validator(mode="after")
    def _reading_is_of_the_attachment(self) -> SubmittedCsafDocument:
        if self.reading.document_id != self.attachment.id_:
            raise ValueError(
                f"the reading names document {self.reading.document_id!r},"
                f" not the attachment {self.attachment.id_!r} it was read from"
            )
        if self.attachment.content is None:
            raise ValueError(
                "a submitted CSAF document's attachment needs its JSON text"
                " as content (CSAF-01-001)"
            )
        if len(self.attachment.content) > MAX_CSAF_CONTENT_CHARS:
            raise ValueError(
                f"a submitted CSAF document of {len(self.attachment.content)}"
                f" characters is more than the {MAX_CSAF_CONTENT_CHARS} a"
                " receiver reads (CSAF-04-009)"
            )
        if self.attachment.media_type != "application/json":
            raise ValueError(
                "a submitted CSAF document's attachment needs the media type"
                f" application/json, not {self.attachment.media_type!r}"
                " (CSAF-01-002)"
            )
        return self


class ReportClaimsRecord(CoreRecord):
    """The receiver's record of what a report's attached document claimed.

    One per attached document a reader recognized, stored with the report it
    came on and kept apart from it, so the report stays as received
    (VM-08-002).  It holds the reading, the receiver's time of receipt and
    one :class:`ClaimOutcome` for every value read (CSAF-04-004), with the
    case-split and candidate-parties signals the document raised, each
    ``None`` when it raised none (CSAF-04-006, CSAF-04-007).  It is
    receiver-local and is never sent to another actor (CSAF-04-005).

    ``received_at`` is the instant of the act that read the document, so no
    clock is read below the act's edge (ADR-0176).  It is not the Offer's
    ``published``, which is the sender's claimed time (CLP-15-003); a date the
    document states is compared with it.  ``case_id`` names the case the
    document filled, on the record of the side that created that case;
    ``None`` on a record that shaped no case.  The id is derived from the
    report id, the document's content digest and ``case_id``
    (:meth:`build_id`), so a resent Offer
    finds the record it already wrote even when the parser minted the
    document a new id, and two different documents never share a record.
    """

    type_: Literal["ReportClaimsRecord"] = Field(
        default="ReportClaimsRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    report_id: UriString
    activity_id: NonEmptyString
    received_at: datetime
    case_id: UriString | None = None
    reading: ClaimsReading
    outcomes: dict[NonEmptyString, ClaimOutcome] = Field(default_factory=dict)
    case_split_signal: CaseSplitSignal | None = None
    candidate_parties_signal: CandidatePartiesSignal | None = None

    _serialize_received_at = timestamp_serializer("received_at")

    @classmethod
    def build_id(
        cls, report_id: str, document_digest: str, case_id: str | None = None
    ) -> str:
        """Return the stable DataLayer id for a document on *report_id*.

        *document_digest* is the document's content digest
        (:attr:`ClaimsReading.document_digest`).  *case_id* names the case
        the document filled, for the record of the side that created it: two
        cases made from one report each keep what became of the claims in
        their own record.
        """
        report = urllib.parse.quote(report_id, safe="")
        document = urllib.parse.quote(document_digest, safe="")
        record_id = f"report-claims/{report}/{document}"
        if case_id is None:
            return record_id
        return f"{record_id}/{urllib.parse.quote(case_id, safe='')}"

    @model_validator(mode="before")
    @classmethod
    def _derive_id_and_outcomes(cls, data: Any) -> Any:
        """Derive the id, and give every value read an outcome.

        The id comes from the report id and the document's content digest.  A value the document
        claimed with no outcome given starts ``DISPLAY_ONLY``, and an outcome
        for a path the document claimed nothing at is refused (CSAF-04-004).
        Both are derived before validation, so a validated assignment never
        re-enters them (ARCH-21-004).
        """
        if not isinstance(data, dict) or "reading" not in data:
            return data
        raw = data["reading"]
        reading = (
            raw if isinstance(raw, ClaimsReading) else ClaimsReading(**raw)
        )
        data = dict(data)
        report_id = data.get("report_id")
        if isinstance(report_id, str):
            case_id = data.get("case_id")
            data = with_record_id(
                data,
                cls.build_id(
                    report_id,
                    reading.document_digest,
                    case_id if isinstance(case_id, str) else None,
                ),
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
    ) -> ReportClaimsRecord:
        """Return a copy recording *outcome* for the value at *path*."""
        return self.with_outcomes({path: outcome})

    def with_outcomes(
        self, outcomes: Mapping[str, ClaimOutcome]
    ) -> ReportClaimsRecord:
        """Return a copy recording each outcome of *outcomes* at its path.

        Raises:
            KeyError: when a path names no value the document claimed.
        """
        unknown = sorted(set(outcomes) - set(self.outcomes))
        if unknown:
            raise KeyError(
                f"{unknown} name no value the document claimed (CSAF-04-004)"
            )
        return self._copy_with(outcomes={**self.outcomes, **outcomes})

    def with_signals(
        self,
        case_split: CaseSplitSignal | None,
        candidate_parties: CandidatePartiesSignal | None,
    ) -> ReportClaimsRecord:
        """Return a copy holding *case_split* and *candidate_parties*."""
        return self._copy_with(
            case_split_signal=case_split,
            candidate_parties_signal=candidate_parties,
        )

    def _copy_with(self, **changes: object) -> ReportClaimsRecord:
        """A validated copy with *changes*, so no assignment skips validation."""
        return type(self)(**{**self.model_dump(), **changes})


__all__ = [
    "CandidatePartiesSignal",
    "CaseSplitDifference",
    "CaseSplitSignal",
    "ClaimOutcome",
    "ClaimedAcknowledgment",
    "ClaimedNote",
    "ClaimedReference",
    "ClaimedVulnerabilityId",
    "ClaimsReading",
    "MAX_CSAF_CONTENT_CHARS",
    "ReportClaims",
    "ReportClaimsRecord",
    "SchemaError",
    "SchemaVerdict",
    "SkippedClaim",
    "SubmittedCsafDocument",
    "VulnerabilityClaims",
    "csaf_document_text",
]
