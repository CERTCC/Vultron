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
"""The pinned schemas of one side, and how references and paths resolve in them.

Annotations are dropped on read (:func:`strip_annotations`), so two sides that
differ only in a description compare equal. A ``$ref`` the pin does not map is
reported as a problem of that side, never raised on read.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.csaf.pin import PINNED_COPY_DIR, CsafPin
from vultron.metadata.csaf.regenerate import resolve_relative_ref, schema_refs

#: The upstream paths the pin maps from upstream. Every other pinned file (the
#: JSON Schema 2020-12 meta-schemas) is frozen and read from the pinned copy.
WATCHED_SCHEMA_DIRS = (
    "csaf_2.1/json_schema/",
    "csaf_2.1/referenced_schema/",
)


#: Schema keywords that annotate a schema without changing what it accepts.
_ANNOTATIONS = frozenset({"description", "$comment", "examples"})


#: Keywords whose value maps names to subschemas.
_SCHEMA_MAPS = frozenset(
    {
        "properties",
        "patternProperties",
        "$defs",
        "definitions",
        "dependentSchemas",
    }
)


#: Keywords whose value is a subschema, or a list of them.
_SCHEMA_VALUES = frozenset(
    {
        "items",
        "prefixItems",
        "additionalItems",
        "additionalProperties",
        "unevaluatedItems",
        "unevaluatedProperties",
        "contains",
        "propertyNames",
        "contentSchema",
        "not",
        "if",
        "then",
        "else",
        "allOf",
        "anyOf",
        "oneOf",
    }
)


class UnresolvedReferenceError(LookupError):
    """A ``$ref`` or path names no schema on one side.

    The schema may be unmapped by the pin, gone or not JSON on that side, or
    the node a JSON Pointer names may not exist. The message is the reference.
    """


def strip_annotations(schema: object) -> object:
    """Return *schema* without the annotation keywords of :data:`_ANNOTATIONS`.

    Only schema positions are walked, so a property *named* ``description``
    stays, while each schema's own ``description`` goes.
    """
    if not isinstance(schema, dict):
        return schema
    out: dict[str, object] = {}
    for key, value in schema.items():
        if key in _ANNOTATIONS:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {
                name: strip_annotations(sub) for name, sub in value.items()
            }
        elif key in _SCHEMA_VALUES and isinstance(value, list):
            out[key] = [strip_annotations(sub) for sub in value]
        elif key in _SCHEMA_VALUES:
            out[key] = strip_annotations(value)
        else:
            out[key] = value
    return out


def is_watched(local: str) -> bool:
    """Return whether the pinned file *local* is read from upstream."""
    return local.startswith(WATCHED_SCHEMA_DIRS)


@dataclass(frozen=True)
class SchemaSet:
    """The schemas the pin lists, read from one side, with annotations dropped.

    ``files`` maps each pinned path to its schema; a file that side lacks, or
    that is not JSON, is absent and named in ``problems``.
    """

    pin: CsafPin
    files: Mapping[str, object]
    problems: tuple[str, ...] = ()

    @classmethod
    def read(
        cls, pin: CsafPin, source: Path, frozen: Path = PINNED_COPY_DIR
    ) -> SchemaSet:
        """Read the watched pinned files from *source*, the rest from *frozen*."""
        files: dict[str, object] = {}
        problems: list[str] = []
        for local in sorted(set(pin.sources.values())):
            path = (source if is_watched(local) else frozen) / local
            try:
                files[local] = strip_annotations(json.loads(path.read_bytes()))
            except FileNotFoundError:
                problems.append(f"`{local}` is gone upstream")
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                problems.append(f"`{local}` is not JSON upstream: {exc}")
        problems.extend(_unmapped_refs(pin, files))
        return cls(pin=pin, files=files, problems=tuple(problems))

    def target(self, ref: str, origin: str) -> tuple[str, str]:
        """Return the ``(file, fragment)`` that *ref*, read in *origin*, names."""
        target, _, fragment = ref.partition("#")
        if not target:
            local = origin
        elif "://" in target:
            if target not in self.pin.sources:
                raise UnresolvedReferenceError(target)
            local = self.pin.sources[target]
        else:
            local = resolve_relative_ref(target, origin)
        if local not in self.files:
            raise UnresolvedReferenceError(ref)
        return local, fragment

    def node(self, local: str, fragment: str) -> object:
        """Return the node the JSON Pointer *fragment* names in *local*."""
        node = self.files[local]
        if not fragment:
            return node
        if not fragment.startswith("/"):
            raise UnresolvedReferenceError(f"{local}#{fragment}")
        for token in fragment[1:].split("/"):
            key = token.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and key in node:
                node = node[key]
            elif (
                isinstance(node, list)
                and key.isdigit()
                and int(key) < len(node)
            ):
                node = node[int(key)]
            else:
                raise UnresolvedReferenceError(f"{local}#{fragment}")
        return node

    def locate(self, path: str) -> tuple[object, str] | None:
        """Return the schema of the document field *path*, or ``None``.

        Raises:
            UnresolvedReferenceError: a ``$ref`` on the way is not mapped.
        """
        if self.pin.root not in self.files:
            raise UnresolvedReferenceError(self.pin.root)
        here: tuple[object, str] = (self.files[self.pin.root], self.pin.root)
        for segment in path.split("."):
            name = segment.removesuffix("[]")
            found = self._step(here, functools.partial(_property, name=name))
            if found is None:
                return None
            here = found
            if segment.endswith("[]"):
                found = self._step(here, _items)
                if found is None:
                    return None
                here = found
        return here

    def _step(
        self,
        here: tuple[object, str],
        pick: Callable[[dict[str, object]], object | None],
    ) -> tuple[object, str] | None:
        for node, origin in self._candidates(*here, seen=frozenset()):
            picked = pick(node)
            if picked is not None:
                return picked, origin
        return None

    def _candidates(
        self, node: object, origin: str, seen: frozenset[str]
    ) -> Iterator[tuple[dict[str, object], str]]:
        """Yield *node* and every schema it pulls in by ``$ref`` or a combinator."""
        if not isinstance(node, dict):
            return
        yield node, origin
        ref = node.get("$ref")
        if isinstance(ref, str):
            local, fragment = self.target(ref, origin)
            key = f"{local}#{fragment}"
            if key not in seen:
                yield from self._candidates(
                    self.node(local, fragment), local, seen | {key}
                )
        for keyword in ("allOf", "anyOf", "oneOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    yield from self._candidates(branch, origin, seen)

    def expand(
        self, node: object, origin: str, seen: frozenset[str] = frozenset()
    ) -> object:
        """Return *node* with every ``$ref`` replaced by the schema it names.

        A reference back into a schema already being expanded is kept as a
        marker naming it, so a recursive schema expands to a finite tree.
        """
        if isinstance(node, list):
            return [self.expand(item, origin, seen) for item in node]
        if not isinstance(node, dict):
            return node
        out: dict[str, object] = {}
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                local, fragment = self.target(value, origin)
                name = f"{local}#{fragment}"
                out[key] = (
                    f"(recursive) {name}"
                    if name in seen
                    else self.expand(
                        self.node(local, fragment), local, seen | {name}
                    )
                )
            else:
                out[key] = self.expand(value, origin, seen)
        return out


def _property(node: dict[str, object], name: str) -> object | None:
    properties = node.get("properties")
    return properties.get(name) if isinstance(properties, dict) else None


def _items(node: dict[str, object]) -> object | None:
    items = node.get("items")
    return items if isinstance(items, dict) else None


def _unmapped_refs(pin: CsafPin, files: Mapping[str, object]) -> list[str]:
    """Name each ``$ref`` in *files* that points outside the pin record."""
    listed = set(pin.sources.values())
    found: list[str] = []
    for origin, schema in sorted(files.items()):
        for ref in sorted(set(schema_refs(schema))):
            target = ref.partition("#")[0]
            if not target:
                continue
            if "://" in target:
                if target not in pin.sources:
                    found.append(
                        f"`{origin}` references `{target}`, which the pin "
                        "record does not map"
                    )
            elif resolve_relative_ref(target, origin) not in listed:
                found.append(
                    f"`{origin}` references `{target}`, a file the pin "
                    "record does not list"
                )
    return found
