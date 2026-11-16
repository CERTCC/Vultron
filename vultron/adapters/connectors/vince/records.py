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

"""The records the VINCE API serves for one case, read at the edge.

Each model holds the fields of one VINCE Comm serializer
(``vinny/serializers.py``) that a crosswalk row reads, and ignores the rest:
the crosswalk names every field the translation reads (CRD-03-001).  An
empty string, which VINCE sends for an unset text field, reads as absent.

The case record must parse, since no row can place anything without the
case's ``vuid``, ``pk`` and ``created`` time; a case that fails is refused
with :class:`~vultron.errors.VinceCaseRecordsError`.  Any other record that
fails to parse is not a reason to refuse the case (CRD-01-005): the
translation returns it as an untranslated fact.  No problem message quotes
a VINCE value, so an error is safe to log (VSD-01-003).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    JsonValue,
    ValidationError,
    field_validator,
)

from vultron.core.models._helpers import as_utc
from vultron.errors import VinceCaseRecordsError
from vultron.primitives import NonEmptyString, is_blank_string


def _blank_is_absent(value: object) -> object:
    """Read VINCE's empty string for an unset field as absent."""
    if isinstance(value, str) and is_blank_string(value):
        return None
    return value


#: A VINCE text field: absent when VINCE sends nothing or an empty string.
Text = Annotated[str | None, BeforeValidator(_blank_is_absent)]
#: A VINCE time: absent when unset; a time with no offset is read as UTC.
Time = Annotated[datetime | None, BeforeValidator(_blank_is_absent)]


class Record(BaseModel):
    """One VINCE record: frozen, and blind to fields no row reads."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    @field_validator("*", mode="after")
    @classmethod
    def _utc(cls, value: object) -> object:
        return as_utc(value) if isinstance(value, datetime) else value


class VinceCase(Record):
    """``case/<vuid>/``: the case itself (VINCE-CA, VINCE-EM)."""

    vuid: NonEmptyString
    pk: int
    created: datetime
    modified: Time = None
    status: Text = None
    title: Text = None
    summary: Text = None
    due_date: Time = None


class VinceReport(Record):
    """``case/<vuid>/report/``: the original report (VINCE-PA-03/04,
    VINCE-RM-01/03, VINCE-CS-01 to VINCE-CS-03, VINCE-CT-03)."""

    date_submitted: Time = None
    vendor_name: Text = None
    product_name: Text = None
    product_version: Text = None
    vul_description: Text = None
    vul_exploit: Text = None
    vul_impact: Text = None
    vul_discovery: Text = None
    vul_public: bool | None = None
    vul_exploited: bool | None = None
    exploit_references: Text = None
    contact_name: Text = None
    contact_email: Text = None
    contact_phone: Text = None
    contact_org: Text = None

    @property
    def shares_contact(self) -> bool:
        """Whether the reporter agreed to share a contact (VINCE-PA-03)."""
        return any(
            (
                self.contact_name,
                self.contact_email,
                self.contact_phone,
                self.contact_org,
            )
        )


class VincePostAuthor(Record):
    """The author of a post, as the post serializer nests it."""

    org: Text = None


class VincePost(Record):
    """One item of ``case/<vuid>/posts/`` (VINCE-CT-02, VINCE-CT-04)."""

    created: Time = None
    author: VincePostAuthor | None = None
    pinned: bool = False
    content: Text = None


class VinceVul(Record):
    """One item of ``case/<vuid>/vuls/`` (VINCE-CT-01)."""

    name: NonEmptyString
    cve: Text = None
    description: Text = None
    date_added: Time = None


class VinceVendor(Record):
    """One item of ``case/<vuid>/vendors/`` (VINCE-PA-02, VINCE-RM-04)."""

    vendor: NonEmptyString
    date_added: Time = None


class VinceVendorVul(Record):
    """One item of ``case/<vuid>/vendors/vuls/`` (VINCE-RM-05 to
    VINCE-RM-07)."""

    vendor: NonEmptyString
    vulnerability: Text = None
    status: Text = None
    statement_date: Time = None


class VinceNote(Record):
    """``case/<vuid>/note/``: the vulnerability note (VINCE-CS-04,
    VINCE-CT-04)."""

    published: bool = False
    datefirstpublished: Time = None
    dateupdated: Time = None
    revision: int | None = None


#: The VINCE reads the translation takes, each keyed by its path below
#: ``case/<vuid>/`` (``case`` for the case itself).
READS = ("case", "report", "posts", "vuls", "vendors", "vendors/vuls", "note")


def _problem(read: str, exc: ValidationError) -> str:
    """*exc* as one line naming each failing field, never its value."""
    fields = "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or '(record)'}:"
        f" {error['msg']}"
        for error in exc.errors(include_input=False)
    )
    return f"{read}: {fields}"


@dataclass(frozen=True)
class ParsedRead[R: Record]:
    """The items of one list read, each with its index in the read.

    Attributes:
        items: Each item that parsed, with its index.
        problems: Each item that did not, with its index and why.
    """

    items: tuple[tuple[int, R], ...] = ()
    problems: tuple[tuple[int, str], ...] = ()


def parse_list[R: Record](
    read: str, raw: object, model: type[R]
) -> ParsedRead[R]:
    """Parse the list read *read* item by item.

    A ``null`` read is VINCE's 404 and holds no item.  A read that is not a
    list is one problem at index ``-1``.
    """
    if raw is None:
        return ParsedRead()
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return ParsedRead(problems=((-1, f"{read}: not a list"),))
    items: list[tuple[int, R]] = []
    problems: list[tuple[int, str]] = []
    for index, item in enumerate(raw):
        try:
            items.append((index, model.model_validate(item)))
        except ValidationError as exc:
            problems.append((index, _problem(f"{read}[{index}]", exc)))
    return ParsedRead(items=tuple(items), problems=tuple(problems))


def parse_one[R: Record](
    read: str, raw: object, model: type[R]
) -> R | str | None:
    """Parse the single-record read *read*: the record, ``None`` for a
    ``null`` (404) read, or the problem that refused it."""
    if raw is None:
        return None
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        return _problem(read, exc)


def parse_case(reads: Mapping[str, JsonValue]) -> VinceCase:
    """The case record of *reads*.

    Raises:
        VinceCaseRecordsError: *reads* has no ``case`` read, or it does not
            parse, so no row can place an entry.
    """
    raw = reads.get("case")
    if raw is None:
        raise VinceCaseRecordsError(None, ["case: the case read is missing"])
    try:
        return VinceCase.model_validate(raw)
    except ValidationError as exc:
        vuid = raw.get("vuid") if isinstance(raw, Mapping) else None
        raise VinceCaseRecordsError(
            vuid if isinstance(vuid, str) else None, [_problem("case", exc)]
        ) from exc


__all__ = [
    "READS",
    "ParsedRead",
    "Record",
    "VinceCase",
    "VinceNote",
    "VincePost",
    "VincePostAuthor",
    "VinceReport",
    "VinceVendor",
    "VinceVendorVul",
    "VinceVul",
    "parse_case",
    "parse_list",
    "parse_one",
]
