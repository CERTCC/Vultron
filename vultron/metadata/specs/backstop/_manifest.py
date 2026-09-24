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
"""Spec manifest parsing and resolution (SR-12-006)."""

from __future__ import annotations

import re

from vultron.metadata.specs.backstop._model import (
    GroupHit,
    Manifest,
)

_REQ_RE = re.compile(r"^[A-Z]+-\d\d-\d{3}$")
_GROUP_RE = re.compile(r"^[A-Z]+-\d\d$")
#: A free-text reason: an em-dash (or ``--``/`` - ``) through the end of its
#: entry. The entry ends at a ``;`` or at a sentence-ending ``.`` that a fresh
#: ID run follows \u2014 never at a comma, which reason prose uses freely.
_REASON_RE = re.compile(
    r"\s+(?:[\u2014\u2013]|--|-)\s.*?(?=;|\.\s+[A-Z]+-\d\d|$)"
)
#: Entry separators outside a reason: ``;``, ``,``, or ``.`` before an ID run.
_ENTRY_SEP_RE = re.compile(r"[;,]|\.\s+(?=[A-Z]+-\d\d)")
_ID_RUN_RE = re.compile(r"\s*((?:[A-Z]+(?:-\d\d(?:-\d{3})?)?\b\s*)+)")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
_HEADING_RE = re.compile(r"^(Loaded|Considered)\b[^:]*:(.*)$")


def _leading_ids(text: str, topics: set[str]) -> set[str]:
    """IDs at the start of each entry, before any reason text.

    An em-dash opens a free-text reason, which runs to the next ``;`` or
    sentence break. A comma inside a reason is prose, not a separator: without
    that stop, ``BT-01 — irrelevant, CM-02 covers it`` read CM-02 as dismissed
    and let an unresolved MUST group through. Erring the other way only costs a
    false alarm, so the reason swallows anything it cannot rule out.
    """
    ids: set[str] = set()
    for piece in _ENTRY_SEP_RE.split(_REASON_RE.sub(";", text)):
        match = _ID_RUN_RE.match(piece)
        if match is None:
            continue
        ids.update(
            token
            for token in match.group(1).split()
            if token in topics
            or _GROUP_RE.match(token)
            or _REQ_RE.match(token)
        )
    return ids


def _manifest_target(
    manifest: Manifest, line: str, current: set[str] | None
) -> tuple[set[str] | None, str]:
    """Return the ID set *line* feeds and the text to scan for IDs."""
    stripped = _BULLET_RE.sub("", line).replace("*", "").strip()
    heading = _HEADING_RE.match(stripped)
    if heading:
        kind, rest = heading.groups()
        target = manifest.loaded if kind == "Loaded" else manifest.dismissed
        return target, rest
    if stripped.startswith("Spec manifest"):
        return None, ""
    if _BULLET_RE.match(line) or line[:1].isspace() or not stripped:
        return current, _BULLET_RE.sub("", line)
    return None, ""


def parse_manifest(text: str, topics: set[str]) -> Manifest:
    """Extract loaded and dismissed IDs from a Spec manifest block."""
    manifest = Manifest()
    current: set[str] | None = None
    for line in text.splitlines():
        current, rest = _manifest_target(manifest, line, current)
        if current is not None:
            current.update(_leading_ids(rest, topics))
    return manifest


def is_resolved(hit: GroupHit, manifest: Manifest) -> bool:
    """Whether the manifest loads, dismisses, or itemises *hit*."""
    listed = manifest.loaded | manifest.dismissed
    return (
        hit.group in listed
        or hit.topic in manifest.loaded
        or hit.reqs <= listed
    )


def unresolved_groups(
    must: dict[str, GroupHit], manifest: Manifest
) -> list[GroupHit]:
    """MUST-tier groups the manifest does not resolve, sorted by group."""
    return [
        must[g] for g in sorted(must) if not is_resolved(must[g], manifest)
    ]
