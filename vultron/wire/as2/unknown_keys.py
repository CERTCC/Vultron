"""Inbound unknown-key disposition at the parse edge (MV-11).

``parse_activity`` calls :func:`partition_unknown_keys` on the raw body before
anything validates it, and ``parse_fetched_object`` calls it on a fetched
object's body, which is inbound data too (MV-11-001).  The walk visits every
object at every depth — the envelope, an inline object whose ``type`` resolves
to a wire class or to a core class, an inline ``Link``, and an inline dict with
no ``type`` — and partitions each object's keys against the declared spellings
of the class that will validate it (MV-11-001):

* a **declared** key is kept;
* a **near miss** — the same string as a declared spelling once both are
  lowercased and stripped of every non-alphanumeric character — refuses the
  whole activity, naming the arriving key and the spelling it resembles
  (MV-11-002);
* any **other** key is **set aside**: dropped from the body that is validated
  and returned to the caller to report (MV-11-003).

The disposition never depends on which branch the class belongs to.  A core
class keeps ``extra="forbid"`` (ARCH-12-003, MV-11-004); it simply never sees an
inbound unknown key, because this walk removes them first.

The near-miss test is exactly the normalisation above.  No edit distance or
other similarity measure is used (MV-11-009).  A name the protocol once read
and no longer does is no different from any other unknown key: before 1.0
Vultron supports one protocol version, so no list of retired names is kept
(ADR-0175).
"""

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

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from vultron.core.models.actor import CoreActor
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.inline_class import (
    CONTEXT_KEY,
    _candidates_for,
    _class_spellings,
    _declared_for_type,
    _merged_spellings,
    declared_slot_class,
    inline_class,
    normalise,
    reads_inside_preview,
    resolve_inline_class,
    slot_classes,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)

#: How a report names the root of an activity body.
ENVELOPE = "the envelope"


# Field names whose values are opaque data blobs (declared ``dict[str, Any]``),
# NOT AS2 object references.  These must not be recursively coerced into typed
# vocabulary instances: a ``CaseLedgerEntry.payload_snapshot`` may itself carry
# an ``{"type": "Announce", "object": {...}}`` snapshot dict, and coercing it to
# an ``as_Announce`` model would make ``CaseLedgerEntry`` validation fail
# (payload_snapshot expects a dict), causing the parser to fall back to the base
# ``as_Object`` type and mis-route the entry (SYNC-13-004).  The partition does
# not descend into them either: a snapshot is carried as received.
OPAQUE_PAYLOAD_KEYS = frozenset({"payloadSnapshot", "payload_snapshot"})

#: Keys whose values the partition carries as received: the opaque payloads
#: above, and the JSON-LD context, whose term definitions are not AS2 objects.
_UNEXAMINED_KEYS = OPAQUE_PAYLOAD_KEYS | {CONTEXT_KEY}


@dataclass(frozen=True)
class SetAsideKey:
    """One unknown inbound key removed from the body before validation."""

    path: str
    key: str
    #: How a report names the root object (``path == ""``).
    root: str = ENVELOPE

    @property
    def location(self) -> str:
        """Where the key sat, as named in a report."""
        return location_of(self.path, self.root)


@dataclass
class _Walk:
    """Accumulates the outcome of one partition walk."""

    #: How a report names the root object.
    root: str = ENVELOPE
    set_aside: list[SetAsideKey] = field(default_factory=list)
    near_misses: list[str] = field(default_factory=list)

    def set_aside_key(self, path: str, key: str) -> None:
        """Record *key* at *path* as set aside."""
        self.set_aside.append(SetAsideKey(path=path, key=key, root=self.root))


def location_of(path: str, root: str = ENVELOPE) -> str:
    """Name *path* in a report: quoted, or *root* for the root object."""
    return repr(path) if path else root


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _partition_value(
    value: object,
    candidates: tuple[type[BaseModel], ...],
    path: str,
    walk: _Walk,
    in_preview: bool = False,
) -> object:
    if isinstance(value, list):
        return [
            _partition_value(
                item, candidates, f"{path}[{index}]", walk, in_preview
            )
            for index, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        return value
    if in_preview:
        # The class the parser reads it with (``inline_class``), so one class
        # decides its keys and validates it (ADR-0217).
        shown = inline_class(value, path, candidates, in_preview=True)
        classes = (shown,) if shown is not None else candidates
    else:
        resolved = resolve_inline_class(value, path)
        declared = _declared_for_type(value, candidates, resolved)
        fallback = (resolved,) if resolved is not None else candidates
        classes = declared or fallback
    return _partition_object(value, classes, path, walk, in_preview)


def _partition_object(
    value: dict[str, Any],
    classes: tuple[type[BaseModel], ...],
    path: str,
    walk: _Walk,
    in_preview: bool = False,
) -> dict[str, Any]:
    inner = reads_inside_preview(classes, in_preview)
    if not classes:
        # No class decides this dict's keys (a ``dict[str, Any]`` slot, or an
        # unresolved type in an untyped slot), so nothing validates them away
        # either; typed dicts inside it are still partitioned by their type.
        return {
            key: (
                item
                if key in _UNEXAMINED_KEYS
                else _partition_value(item, (), _join(path, key), walk, inner)
            )
            for key, item in value.items()
        }
    spellings = _merged_spellings(classes)
    kept: dict[str, Any] = {}
    location = location_of(path, walk.root)
    embedded_profile = bool(path) and _is_actor_profile(classes)
    for key, item in value.items():
        if embedded_profile and normalise(key) == _PROFILE_KEYS_NORMALISED:
            # An actor profile embedded in a received activity loses its
            # keys: a key is trusted only as fetched from the actor's own
            # profile URL, so no stored copy may carry one (SIG-02-003).
            walk.set_aside_key(path, key)
        elif key in spellings.annotations:
            kept[key] = (
                item
                if key in _UNEXAMINED_KEYS
                else _partition_value(
                    item,
                    _candidates_for(spellings.annotations[key]),
                    _join(path, key),
                    walk,
                    inner,
                )
            )
        elif (
            declared := spellings.by_normalised.get(normalise(key))
        ) is not None:
            walk.near_misses.append(
                f"{key!r} at {location} resembles the declared spelling"
                f" {declared!r}"
            )
        else:
            walk.set_aside_key(path, key)
    return kept


#: ``assertionMethod`` under the near-miss normalisation, which every
#: spelling the actor classes accept (``assertion_method`` too) reduces to.
_PROFILE_KEYS_NORMALISED = "assertionmethod"


def _is_actor_profile(classes: tuple[type[BaseModel], ...]) -> bool:
    """Whether *classes* read an object as an actor profile."""
    return any(issubclass(cls, (CoreActor, as_Actor)) for cls in classes)


def partition_unknown_keys(
    body: dict[str, Any],
    cls: type[BaseModel],
    *,
    subject: str = "Activity",
    root: str = ENVELOPE,
) -> tuple[dict[str, Any], list[SetAsideKey]]:
    """Partition every object's keys in *body*; *cls* validates its root.

    Returns a copy of *body* with every set-aside key removed, and the keys set
    aside, in walk order, for the caller to report (MV-11-003).  *body* itself
    is not modified: it is the received evidence (VM-08-002).

    Args:
        body: The inbound body: a received activity, or a fetched object.
        cls: The class that validates the root of *body*.
        subject: What a refusal names *body* as.
        root: What a report or refusal names the root object as.

    Raises:
        VultronParseValidationError: If any key is a near miss.  Every
            such key in the body is named, not only the first (EH-07-001).
            Also raised, rather than ``RecursionError``, for a body nested
            beyond the interpreter's recursion limit.
    """
    walk = _Walk(root=root)
    try:
        kept = _partition_object(body, (cls,), "", walk)
    except RecursionError as exc:
        # Not a ``VultronParseError``, so left alone it escapes the inbox's
        # handler as a 500.  A body nested this deep is malformed, not an
        # internal fault: refuse it as the schema fault it is (MV-02-002).
        raise VultronParseValidationError(
            f"{subject} nests objects too deeply to parse."
        ) from exc
    if walk.near_misses:
        raise VultronParseValidationError(
            f"{subject} carries misspelled key(s) (MV-11-002): "
            + "; ".join(walk.near_misses)
        )
    return kept, walk.set_aside


def report_set_aside(
    set_aside: list[SetAsideKey], ids: Mapping[str, object]
) -> None:
    """Log one INFO record per set-aside key (MV-11-003, SL-02-001/002).

    INFO, not WARNING: a property this receiver does not read is a normal
    protocol event — usually a peer's extension — not an anomaly (SL-03-001).
    The key survives only in the received body (VM-08-002).

    Args:
        set_aside: The keys :func:`partition_unknown_keys` set aside.
        ids: The identifiers each record carries, such as ``activity_id``
            and ``actor_id`` (SL-02-001), in the order they are logged.
    """
    named = " ".join(f"{name}={value}" for name, value in ids.items())
    for entry in set_aside:
        logger.info(
            "Set aside unknown key %r at %s; it is not read by this receiver"
            " (MV-11-003) [%s]",
            entry.key,
            entry.location,
            named,
        )


#: Names other modules import from here, kept after their move to
#: ``inline_class.py``.
__all__ = [
    "CONTEXT_KEY",
    "ENVELOPE",
    "OPAQUE_PAYLOAD_KEYS",
    "SetAsideKey",
    "_class_spellings",
    "declared_slot_class",
    "inline_class",
    "location_of",
    "normalise",
    "partition_unknown_keys",
    "report_set_aside",
    "resolve_inline_class",
    "slot_classes",
]
