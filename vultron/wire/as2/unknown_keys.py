"""Inbound unknown-key disposition at the parse edge (MV-11).

``parse_activity`` calls :func:`partition_unknown_keys` on the raw body before
anything validates it.  The walk visits every object at every depth — the
envelope, an inline object whose ``type`` resolves to a wire class or to a core
class, an inline ``Link``, and an inline dict with no ``type`` — and partitions
each object's keys against the declared spellings of the class that will
validate it (MV-11-001):

* a **declared** key is kept;
* a **near miss** — the same string as a declared spelling once both are
  lowercased and stripped of every non-alphanumeric character — or a
  **retired** name refuses the whole activity, naming the arriving key and the
  spelling it resembles (MV-11-002);
* any **other** key is **set aside**: dropped from the body that is validated
  and returned to the caller to report (MV-11-003).

The disposition never depends on which branch the class belongs to.  A core
class keeps ``extra="forbid"`` (ARCH-12-003, MV-11-004); it simply never sees an
inbound unknown key, because this walk removes them first.

The near-miss test is exactly the normalisation above plus :data:`RETIRED_NAMES`.
No edit distance or other similarity measure is used (MV-11-002).
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

import types
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from types import MappingProxyType
from typing import Any, TypeAliasType, Union, get_args, get_origin

from pydantic import AliasChoices, AliasPath, BaseModel

from vultron.core.models._helpers import strip_annotated
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseStub,
)

#: The JSON-LD context key every object may carry (MV-11-001).
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

_VFD_RETIRED = (
    "vfd_state/vfdState is retired (ADR-0075); use vf_state for vendor"
    " participants and d_state for deployer participants instead"
)

#: Names the protocol once read and no longer does, mapped to the replacement
#: a sender should use (MV-11-002, MV-11-004).  Matched by name, not by
#: normalisation, and consulted only here: core types carry no per-class
#: retired-key guard (SDO-03-005) — ``extra="forbid"`` refuses these on
#: in-process and stored data.
RETIRED_NAMES: Mapping[str, str] = MappingProxyType(
    {"vfd_state": _VFD_RETIRED, "vfdState": _VFD_RETIRED}
)


@dataclass(frozen=True)
class SetAsideKey:
    """One unknown inbound key removed from the body before validation."""

    path: str
    key: str

    @property
    def location(self) -> str:
        """Where the key sat, as named in a report."""
        return location_of(self.path)


@dataclass(frozen=True)
class _Spellings:
    """The declared spellings of one or more classes, indexed two ways."""

    #: Every declared spelling, mapped to the fields' annotations it can fill.
    annotations: Mapping[str, tuple[Any, ...]]
    #: Normalised spelling → the declared spelling a refusal names.
    by_normalised: Mapping[str, str]


@dataclass
class _Walk:
    """Accumulates the outcome of one partition walk."""

    set_aside: list[SetAsideKey] = field(default_factory=list)
    near_misses: list[str] = field(default_factory=list)


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
    annotations: dict[str, tuple[Any, ...]] = {CONTEXT_KEY: ()}
    preferred: list[str] = []
    fallback: list[str] = []
    for name, info in cls.model_fields.items():
        aliases = _alias_keys(info.validation_alias) + _alias_keys(info.alias)
        spellings = aliases + ([name] if by_name or not aliases else [])
        for spelling in spellings:
            annotations[spelling] = (info.annotation,)
        preferred.extend(aliases)
        fallback.append(name)
    for name, computed in cls.model_computed_fields.items():
        alias = getattr(computed, "alias", None)
        generator = cls.model_config.get("alias_generator")
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
    annotations: dict[str, tuple[Any, ...]] = {}
    by_normalised: dict[str, str] = {}
    for cls in classes:
        spellings = _class_spellings(cls)
        for key, found in spellings.annotations.items():
            annotations[key] = annotations.get(key, ()) + found
        for norm, spelling in spellings.by_normalised.items():
            by_normalised.setdefault(norm, spelling)
    return _Spellings(annotations=annotations, by_normalised=by_normalised)


def _model_candidates(annotation: Any) -> tuple[type[BaseModel], ...] | None:
    """Return the model classes a field annotation validates a dict into.

    Looks through ``Annotated``, unions, ``Optional`` and sequence containers.
    Returns ``None`` when the annotation also admits a plain dict or ``Any``:
    then no class decides what a key means, so the dict is carried unexamined.
    """
    found: list[type[BaseModel]] = []

    def visit(ann: Any) -> bool:
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
        if origin in (list, set, frozenset, tuple):
            return all(visit(arg) for arg in get_args(ann) if arg is not ...)
        return True

    if not visit(annotation):
        return None
    return tuple(dict.fromkeys(found))


def _candidates_for(
    annotations: tuple[Any, ...],
) -> tuple[type[BaseModel], ...]:
    """Union the model candidates of every annotation a key can fill."""
    found: list[type[BaseModel]] = []
    for annotation in annotations:
        candidates = _model_candidates(annotation)
        if candidates is None:
            return ()
        found.extend(candidates)
    return tuple(dict.fromkeys(found))


_CASE_TYPE = "VulnerabilityCase"

#: The keys of a minimal case reference (MV-10-001).  An inline case carrying
#: no other key is the stub, not a full case missing its fields.
_CASE_STUB_KEYS = frozenset({CONTEXT_KEY, "id", "type", "summary"})


def _reads_as_case_stub(value: dict[str, Any]) -> bool:
    """Whether an inline ``VulnerabilityCase`` dict is the stub (MV-10-001).

    Either it carries nothing beyond a minimal reference, or it carries a key
    only the stub declares — the ``caseStatus`` an embargoed Invite's stub adds
    for informed consent (CM-17-002).  Resolving that one to the full case
    judged ``caseStatus`` against a class that has no such field.
    """
    keys = value.keys()
    if keys <= _CASE_STUB_KEYS:
        return True
    stub = _class_spellings(as_VulnerabilityCaseStub).annotations.keys()
    case = _class_spellings(find_in_vocabulary(_CASE_TYPE)).annotations.keys()
    return not keys.isdisjoint(stub - case)


def resolve_inline_class(value: dict[str, Any]) -> type[BaseModel] | None:
    """Return the most specific *wire* class for an inline dict's ``type``.

    Returns ``None`` when the dict names no string ``type`` or the wire
    registry holds no class for it, which leaves the dict for its parent field
    to validate (MV-04-003).  The lookup is ``find_in_vocabulary``'s wire-only
    default (VM-06-008, ISSUE-3217).  Shared by this partition and the parser's
    expansion, so both judge an inline object as the same class.
    """
    obj_type = value.get("type")
    if not isinstance(obj_type, str):
        return None
    if obj_type == _CASE_TYPE and _reads_as_case_stub(value):
        return as_VulnerabilityCaseStub
    try:
        return find_in_vocabulary(obj_type)
    except KeyError:
        return None


def location_of(path: str) -> str:
    """Name *path* in a report: quoted, or ``the envelope`` for the root."""
    return repr(path) if path else "the envelope"


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
    resolved = resolve_inline_class(value)
    classes = (resolved,) if resolved is not None else candidates
    return _partition_object(value, classes, path, walk)


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
    location = location_of(path)
    for key, item in value.items():
        if key in spellings.annotations:
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
        elif key in RETIRED_NAMES:
            walk.near_misses.append(
                f"{key!r} at {location}: {RETIRED_NAMES[key]}"
            )
        elif (
            declared := spellings.by_normalised.get(normalise(key))
        ) is not None:
            walk.near_misses.append(
                f"{key!r} at {location} resembles the declared spelling"
                f" {declared!r}"
            )
        else:
            walk.set_aside.append(SetAsideKey(path=path, key=key))
    return kept


def partition_unknown_keys(
    body: dict[str, Any], cls: type[BaseModel]
) -> tuple[dict[str, Any], list[SetAsideKey]]:
    """Partition every object's keys in *body*; *cls* validates the envelope.

    Returns a copy of *body* with every set-aside key removed, and the keys set
    aside, in walk order, for the caller to report (MV-11-003).  *body* itself
    is not modified: it is the received evidence (VM-08-002).

    Raises:
        VultronParseValidationError: If any key is a near miss or a retired
            name.  Every such key in the body is named, not only the first
            (EH-07-001).
    """
    walk = _Walk()
    kept = _partition_object(body, (cls,), "", walk)
    if walk.near_misses:
        raise VultronParseValidationError(
            "Activity carries misspelled or retired key(s) (MV-11-002): "
            + "; ".join(walk.near_misses)
        )
    return kept, walk.set_aside
