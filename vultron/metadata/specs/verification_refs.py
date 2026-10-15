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
"""The mechanical half of MS-10-009: tests a ``verification:`` clause names.

A ``verification:`` clause is a claim about the suite. Whether the named check
*inspects* the property stays a review judgment, but two parts of the claim
can be read off the tree:

- **The named test exists** (MS-10-010). A pytest node such as
  ``test/x/test_y.py::TestZ::test_w`` must resolve, segment by segment, in
  that file, and a bare ``test_<name>`` token must name a function, class or
  module in the test files or directories the clause names, or anywhere in the
  test tree when it names none. A missing *file* is MS-15-001's to report, so
  a node in a missing file is not reported twice.
- **The named test carries the marker** (MS-10-011). When the clause of a
  ``protocol`` or ``foundation`` requirement names test files, at least one of
  them carries ``@pytest.mark.spec("<ID>")``. A clause naming no test file is
  left to the SR-05-005 marker guard.

``spec-lint`` reports the first check corpus-wide as a hard error. The second
has a backlog, so it is held back two ways instead: ``spec-lint
--changed-since REF`` fails each requirement the branch changed (see
:func:`changed_requirement_ids`), and a growth guard under
``test/architecture/`` fails each requirement a PR adds to the set.

Requirements: specs/meta-specifications.yaml MS-10-009 through MS-10-011.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.base import iter_tree_texts
from vultron.metadata.specs.coverage import marked_ids_in
from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import (
    IMPLEMENTER_KINDS,
    BehavioralSpec,
    StatementSpec,
)

#: Repository-relative directories that hold test modules.
TEST_ROOTS: tuple[str, ...] = ("test", "integration_tests")

#: A ``.py`` path, optionally followed by a pytest node suffix (``::A::b``).
_PY_REF_RE = re.compile(
    r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.py)((?:::[\w]+(?:\[[^\]\s]*\])?)+)?"
)
#: A directory under a test root, written with its trailing slash.
_DIR_REF_RE = re.compile(
    r"(?<![\w./-])((?:test|integration_tests)/[\w./-]*/)(?![\w.-])"
)
#: A bare ``test_<name>`` token. Not part of a path or node (no ``/``, ``.``
#: or ``:`` before it), not a file or attribute (no ``.x`` after it). A
#: trailing ``*`` makes it a prefix pattern.
_NAME_RE = re.compile(r"(?<![\w/.:-])(test_\w+)(\*?)(?!\w|\.\w)")
_PARAM_RE = re.compile(r"\[[^\]]*\]$")

Spec = BehavioralSpec | StatementSpec


@dataclass(frozen=True)
class IndexedTestFile:
    """What one test file defines, as far as a clause can name it.

    Attributes:
        nodes: pytest-addressable names: top-level functions and classes, and
            ``Class::member`` paths through nested classes.
        names: Every function or class name anywhere in the file, and the
            module's own stem.
        source: The file text, read for ``@pytest.mark.spec`` markers.
    """

    nodes: frozenset[str]
    names: frozenset[str]
    source: str


#: A ``def`` or ``class`` statement, with its indentation.
_DEF_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?:async[ \t]+)?(?P<kw>def|class)[ \t]+(?P<name>\w+)",
    re.MULTILINE,
)


def index_module(path: Path, source: str) -> IndexedTestFile:
    """Index the names *source* (the text of *path*) defines.

    A line scan, not a parse: indexing the whole test tree runs on every
    ``spec-lint``, and ``ast.parse`` of it costs seconds. A node path follows
    the chain of enclosing classes by indentation; a ``def`` inside a function
    is a name but not a node. A ``def`` written inside a string is read as code:
    it adds a name, and one at a shallower indent than its class ends that class
    early. Test sources do not do this, and the corpus check would report it.
    """
    nodes: set[str] = set()
    names: set[str] = {path.stem}
    #: Open scopes as ``(indent, node path or None)``; ``None`` is a function.
    stack: list[tuple[int, str | None]] = []
    for match in _DEF_RE.finditer(source):
        indent = len(match.group("indent").expandtabs())
        name = match.group("name")
        names.add(name)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            node_path: str | None = name
        elif (parent := stack[-1][1]) is not None:
            node_path = f"{parent}::{name}"
        else:
            node_path = None
        if node_path is not None:
            nodes.add(node_path)
        is_class = match.group("kw") == "class"
        stack.append((indent, node_path if is_class else None))
    return IndexedTestFile(frozenset(nodes), frozenset(names), source)


@dataclass
class SuiteIndex:
    """Every test module under :data:`TEST_ROOTS`, keyed by relative path."""

    modules: Mapping[str, IndexedTestFile] = field(default_factory=dict)

    @classmethod
    def build(cls, repo_root: Path) -> SuiteIndex:
        """Index each ``*.py`` file under the test roots of *repo_root*."""
        return cls(
            {
                rel: index_module(Path(rel), source)
                for rel, source in iter_tree_texts(
                    repo_root, TEST_ROOTS, "*.py"
                )
            }
        )

    def resolve_file(self, ref: str) -> list[str]:
        """Index keys *ref* names: the path itself, or files ending with it."""
        if ref in self.modules:
            return [ref]
        suffix = "/" + ref
        return sorted(k for k in self.modules if k.endswith(suffix))

    def under(self, directory: str) -> list[str]:
        """Index keys under *directory* (written with a trailing ``/``)."""
        return sorted(k for k in self.modules if k.startswith(directory))


@dataclass(frozen=True)
class ClauseRefs:
    """The test references one ``verification:`` clause makes.

    Attributes:
        files: Index keys of the test files the clause names.
        nodes: ``(file reference, node path)`` pairs, as written.
        dirs: Test directories the clause names.
        names: Bare ``test_<name>`` tokens, with ``*`` kept on a prefix.
    """

    files: tuple[str, ...]
    nodes: tuple[tuple[str, str], ...]
    dirs: tuple[str, ...]
    names: tuple[str, ...]


def clause_refs(text: str, index: SuiteIndex) -> ClauseRefs:
    """Read the test files, nodes, directories and names *text* names."""
    files: list[str] = []
    nodes: list[tuple[str, str]] = []
    for match in _PY_REF_RE.finditer(text):
        ref, node = match.group(1), match.group(2)
        resolved = index.resolve_file(ref)
        files.extend(k for k in resolved if k not in files)
        if node:
            nodes.append((ref, node.removeprefix("::")))
    dirs = tuple(dict.fromkeys(_DIR_REF_RE.findall(text)))
    names = tuple(
        dict.fromkeys(name + star for name, star in _NAME_RE.findall(text))
    )
    return ClauseRefs(tuple(files), tuple(nodes), dirs, names)


def _node_problem(
    spec_id: str, ref: str, node: str, index: SuiteIndex
) -> str | None:
    resolved = index.resolve_file(ref)
    if not resolved:
        return None  # a missing file is MS-15-001's finding, not this one's
    wanted = "::".join(_PARAM_RE.sub("", seg) for seg in node.split("::"))
    if any(wanted in index.modules[k].nodes for k in resolved):
        return None
    return (
        f"{spec_id}: verification names `{ref}::{node}`, but `{wanted}` is "
        f"not a test in {', '.join(resolved)} (MS-10-010). Point at the test "
        f"that exists, or write the missing test."
    )


def _matches(name: str, defined: Iterable[str]) -> bool:
    if name.endswith("*"):
        prefix = name[:-1]
        return any(d.startswith(prefix) for d in defined)
    return name in defined


def _name_problem(
    spec_id: str, name: str, scope: list[str], index: SuiteIndex
) -> str | None:
    if any(_matches(name, index.modules[k].names) for k in scope):
        return None
    elsewhere = sorted(
        k
        for k, module in index.modules.items()
        if k not in scope and _matches(name, module.names)
    )
    if elsewhere:
        where = (
            f"it is defined in {', '.join(elsewhere)}, not in the test "
            f"files or directories the clause names. Name that module"
        )
    else:
        where = "no test file defines it. Point at the test that exists"
    return (
        f"{spec_id}: verification names `{name}`, but {where}, or write the "
        f"missing test (MS-10-010)."
    )


def unresolved_test_refs(
    spec_id: str, spec: Spec, index: SuiteIndex
) -> list[str]:
    """Every test the clause of *spec* names that does not exist (MS-10-010).

    A bare name is looked up in the test files and directories the clause
    names, and in the whole test tree only when it names neither.
    """
    text = spec.verification or ""
    if not text:
        return []
    refs = clause_refs(text, index)
    problems = [
        p
        for ref, node in refs.nodes
        if (p := _node_problem(spec_id, ref, node, index)) is not None
    ]
    scope = list(refs.files)
    for directory in refs.dirs:
        scope.extend(k for k in index.under(directory) if k not in scope)
    if not scope:
        scope = list(index.modules)
    problems.extend(
        p
        for name in refs.names
        if (p := _name_problem(spec_id, name, scope, index)) is not None
    )
    return problems


def check_test_refs(registry: SpecRegistry, repo_root: Path) -> list[str]:
    """Hard errors for every unresolved test reference in the corpus."""
    index = SuiteIndex.build(repo_root)
    errors: list[str] = []
    for spec_id, spec in sorted(registry.all_specs.items()):
        errors.extend(unresolved_test_refs(spec_id, spec, index))
    return errors


def named_tests_lack_marker(
    spec_id: str, spec: Spec, index: SuiteIndex
) -> bool:
    """Whether *spec* names test files and none carries its marker.

    Only ``protocol`` and ``foundation`` requirements are held to this
    (SR-05-004); a clause that names no test file that exists is not.
    """
    if spec.kind not in IMPLEMENTER_KINDS or not spec.verification:
        return False
    files = clause_refs(spec.verification, index).files
    if not files:
        return False
    return spec_id not in marked_ids_in(index.modules[k].source for k in files)


def unmarked_named_test_ids(repo_root: Path) -> frozenset[str]:
    """IDs whose clause names test files, none carrying the ID's marker.

    The per-item extractor behind the MS-10-011 growth guard
    (:func:`vultron.metadata.specs.growth_guard.added_since_base`): it reads
    ``specs/`` and the test roots under *repo_root*, so the same function runs
    on the working tree and on a materialized base tree.
    """
    registry = load_registry(repo_root / "specs")
    index = SuiteIndex.build(repo_root)
    return frozenset(
        spec_id
        for spec_id, spec in registry.all_specs.items()
        if named_tests_lack_marker(spec_id, spec, index)
    )


def marker_problem(spec_id: str) -> str:
    """The error ``spec-lint --changed-since`` prints for an MS-10-011 miss."""
    return (
        f"{spec_id}: no test file its verification names carries @pytest.mark."
        f'spec("{spec_id}") (MS-10-011). Mark the test that verifies it, or '
        f"name the test file that does. For behavior not built yet, use the "
        f"strict-xfail pattern in notes/spec-authoring-rules.md."
    )


def requirement_fingerprints(repo_root: Path) -> dict[str, str]:
    """Each requirement ID under *repo_root* with a dump of its record.

    The reader behind :func:`changed_requirement_ids`: two trees disagree on
    an ID exactly when some field of that requirement differs.
    """
    registry = load_registry(repo_root / "specs")
    return {
        spec_id: spec.model_dump_json()
        for spec_id, spec in registry.all_specs.items()
    }


def changed_requirement_ids(
    base: Mapping[str, str], head: Mapping[str, str]
) -> frozenset[str]:
    """IDs added at *head*, or whose record differs from *base*."""
    return frozenset(
        spec_id
        for spec_id, record in head.items()
        if base.get(spec_id) != record
    )


__all__ = [
    "TEST_ROOTS",
    "ClauseRefs",
    "SuiteIndex",
    "IndexedTestFile",
    "changed_requirement_ids",
    "check_test_refs",
    "clause_refs",
    "index_module",
    "marker_problem",
    "named_tests_lack_marker",
    "requirement_fingerprints",
    "unmarked_named_test_ids",
    "unresolved_test_refs",
]
