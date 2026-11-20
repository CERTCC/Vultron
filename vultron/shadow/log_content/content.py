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

"""What in a case reading is case content, and its tracker references.

:func:`reading_content` lists the strings of a reading that a shadow log
record must not carry (VSD-01-003); :func:`tracker_references` lists the
outside tracker references a record names instead.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from vultron.core.models.case_reading import CaseReading
from vultron.core.models.case_reference import CVE_REFERENCE_TAG_RELS

#: The ``rel`` of an outside tracker reference.
ISSUE_TRACKING_REL = CVE_REFERENCE_TAG_RELS["issue-tracking"]

#: Payload keys whose string values are vocabulary, types or times: never
#: case content.  An ``id`` key, or one that ends in ``Id``, holds an id.
#: Every other string in a payload is content, unless it is an IRI, so a key
#: an outside reader adds is withheld until it is listed here.
_VOCABULARY_KEYS = frozenset(
    {
        "@context",
        "id",
        "state",
        "status",
        "type",
        "published",
        "updated",
        "startTime",
        "endTime",
        "deleted",
        "mediaType",
        "rel",
        "semanticType",
        "emState",
        "pxaState",
        "rmState",
        "vfState",
        "cvdRole",
        "caseRoles",
    }
)

#: An IRI names an object or actor: an identifier, not content.
_IRI = re.compile(r"(?:urn|https?):\S+\Z")

#: Payload keys whose string values are where a link points.  An IRI under
#: one of them is content, not an id: a patch, advisory or exploit URL is a
#: vul detail.  Only an outside tracker reference (:func:`tracker_references`)
#: is named instead.
_LINK_KEYS = frozenset({"href", "url"})

#: A string shorter than this carries no case content worth withholding,
#: and replacing it would cut through every word that holds it.
_SHORTEST_CONTENT = 4


def longest_first(pieces: Iterable[str]) -> tuple[str, ...]:
    """*pieces*, each once, longest first, so a longer string is replaced
    before a shorter one it holds."""
    return tuple(sorted(set(pieces), key=lambda piece: (-len(piece), piece)))


def _names_no_content(key: str | None) -> bool:
    """Whether a string under payload key *key* is never case content."""
    return key is not None and (key in _VOCABULARY_KEYS or key.endswith("Id"))


def _payload_strings(
    value: object, key: str | None, found: set[str], links: set[str]
) -> None:
    """Add each content string in *value*, found under *key*, to *found*,
    and each link target to *links*."""
    if isinstance(value, Mapping):
        for name, item in value.items():
            _payload_strings(item, str(name), found, links)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _payload_strings(item, key, found, links)
    elif isinstance(value, str) and key in _LINK_KEYS:
        links.add(value.strip())
    elif isinstance(value, str) and not _names_no_content(key):
        found.add(value)


def _rels(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _references_in(value: object, found: list[str]) -> None:
    """Append the href of each tracker reference in *value* to *found*."""
    if isinstance(value, Mapping):
        url = value.get("url")
        if value.get("type") == "CaseReference" and isinstance(url, Mapping):
            href = url.get("href")
            if (
                isinstance(href, str)
                and href
                and ISSUE_TRACKING_REL in _rels(url.get("rel"))
                and href not in found
            ):
                found.append(href)
        for item in value.values():
            _references_in(item, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _references_in(item, found)


def tracker_references(reading: CaseReading) -> tuple[str, ...]:
    """The outside tracker references *reading*'s ledger holds, in order.

    Each is the ``href`` of an ``issue-tracking`` ``CaseReference``, such as
    a VINCE case URL.
    """
    found: list[str] = []
    for entry in reading.ledger:
        _references_in(entry.payload_snapshot, found)
    return tuple(found)


def _identifiers(reading: CaseReading) -> set[str]:
    ids: set[str] = set(tracker_references(reading))
    for entry in reading.ledger:
        ids.update((entry.context, entry.id_, entry.log_object_id))
    for citation in reading.citations:
        ids.update((citation.entry_id, citation.source_record))
    for inference in reading.inferences:
        ids.update((inference.entry_id, inference.rule_id))
    ids.update(fact.source_record for fact in reading.untranslated)
    return ids


def reading_content(reading: CaseReading) -> tuple[str, ...]:
    """The strings of *reading* that are case content, longest first.

    Content is every string in an entry's payload except vocabulary, times
    and IRIs, every link target except a tracker reference, every
    untranslated fact (which names its field and value) and every inference
    caveat.  The reading's ids are not content.  Each line of a multi-line
    string is content too, so a traceback line that quotes one line of a
    description still loses it.
    """
    found: set[str] = set()
    links: set[str] = set()
    for entry in reading.ledger:
        _payload_strings(entry.payload_snapshot, None, found, links)
    found.update(fact.fact for fact in reading.untranslated)
    found.update(inference.caveat for inference in reading.inferences)
    pieces: set[str] = set()
    for text in found:
        pieces.add(text.strip())
        pieces.update(line.strip() for line in text.splitlines())
    # The ids hold the tracker references, so neither is withheld.
    ids = _identifiers(reading)
    return longest_first(
        [
            piece
            for piece in pieces
            if len(piece) >= _SHORTEST_CONTENT
            and piece not in ids
            and not _IRI.match(piece)
        ]
        + [
            link
            for link in links
            if len(link) >= _SHORTEST_CONTENT and link not in ids
        ]
    )


__all__ = [
    "ISSUE_TRACKING_REL",
    "longest_first",
    "reading_content",
    "tracker_references",
]
