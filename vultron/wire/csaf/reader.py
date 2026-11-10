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

"""Read a CSAF 2.1 document attached to a report into core claims.

The two-stage parse of ``notes/csaf-report-content.md``:

1. **Recognize, then check.** An attached document is CSAF 2.1 when its own
   ``$schema`` and ``document.csaf_version`` say so (CSAF-01-003).  The
   generated models check it, and the verdict is schema-valid or
   schema-invalid with every error (CSAF-04-001, CSAF-04-002).
2. **Read the claims.** When the models accept the document, the claims come
   from what the parsed object holds as *set*, its ``exclude_unset`` dump, so a
   default the schema declares is never read as the sender's (CSAF-02-005).
   When they refuse it, the claims come from the raw JSON one field at a time,
   and each field that cannot be read is skipped and named (CSAF-04-003).  The
   same field reader serves both, so a schema-valid document reads exactly as
   it would field by field.

Nothing here refuses a report: a document that cannot be read is not CSAF to
this reader, and a schema-invalid one still yields what it can (CSAF-02-006).
The result is a format-neutral core
:class:`~vultron.core.models.report_claims.ClaimsReading`; this module imports
only core models (ARCH-22-001).
"""

import hashlib
import json
import logging
from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import TypeGuard

from pydantic import AwareDatetime, JsonValue, TypeAdapter, ValidationError

from vultron.core.models.attached_document import AttachedDocument
from vultron.core.models.report import ReportAttachment
from vultron.core.models.report_claims import (
    ClaimedAcknowledgment,
    ClaimedReference,
    ClaimsReading,
    ReportClaims,
    SchemaError,
    SchemaVerdict,
    SkippedClaim,
    VulnerabilityClaims,
)
from vultron.wire.csaf.models import CommonSecurityAdvisoryFramework

logger = logging.getLogger(__name__)

#: The ``$schema`` value every CSAF 2.1 document carries (CSAF-01-003).
CSAF_21_SCHEMA = "https://docs.oasis-open.org/csaf/csaf/v2.1/schema/csaf.json"
#: The ``document.csaf_version`` value of a CSAF 2.1 document.
CSAF_21_VERSION = "2.1"
#: The ``document_format`` a reading of a CSAF 2.1 document names.
CSAF_21_FORMAT = "CSAF 2.1"

#: The SSVC namespace and decision-point key of Exploitation.
_SSVC_NAMESPACE = "ssvc"
_SSVC_EXPLOITATION_KEY = "E"
#: The document-level note categories a summary is read from, in preference.
_SUMMARY_NOTE_CATEGORIES = ("summary", "description")

#: The largest attachment content, in characters, the reader parses.  Every
#: received report's attachments are parsed and schema-checked, so an
#: unbounded one would let one Offer occupy the receiver; a larger one is kept
#: with the report and not read.  The inbox-wide body limit is #4596
#: (IE-03-002).
MAX_CSAF_CONTENT_CHARS = 8 * 1024 * 1024

_AWARE_DATETIME: TypeAdapter[datetime] = TypeAdapter(AwareDatetime)


def is_csaf_21(data: object) -> TypeGuard[dict[str, JsonValue]]:
    """Whether *data*, a parsed JSON value, says it is a CSAF 2.1 document.

    Read from the document itself, by its ``$schema`` and its
    ``document.csaf_version`` (CSAF-01-003), never from the attachment's
    media type, which CSAF shares with every other JSON document.
    """
    if not isinstance(data, dict) or data.get("$schema") != CSAF_21_SCHEMA:
        return False
    document = data.get("document")
    return (
        isinstance(document, dict)
        and document.get("csaf_version") == CSAF_21_VERSION
    )


def content_digest(content: str) -> str:
    """The SHA-256 of an attachment's content, as hex: the document's name."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def read_csaf_document(
    document_id: str, data: dict[str, JsonValue], *, digest: str | None = None
) -> ClaimsReading:
    """Check the CSAF 2.1 document *data* and read what it claims.

    *document_id* is the id of the attachment that carried it, and *digest*
    the digest of its content (:func:`content_digest`); without one, the
    digest is taken of *data* written as canonical JSON.  The caller has
    already recognized *data* as CSAF 2.1 (:func:`is_csaf_21`).
    """
    if digest is None:
        digest = content_digest(json.dumps(data, sort_keys=True))
    try:
        # Strict JSON mode, so the check is the schema's: a number is no
        # date-time string and a string no number (CSAF-04-001).
        parsed = CommonSecurityAdvisoryFramework.model_validate_json(
            json.dumps(data), strict=True
        )
    except ValidationError as exc:
        reader = _FieldReader()
        return ClaimsReading(
            document_id=document_id,
            document_digest=digest,
            document_format=CSAF_21_FORMAT,
            schema_verdict=SchemaVerdict.SCHEMA_INVALID,
            schema_errors=_schema_errors(exc),
            claims=reader.read(data),
            skipped=reader.skipped,
        )
    stated = parsed.model_dump(mode="json", by_alias=True, exclude_unset=True)
    reader = _FieldReader()
    return ClaimsReading(
        document_id=document_id,
        document_digest=digest,
        document_format=CSAF_21_FORMAT,
        schema_verdict=SchemaVerdict.SCHEMA_VALID,
        claims=reader.read(stated),
        skipped=reader.skipped,
    )


def read_report_attachments(
    attachments: Sequence[ReportAttachment] | None,
    *,
    activity_id: str,
    actor_id: str,
) -> list[ClaimsReading]:
    """Read every CSAF 2.1 document among a received report's attachments.

    An attachment whose content is not JSON, or JSON that is not CSAF 2.1, is
    no CSAF document and yields no reading; the report is kept whatever its
    attachments hold (CSAF-02-006).  *activity_id* and *actor_id*, the
    carrying activity and its sender, are logged with each attachment passed
    over.
    """
    readings: list[ClaimsReading] = []
    for attachment in attachments or []:
        # CSAF travels as a ``Document`` (CSAF-01-001); an image, audio or
        # video file, or an attachment that is no file (a ``Note``, a
        # ``Link``, a bare URI), is kept with the report and not read.
        if not isinstance(attachment, AttachedDocument):
            continue
        data = _json_content(attachment, activity_id, actor_id)
        if data is None:
            continue
        if not is_csaf_21(data):
            logger.debug(
                "Attachment '%s' of activity '%s' from actor '%s' is not a"
                " CSAF 2.1 document (CSAF-01-003)",
                attachment.id_,
                activity_id,
                actor_id,
            )
            continue
        assert attachment.content is not None  # _json_content parsed it
        readings.append(
            read_csaf_document(
                attachment.id_, data, digest=content_digest(attachment.content)
            )
        )
    return readings


def _json_content(
    attachment: AttachedDocument, activity_id: str, actor_id: str
) -> object | None:
    """The attachment's content parsed as JSON, or ``None`` when it is not."""
    if attachment.content is None:
        return None
    if len(attachment.content) > MAX_CSAF_CONTENT_CHARS:
        logger.info(
            "Attachment '%s' of activity '%s' from actor '%s' holds %d"
            " characters, more than the %d this reader parses, so it is not"
            " read as CSAF (CSAF-02-006)",
            attachment.id_,
            activity_id,
            actor_id,
            len(attachment.content),
            MAX_CSAF_CONTENT_CHARS,
        )
        return None
    try:
        data: object = json.loads(attachment.content)
    except (ValueError, RecursionError) as exc:
        logger.info(
            "Attachment '%s' of activity '%s' from actor '%s' is not"
            " readable JSON, so it is not read as CSAF (CSAF-02-006): %s",
            attachment.id_,
            activity_id,
            actor_id,
            exc,
        )
        return None
    return data


def _location(loc: Sequence[int | str]) -> str:
    """Write a field location as a path from the document root, ``$``."""
    path = "$"
    for part in loc:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _schema_errors(exc: ValidationError) -> list[SchemaError]:
    """Every error the models raised, each at its location in the document."""
    return [
        SchemaError(
            path=_location(error["loc"]), message=error["msg"] or error["type"]
        )
        for error in exc.errors(include_url=False, include_input=False)
    ]


class _FieldReader:
    """Read the claim fields of a CSAF document one field at a time.

    Each helper reads one field: an absent field yields nothing, and a field
    that is present but unreadable yields nothing and is recorded in
    :attr:`skipped` (CSAF-04-003).
    """

    def __init__(self) -> None:
        self.skipped: list[SkippedClaim] = []

    def _skip(self, path: str, reason: str) -> None:
        self.skipped.append(SkippedClaim(path=path, reason=reason))

    def _object(
        self, container: dict[str, JsonValue], key: str, path: str
    ) -> dict[str, JsonValue] | None:
        if key not in container:
            return None
        value = container[key]
        if not isinstance(value, dict):
            self._skip(f"{path}.{key}", "not an object")
            return None
        return value

    def _items(
        self, container: dict[str, JsonValue], key: str, path: str
    ) -> Iterator[tuple[str, dict[str, JsonValue]]]:
        """Yield each object in the list at *key*, with its path."""
        if key not in container:
            return
        value = container[key]
        here = f"{path}.{key}"
        if not isinstance(value, list):
            self._skip(here, "not a list")
            return
        for index, item in enumerate(value):
            if isinstance(item, dict):
                yield f"{here}[{index}]", item
            else:
                self._skip(f"{here}[{index}]", "not an object")

    def _text(
        self, container: dict[str, JsonValue], key: str, path: str
    ) -> str | None:
        if key not in container:
            return None
        value = container[key]
        if isinstance(value, str) and value.strip():
            return value
        self._skip(f"{path}.{key}", "not a non-empty string")
        return None

    def _date(
        self, container: dict[str, JsonValue], key: str, path: str
    ) -> datetime | None:
        if key not in container:
            return None
        value = container[key]
        # A JSON date-time is a string; a number is never read as one.
        if isinstance(value, str):
            try:
                return _AWARE_DATETIME.validate_python(value)
            except ValidationError:
                pass
        self._skip(f"{path}.{key}", "not a date-time with a time zone offset")
        return None

    def read(self, data: dict[str, JsonValue]) -> ReportClaims:
        """Read the claims of the whole document *data*."""
        document = self._object(data, "document", "$") or {}
        vendors_by_product = self._vendors_by_product(data)
        vulnerabilities: list[VulnerabilityClaims] = []
        affected: list[str] = []
        for path, vul in self._items(data, "vulnerabilities", "$"):
            vulnerabilities.append(self._vulnerability(vul, path))
            affected.extend(self._known_affected(vul, path))
        vendors = [
            vendors_by_product[product]
            for product in affected
            if product in vendors_by_product
        ]
        return ReportClaims(
            document_category=self._text(document, "category", "$.document"),
            name=self._text(document, "title", "$.document"),
            summary=self._summary(document),
            distribution_label=self._distribution_label(document),
            acknowledgments=self._acknowledgments(document),
            involved_parties=self._involved_parties(document),
            references=self._references(document, "$.document"),
            vulnerabilities=vulnerabilities,
            known_affected_vendors=list(dict.fromkeys(vendors)),
        )

    def _summary(self, document: dict[str, JsonValue]) -> str | None:
        """The document-level ``summary`` note, else its ``description`` note."""
        notes: dict[str, str] = {}
        for path, note in self._items(document, "notes", "$.document"):
            category = note.get("category")
            if category not in _SUMMARY_NOTE_CATEGORIES or category in notes:
                continue
            text = self._text(note, "text", path)
            if text is not None:
                notes[category] = text
        return next(
            (notes[c] for c in _SUMMARY_NOTE_CATEGORIES if c in notes), None
        )

    def _distribution_label(
        self, document: dict[str, JsonValue]
    ) -> str | None:
        """The TLP label the document is shared under."""
        distribution = (
            self._object(document, "distribution", "$.document") or {}
        )
        tlp = self._object(distribution, "tlp", "$.document.distribution")
        if tlp is None:
            return None
        return self._text(tlp, "label", "$.document.distribution.tlp")

    def _acknowledgments(
        self, document: dict[str, JsonValue]
    ) -> list[ClaimedAcknowledgment]:
        found: list[ClaimedAcknowledgment] = []
        for here, item in self._items(
            document, "acknowledgments", "$.document"
        ):
            names = self._text_list(item, "names", here)
            organization = self._text(item, "organization", here)
            summary = self._text(item, "summary", here)
            if not (names or organization or summary):
                self._skip(here, "an acknowledgment that names no one")
                continue
            found.append(
                ClaimedAcknowledgment(
                    names=names, organization=organization, summary=summary
                )
            )
        return found

    def _involved_parties(self, document: dict[str, JsonValue]) -> list[str]:
        """The names of the entities the document's involvement lists."""
        involvement = self._object(document, "involvement", "$.document")
        if involvement is None:
            return []
        names = [
            name
            for here, entity in self._items(
                involvement, "entities", "$.document.involvement"
            )
            if (name := self._text(entity, "name", here)) is not None
        ]
        return list(dict.fromkeys(names))

    def _text_list(
        self, container: dict[str, JsonValue], key: str, path: str
    ) -> list[str]:
        """The readable strings of the list at *key*; skip it if any is not."""
        if key not in container:
            return []
        value = container[key]
        here = f"{path}.{key}"
        if not isinstance(value, list):
            self._skip(here, "not a list")
            return []
        readable = [v for v in value if isinstance(v, str) and v.strip()]
        if len(readable) != len(value):
            self._skip(here, "holds an entry that is not a non-empty string")
        return readable

    def _references(
        self, container: dict[str, JsonValue], path: str
    ) -> list[ClaimedReference]:
        references: list[ClaimedReference] = []
        for here, item in self._items(container, "references", path):
            url = self._text(item, "url", here)
            if url is None:
                if "url" not in item:
                    self._skip(here, "a reference without a url")
                continue
            references.append(
                ClaimedReference(
                    url=url,
                    summary=self._text(item, "summary", here),
                    category=self._text(item, "category", here),
                )
            )
        return references

    def _vulnerability(
        self, vul: dict[str, JsonValue], path: str
    ) -> VulnerabilityClaims:
        ids = [cve] if (cve := self._text(vul, "cve", path)) else []
        for here, item in self._items(vul, "ids", path):
            if (text := self._text(item, "text", here)) is not None:
                ids.append(text)
        dates = [
            date
            for here, item in self._items(
                vul, "first_known_exploitation_dates", path
            )
            if (date := self._date(item, "exploitation_date", here))
            is not None
        ]
        return VulnerabilityClaims(
            ids=list(dict.fromkeys(ids)),
            title=self._text(vul, "title", path),
            disclosure_date=self._date(vul, "disclosure_date", path),
            exploitation=self._exploitation(vul, path),
            first_known_exploitation_dates=dates,
            references=self._references(vul, path),
        )

    def _exploitation(
        self, vul: dict[str, JsonValue], path: str
    ) -> str | None:
        """The one SSVC Exploitation value the vulnerability's metrics state.

        Read from each metric's ``content.ssvc_v2`` selection list, the
        selection whose namespace is ``ssvc`` and whose key is ``E``.  The
        value key is copied as written.  Metrics that state more than one
        value say no single thing, so the field is skipped.
        """
        keys: list[str] = []
        for here, metric in self._items(vul, "metrics", path):
            content = self._object(metric, "content", here) or {}
            ssvc = self._object(content, "ssvc_v2", f"{here}.content") or {}
            ssvc_path = f"{here}.content.ssvc_v2"
            for sel_path, selection in self._items(
                ssvc, "selections", ssvc_path
            ):
                if (
                    selection.get("namespace") != _SSVC_NAMESPACE
                    or selection.get("key") != _SSVC_EXPLOITATION_KEY
                ):
                    continue
                for val_path, value in self._items(
                    selection, "values", sel_path
                ):
                    if (key := self._text(value, "key", val_path)) is not None:
                        keys.append(key)
        distinct = list(dict.fromkeys(keys))
        if len(distinct) > 1:
            self._skip(
                f"{path}.metrics",
                f"states several SSVC Exploitation values {distinct}",
            )
            return None
        return distinct[0] if distinct else None

    def _known_affected(
        self, vul: dict[str, JsonValue], path: str
    ) -> list[str]:
        status = self._object(vul, "product_status", path) or {}
        return self._text_list(
            status, "known_affected", f"{path}.product_status"
        )

    def _vendors_by_product(
        self, data: dict[str, JsonValue]
    ) -> dict[str, str]:
        """Map each product id to the vendor branch nearest above it."""
        tree = self._object(data, "product_tree", "$") or {}
        found: dict[str, str] = {}
        self._walk_branches(tree, "$.product_tree", found)
        return found

    def _walk_branches(
        self,
        tree: dict[str, JsonValue],
        path: str,
        found: dict[str, str],
    ) -> None:
        """Walk the branch tree depth first, with a stack, not recursion.

        A sender controls the depth, and nesting ``json.loads`` accepts can
        exceed the interpreter's recursion limit, so recursion here would
        raise on document content and refuse the report (CSAF-02-006).
        """
        stack: list[Iterator[tuple[str, dict[str, JsonValue], str | None]]]
        stack = [self._children(tree, path, None)]
        while stack:
            child = next(stack[-1], None)
            if child is None:
                stack.pop()
                continue
            here, branch, name = child
            product = self._object(branch, "product", here)
            if product is not None and name is not None:
                product_id = self._text(
                    product, "product_id", f"{here}.product"
                )
                if product_id is not None:
                    found.setdefault(product_id, name)
            stack.append(self._children(branch, here, name))

    def _children(
        self, node: dict[str, JsonValue], path: str, vendor: str | None
    ) -> Iterator[tuple[str, dict[str, JsonValue], str | None]]:
        """Yield each branch below *node*, with its path and its vendor."""
        for here, branch in self._items(node, "branches", path):
            name = vendor
            if branch.get("category") == "vendor":
                name = self._text(branch, "name", here) or vendor
            yield here, branch, name


__all__ = [
    "CSAF_21_FORMAT",
    "CSAF_21_SCHEMA",
    "CSAF_21_VERSION",
    "MAX_CSAF_CONTENT_CHARS",
    "content_digest",
    "is_csaf_21",
    "read_csaf_document",
    "read_report_attachments",
]
