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

"""Architecture boundaries of the read-only measurement layer (CEH-01-001, CEH-01-002).

Two one-way guarantees keep ``vultron/measure/`` safe to run on an archived
ledger and keep it out of case behavior:

* **No protocol-path module imports it** (CEH-01-001).  A module under
  ``vultron/core/``, ``vultron/wire/`` or ``vultron/adapters/`` that imports the
  layer — at module level, inside a function, as ``from vultron import
  measure``, or through ``importlib`` by name — fails the first test.
* **It writes nothing** (CEH-01-002).  A save, create or other store write, a
  write-mode ``open``, or a ``Path`` write inside ``vultron/measure/`` fails
  the second test.  The one admitted write is a command's own output file,
  listed by ``path::function`` in :data:`OUTPUT_FILE_WRITERS`; there is no
  command yet, so the list is empty.

Each detector is first run against inline sources holding every shape it must
catch, so neither test passes by scanning nothing.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_MEASURE = "vultron.measure"

_PROTOCOL_ROOTS = tuple(
    _corpus.REPO_ROOT / "vultron" / name
    for name in ("core", "wire", "adapters")
)

_MEASURE_ROOT = _corpus.REPO_ROOT / "vultron" / "measure"


# ---------------------------------------------------------------------------
# CEH-01-001: nothing in the protocol path imports the layer
# ---------------------------------------------------------------------------


def _names_measure(name: str) -> bool:
    return name == _MEASURE or name.startswith(_MEASURE + ".")


def _measure_imports(tree: ast.AST) -> list[int]:
    """Return the line of every import of the measure layer in *tree*."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _names_measure(module) or (
                module == "vultron"
                and any(alias.name == "measure" for alias in node.names)
            ):
                lines.append(node.lineno)
        elif isinstance(node, ast.Import):
            if any(_names_measure(alias.name) for alias in node.names):
                lines.append(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and _names_measure(node.args[0].value)
            and _corpus.callee_name(node.func)
            in {"import_module", "__import__"}
        ):
            lines.append(node.lineno)
    return lines


@pytest.mark.parametrize(
    "source",
    [
        "import vultron.measure",
        "import vultron.measure.ledger as ledger",
        "from vultron.measure.ledger import read_case_ledgers",
        "from vultron import measure",
        "def f():\n    from vultron.measure import ledger\n",
        "import importlib\nimportlib.import_module('vultron.measure.ledger')",
        "__import__('vultron.measure')",
    ],
)
def test_the_import_detector_catches_each_shape(source):
    assert _measure_imports(_corpus.parse_inline(source))


@pytest.mark.parametrize(
    "source",
    [
        "import vultron.measurement_other",
        "from vultron.core import measure_x",
        "x = 'vultron.measure'",
    ],
)
def test_the_import_detector_ignores_near_misses(source):
    assert not _measure_imports(_corpus.parse_inline(source))


@pytest.mark.spec("CEH-01-001")
def test_no_protocol_path_module_imports_the_measure_layer():
    violations = sorted(
        f"{path.relative_to(_corpus.REPO_ROOT).as_posix()}:{line}"
        for root in _PROTOCOL_ROOTS
        for path, tree in _corpus.files_mentioning("measure", under=root)
        for line in _measure_imports(tree)
    )
    assert not violations, (
        "The protocol path must not import the measurement layer "
        "(CEH-01-001):\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# CEH-01-002: the layer writes nothing
# ---------------------------------------------------------------------------

#: Method names that write to a store, a ledger or the file system.
_WRITE_METHODS = frozenset(
    {
        "save",
        "save_many",
        "create",
        "delete",
        "transaction",
        "write",
        "writelines",
        "write_text",
        "write_bytes",
        "touch",
        "mkdir",
        "unlink",
        "rmdir",
        "rename",
        "symlink_to",
        "dump",
    }
)

#: Characters that make an ``open`` mode writable.
_WRITE_MODE_CHARS = frozenset("wax+")

#: ``path::function`` of each command that writes its own output file — the one
#: write CEH-01-002 admits.  Empty until the layer has a command.
OUTPUT_FILE_WRITERS: frozenset[str] = frozenset()


def _open_mode(call: ast.Call, positional: int) -> ast.expr | None:
    """Return the mode argument of an ``open`` call, positional or keyword."""
    for keyword in call.keywords:
        if keyword.arg == "mode":
            return keyword.value
    if len(call.args) > positional:
        return call.args[positional]
    return None


def _is_write_open(call: ast.Call) -> bool:
    """Whether *call* is ``open(…)`` or ``x.open(…)`` with a writable mode.

    A mode that is not a string literal cannot be proved read-only, so it
    counts as a write.
    """
    if isinstance(call.func, ast.Name) and call.func.id == "open":
        mode = _open_mode(call, positional=1)
    elif isinstance(call.func, ast.Attribute) and call.func.attr == "open":
        mode = _open_mode(call, positional=0)
    else:
        return False
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return bool(_WRITE_MODE_CHARS & set(mode.value))
    return True


def _writes(tree: ast.AST) -> list[tuple[str, int]]:
    """Return ``(enclosing function, line)`` for every write call in *tree*."""
    found: list[tuple[str, int]] = []

    def visit(node: ast.AST, function: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        if isinstance(node, ast.Call) and (
            _is_write_open(node)
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _WRITE_METHODS
            )
        ):
            found.append((function, node.lineno))
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(tree, "<module>")
    return found


@pytest.mark.parametrize(
    "source",
    [
        "dl.save(obj)",
        "dl.save_many([obj])",
        "dl.create(obj)",
        "store.delete(key)",
        "with dl.transaction():\n    pass",
        "open(path, 'w')",
        "open(path, mode='a')",
        "open(path, 'r+')",
        "open(path, mode)",
        "path.open('x')",
        "path.open(mode='wb')",
        "path.write_text('x')",
        "path.write_bytes(b'x')",
        "fh.write('x')",
        "json.dump(data, fh)",
        "path.mkdir()",
        "path.unlink()",
    ],
)
def test_the_write_detector_catches_each_shape(source):
    assert _writes(_corpus.parse_inline(source))


@pytest.mark.parametrize(
    "source",
    [
        "open(path)",
        "open(path, 'r')",
        "path.open(encoding='utf-8')",
        "path.open('rb')",
        "path.read_text(encoding='utf-8')",
        "json.dumps(data)",
        "text.replace('-', ' ')",
    ],
)
def test_the_write_detector_ignores_reads(source):
    assert not _writes(_corpus.parse_inline(source))


def _measure_files() -> list[tuple[Path, ast.AST]]:
    files = list(_corpus.all_trees(_MEASURE_ROOT))
    assert files, f"no Python source found under {_MEASURE_ROOT}"
    return files


@pytest.mark.spec("CEH-01-002")
def test_the_measure_layer_writes_nothing():
    violations = sorted(
        f"{rel}::{function} (line {line})"
        for path, tree in _measure_files()
        for rel in [path.relative_to(_corpus.REPO_ROOT).as_posix()]
        for function, line in _writes(tree)
        if f"{rel}::{function}" not in OUTPUT_FILE_WRITERS
    )
    assert not violations, (
        "The measurement layer must not write to a store, a ledger or a file "
        "other than a command's own output (CEH-01-002):\n"
        + "\n".join(violations)
    )


def test_every_admitted_output_writer_still_writes():
    """An admitted writer that no longer writes is a stale entry; remove it."""
    actual = {
        f"{path.relative_to(_corpus.REPO_ROOT).as_posix()}::{function}"
        for path, tree in _measure_files()
        for function, _line in _writes(tree)
    }
    assert actual >= OUTPUT_FILE_WRITERS, sorted(OUTPUT_FILE_WRITERS - actual)
