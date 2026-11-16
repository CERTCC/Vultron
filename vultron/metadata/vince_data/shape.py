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
is still VINCE data, and so is a string value that itself parses as a JSON
object or array: a recording tool (a HAR file, a cassette) keeps each
response body as such a string, and a HAR ``content`` object may hold it
base64-encoded beside ``"encoding": "base64"``, which is decoded first.
The ``csaf/`` read has no signature, because a CSAF document from VINCE
has the same keys as any other CSAF document, and the shadow does not read
it (crosswalk § Not read).

A signature is all or nothing: an object missing one of its signature's
keys is not recognised. The signatures name only keys every response of
their serializer carries.
"""

from __future__ import annotations

import base64
import binascii
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

#: Every suffix the check reads, matched without regard to case. ``.har``
#: is an HTTP archive, the usual shape of a recorded response; ``.json5``
#: is read as JSON with comments, and refused when it uses more of JSON5.
JSON_SUFFIXES = (".json", ".jsonc", ".json5", ".har", *LINE_SUFFIXES)


def is_json_path(path: str) -> bool:
    """Whether the check reads the file at *path*, by its suffix."""
    return path.lower().endswith(JSON_SUFFIXES)


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


def _embedded(text: str) -> object | None:
    """The JSON object or array a string value holds, or ``None``."""
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        inner: object = json.loads(stripped)
    except json.JSONDecodeError, RecursionError:
        return None
    return inner


def _base64_text(obj: Mapping[str, object]) -> str | None:
    """The text a HAR ``content`` object holds base64-encoded, or ``None``.

    A body that does not decode to UTF-8 text holds no JSON, so it is
    ``None`` too.
    """
    text = obj.get("text")
    if obj.get("encoding") != "base64" or not isinstance(text, str):
        return None
    try:
        return base64.b64decode(text, validate=True).decode("utf-8")
    except binascii.Error, UnicodeDecodeError:
        return None


def _children(value: object, where: str) -> Iterator[tuple[object, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield child, f"{where}.{key}"
        decoded = _base64_text(value)
        inner = None if decoded is None else _embedded(decoded)
        if inner is not None:
            yield inner, f"{where}.text<base64>"
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield child, f"{where}[{index}]"
    elif isinstance(value, str):
        inner = _embedded(value)
        if inner is not None:
            yield inner, f"{where}<json>"


def walk_objects(document: object) -> Iterator[tuple[dict[str, object], str]]:
    """Every JSON object in *document*, depth first, with its location.

    String values that parse as a JSON object or array are walked too.
    """
    stack: list[tuple[object, str]] = [(document, "$")]
    while stack:
        value, where = stack.pop()
        if isinstance(value, dict):
            yield value, where
        stack.extend(reversed(list(_children(value, where))))


def shape_kind(obj: Mapping[str, object]) -> str | None:
    """The VINCE serializer kind *obj* has the keys of, or ``None``."""
    return _kind_of(obj)


def find_vince_shape(document: object) -> ShapeMatch | None:
    """The first VINCE-shaped object in *document*, depth first, or ``None``."""
    for obj, where in walk_objects(document):
        kind = _kind_of(obj)
        if kind is not None:
            return ShapeMatch(kind, where)
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


def _loads(text: str) -> object:
    try:
        return json.loads(text)
    except RecursionError as exc:
        raise UnreadableJson("nested too deeply to read") from exc


def read_documents(name: str, text: str) -> list[object]:
    """Parse *text*, the content of the file *name*, into its documents.

    A ``.jsonl`` or ``.ndjson`` file holds one document per non-blank line,
    split on ``\\n`` alone, since JSON strings may hold other line
    separators; any other file holds one, read as JSON with comments allowed.

    Raises:
        UnreadableJson: When the text does not parse.
    """
    if name.lower().endswith(LINE_SUFFIXES):
        documents = []
        for number, line in enumerate(text.split("\n"), start=1):
            if not line.strip():
                continue
            try:
                documents.append(_loads(line))
            except json.JSONDecodeError as exc:
                raise UnreadableJson(f"line {number}: {exc}") from exc
        return documents
    try:
        return [_loads(text)]
    except json.JSONDecodeError:
        pass
    try:
        return [_loads(_strip_jsonc(text))]
    except json.JSONDecodeError as exc:
        raise UnreadableJson(str(exc)) from exc


__all__ = [
    "JSON_SUFFIXES",
    "is_json_path",
    "shape_kind",
    "walk_objects",
    "SIGNATURES",
    "ShapeMatch",
    "UnreadableJson",
    "find_vince_shape",
    "read_documents",
]
