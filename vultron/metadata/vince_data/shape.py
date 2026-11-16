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
"""Tell a VINCE API response apart from other JSON, by its keys.

Each VINCE API read the shadow makes answers with objects of one serializer
of VINCE Comm (``vinny/serializers.py`` in ``CERTCC/VINCE``). Every such
object carries that serializer's fields as its keys, so a JSON object whose
keys include a serializer's *signature*, a distinctive subset of its fields,
is VINCE-shaped. The subset, not the whole field list, is matched because a
response may lack fields: the report read drops its contact fields when the
reporter did not agree to share them.

The walk visits every object in a document, not only the top level: a
recorded response pasted into a larger file, or wrapped in a per-case bundle,
is still VINCE data. The ``csaf/`` read has no signature, because a CSAF
document from VINCE has the same keys as any other CSAF document, and the
shadow does not read it (crosswalk § Not read).
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

#: The keys that mark one VINCE serializer's objects, by the read that
#: serves them. Field names are VINCE Comm's own.
SIGNATURES: Mapping[str, frozenset[str]] = {
    # CaseSerializer: cases/ and case/<vuid>/
    "case": frozenset({"vuid", "created", "status", "title", "due_date"}),
    # PostSerializer: case/<vuid>/posts/
    "post": frozenset({"created", "author", "pinned", "content"}),
    # OrigReportSerializer: case/<vuid>/report/
    "report": frozenset(
        {"vul_description", "vul_public", "vul_exploited", "date_submitted"}
    ),
    # VulSerializer: case/<vuid>/vuls/
    "vul": frozenset({"name", "cve", "description", "date_added"}),
    # VendorSerializer: case/<vuid>/vendors/
    "vendor": frozenset({"vendor", "status", "date_added", "cert_addendum"}),
    # VendorStatusSerializer: case/<vuid>/vendors/vuls/
    "vendor vul status": frozenset(
        {"vulnerability", "vendor", "status", "statement_date"}
    ),
    # VulNoteSerializer: case/<vuid>/note/
    "note": frozenset(
        {"vuid", "datefirstpublished", "dateupdated", "revision"}
    ),
    # VendorInfoSerializer: vendor/
    "vendor info": frozenset({"vendor_name", "emails", "users"}),
}

#: The file suffixes read one JSON document per non-blank line.
LINE_SUFFIXES = (".jsonl", ".ndjson")

#: Every suffix the check reads.
JSON_SUFFIXES = (".json", *LINE_SUFFIXES)


@dataclass(frozen=True)
class ShapeMatch:
    """The first VINCE-shaped object found in a document."""

    kind: str
    where: str

    def describe(self) -> str:
        """``a VINCE <kind> object at <where>``, for a fault message."""
        return f"a VINCE {self.kind} object at {self.where}"


class UnreadableJson(ValueError):
    """A file the check cannot parse, so it cannot rule out VINCE data."""


def _kind_of(obj: Mapping[str, object]) -> str | None:
    keys = obj.keys()
    for kind, signature in SIGNATURES.items():
        if signature <= keys:
            return kind
    return None


def _children(value: object, where: str) -> Iterator[tuple[object, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield child, f"{where}.{key}"
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield child, f"{where}[{index}]"


def find_vince_shape(document: object) -> ShapeMatch | None:
    """The first VINCE-shaped object in *document*, depth first, or ``None``."""
    stack: list[tuple[object, str]] = [(document, "$")]
    while stack:
        value, where = stack.pop()
        if isinstance(value, dict):
            kind = _kind_of(value)
            if kind is not None:
                return ShapeMatch(kind, where)
        stack.extend(reversed(list(_children(value, where))))
    return None


def _strip_jsonc(text: str) -> str:
    """*text* without ``//`` and ``/* */`` comments or trailing commas.

    Comments and commas inside a string are kept. ``tsconfig.json`` files
    are JSON with comments, and still need reading.
    """
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(text[i : i + 2] if ch == "\\" else ch)
            in_string = ch != '"'
            i += 2 if ch == "\\" else 1
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if ch in "]}":
            _drop_trailing_comma(out)
        in_string = ch == '"'
        out.append(ch)
        i += 1
    return "".join(out)


def _drop_trailing_comma(out: list[str]) -> None:
    """Pop the whitespace and the one comma that end *out*, if a comma does."""
    j = len(out)
    while j and out[j - 1].isspace():
        j -= 1
    if j and out[j - 1] == ",":
        del out[j - 1 :]


def read_documents(name: str, text: str) -> list[object]:
    """Parse *text*, the content of the file *name*, into its documents.

    A ``.jsonl`` or ``.ndjson`` file holds one document per non-blank line;
    any other file holds one, read as JSON with comments allowed.

    Raises:
        UnreadableJson: When the text does not parse.
    """
    if name.endswith(LINE_SUFFIXES):
        documents = []
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                documents.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise UnreadableJson(f"line {number}: {exc}") from exc
        return documents
    try:
        return [json.loads(text)]
    except json.JSONDecodeError:
        pass
    try:
        return [json.loads(_strip_jsonc(text))]
    except json.JSONDecodeError as exc:
        raise UnreadableJson(str(exc)) from exc


__all__ = [
    "JSON_SUFFIXES",
    "SIGNATURES",
    "ShapeMatch",
    "UnreadableJson",
    "find_vince_shape",
    "read_documents",
]
