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
"""The sanitizer: one VINCE case in, a synthetic case of the same shape out
(#6348, VSD-02-005 to VSD-02-008, ADR-0189).

The source is a per-case bundle in the fixture form :mod:`.generator`
writes, ``{"reads": {"case": ..., "posts": ..., ...}}``, read from a path
outside the repository checkout. Every field of every read is classified in
:data:`~.sanitizer_fields.READS`, and each class decides what the output holds:

- **kept**: the enumerated values the VINCE API defines (case and vendor
  statuses, the fixed author labels of a post), booleans, counts, ``null``
  and empty strings, and the order of every list;
- **replaced**: free text becomes lorem ipsum with the same number of words;
  names, emails, phones and organizations become generated fakes; the case's
  ``vuid`` becomes the caller's synthetic id, and every other id (``pk``,
  vul names, CVE ids) a synthetic one. Equal source values get equal
  replacements, so ids and names that pointed at one object still do;
- **shifted**: every timestamp moves by one whole number of days, so their
  order and spacing stay and the earliest lands on :data:`ANCHOR_DATE`.

A field the map does not classify is refused with an error naming it
(VSD-02-007): a new API field fails closed. An error names a field by its
place in the bundle, never by its value, and the sanitizer logs only the
synthetic case id and counts (VSD-01-003, VSD-02-006).

Every replacement depends only on what the sanitizer keeps: the order a
value first appears in, a word count, the synthetic case id. So sanitizing
its own output changes nothing, and that is how the check knows the
sanitizer wrote a file (:func:`verify_sanitized`): a fresh sanitization of
the file, for the case id it names, must write it byte for byte. A
hand-made file passes only if it holds nothing the sanitizer would not
write, which leaves no room for case content.

Usage::

    uv run vince-data sanitize /outside/the/checkout/case.json --vuid 998001
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from vultron.metadata.generated_files import serialize_json, write_generated
from vultron.metadata.vince_data.marker import (
    FIXTURE_DIR,
    SANITIZER,
    marker_for,
)
from vultron.metadata.vince_data.sanitizer_fields import (
    CASE_STATUSES,
    ENUMERATED_VALUES,
    INACTIVE_SUFFIX,
    POST_ORG_LABELS,
    READS,
    REMOVED_AUTHOR_EMAIL,
    REMOVED_AUTHOR_NAME,
    VENDOR_STATUSES,
    Leaf,
    ListOf,
    Shape,
)

logger = logging.getLogger(__name__)

#: Where the sanitizer writes a case, relative to the repository root.
SANITIZED_DIR = f"{FIXTURE_DIR}/sanitized"

#: The synthetic case ids the sanitizer writes under, a range apart from
#: the generator's ``9999xx`` that no VINCE case uses.
SANITIZED_VUIDS = range(998000, 999000)

#: The day the earliest timestamp of a sanitized case falls on.
ANCHOR_DATE = date(2090, 1, 1)

#: The source bundle's top-level keys: the reads, and a marker a synthetic
#: source may carry.
_SOURCE_KEYS = frozenset({"reads", "synthetic"})


class SanitizeError(ValueError):
    """A source the sanitizer refuses. The message names a place, never a
    value of the source."""


class UnclassifiedField(SanitizeError):
    """A response field the sanitizer does not classify (VSD-02-007)."""

    def __init__(self, where: str) -> None:
        super().__init__(
            f"{where}: a VINCE response field the sanitizer does not "
            "classify, refused so it cannot carry case content through "
            "(VSD-02-007)"
        )
        self.field = where


_LOREM_TEXT = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua enim ad minim "
    "veniam quis nostrud exercitation ullamco laboris nisi aliquip ex ea "
    "commodo consequat duis aute irure in reprehenderit voluptate velit "
    "esse cillum fugiat nulla pariatur excepteur sint occaecat cupidatat "
    "non proident sunt culpa qui officia deserunt mollit anim id est "
    "laborum"
)
_LOREM = tuple(_LOREM_TEXT.split())

_LABELS_TEXT = (
    "Alpha Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo "
    "Lima Mike November Oscar Papa Quebec Romeo Sierra Tango Uniform Victor "
    "Whiskey Xray Yankee Zulu"
)
_LABELS = tuple(_LABELS_TEXT.split())


def _label(n: int) -> str:
    return _LABELS[n] if n < len(_LABELS) else str(n + 1)


def lorem(words: int, ordinal: int) -> str:
    """Lorem ipsum of *words* words, starting where text *ordinal* starts."""
    if words == 0:
        return ""
    start = ordinal * 7
    chosen = [_LOREM[(start + i) % len(_LOREM)] for i in range(words)]
    return " ".join(chosen).capitalize() + "."


#: The fake each replaced class writes for the *n*-th distinct value.
_FAKES: Mapping[Leaf, Callable[[int, str], str]] = {
    Leaf.ORG: lambda n, vuid: f"Example Org {_label(n)}",
    Leaf.NAME: lambda n, vuid: f"Example Person {_label(n)}",
    Leaf.EMAIL: lambda n, vuid: f"person-{n + 1}@example.com",
    Leaf.PHONE: lambda n, vuid: f"+1-555-0199 x{n + 1}",
    Leaf.CVE: lambda n, vuid: f"CVE-2098-{n + 1:04d}",
    Leaf.VUL_NAME: lambda n, vuid: f"VU#{vuid}.{n + 1}",
}

#: The values a replaced class keeps, being the API's own.
_KEPT: Mapping[Leaf, frozenset[str]] = {
    Leaf.NAME: frozenset({REMOVED_AUTHOR_NAME}),
    Leaf.EMAIL: frozenset({REMOVED_AUTHOR_EMAIL}),
}

_STATUSES: Mapping[Leaf, frozenset[str]] = {
    Leaf.CASE_STATUS: CASE_STATUSES,
    Leaf.VENDOR_STATUS: VENDOR_STATUSES,
}

_TIMESTAMP = re.compile(
    r"(\d{4}-\d{2}-\d{2})((?:T[0-9:.]+)?(?:Z|[+-][0-9:]+)?)"
)


def _parse_day(value: str) -> tuple[date, str] | None:
    """The date and the rest of timestamp *value*, or ``None``."""
    match = _TIMESTAMP.fullmatch(value)
    if match is None:
        return None
    try:
        datetime.fromisoformat(value)
        return date.fromisoformat(match.group(1)), match.group(2)
    except ValueError:
        return None


@dataclass
class _Replacements:
    """One sanitization's state: the synthetic id, the day offset, and the
    replacement each distinct value got."""

    vuid: str
    day_offset: int = 0
    ordinals: dict[Leaf, dict[str, int]] = field(default_factory=dict)
    texts: int = 0

    def fake(self, leaf: Leaf, value: str) -> str:
        seen = self.ordinals.setdefault(leaf, {})
        n = seen.setdefault(value, len(seen))
        return _FAKES[leaf](n, self.vuid)

    def text(self, value: str) -> str:
        words = len(value.split())
        if words == 0:
            return ""
        self.texts += 1
        return lorem(words, self.texts - 1)


Visit = Callable[[Leaf, object, str], object]


def _refuse_type(where: str, wanted: str) -> SanitizeError:
    return SanitizeError(f"{where}: expected {wanted}")


def _walk(shape: Shape, value: object, where: str, visit: Visit) -> object:
    if value is None:
        return None
    if isinstance(shape, Leaf):
        return visit(shape, value, where)
    if isinstance(shape, ListOf):
        if not isinstance(value, list):
            raise _refuse_type(where, "a list")
        return [
            _walk(shape.item, item, f"{where}[{i}]", visit)
            for i, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        raise _refuse_type(where, "an object")
    for key in value:
        if key not in shape.fields:
            raise UnclassifiedField(f"{where}.{key}")
    return {
        key: _walk(child, value[key], f"{where}.{key}", visit)
        for key, child in shape.fields.items()
        if key in value
    }


def _walk_reads(reads: object, visit: Visit) -> dict[str, object]:
    if not isinstance(reads, dict):
        raise _refuse_type("reads", "an object")
    for key in reads:
        if key not in READS:
            raise UnclassifiedField(f"reads.{key}")
    missing = [key for key in READS if key not in reads]
    if missing:
        raise SanitizeError(f"reads.{missing[0]}: a per-case read is missing")
    if reads["case"] is None:
        raise SanitizeError("reads.case: the case read is missing")
    return {
        key: _walk(shape, reads[key], f"reads.{key}", visit)
        for key, shape in READS.items()
    }


def _string(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise _refuse_type(where, "a string")
    return value


def _days(leaf: Leaf, value: object, where: str) -> Iterator[date]:
    if leaf is Leaf.TIME:
        parsed = _parse_day(_string(value, where))
        if parsed is None:
            raise _refuse_type(where, "an ISO 8601 timestamp")
        yield parsed[0]


def _timestamp_days(reads: object) -> list[date]:
    days: list[date] = []

    def collect(leaf: Leaf, value: object, where: str) -> object:
        days.extend(_days(leaf, value, where))
        return value

    _walk_reads(reads, collect)
    return days


def _integer(value: object, where: str, wanted: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _refuse_type(where, wanted)
    return value


def _keep_bool(state: _Replacements, value: object, where: str) -> object:
    if not isinstance(value, bool):
        raise _refuse_type(where, "a boolean")
    return value


def _keep_count(state: _Replacements, value: object, where: str) -> object:
    return _integer(value, where, "an integer")


def _new_pk(state: _Replacements, value: object, where: str) -> object:
    _integer(value, where, "an integer id")
    return int(state.vuid) - 990000


def _new_vuid(state: _Replacements, value: object, where: str) -> object:
    if isinstance(value, int) and not isinstance(value, bool):
        return int(state.vuid)
    _string(value, where)
    return state.vuid


def _lorem_list(state: _Replacements, value: object, where: str) -> object:
    if not isinstance(value, list):
        raise _refuse_type(where, "a list of strings")
    return [
        state.text(_string(item, f"{where}[{i}]"))
        for i, item in enumerate(value)
    ]


def _lorem_text(state: _Replacements, value: object, where: str) -> object:
    return state.text(_string(value, where))


def _shift_time(state: _Replacements, value: object, where: str) -> object:
    parsed = _parse_day(_string(value, where))
    if parsed is None:
        raise _refuse_type(where, "an ISO 8601 timestamp")
    day, rest = parsed
    return (day + timedelta(days=state.day_offset)).isoformat() + rest


Handler = Callable[[_Replacements, object, str], object]

#: How each class that is not a name, contact or id is sanitized.
_HANDLERS: Mapping[Leaf, Handler] = {
    Leaf.BOOL: _keep_bool,
    Leaf.COUNT: _keep_count,
    Leaf.PK: _new_pk,
    Leaf.VUID: _new_vuid,
    Leaf.TEXT_LIST: _lorem_list,
    Leaf.TEXT: _lorem_text,
    Leaf.TIME: _shift_time,
}


def _replace(state: _Replacements) -> Visit:
    def visit(leaf: Leaf, value: object, where: str) -> object:
        if leaf in _STATUSES:
            text = _string(value, where)
            if text not in _STATUSES[leaf]:
                raise SanitizeError(
                    f"{where}: not a status the VINCE API defines for this "
                    "field, so it cannot be kept and is not classified for "
                    "replacement"
                )
            return text
        handler = _HANDLERS.get(leaf)
        if handler is not None:
            return handler(state, value, where)
        return _identity(state, leaf, _string(value, where))

    return visit


def _identity(state: _Replacements, leaf: Leaf, text: str) -> str:
    """A name, contact, organization or id: kept when the API defines it,
    empty when empty, a fake otherwise."""
    if not text.strip() or text in _KEPT.get(leaf, frozenset()):
        return text
    if leaf is Leaf.POST_ORG:
        if text in POST_ORG_LABELS:
            return text
        if text.endswith(INACTIVE_SUFFIX):
            org = text.removesuffix(INACTIVE_SUFFIX)
            return state.fake(Leaf.ORG, org) + INACTIVE_SUFFIX
        return state.fake(Leaf.ORG, text)
    return state.fake(leaf, text)


def _check_vuid(vuid: str) -> None:
    if not vuid.isdigit() or int(vuid) not in SANITIZED_VUIDS:
        raise SanitizeError(
            f"case id {vuid}: a sanitized case id must be one of "
            f"{SANITIZED_VUIDS.start} to {SANITIZED_VUIDS.stop - 1}"
        )


def transform(reads: object, vuid: str) -> dict[str, object]:
    """The sanitized form of the per-case *reads*, as case *vuid*.

    Raises:
        SanitizeError: When a read or field is not one the sanitizer
            classifies, or holds a value of the wrong kind.
    """
    _check_vuid(vuid)
    days = _timestamp_days(reads)
    state = _Replacements(vuid)
    if days:
        state.day_offset = (ANCHOR_DATE - min(days)).days
    return _walk_reads(reads, _replace(state))


def render(sanitized: Mapping[str, object]) -> str:
    """The text of the file the sanitizer writes for *sanitized* reads."""
    return serialize_json({**marker_for(SANITIZER), "reads": sanitized})


def sanitized_path(vuid: str) -> str:
    """The repository-relative path the sanitizer writes case *vuid* to."""
    return f"{SANITIZED_DIR}/{vuid}.json"


def _leaves(
    value: object, where: str = "reads"
) -> Iterator[tuple[str, object]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, f"{where}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from _leaves(child, f"{where}[{i}]")
    else:
        yield where, value


def source_values(reads: object) -> frozenset[str | int]:
    """Every value of the source *reads* a sanitized case must not hold.

    Every string but an enumerated or blank one, and every integer a
    ``vuid`` or ``pk`` holds, as a number and as a string.
    """
    found: set[str | int] = set()
    for where, value in _leaves(reads):
        if isinstance(value, str):
            if value.strip() and value not in ENUMERATED_VALUES:
                found.add(value)
            if where.endswith((".vuid", ".pk")) and value.isdigit():
                found.add(int(value))
        elif (
            isinstance(value, int)
            and not isinstance(value, bool)
            and where.endswith((".vuid", ".pk"))
        ):
            found |= {value, str(value)}
    return frozenset(found)


def _assert_no_source_value(source: object, sanitized: object) -> None:
    """Refuse an output holding a source value, whatever its field."""
    forbidden = source_values(source)
    for where, value in _leaves(sanitized):
        if isinstance(value, bool) or where.endswith(".revision"):
            continue
        if isinstance(value, (str, int)) and value in forbidden:
            raise SanitizeError(
                f"{where}: the sanitized value repeats a value of the source "
                "case, so it is not written; choose another --vuid if it is "
                "an id (VSD-02-006, VSD-02-008)"
            )


def sanitize(source: object, vuid: str) -> str:
    """The text of the synthetic case the source bundle *source* becomes.

    Raises:
        SanitizeError: When the source is not a bundle the sanitizer
            classifies whole, or the result would repeat a source value.
    """
    if not isinstance(source, dict):
        raise _refuse_type("the source", "a per-case bundle object")
    for key in source:
        if key not in _SOURCE_KEYS:
            raise UnclassifiedField(str(key))
    if "reads" not in source:
        raise SanitizeError("reads: the source bundle has no reads")
    reads = source["reads"]
    sanitized = transform(reads, vuid)
    _assert_no_source_value(reads, sanitized)
    for key, read in sanitized.items():
        count = len(read) if isinstance(read, list) else int(read is not None)
        logger.debug(
            "Sanitized read %s of case %s: %d items", key, vuid, count
        )
    logger.info("Sanitized a VINCE case into synthetic case %s", vuid)
    return render(sanitized)


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def sanitize_file(source: Path, root: Path, vuid: str) -> str:
    """Sanitize the bundle at *source* into the fixture directory of the
    checkout at *root*; return the repository-relative path written.

    Raises:
        SanitizeError: When *source* lies inside the checkout, where a
            source case must never be put (#6348 AC-4), when it cannot be
            read as JSON, or when :func:`sanitize` refuses it.
    """
    if _inside(source, root):
        raise SanitizeError(
            "the source case lies inside the repository checkout; keep it "
            "outside, so it cannot be committed (ADR-0189)"
        )
    # The refusal is raised outside the ``except``, so the decode error,
    # whose ``doc`` holds the whole source, is not chained to it.
    document: object = None
    reason: str | None = None
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        reason = type(exc).__name__
    if reason is not None:
        raise SanitizeError(
            f"the source case cannot be read as JSON ({reason})"
        )
    text = sanitize(document, vuid)
    path = sanitized_path(vuid)
    write_generated(root / path, text)
    return path


def verify_sanitized(path: str, text: str) -> str | None:
    """``None`` when the sanitizer writes exactly *text* to *path*.

    The sanitizer's :data:`~.marker.ProducerVerifier`. A sanitization of
    the sanitizer's own output, as the case id it names, writes it again
    byte for byte; a file that does not survive that, or sits where the
    sanitizer would not write its case, was not written by the sanitizer
    or was edited since (VSD-02-005).
    """
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return "does not parse as the sanitizer's JSON"
    reads = document.get("reads") if isinstance(document, dict) else None
    case = reads.get("case") if isinstance(reads, dict) else None
    vuid = case.get("vuid") if isinstance(case, dict) else None
    if not isinstance(vuid, str):
        return "names no case id the sanitizer writes, in reads.case.vuid"
    try:
        expected = render(transform(reads, vuid))
    except SanitizeError as exc:
        return f"the sanitizer refuses it: {exc}"
    if path != sanitized_path(vuid):
        return (
            f"the sanitizer writes case {vuid} only to {sanitized_path(vuid)}"
        )
    if expected != text:
        return (
            "differs from what the sanitizer writes for it, so the sanitizer "
            "did not write it, or it was edited since"
        )
    return None


__all__ = [
    "ANCHOR_DATE",
    "CASE_STATUSES",
    "ENUMERATED_VALUES",
    "READS",
    "SANITIZED_DIR",
    "SANITIZED_VUIDS",
    "SanitizeError",
    "UnclassifiedField",
    "VENDOR_STATUSES",
    "lorem",
    "render",
    "sanitize",
    "sanitize_file",
    "sanitized_path",
    "source_values",
    "transform",
    "verify_sanitized",
]
