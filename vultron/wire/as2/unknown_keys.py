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
import types
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from types import MappingProxyType
from typing import (
    Any,
    Literal,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
)

from pydantic import AliasChoices, AliasPath, BaseModel

from vultron.core.models._helpers import strip_annotated
from vultron.core.models.actor import CoreActor
from vultron.wire.as2.errors import (
    VultronParseUnknownTypeError,
    VultronParseValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.registry import (
    AmbiguousWireTypeError,
    resolve_wire_type,
    resolved_wire_type_name,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseReference,
    is_case_reference_shape,
)

logger = logging.getLogger(__name__)

#: How a report names the root of an activity body.
ENVELOPE = "the envelope"

#: The JSON-LD context key every object may carry (MV-11-001).  It is the only
#: JSON-LD keyword that is a declared spelling: ``@id`` and ``@type`` are near
#: misses of ``id`` and ``type`` by design, because AS2 compacts them away (AS2
#: Core section 2.1), so they MUST NOT be declared or exempted (MV-11-007).
CONTEXT_KEY = "@context"

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


@dataclass(frozen=True)
class _Spellings:
    """The declared spellings of one or more classes, indexed two ways."""

    #: Every declared spelling, mapped to the fields' annotations it can fill.
    annotations: Mapping[str, tuple[object, ...]]
    #: Normalised spelling → the declared spelling a refusal names.
    by_normalised: Mapping[str, str]


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


def normalise(key: str) -> str:
    """Lowercase *key* and remove every non-alphanumeric character (MV-11-002)."""
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _alias_keys(alias: object) -> list[str]:
    """Return the top-level keys a validation alias reads."""
    if isinstance(alias, str):
        return [alias]
    if isinstance(alias, AliasPath):
        first = alias.path[0] if alias.path else None
        return [first] if isinstance(first, str) else []
    if isinstance(alias, AliasChoices):
        return [key for choice in alias.choices for key in _alias_keys(choice)]
    return []


@cache
def _class_spellings(cls: type[BaseModel]) -> _Spellings:
    """Enumerate every key *cls* accepts on input (MV-11-001).

    A declared spelling is a field name (both roots validate by name, CS-14-001
    and CS-14-002), the alias the class generates or declares for it, any
    explicit validation alias, a computed field's spellings (its value is
    checked against the derived one rather than refused, ARCH-23-005), and
    ``@context``.  A refusal names the alias ahead of the field name, because
    the alias is the AS2 spelling a sender reads.
    """
    by_name = bool(
        cls.model_config.get("validate_by_name")
        or cls.model_config.get("populate_by_name")
    )
    annotations: dict[str, tuple[object, ...]] = {CONTEXT_KEY: ()}
    preferred: list[str] = []
    fallback: list[str] = []
    for name, info in cls.model_fields.items():
        aliases = _alias_keys(info.validation_alias) + _alias_keys(info.alias)
        spellings = aliases + ([name] if by_name or not aliases else [])
        for spelling in spellings:
            annotations[spelling] = (info.annotation,)
        preferred.extend(aliases)
        fallback.append(name)
    generator = cls.model_config.get("alias_generator")
    for name, computed in cls.model_computed_fields.items():
        alias = getattr(computed, "alias", None)
        spellings = [name]
        if isinstance(alias, str):
            spellings.insert(0, alias)
        elif callable(generator):
            spellings.insert(0, generator(name))
        for spelling in spellings:
            annotations.setdefault(spelling, ())
        preferred.append(spellings[0])
    by_normalised: dict[str, str] = {}
    for spelling in [*preferred, *fallback, CONTEXT_KEY]:
        by_normalised.setdefault(normalise(spelling), spelling)
    return _Spellings(
        annotations=MappingProxyType(annotations),
        by_normalised=MappingProxyType(by_normalised),
    )


def _merged_spellings(classes: tuple[type[BaseModel], ...]) -> _Spellings:
    """Merge the spellings of several candidate classes (an untyped dict)."""
    if len(classes) == 1:
        return _class_spellings(classes[0])
    annotations: dict[str, tuple[object, ...]] = {}
    by_normalised: dict[str, str] = {}
    for cls in classes:
        spellings = _class_spellings(cls)
        for key, found in spellings.annotations.items():
            annotations[key] = annotations.get(key, ()) + found
        for norm, spelling in spellings.by_normalised.items():
            by_normalised.setdefault(norm, spelling)
    return _Spellings(annotations=annotations, by_normalised=by_normalised)


def _model_candidates(
    annotation: object,
) -> tuple[type[BaseModel], ...] | None:
    """Return the model classes a field annotation validates a dict into.

    Looks through ``Annotated``, unions, ``Optional`` and sequence containers.
    Returns ``None`` when the annotation also admits a plain dict or ``Any``:
    then no class decides what a key means, so the dict is carried unexamined.
    """
    found: list[type[BaseModel]] = []

    def visit(ann: object) -> bool:
        ann = strip_annotated(ann)
        if isinstance(ann, TypeAliasType):
            return visit(ann.__value__)
        if ann is Any:
            return False
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            found.append(ann)
            return True
        origin = get_origin(ann)
        if origin is Union or isinstance(ann, types.UnionType):
            return all(visit(arg) for arg in get_args(ann))
        if origin in (dict, Mapping) or ann is dict:
            return False
        if origin in (list, set, frozenset, tuple, Sequence):
            return all(visit(arg) for arg in get_args(ann) if arg is not ...)
        return True

    if not visit(annotation):
        return None
    return tuple(dict.fromkeys(found))


def _candidates_for(
    annotations: tuple[object, ...],
) -> tuple[type[BaseModel], ...]:
    """Union the model candidates of every annotation a key can fill."""
    found: list[type[BaseModel]] = []
    for annotation in annotations:
        candidates = _model_candidates(annotation)
        if candidates is None:
            return ()
        found.extend(candidates)
    return tuple(dict.fromkeys(found))


def resolve_inline_class(
    value: dict[str, Any], path: str = ""
) -> type[BaseModel] | None:
    """Return the most specific *wire* class for an inline dict's ``type``.

    Returns ``None`` when the dict's ``type`` names no known type, which
    leaves the dict for its parent field to validate (MV-04-004).  The lookup
    is the shared resolver's wire-only default (VM-06-008, ISSUE-3217), so a
    ``type`` list resolves to its most specific known class (ADR-0196).
    Shared by this partition, which calls it on the raw dict, and the
    parser's expansion, which calls it on the partitioned one; both calls
    answer the same class.

    A list that names two unrelated known types names no class to leave the
    dict to either, so it refuses the activity as an unknown type at any
    depth, as it does at the top (ADR-0196).  *path* locates it.

    The ``type`` decides the class, a case stub included: a stub names
    itself ``VulnerabilityCaseStub`` (CM-11-013).  The one exception is a
    ``VulnerabilityCase`` that carries only its ``id`` and ``type``: that is
    the typed reference a participant's act on a case names it by
    (:class:`as_VulnerabilityCaseReference`, AKM-03-004), and a dict with any
    other key is a case.  The partition, on the raw dict, therefore decides a
    foreign key against the case's fields and sets it aside; the expansion,
    on the partitioned dict, then sees the reference that remains.  A key the
    case declares keeps the dict a case in both calls.
    """
    if is_case_reference_shape(value):
        return as_VulnerabilityCaseReference
    try:
        return resolve_wire_type(value.get("type"))
    except AmbiguousWireTypeError as exc:
        where = f" at {path!r}" if path else ""
        raise VultronParseUnknownTypeError(
            f"Unrecognized inline object type{where}: {exc.args[0]}."
        ) from exc
    except KeyError:
        return None


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
) -> object:
    if isinstance(value, list):
        return [
            _partition_value(item, candidates, f"{path}[{index}]", walk)
            for index, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        return value
    resolved = resolve_inline_class(value, path)
    declared = _declared_for_type(value, candidates, resolved)
    fallback = (resolved,) if resolved is not None else candidates
    classes = declared or fallback
    return _partition_object(value, classes, path, walk)


def _type_literal_values(cls: type[BaseModel]) -> tuple[object, ...]:
    """The values a class's ``type_`` ``Literal`` admits, or ``()``."""
    field = cls.model_fields.get("type_")
    if field is None:
        return ()
    annotation = strip_annotated(field.annotation)
    if get_origin(annotation) is not Literal:
        return ()
    return get_args(annotation)


def _declared_for_type(
    value: dict[str, Any],
    candidates: tuple[type[BaseModel], ...],
    resolved: type[BaseModel] | None,
) -> tuple[type[BaseModel], ...]:
    """The slot's declared classes that name *value*'s ``type``, when the wire
    class its ``type`` resolves to is another class.

    A slot may declare its own model for a shared AS2 type: a case
    reference's ``url`` is a ``CaseReferenceLink``, while ``type: Link``
    resolves to the wire ``as_Link``.  The class that validates the slot then
    decides its keys, so a Link property the reference does not hold is set
    aside and reported here, not read by a class that never keeps it.  A
    resolved subclass of a declared class keeps its own, wider, fields.
    """
    obj_type = resolved_wire_type_name(value.get("type"))
    if resolved is None or obj_type is None:
        return ()
    matches = tuple(
        cls for cls in candidates if obj_type in _type_literal_values(cls)
    )
    if any(issubclass(resolved, cls) for cls in matches):
        return ()
    return matches


def _partition_object(
    value: dict[str, Any],
    classes: tuple[type[BaseModel], ...],
    path: str,
    walk: _Walk,
) -> dict[str, Any]:
    if not classes:
        # No class decides this dict's keys (a ``dict[str, Any]`` slot, or an
        # unresolved type in an untyped slot), so nothing validates them away
        # either; typed dicts inside it are still partitioned by their type.
        return {
            key: (
                item
                if key in _UNEXAMINED_KEYS
                else _partition_value(item, (), _join(path, key), walk)
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
