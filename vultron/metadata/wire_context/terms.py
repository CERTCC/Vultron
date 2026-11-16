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
"""Refuse a Vultron wire field with no JSON-LD term (VM-10-007, ADR-0194).

Three rules apply to every field that a wire class, or a model nested in one,
serializes (:func:`~vultron.metadata.wire_context.sync.wire_field_classes`,
:func:`~vultron.metadata.wire_context.sync.serialized_fields`), computed
fields included, unless the field is ``exclude=True``:

- **VM-10-007, no term.** The field is a marked Vultron property, or its wire
  name is a top-level term of a context Vultron cites
  (:data:`CITED_CONTEXTS`), or a type-scoped term of a cited context for a
  field of that type (Multikey's ``controller`` counts only on a
  ``Multikey``).  A JSON-LD keyword (``@context``) needs no term.
- **VM-10-012, two meanings.** Every declaration of one Vultron property's
  wire name carries the same definition and value kind.
- **VM-10-009, an external name.** No Vultron property's wire name is a
  top-level term of a pinned external context, cited or not, so citing a
  pinned context later cannot silently redefine a Vultron term.

Each known violation sits in an owner's ratchet constant in
:data:`RATCHET_PATH` (one ``KNOWN_*`` constant per owning Task, each with
``# owner: #N``, ARCH-18-003).  :func:`check_wire_terms` subtracts them and
reports both what is left and every entry that no longer matches a violation
(ARCH-18-001, ARCH-18-006).  The constants are read from the source by
``ast``, not imported, because ``vultron/`` does not import ``test/``.
``uv run wire-context --check`` and the unit test both call it.

An entry is ``<declaring class>.<wire name>: <rule>``, so it excuses only the
rule it was filed for: a field that moves from one rule to another fails as a
new violation, and its old entry as stale.

Loose readings, and whether each can miss or invent a violation:

- **A class is named by its qualified name, without its module** (misses):
  two classes of one name in two modules share an entry, so one entry could
  excuse both.  No two wire classes share a name today.
- **A model with a plain whole-model serializer is not walked** (misses): its
  fields are not its wire keys, but a custom serializer could still write a
  key the walk never sees.  Fields added by a ``model_serializer`` in
  ``wrap`` mode, or by hand after a dump, are not seen either.
- **An unmarked field whose wire name is another class's Vultron property**
  is reported as having no term (neither): the context gives it the other
  class's meaning, which the message notes, but the fix is the same.
- **The first declaration of a name, in qualified-name order, is the
  reference for VM-10-012** (neither): every later one that disagrees is
  reported, and the first is named in each message.
"""

from __future__ import annotations

import ast
import typing
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from vultron.core.models._helpers.class_annotations import own_annotations
from vultron.core.models.base import (
    VultronPropertyDeclaration,
    declared_vultron_property,
)
from vultron.metadata.base import repo_root
from vultron.metadata.file_loading import MetadataLoadError, read_utf8
from vultron.metadata.ratchet_markers import baselines_in, ratchet_bindings
from vultron.metadata.wire_context.pin import ContextTerms, load_all_terms
from vultron.metadata.wire_context.sync import (
    serialized_fields,
    wire_field_classes,
    wire_name,
)
from vultron.wire.as2.signing import DATA_INTEGRITY_CONTEXT, MULTIKEY_CONTEXT
from vultron.wire.as2.vocab.base.base import ACTIVITY_STREAMS_NS
from vultron.wire.as2.vocab.base.registry import declared_wire_type

#: The external contexts a Vultron message or actor profile cites today: a
#: term counts for VM-10-007 only when one of these defines it.  Each must be
#: a pinned context (``third_party/jsonld/pin.json``).  Controlled
#: Identifiers v1 is pinned but not cited, so the profile's
#: ``assertionMethod`` has no term until #6418 cites it and adds it here.
CITED_CONTEXTS: tuple[str, ...] = (
    ACTIVITY_STREAMS_NS,
    DATA_INTEGRITY_CONTEXT,
    MULTIKEY_CONTEXT,
)

#: Repository-relative path of the module holding the owners' ratchets.
RATCHET_PATH = "test/metadata/wire_term_ratchets.py"


class TermRule(StrEnum):
    """The rule a field breaks, by its requirement ID."""

    NO_TERM = "VM-10-007"
    EXTERNAL_NAME = "VM-10-009"
    TWO_MEANINGS = "VM-10-012"


_RULE_TEXT: dict[TermRule, str] = {
    TermRule.NO_TERM: (
        "no JSON-LD term: mark it a Vultron property with vultron_property(),"
        " or use a term a cited context defines"
    ),
    TermRule.EXTERNAL_NAME: (
        "a Vultron property named like a pinned external context's top-level"
        " term: use the external term, or rename the property"
    ),
    TermRule.TWO_MEANINGS: (
        "two declarations of one Vultron property disagree: share one"
        " definition and value kind, or rename one apart"
    ),
}


@dataclass(frozen=True, order=True)
class TermViolation:
    """One field that breaks one rule.

    ``owner`` is the class that declares the field (the first class in the
    method resolution order whose own annotations name it), so a field
    inherited by many subclasses is one violation.
    """

    owner: str
    wire_name: str
    rule: TermRule
    detail: str = ""

    @property
    def key(self) -> str:
        """The ratchet entry that excuses it: ``<Class>.<wireName>: <rule>``."""
        return f"{self.owner}.{self.wire_name}: {self.rule.value}"

    def message(self) -> str:
        """The failure line: field, class and rule."""
        extra = f" ({self.detail})" if self.detail else ""
        return (
            f"`{self.wire_name}` on {self.owner} breaks {self.rule.value}:"
            f" {_RULE_TEXT[self.rule]}{extra}"
        )


def _declaring_class(cls: type[BaseModel], name: str) -> type:
    """The class in *cls*'s MRO that itself declares field *name*.

    A field is declared by an annotation, a computed field by a property in
    the class body.
    """
    for klass in cls.__mro__:
        if name in own_annotations(klass) or name in vars(klass):
            return klass
    return cls


def _scoping_type(cls: type[BaseModel]) -> str | None:
    """The wire ``type`` that selects *cls*'s type-scoped terms.

    The ``type_`` default when the class declares one, else a ``type_``
    annotated as one ``Literal`` value with no default (``Multikey``).
    """
    if (value := declared_wire_type(cls)) is not None:
        return value
    info = cls.model_fields.get("type_")
    if info is None:
        return None
    annotation = info.annotation
    if typing.get_origin(annotation) is Literal:
        args = typing.get_args(annotation)
        if len(args) == 1 and isinstance(args[0], str):
            return args[0]
    return None


@dataclass(frozen=True)
class _Terms:
    """The external terms each rule reads."""

    cited_top_level: frozenset[str]
    cited_type_scoped: Mapping[str, frozenset[str]]
    pinned_top_level: frozenset[str]

    @classmethod
    def of(
        cls, pinned: Mapping[str, ContextTerms], cited: Sequence[str]
    ) -> _Terms:
        if missing := [url for url in cited if url not in pinned]:
            raise ValueError(
                f"cited contexts {missing} have no pinned copy; pin them in"
                " third_party/jsonld/pin.json (VM-10-011)"
            )
        scoped: dict[str, frozenset[str]] = {}
        for url in cited:
            for scope, terms in pinned[url].type_scoped.items():
                scoped[scope] = scoped.get(scope, frozenset()) | terms
        return cls(
            cited_top_level=frozenset().union(
                *(pinned[url].top_level for url in cited)
            ),
            cited_type_scoped=scoped,
            pinned_top_level=frozenset().union(
                *(terms.top_level for terms in pinned.values())
            ),
        )


def term_violations(
    classes: Iterable[type[BaseModel]],
    pinned: Mapping[str, ContextTerms],
    cited: Sequence[str] = CITED_CONTEXTS,
) -> list[TermViolation]:
    """Every field of *classes* that breaks VM-10-007, VM-10-009 or VM-10-012.

    *pinned* maps each pinned context's URL to its terms
    (:func:`~vultron.metadata.wire_context.pin.load_all_terms`); *cited* names
    the ones a Vultron message or profile cites.  Sorted, without duplicates.
    """
    terms = _Terms.of(pinned, cited)
    found: set[TermViolation] = set()
    unmarked: list[tuple[str, str]] = []
    declared: dict[str, tuple[VultronPropertyDeclaration, str]] = {}
    for cls in sorted(
        classes, key=lambda c: f"{c.__module__}.{c.__qualname__}"
    ):
        scope = _scoping_type(cls)
        scoped = (
            terms.cited_type_scoped.get(scope, frozenset())
            if scope
            else frozenset()
        )
        for name, info in serialized_fields(cls):
            wire = wire_name(name, info)
            owner = _declaring_class(cls, name).__qualname__
            declaration = declared_vultron_property(info)
            if declaration is None:
                if not (
                    wire.startswith("@")
                    or wire in terms.cited_top_level
                    or wire in scoped
                ):
                    unmarked.append((owner, wire))
                continue
            if wire in terms.pinned_top_level:
                found.add(TermViolation(owner, wire, TermRule.EXTERNAL_NAME))
            first, first_owner = declared.setdefault(
                wire, (declaration, owner)
            )
            if first != declaration:
                found.add(
                    TermViolation(
                        owner,
                        wire,
                        TermRule.TWO_MEANINGS,
                        f"{first_owner} declares {first.as_json()},"
                        f" {owner} declares {declaration.as_json()}",
                    )
                )
    for owner, wire in unmarked:
        detail = (
            f"the context gives it {declared[wire][1]}'s meaning"
            if wire in declared
            else ""
        )
        found.add(TermViolation(owner, wire, TermRule.NO_TERM, detail))
    return sorted(found)


def wire_term_violations() -> list[TermViolation]:
    """Every violation in the wire vocabulary, against the pinned contexts."""
    return term_violations(wire_field_classes(), load_all_terms())


@dataclass(frozen=True)
class Ratchet:
    """One owner's ratchet constant: its name, owners and entries."""

    name: str
    owners: tuple[int, ...]
    entries: frozenset[str]

    @property
    def cites(self) -> str:
        return ", ".join(f"#{n}" for n in self.owners) or "no owner"


def _entries(name: str, value: ast.expr, line: int) -> frozenset[str]:
    """The strings of a ``frozenset({...})`` or ``frozenset()`` literal."""
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "frozenset"
        and not value.keywords
        and len(value.args) <= 1
    ):
        if not value.args:
            return frozenset()
        try:
            literal = ast.literal_eval(value.args[0])
        except ValueError:
            literal = None
        if isinstance(literal, (set, tuple, list)) and all(
            isinstance(item, str) for item in literal
        ):
            return frozenset(literal)
    raise MetadataLoadError(
        f"{name} must be a frozenset literal of strings",
        path=RATCHET_PATH,
        line=line,
    )


def load_ratchets(root: Path | None = None) -> list[Ratchet]:
    """Read every ratchet-named constant of :data:`RATCHET_PATH`.

    Uses the marker parser's own walk of module-level bindings
    (:func:`~vultron.metadata.ratchet_markers.ratchet_bindings`), so this
    reads every constant ARCH-18-003 sees.  Raises ``MetadataLoadError`` for
    one this check cannot read exactly: a value that is not a ``frozenset``
    literal of strings, a name bound twice, or one grown in place.
    """
    base = root or repo_root()
    path = base / RATCHET_PATH
    source = read_utf8(path, RATCHET_PATH)
    tree = ast.parse(source, filename=str(path))
    owners = {
        (b.name, b.line): b.owners
        for b in baselines_in(tree, source, Path(RATCHET_PATH))
    }
    ratchets: list[Ratchet] = []
    seen: set[str] = set()
    for binding in ratchet_bindings(tree):
        line = binding.node.lineno
        if binding.mutated or binding.name in seen:
            raise MetadataLoadError(
                f"{binding.name} is bound more than once or grown in place;"
                " bind each ratchet once, to its literal",
                path=RATCHET_PATH,
                line=line,
            )
        seen.add(binding.name)
        ratchets.append(
            Ratchet(
                binding.name,
                owners.get((binding.name, line), ()),
                _entries(binding.name, binding.value, line),
            )
        )
    return ratchets


@dataclass(frozen=True)
class TermCheckReport:
    """What the check found: unexcused violations and stale entries."""

    unexcused: tuple[TermViolation, ...]
    stale: tuple[tuple[Ratchet, str], ...]
    duplicated: tuple[tuple[str, tuple[str, ...]], ...]

    @property
    def ok(self) -> bool:
        return not (self.unexcused or self.stale or self.duplicated)

    def lines(self) -> list[str]:
        """One failure line per problem."""
        out = [v.message() for v in self.unexcused]
        out += [
            f"{ratchet.name} (owner {ratchet.cites}) lists `{entry}`, which"
            f" breaks no rule now; remove the entry (ARCH-18-006)"
            for ratchet, entry in self.stale
        ]
        out += [
            f"`{entry}` sits in more than one ratchet: {', '.join(names)};"
            " one owner each"
            for entry, names in self.duplicated
        ]
        return out


def compare(
    violations: Iterable[TermViolation], ratchets: Iterable[Ratchet]
) -> TermCheckReport:
    """Hold the ratchets equal to *violations* in both directions."""
    found = list(violations)
    keys = {v.key for v in found}
    holders: dict[str, list[str]] = {}
    stale: list[tuple[Ratchet, str]] = []
    for ratchet in ratchets:
        for entry in sorted(ratchet.entries):
            holders.setdefault(entry, []).append(ratchet.name)
            if entry not in keys:
                stale.append((ratchet, entry))
    return TermCheckReport(
        unexcused=tuple(v for v in found if v.key not in holders),
        stale=tuple(stale),
        duplicated=tuple(
            (entry, tuple(names))
            for entry, names in sorted(holders.items())
            if len(names) > 1
        ),
    )


def check_wire_terms(root: Path | None = None) -> TermCheckReport:
    """Check the wire vocabulary against the owners' ratchets."""
    return compare(wire_term_violations(), load_ratchets(root))


__all__ = [
    "CITED_CONTEXTS",
    "RATCHET_PATH",
    "Ratchet",
    "TermCheckReport",
    "TermRule",
    "TermViolation",
    "check_wire_terms",
    "compare",
    "load_ratchets",
    "term_violations",
    "wire_term_violations",
]
