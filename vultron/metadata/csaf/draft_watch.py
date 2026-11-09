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
"""Say whether the CSAF 2.1 draft upstream changes what the models depend on.

The scheduled ``CSAF Draft Watch`` workflow (CSAF-05-005) runs this script
over two checkouts of ``oasis-tcs/csaf``: one at the pinned commit
(``--baseline``) and one at the head of the default branch (``--upstream``).
It compares three things:

- **The generated models.** The schemas are read from the pinned local copy
  and from upstream, at the paths the pin record maps, and the models are
  generated from each. The JSON Schema meta-schemas are frozen, so both sides
  take them from the pinned local copy. Annotations (``description``,
  ``$comment``, ``examples``) are dropped from every schema first, on both
  sides, so a reworded description is no change. A ``$ref`` the pin does not
  map, or a pinned file upstream no longer has, is reported as a change, never
  raised: models cannot be generated until the pin maps it.
- **The profile text**, ``profiles.md``, line by line.
- **The list of mandatory tests** in ``testcases.json``, by test ID.

It also says which of the CSAF fields this codebase reads (:data:`READ_FIELDS`)
the change touches (CSAF-05-007): a change there needs its mapping reviewed,
and a change elsewhere needs only a regeneration.

The script never moves the pin. Exit status: 0 when nothing the models,
profiles or test list depend on changed; 3 when something did, with the issue
body written to ``--report``; anything else is a failed run.

Usage::

    uv run csaf-draft-watch --baseline <pinned checkout> \\
        --upstream <upstream checkout> [--upstream-commit <sha>] \\
        [--report <file>]
"""

from __future__ import annotations

import argparse
import difflib
import functools
import json
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from vultron.metadata.csaf.corpus import TESTCASES_FILE, load_corpus_index
from vultron.metadata.csaf.pin import (
    PINNED_COPY_DIR,
    CsafPin,
    load_pin,
)
from vultron.metadata.csaf.regenerate import (
    render_models,
    resolve_relative_ref,
    schema_refs,
)
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.generated_files import write_generated

#: Exit status when upstream changes what the models, profiles or test list
#: depend on.
EXIT_CHANGED = 3

#: The upstream paths the pin maps from upstream. Every other pinned file (the
#: JSON Schema 2020-12 meta-schemas) is frozen and read from the pinned copy.
WATCHED_SCHEMA_DIRS = (
    "csaf_2.1/json_schema/",
    "csaf_2.1/referenced_schema/",
)
#: The profile text of the CSAF 2.1 draft, in the upstream repository.
PROFILES_FILE = PurePosixPath("csaf_2.1/prose/edit/src/profiles.md")
#: The test group whose test IDs make up the list of mandatory tests.
MANDATORY_GROUP = "mandatory"

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
#: How much of each diff the issue body quotes. GitHub caps a body at 65,536
#: characters, and a long diff says no more than its first lines.
_DIFF_LINES = 200


@dataclass(frozen=True)
class ReadField:
    """A CSAF field this codebase reads, as a document path, and why."""

    path: str
    specs: tuple[str, ...]


#: The CSAF fields this codebase reads, with the requirements that read them.
#: ``[]`` steps into the items of an array. A test checks that each one
#: resolves in the pinned schema, so a path that drifts from it fails.
READ_FIELDS: tuple[ReadField, ...] = (
    ReadField("$schema", ("CSAF-01-003",)),
    ReadField("document.csaf_version", ("CSAF-01-003",)),
    ReadField("document.category", ("CSAF-04-009",)),
    ReadField("document.title", ("CSAF-03-007",)),
    ReadField("document.notes[].category", ("CSAF-03-007",)),
    ReadField("document.notes[].text", ("CSAF-03-007",)),
    ReadField("document.references[]", ("CSAF-03-009",)),
    ReadField(
        "vulnerabilities[].disclosure_date",
        ("CSAF-03-001", "CSAF-03-002", "CSAF-03-003", "CSAF-04-006"),
    ),
    ReadField(
        "vulnerabilities[].first_known_exploitation_dates[]",
        ("CSAF-03-005", "CSAF-04-006"),
    ),
    ReadField(
        "vulnerabilities[].metrics[].content.ssvc_v2",
        ("CSAF-03-004", "CSAF-04-006"),
    ),
    ReadField("vulnerabilities[].cve", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].ids[]", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].title", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].notes[].category", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].notes[].text", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].references[]", ("CSAF-03-009",)),
    ReadField(
        "vulnerabilities[].product_status.known_affected[]", ("CSAF-04-007",)
    ),
    ReadField("product_tree.branches[].category", ("CSAF-04-007",)),
    ReadField("product_tree.branches[].name", ("CSAF-04-007",)),
    ReadField("product_tree.branches[].product.product_id", ("CSAF-04-007",)),
)


class UnresolvedReferenceError(LookupError):
    """A ``$ref`` names a schema the pin does not map, or a missing node."""


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


@dataclass(frozen=True)
class AffectedField:
    """A read field the upstream change touches, and how."""

    field: ReadField
    how: str


def affected_fields(
    baseline: SchemaSet,
    upstream: SchemaSet,
    read_fields: Sequence[ReadField] = READ_FIELDS,
) -> list[AffectedField]:
    """Return each of *read_fields* whose schema differs between the two sides.

    Raises:
        ValueError: a read field does not resolve in *baseline*, the pinned
            schema, so :data:`READ_FIELDS` has drifted from it.
    """
    affected: list[AffectedField] = []
    for read in read_fields:
        located = baseline.locate(read.path)
        if located is None:
            raise ValueError(
                f"{read.path} is not a field of the pinned CSAF schema"
            )
        pinned = baseline.expand(*located)
        try:
            found = upstream.locate(read.path)
            if found is None:
                affected.append(AffectedField(read, "is gone upstream"))
            elif upstream.expand(*found) != pinned:
                affected.append(AffectedField(read, "changed"))
        except UnresolvedReferenceError as exc:
            affected.append(
                AffectedField(
                    read,
                    f"cannot be read upstream: `{exc}` is not in the pin record",
                )
            )
    return affected


#: Generates the models package from a schema directory and its pin.
Renderer = Callable[[Path, CsafPin], Mapping[str, str]]


def _models_of(schemas: SchemaSet, render: Renderer) -> Mapping[str, str]:
    """Generate the models from *schemas*, written out to a staging directory."""
    with TemporaryDirectory(prefix="csaf-draft-watch-") as staging:
        for local, schema in schemas.files.items():
            write_generated(
                Path(staging) / local, json.dumps(schema, indent=2)
            )
        return render(Path(staging), schemas.pin)


def _diff(before: str, after: str, name: str) -> list[str]:
    return list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            f"pinned/{name}",
            f"upstream/{name}",
            lineterm="",
        )
    )


def model_diff(
    baseline: Mapping[str, str], upstream: Mapping[str, str]
) -> tuple[list[str], list[str]]:
    """Return the modules that differ and a unified diff of them."""
    changed = sorted(
        name
        for name in set(baseline) | set(upstream)
        if baseline.get(name) != upstream.get(name)
    )
    lines = [
        line
        for name in changed
        for line in _diff(baseline.get(name, ""), upstream.get(name, ""), name)
    ]
    return changed, lines


@dataclass(frozen=True)
class DraftChange:
    """What upstream changes, of what this codebase depends on."""

    problems: tuple[str, ...] = ()
    changed_modules: tuple[str, ...] = ()
    model_diff: tuple[str, ...] = ()
    fields: tuple[AffectedField, ...] = ()
    profiles_diff: tuple[str, ...] = ()
    tests_added: tuple[str, ...] = ()
    tests_removed: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        """Whether anything the models, profiles or test list depend on changed."""
        return bool(
            self.problems
            or self.changed_modules
            or self.fields
            or self.profiles_diff
            or self.tests_added
            or self.tests_removed
        )


def compare_schemas(
    pin: CsafPin,
    upstream: Path,
    *,
    pinned: Path = PINNED_COPY_DIR,
    read_fields: Sequence[ReadField] = READ_FIELDS,
    render: Renderer = render_models,
) -> DraftChange:
    """Compare the models from *upstream*'s schemas with the pinned ones.

    The models are generated only when the two schema sets differ once
    annotations are dropped: equal inputs generate equal models.
    """
    before = SchemaSet.read(pin, pinned, frozen=pinned)
    if before.problems:
        raise ValueError(
            f"the pinned local copy is incomplete: {list(before.problems)}"
        )
    after = SchemaSet.read(pin, upstream, frozen=pinned)
    fields = tuple(affected_fields(before, after, read_fields))
    if after.problems:
        return DraftChange(problems=after.problems, fields=fields)
    if after.files == before.files:
        return DraftChange(fields=fields)
    changed, lines = model_diff(
        _models_of(before, render), _models_of(after, render)
    )
    return DraftChange(
        changed_modules=tuple(changed), model_diff=tuple(lines), fields=fields
    )


def _read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def compare_profiles(baseline: Path, upstream: Path) -> tuple[list[str], str]:
    """Return a diff of the profile text, and a problem when upstream lost it.

    Raises:
        FileNotFoundError: *baseline*, the pinned checkout, has no profiles.
    """
    before = _read_text(baseline / PROFILES_FILE)
    if before is None:
        raise FileNotFoundError(baseline / PROFILES_FILE)
    after = _read_text(upstream / PROFILES_FILE)
    if after is None:
        return [], f"`{PROFILES_FILE}` is gone upstream"
    lines = [line.rstrip() for line in before.splitlines()]
    new_lines = [line.rstrip() for line in after.splitlines()]
    if lines == new_lines:
        return [], ""
    return (
        _diff("\n".join(lines), "\n".join(new_lines), str(PROFILES_FILE)),
        "",
    )


def mandatory_tests(clone: Path) -> set[str]:
    """Return the IDs of the mandatory tests in *clone*'s test-case index."""
    return {
        case.id
        for case in load_corpus_index(clone).tests
        if case.group == MANDATORY_GROUP
    }


def compare_tests(
    baseline: Path, upstream: Path
) -> tuple[list[str], list[str], str]:
    """Return the mandatory tests added and removed, and any upstream problem.

    Raises:
        FileNotFoundError, MetadataLoadError: the pinned checkout's index is
            missing or malformed, which is a fault of the run, not a change.
    """
    before = mandatory_tests(baseline)
    try:
        after = mandatory_tests(upstream)
    except FileNotFoundError:
        return [], [], f"`{TESTCASES_FILE}` is gone upstream"
    except MetadataLoadError as exc:
        return [], [], f"`{TESTCASES_FILE}` no longer reads upstream: {exc}"
    return (
        sorted(after - before, key=_test_order),
        sorted(before - after, key=_test_order),
        "",
    )


def _test_order(test_id: str) -> tuple[tuple[int, str], ...]:
    """Order test IDs such as ``6.1.9`` before ``6.1.10``."""
    return tuple(
        (int(part), "") if part.isdigit() else (-1, part)
        for part in test_id.split(".")
    )


def compare(
    pin: CsafPin,
    baseline: Path,
    upstream: Path,
    *,
    pinned: Path = PINNED_COPY_DIR,
    read_fields: Sequence[ReadField] = READ_FIELDS,
    render: Renderer = render_models,
) -> DraftChange:
    """Compare the upstream checkout with the pinned checkout and local copy."""
    schemas = compare_schemas(
        pin, upstream, pinned=pinned, read_fields=read_fields, render=render
    )
    profiles, profiles_problem = compare_profiles(baseline, upstream)
    added, removed, tests_problem = compare_tests(baseline, upstream)
    problems = schemas.problems + tuple(
        p for p in (profiles_problem, tests_problem) if p
    )
    return DraftChange(
        problems=problems,
        changed_modules=schemas.changed_modules,
        model_diff=schemas.model_diff,
        fields=schemas.fields,
        profiles_diff=tuple(profiles),
        tests_added=tuple(added),
        tests_removed=tuple(removed),
    )


def _diff_block(lines: Sequence[str]) -> list[str]:
    shown = list(lines[:_DIFF_LINES])
    if len(lines) > _DIFF_LINES:
        shown.append(f"... {len(lines) - _DIFF_LINES} more lines")
    return [
        "<details><summary>Diff</summary>",
        "",
        # Four backticks, so a fence inside the diff does not close it.
        "````diff",
        *shown,
        "````",
        "",
        "</details>",
    ]


def _fields_section(change: DraftChange) -> list[str]:
    lines = ["## CSAF fields this codebase reads", ""]
    if not change.fields:
        return [
            *lines,
            "None of them changed, so regenerating the models is enough.",
        ]
    lines.append(
        "Each of these sets a case input, so review its mapping in the "
        "crosswalk:"
    )
    lines.append("")
    lines.extend(
        f"- `{a.field.path}` ({', '.join(a.field.specs)}) {a.how}."
        for a in change.fields
    )
    return lines


def render_issue(
    change: DraftChange, pin: CsafPin, upstream_commit: str | None = None
) -> str:
    """Return the body of the issue the job opens for *change*."""
    head = (
        f"commit `{upstream_commit}` of {pin.repository}"
        if upstream_commit
        else f"the head of {pin.repository}"
    )
    lines = [
        f"{head} changes what Vultron's CSAF models depend on, compared with "
        f"the pinned revision `{pin.short_commit}` (draft {pin.draft_stage}) "
        "in `third_party/csaf/pin.json`.",
        "",
        *_fields_section(change),
    ]
    if change.problems:
        lines += ["", "## Inputs the pin cannot follow", ""]
        lines += [f"- {problem}" for problem in change.problems]
    if change.changed_modules:
        lines += ["", "## Generated models", ""]
        lines += [f"- `{name}` differs" for name in change.changed_modules]
        lines += ["", *_diff_block(change.model_diff)]
    if change.profiles_diff:
        lines += ["", "## Profile text", "", f"`{PROFILES_FILE}` changed.", ""]
        lines += _diff_block(change.profiles_diff)
    if change.tests_added or change.tests_removed:
        lines += ["", "## Mandatory tests", ""]
        lines += [f"- added: {t}" for t in change.tests_added]
        lines += [f"- removed: {t}" for t in change.tests_removed]
    lines += [
        "",
        "## What to do",
        "",
        "1. Bump the pin: copy the schemas the pin lists from the new upstream "
        "commit into `third_party/csaf/schemas/`, and update the commit, "
        "draft stage, `sources` and `sha256` in `third_party/csaf/pin.json`. "
        "A new source needs a licence file beside it and an entry in "
        "`LICENSE.md`.",
        "2. Regenerate the models: `uv run csaf-models`.",
        "3. Re-check the crosswalk in `docs/reference/csaf_crosswalk/` for "
        "each field above, and run `uv run csaf-corpus --clone <clone>` over "
        "a clone at the new commit.",
        "",
        "Close this issue from the pull request that moves the pin. While it "
        "stays open, the `CSAF Draft Watch` workflow opens no other issue and "
        "does not comment here (CSAF-05-006).",
    ]
    return "\n".join(lines) + "\n"


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="csaf-draft-watch", description=(__doc__ or "").split("\n\n")[0]
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="a checkout of the upstream repository at the pinned commit",
    )
    parser.add_argument(
        "--upstream",
        type=Path,
        required=True,
        help="a checkout of the upstream repository at the commit to compare",
    )
    parser.add_argument(
        "--upstream-commit",
        help="the commit --upstream is at, named in the issue body",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="where to write the issue body when something changed",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Compare the checkouts; exit :data:`EXIT_CHANGED` when something changed."""
    args = _parse_args(argv)
    pin = load_pin()
    change = compare(pin, args.baseline, args.upstream)
    if not change.changed:
        print(
            "No change to what the CSAF models, profiles or tests depend on."
        )
        return 0
    body = render_issue(change, pin, args.upstream_commit)
    if args.report is not None:
        write_generated(args.report, body)
    print(body)
    return EXIT_CHANGED


if __name__ == "__main__":
    sys.exit(main())
