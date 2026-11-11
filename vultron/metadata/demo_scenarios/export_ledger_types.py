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

"""Export the case-ledger line types to TypeScript for ``ui/``.

The Log Replay demo reads the case ledger the CASE_MANAGER writes.  It must
not keep its own copy of what a ledger entry or a participant status holds:
a hand-written copy kept ``vfdState`` long after ADR-0075 split it into
``vfState`` and ``dState``, so replay lost every VFD state (#4729).  The core
models are the single source.  This module projects five of them onto
``ui/src/data/ledgerTypes.ts``:

- :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry` — one
  ledger line.  The CASE_MANAGER writes it, so the line must carry every
  field the model always writes, and no key the model does not declare
  (``extra="forbid"``, ARCH-12-003).
- :class:`~vultron.core.models.participant_status.ParticipantStatus` and
  :class:`~vultron.core.models.case_status.CaseStatus` — the statuses inside
  an entry's ``payloadSnapshot``.  The snapshot is the body as received
  (CLP-02-003, VM-08-002), so these follow the parse edge instead: a field is
  required only where the model refuses its absence, and an undeclared key
  was set aside on receipt (MV-11-003), so it is not a fault.
- :class:`~vultron.core.models.case_participant.CaseParticipant`, with the
  :class:`~vultron.core.models.embargo_consent.EmbargoConsent` rows it
  holds: a participant record in a payload, read the same way.  Its
  ``caseRoles`` label the participant's Log Replay lane.

The file holds two views of one projection, so they cannot disagree:

- a TypeScript ``interface`` per model, and a union type per enum field, for
  the type checker;
- ``LEDGER_SHAPES``, the same field list as data, which the UI's line
  validator checks every loaded line against at run time.

Why a ``.ts`` file and not JSON: a JSON import is typed by its contents'
widened shape (``string``, not ``"vf" | "Vf" | "VF"``), so a hand-written
interface would still be needed and would need its own check against the
list.  Generating the interfaces removes that second copy.

A field's wire key is its serialization alias; enum values are what the
model's own serializers write, read by dumping a probe instance, so a
dimension's bare state name (ARCH-25-005) and ``cvdRole``'s role names come
out as they appear on the wire.  A field annotation the projection does not
know raises, so a model change that needs a new kind fails the export
instead of being typed loosely.

The output is deterministic, so ``--check`` (the ``demo-ledger-types-sync``
pre-commit hook) and the drift test
``test/metadata/demo_scenarios/test_export_ledger_types.py`` fail when the
committed file differs from a fresh export.

Usage::

    uv run export-demo-ledger-types           # write the file
    uv run export-demo-ledger-types --check   # exit 1 if it is stale
"""

import argparse
import json
import re
import types
import typing
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import annotated_types
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from vultron.core.models.base import CoreObject
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    DIMENSION_STATE_FIELD,
    is_dimension_model,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.metadata.demo_scenarios.export_states import REPO_ROOT
from vultron.metadata.generated_files import read_committed, write_generated
from vultron.primitives import NonEmptyString

#: Where the artifact lives, beside the other generated ``ui/`` artifacts.
OUTPUT_PATH = REPO_ROOT / "ui" / "src" / "data" / "ledgerTypes.ts"

#: The command that regenerates the artifact, quoted in every hint.
REGEN_COMMAND = "uv run export-demo-ledger-types"

#: The one key the AS2 serializer writes for an excluded field: the JSON-LD
#: context (``CoreObject._serialize_with_jsonld_context``).
JSONLD_CONTEXT_KEY = "@context"

Role = Literal["written", "received"]

#: A TypeScript identifier, which needs no quotes as a property name.
_IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*")


@dataclass(frozen=True)
class LedgerType:
    """One exported model and how a ledger line carries it.

    ``written``: the CASE_MANAGER writes the object itself, so every field
    the model always writes is required and an undeclared key is a fault.
    ``received``: the object sits in a payload kept as received, so only the
    fields the model refuses to go without are required, and an undeclared
    key is tolerated, as the parse edge sets it aside (MV-11-003).
    """

    model: type[CoreObject]
    role: Role


#: The exported models, in output order.  ``CaseParticipant`` carries the
#: ``caseRoles`` the Log Replay lanes are labelled by (#4729 AC-5), and
#: ``EmbargoConsent`` is the row type it holds.
LEDGER_TYPES: tuple[LedgerType, ...] = (
    LedgerType(CaseLedgerEntry, "written"),
    LedgerType(ParticipantStatus, "received"),
    LedgerType(CaseStatus, "received"),
    LedgerType(CaseParticipant, "received"),
    LedgerType(EmbargoConsent, "received"),
)

#: Maps a value at one annotation position to the JSON the model writes for it.
Probe = Callable[[object], Any]


@dataclass(frozen=True)
class EnumType:
    """A named set of wire values, emitted as a ``const`` and a union type."""

    name: str
    values: tuple[str, ...]

    @property
    def const_name(self) -> str:
        """``VfState`` → ``VF_STATE_VALUES``."""
        snake = "".join(
            f"_{ch}" if ch.isupper() and i else ch
            for i, ch in enumerate(self.name)
        )
        return f"{snake.upper()}_VALUES"


@dataclass(frozen=True)
class FieldDef:
    """One field of an exported model, in wire terms."""

    key: str
    shape: dict[str, Any]
    required: bool
    nullable: bool


class _Projector:
    """Projects annotations onto shapes, collecting the enums they name."""

    def __init__(self, exported: Sequence[type[BaseModel]]) -> None:
        self._exported = {model: model.__name__ for model in exported}
        self.enums: dict[str, EnumType] = {}

    def field_shape(
        self, annotation: object, enum_name: str, probe: Probe
    ) -> tuple[dict[str, Any], bool]:
        """Return the shape of *annotation* and whether it admits ``None``."""
        args = typing.get_args(annotation)
        if _is_union(annotation):
            rest = [arg for arg in args if arg is not type(None)]
            nullable = len(rest) < len(args)
            if len(rest) == 1:
                return self.shape(rest[0], enum_name, probe), nullable
            union = [self.shape(arg, enum_name, probe) for arg in rest]
            return {"kind": "union", "of": union}, nullable
        return self.shape(annotation, enum_name, probe), False

    def shape(
        self, annotation: object, enum_name: str, probe: Probe
    ) -> dict[str, Any]:
        """Return the shape of a non-optional *annotation*."""
        scalar = _scalar_shape(annotation)
        if scalar is not None:
            return scalar
        origin = typing.get_origin(annotation)
        args = typing.get_args(annotation)
        if origin is typing.Annotated:
            shape = self.shape(args[0], enum_name, probe)
            return _constrained(shape, _metadata(args[1:]), annotation)
        if origin is Literal and len(args) == 1 and isinstance(args[0], str):
            return {"kind": "literal", "value": args[0]}
        if origin is dict and _is_json_object(args):
            return {"kind": "object"}
        if origin is list and len(args) == 1:
            item_probe: Probe = lambda value: probe([value])[0]  # noqa: E731
            return {
                "kind": "array",
                "items": self.shape(args[0], enum_name, item_probe),
            }
        if _is_union(annotation):
            shape, nullable = self.field_shape(annotation, enum_name, probe)
            if nullable:
                # Only a field carries `nullable`; a nested `X | None` would
                # be projected as non-null and refuse what the model admits.
                raise TypeError(
                    f"No ledger shape for nested optional {annotation!r} "
                    f"(enum name {enum_name!r}). Teach export_ledger_types.py "
                    "a nullable shape rather than dropping the None."
                )
            return shape
        return self._class_shape(annotation, enum_name, probe)

    def _class_shape(
        self, annotation: object, enum_name: str, probe: Probe
    ) -> dict[str, Any]:
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            return self._enum(enum_name, [probe(m) for m in annotation])
        # An exported model is a reference.  ``is_dimension_model`` admits
        # only bare-state dimensions, so ``EmbargoConsent`` (a ``state``
        # field, but an object on the wire) is not one either way; checking
        # the export first keeps an exported model a reference regardless.
        if annotation in self._exported:
            return {"kind": "ref", "type": self._exported[annotation]}  # type: ignore[index]
        if is_dimension_model(annotation):
            dimension = typing.cast(type[BaseModel], annotation)
            states = dimension.model_fields[DIMENSION_STATE_FIELD].annotation
            if isinstance(states, type) and issubclass(states, Enum):
                return self._enum(
                    enum_name,
                    [
                        probe(dimension(**{DIMENSION_STATE_FIELD: m}))
                        for m in states
                    ],
                )
        raise TypeError(
            f"No ledger shape for annotation {annotation!r} (enum name "
            f"{enum_name!r}). Teach export_ledger_types.py the kind it "
            "needs rather than typing it loosely."
        )

    def _enum(self, name: str, values: list[Any]) -> dict[str, Any]:
        if not all(isinstance(value, str) for value in values):
            raise TypeError(
                f"{name}: enum wire values {values!r} are not strings"
            )
        enum = EnumType(name, tuple(values))
        known = self.enums.setdefault(name, enum)
        if known != enum:
            raise ValueError(
                f"Two fields named {name} carry different values: "
                f"{known.values} and {enum.values}"
            )
        return {"kind": "enum", "type": name}


def _metadata(items: Sequence[object]) -> list[object]:
    """Flatten ``Annotated`` metadata; a ``Field(...)`` carries its own list."""
    flat: list[object] = []
    for item in items:
        if isinstance(item, FieldInfo):
            flat.extend(item.metadata)
        else:
            flat.append(item)
    return flat


def _constrained(
    shape: dict[str, Any], metadata: Sequence[object], annotation: object
) -> dict[str, Any]:
    """Add each known constraint in *metadata* to *shape*; refuse the rest.

    A constraint the projection cannot carry would leave the UI accepting a
    value the model refuses, so it fails the export instead.
    """
    shape = dict(shape)
    for item in metadata:
        bound = _integer_bound(item) if shape["kind"] == "integer" else None
        if bound is not None:
            shape[bound[0]] = bound[1]
        elif (
            isinstance(item, annotated_types.MinLen)
            and shape["kind"] == "array"
        ):
            shape["minItems"] = item.min_length
        else:
            raise TypeError(
                f"No ledger shape for constraint {item!r} on {annotation!r}. "
                "Teach export_ledger_types.py to carry it rather than "
                "dropping it."
            )
    return shape


def _integer_bound(item: object) -> tuple[str, int] | None:
    """``("minimum" | "maximum", n)`` for an integer bound, else ``None``."""
    if isinstance(item, annotated_types.Ge) and isinstance(item.ge, int):
        return "minimum", item.ge
    if isinstance(item, annotated_types.Gt) and isinstance(item.gt, int):
        return "minimum", item.gt + 1
    if isinstance(item, annotated_types.Le) and isinstance(item.le, int):
        return "maximum", item.le
    if isinstance(item, annotated_types.Lt) and isinstance(item.lt, int):
        return "maximum", item.lt - 1
    return None


def _is_json_object(args: tuple[object, ...]) -> bool:
    """Whether ``dict[*args]`` is an untyped JSON object: string keys, any values.

    A mapping with typed values says more than ``Record<string, unknown>``,
    so it is not projected as one.
    """
    return (
        len(args) == 2 and args[0] in (str, NonEmptyString) and args[1] is Any
    )


def _is_union(annotation: object) -> bool:
    origin = typing.get_origin(annotation)
    return origin is typing.Union or isinstance(annotation, types.UnionType)


def _scalar_shape(annotation: object) -> dict[str, Any] | None:
    """The shape of a JSON scalar annotation, or ``None`` if it is not one."""
    if annotation == NonEmptyString:
        return {"kind": "string", "nonEmpty": True}
    simple: dict[object, dict[str, Any]] = {
        str: {"kind": "string", "nonEmpty": False},
        bool: {"kind": "boolean"},
        int: {"kind": "integer"},
        datetime: {"kind": "datetime"},
        timedelta: {"kind": "duration"},
        Any: {"kind": "any"},
    }
    for known, shape in simple.items():
        if annotation is known:
            return dict(shape)
    return None


def wire_fields(model: type[BaseModel]) -> Iterator[tuple[str, FieldInfo]]:
    """Yield ``(name, field)`` for each field *model* writes on the AS2 path.

    An excluded field is never written, except the JSON-LD context, which the
    AS2 serializer adds itself.  A computed field would also be written, and
    none of the exported models has one; the export refuses one rather than
    silently leaving it out.
    """
    if model.model_computed_fields:
        raise TypeError(
            f"{model.__name__} has computed fields "
            f"{sorted(model.model_computed_fields)}; export_ledger_types.py "
            "does not project computed fields yet."
        )
    for name, field in model.model_fields.items():
        if field.exclude and field.serialization_alias != JSONLD_CONTEXT_KEY:
            continue
        yield name, field


def _full_annotation(field: FieldInfo) -> object:
    """The field's annotation with the metadata pydantic lifted off it.

    Pydantic moves a top-level ``Annotated`` field's metadata to
    ``FieldInfo.metadata``, so ``NonEmptyString`` reads back as bare ``str``
    unless the metadata is put back.
    """
    if not field.metadata:
        return field.annotation
    return typing.Annotated[(field.annotation, *field.metadata)]  # type: ignore[valid-type]


def _wire_key(name: str, field: FieldInfo) -> str:
    return field.serialization_alias or field.alias or name


def _field_probe(model: type[BaseModel], name: str, key: str) -> Probe:
    """Return a probe that dumps *value* as *model*'s field *name* writes it."""

    def probe(value: object) -> Any:
        values: dict[str, Any] = {name: value}
        instance = model.model_construct(None, **values)
        dumped = instance.model_dump(
            mode="json", by_alias=True, include={name}
        )
        return dumped[key]

    return probe


#: The author times a received object may omit (ADR-0103, ADR-0176).
_AUTHOR_TIMES = frozenset({"published", "updated", "startTime", "start_time"})


def _is_required(
    ledger_type: LedgerType, key: str, field: FieldInfo, nullable: bool
) -> bool:
    """Whether a line must carry the field, by the model's role (LedgerType)."""
    if ledger_type.role == "written":
        return field.is_required() or not nullable
    if key in _AUTHOR_TIMES:
        # An author time is required where an object is built (ADR-0176), but
        # a received omission reads as ``None`` (ADR-0103): only a class that
        # reads its sender's time refuses it (CLP-15-010).
        return (
            key == "published"
            and ledger_type.model._inbound_requires_published
        )
    return field.is_required()


def _enum_name(model: type[BaseModel], key: str) -> str:
    """The TypeScript name of the enum a field of *model* under *key* holds.

    The capitalized wire key (``vfState`` → ``VfState``), which names the
    machine.  A bare ``state`` names no machine, so it takes the model's name
    (``EmbargoConsent.state`` → ``EmbargoConsentState``).
    """
    if key == DIMENSION_STATE_FIELD:
        return f"{model.__name__}State"
    return key[:1].upper() + key[1:]


def project(
    ledger_types: Sequence[LedgerType] = LEDGER_TYPES,
) -> tuple[dict[str, list[FieldDef]], dict[str, EnumType]]:
    """Project *ledger_types* onto field lists, keyed by model name."""
    projector = _Projector([lt.model for lt in ledger_types])
    shapes: dict[str, list[FieldDef]] = {}
    for ledger_type in ledger_types:
        model = ledger_type.model
        fields: list[FieldDef] = []
        for name, field in wire_fields(model):
            key = _wire_key(name, field)
            enum_name = _enum_name(model, key)
            shape, nullable = projector.field_shape(
                _full_annotation(field),
                enum_name,
                _field_probe(model, name, key),
            )
            required = _is_required(ledger_type, key, field, nullable)
            fields.append(FieldDef(key, shape, required, nullable))
        shapes[model.__name__] = fields
    return shapes, projector.enums


# ---------------------------------------------------------------------------
# TypeScript rendering
# ---------------------------------------------------------------------------

_PREAMBLE = """\
// Generated by `{command}`
// (vultron/metadata/demo_scenarios/export_ledger_types.py) from the Python
// models {models}.
// Do not edit by hand; re-run the exporter and commit the result instead.
//
// The interfaces type a ledger line for the compiler; LEDGER_SHAPES holds the
// same fields as data, for the line validator in src/utils/ledgerShape.ts.

/** The name of each exported model. */
export type LedgerTypeName = {type_names}

/** The kind of value one field holds. */
export type FieldShape =
  | {{ readonly kind: 'string'; readonly nonEmpty: boolean }}
  | {{ readonly kind: 'datetime' }}
  | {{ readonly kind: 'duration' }}
  | {{ readonly kind: 'integer'; readonly minimum?: number; readonly maximum?: number }}
  | {{ readonly kind: 'boolean' }}
  | {{ readonly kind: 'any' }}
  | {{ readonly kind: 'object' }}
  | {{ readonly kind: 'literal'; readonly value: string }}
  | {{ readonly kind: 'enum'; readonly type: string; readonly values: readonly string[] }}
  | {{ readonly kind: 'array'; readonly items: FieldShape; readonly minItems?: number }}
  | {{ readonly kind: 'ref'; readonly type: LedgerTypeName }}
  | {{ readonly kind: 'union'; readonly of: readonly FieldShape[] }}

/** One field: its wire key, its shape, and whether it may be absent or null. */
export interface FieldDefinition {{
  readonly key: string
  readonly shape: FieldShape
  readonly required: boolean
  readonly nullable: boolean
}}

/**
 * One model. `closed` means a key the model does not declare is a fault
 * (the CASE_MANAGER wrote the object); otherwise it was set aside on receipt.
 */
export interface LedgerTypeDefinition {{
  readonly closed: boolean
  readonly fields: readonly FieldDefinition[]
}}
"""


def _ts(value: object) -> str:
    """A TypeScript literal for a JSON value (JSON is valid TypeScript)."""
    return json.dumps(value, ensure_ascii=False)


def _ts_key(key: str) -> str:
    """A property name, quoted only when it is not an identifier."""
    return key if _IDENTIFIER.fullmatch(key) else _ts(key)


def _ts_type(shape: dict[str, Any]) -> str:
    kind = shape["kind"]
    named = {
        "string": "string",
        "datetime": "string",
        "duration": "string",
        "integer": "number",
        "boolean": "boolean",
        "any": "unknown",
        "object": "Record<string, unknown>",
    }
    if kind in named:
        return named[kind]
    if kind == "literal":
        return _ts(shape["value"])
    if kind in ("enum", "ref"):
        return str(shape["type"])
    if kind == "array":
        item = _ts_type(shape["items"])
        return f"Array<{item}>"
    if kind == "union":
        return " | ".join(_ts_type(member) for member in shape["of"])
    raise ValueError(f"unknown shape kind {kind!r}")


def _ts_shape(shape: dict[str, Any], enums: dict[str, EnumType]) -> str:
    """Render *shape* as a literal, pointing each enum at its values const."""
    kind = shape["kind"]
    if kind == "enum":
        enum = enums[shape["type"]]
        return (
            f"{{ kind: {_ts(kind)}, type: {_ts(enum.name)}, "
            f"values: {enum.const_name} }}"
        )
    if kind == "array":
        items = _ts_shape(shape["items"], enums)
        rest = "".join(
            f", {key}: {_ts(value)}"
            for key, value in shape.items()
            if key not in ("kind", "items")
        )
        return f"{{ kind: {_ts(kind)}, items: {items}{rest} }}"
    if kind == "union":
        members = ", ".join(_ts_shape(m, enums) for m in shape["of"])
        return f"{{ kind: {_ts(kind)}, of: [{members}] }}"
    rest = "".join(
        f", {key}: {_ts(value)}"
        for key, value in shape.items()
        if key != "kind"
    )
    return f"{{ kind: {_ts(kind)}{rest} }}"


def _render_enum(enum: EnumType) -> str:
    values = ", ".join(_ts(value) for value in enum.values)
    return (
        f"export const {enum.const_name} = [{values}] as const\n"
        f"export type {enum.name} = (typeof {enum.const_name})[number]\n"
    )


def _render_interface(name: str, fields: Sequence[FieldDef]) -> str:
    lines = [f"export interface {name} {{"]
    for field in fields:
        optional = "" if field.required else "?"
        ts_type = _ts_type(field.shape)
        if field.nullable:
            ts_type = f"{ts_type} | null"
        lines.append(f"  {_ts_key(field.key)}{optional}: {ts_type}")
    lines.append("}\n")
    return "\n".join(lines)


def _render_shapes(
    ledger_types: Sequence[LedgerType],
    shapes: dict[str, list[FieldDef]],
    enums: dict[str, EnumType],
) -> str:
    lines = ["export const LEDGER_SHAPES = {"]
    for ledger_type in ledger_types:
        name = ledger_type.model.__name__
        closed = _ts(ledger_type.role == "written")
        lines.append(f"  {name}: {{")
        lines.append(f"    closed: {closed},")
        lines.append("    fields: [")
        for field in shapes[name]:
            lines.append(
                f"      {{ key: {_ts(field.key)}, "
                f"required: {_ts(field.required)}, "
                f"nullable: {_ts(field.nullable)}, "
                f"shape: {_ts_shape(field.shape, enums)} }},"
            )
        lines.append("    ],")
        lines.append("  },")
    lines.append(
        "} as const satisfies Record<LedgerTypeName, LedgerTypeDefinition>\n"
    )
    return "\n".join(lines)


def render(ledger_types: Sequence[LedgerType] = LEDGER_TYPES) -> str:
    """Render the full, deterministic ``ledgerTypes.ts`` text."""
    shapes, enums = project(ledger_types)
    names = [lt.model.__name__ for lt in ledger_types]
    preamble = _PREAMBLE.format(
        command=REGEN_COMMAND,
        models=", ".join(names),
        type_names=" | ".join(f"'{name}'" for name in names),
    )
    parts = [preamble]
    parts.extend(_render_enum(enum) for enum in enums.values())
    parts.extend(_render_interface(name, shapes[name]) for name in names)
    parts.append(_render_shapes(ledger_types, shapes, enums))
    return "\n".join(parts)


def stale_hint(path: Path) -> str:
    """Return the message a stale or missing artifact is reported with."""
    shown = path.relative_to(REPO_ROOT).as_posix()
    return (
        f"{shown} is stale: a ledger model changed but the TypeScript types "
        f"were not regenerated. Run `{REGEN_COMMAND}` and commit {shown}."
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run export-demo-ledger-types [--check]``."""
    parser = argparse.ArgumentParser(
        prog="export-demo-ledger-types",
        description="Write ui/src/data/ledgerTypes.ts from the ledger models, "
        "or check that the committed copy is current.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Write nothing; exit 1 if the committed file is stale.",
    )
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        if read_committed(OUTPUT_PATH) != text:
            raise SystemExit(stale_hint(OUTPUT_PATH))
        return
    write_generated(OUTPUT_PATH, text)
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")


__all__ = [
    "LEDGER_TYPES",
    "OUTPUT_PATH",
    "REGEN_COMMAND",
    "EnumType",
    "FieldDef",
    "LedgerType",
    "main",
    "project",
    "render",
    "stale_hint",
    "wire_fields",
]


if __name__ == "__main__":
    main()
