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
"""Architecture ratchet: core writes go through typed object methods (HP-08-001).

Persistence writes made on a handler's behalf go through the persistence
port's typed object methods — ``dl.save(obj)`` or ``dl.create(obj)`` with a
domain object — which validate and dehydrate the model so that ``dl.read()``
can rehydrate it (ADR-0034).  Building a record by hand and pushing it through
the record-level compatibility surface bypasses both.  This ratchet scans
``vultron/core/use_cases/`` and ``vultron/core/behaviors/`` for the three
shapes that do so:

* a reference to ``object_to_record`` (an adapter-layer helper — an import or
  a call);
* a hand-built ``StorableRecord(...)`` constructor call (an annotation-only
  import of the type is fine, constructing one is not);
* a record-level ``.update(id_, record)`` call — two positional arguments, or
  a ``record=`` keyword — which is the ``DataLayer.update`` compatibility
  method rather than a domain-object write.

``KNOWN_VIOLATIONS`` pins the pre-existing sites per file, with an exact
site count, under a bidirectional equality assertion (ARCH-18-001): a new file
or a new site in a pinned file fails the test immediately, and a resolved site
fails it until the count (or the entry) is lowered.

Spec: HP-08-001 (``specs/handler-protocol.yaml``); ADR-0034.
Corpus: TB-13-001 (shared ``_corpus`` scan, substring prefilter).
"""

import ast
from collections.abc import Mapping
from types import MappingProxyType

from test.architecture import _corpus

_CORE_ROOT = _corpus.REPO_ROOT / "vultron" / "core"

#: The two subtrees a handler's writes can run in: the use case itself and
#: the BT nodes it reaches through ``BTBridge`` (HP-08-002).
_SCAN_ROOTS = (_CORE_ROOT / "use_cases", _CORE_ROOT / "behaviors")

#: Substring prefilter (TB-13-002): a file without any of these cannot violate.
_FRAGMENTS = ("object_to_record", "StorableRecord(", ".update(")

_RECORD_BUILDER = "object_to_record"
_RECORD_TYPE = "StorableRecord"
_RECORD_UPDATE = "update"
_RECORD_KEYWORD = "record"


def _callee_name(node: ast.AST) -> str | None:
    """The bare name a call resolves to (``f(...)``, ``x.f(...)``), else ``None``."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _names_object_to_record(node: ast.AST) -> bool:
    """True when *node* imports or calls ``object_to_record``."""
    if isinstance(node, ast.ImportFrom | ast.Import):
        return any(
            alias.name.split(".")[-1] == _RECORD_BUILDER
            for alias in node.names
        )
    return _callee_name(node) == _RECORD_BUILDER


def _constructs_storable_record(node: ast.AST) -> bool:
    """True when *node* is a ``StorableRecord(...)`` constructor call."""
    return _callee_name(node) == _RECORD_TYPE


def _is_record_level_update(node: ast.AST) -> bool:
    """True when *node* is a ``.update(id_, record)`` call.

    ``dict.update`` takes one positional argument and a BT node's ``update()``
    takes none, so two positional arguments — or a ``record=`` keyword — is the
    ``DataLayer.update(id_, record)`` compatibility signature.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == _RECORD_UPDATE):
        return False
    if len(node.args) >= 2:
        return True
    return any(kw.arg == _RECORD_KEYWORD for kw in node.keywords)


def _record_level_sites(tree: ast.AST) -> list[str]:
    """Return one ``"line N: <reason>"`` string per record-level site in *tree*."""
    sites: list[str] = []
    for node in ast.walk(tree):
        if _names_object_to_record(node):
            sites.append(
                f"line {_corpus.node_line(node)}: names object_to_record"
            )
        elif _constructs_storable_record(node):
            sites.append(
                f"line {_corpus.node_line(node)}: builds a StorableRecord by hand"
            )
        elif _is_record_level_update(node):
            sites.append(
                f"line {_corpus.node_line(node)}: record-level .update(id_, record)"
            )
    return sites


def _collect_violations() -> dict[str, list[str]]:
    """Map repo-relative path -> record-level sites, for every offending file."""
    violations: dict[str, list[str]] = {}
    for root in _SCAN_ROOTS:
        for py_file, tree in _corpus.files_mentioning(*_FRAGMENTS, under=root):
            sites = _record_level_sites(tree)
            if sites:
                rel = py_file.relative_to(_corpus.REPO_ROOT).as_posix()
                violations[rel] = sites
    return violations


# ---------------------------------------------------------------------------
# Known pre-existing violations.
#
# ``vultron/core/behaviors/helpers.py`` holds the legacy generic
# ``UpdateObject`` and ``CreateObject`` BT nodes, which build a
# ``StorableRecord`` from a dict and push it through ``DataLayer.update()`` /
# ``DataLayer.create()``.  HP-08-001's rationale names them as the one
# retained compatibility use in core.  The value is the exact number of
# record-level sites in the file; lower it as sites are migrated and remove
# the entry at zero.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: Mapping[str, int] = MappingProxyType(
    {"vultron/core/behaviors/helpers.py": 5}
)


def test_core_writes_do_not_build_records_by_hand() -> None:
    """HP-08-001: no hand-built record or record-level update outside the pin.

    See module docstring for the ratchet strategy.
    """
    found = _collect_violations()
    actual = {path: len(sites) for path, sites in found.items()}
    grown = {
        path: count
        for path, count in actual.items()
        if count > KNOWN_VIOLATIONS.get(path, 0)
    }
    shrunk = {
        path: actual.get(path, 0)
        for path, count in KNOWN_VIOLATIONS.items()
        if actual.get(path, 0) < count
    }

    diff_lines: list[str] = []
    if grown:
        diff_lines.append(
            "NEW violations (write domain objects with dl.save()/dl.create();"
            " never object_to_record(), a hand-built StorableRecord, or"
            " .update(id_, record) — HP-08-001):"
        )
        for path in sorted(grown):
            diff_lines.append(
                f"  + {path}: {grown[path]} site(s), pinned"
                f" {KNOWN_VIOLATIONS.get(path, 0)}"
            )
            diff_lines.extend(f"      {site}" for site in found[path])
    if shrunk:
        diff_lines.append(
            "RESOLVED violations (lower or remove these KNOWN_VIOLATIONS"
            " entries):"
        )
        diff_lines.extend(
            f"  - {path}: now {shrunk[path]} site(s), pinned"
            f" {KNOWN_VIOLATIONS[path]}"
            for path in sorted(shrunk)
        )

    assert actual == dict(KNOWN_VIOLATIONS), "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests
# ---------------------------------------------------------------------------


def _sites(source: str) -> list[str]:
    return _record_level_sites(_corpus.parse_inline(source))


def test_detector_flags_an_object_to_record_call() -> None:
    [site] = _sites("rec = object_to_record(obj)\n")
    assert "object_to_record" in site


def test_detector_flags_an_object_to_record_import() -> None:
    [site] = _sites(
        "from vultron.adapters.driven.db_record import object_to_record\n"
    )
    assert "object_to_record" in site


def test_detector_flags_a_hand_built_storable_record() -> None:
    [site] = _sites("rec = StorableRecord(id_=i, type_=t, data_=d)\n")
    assert "StorableRecord" in site


def test_detector_flags_a_two_argument_update() -> None:
    [site] = _sites("self.datalayer.update(self.object_id, storable)\n")
    assert ".update(id_, record)" in site


def test_detector_flags_a_record_keyword_update() -> None:
    [site] = _sites("dl.update(id_=oid, record=storable)\n")
    assert ".update(id_, record)" in site


def test_detector_ignores_typed_object_writes() -> None:
    assert (
        _sites(
            "dl.save(case)\n"
            "self.datalayer.create(participant)\n"
            "dl.save_many([a, b])\n"
        )
        == []
    )


def test_detector_ignores_dict_update_and_bt_update() -> None:
    assert (
        _sites(
            "data.update({'k': 1})\n"
            "status = super().update()\n"
            "read_node.update()\n"
        )
        == []
    )


def test_detector_ignores_an_annotation_only_storable_record_import() -> None:
    assert (
        _sites(
            "from vultron.core.ports.datalayer import StorableRecord\n"
            "def store(obj: 'StorableRecord | PersistableModel') -> None:\n"
            "    dl.create(obj)\n"
        )
        == []
    )
