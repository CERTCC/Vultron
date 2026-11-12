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
  layer — at module level, inside a function, relatively, as ``from vultron
  import measure``, or by name through any call such as ``import_module`` —
  fails the first test.
* **It writes nothing** (CEH-01-002).  Inside ``vultron/measure/``, any
  writing DataLayer method, a write-mode ``open``, a ``Path`` or ``os`` write,
  or an import of a store, ``shutil``, ``sqlite3`` or ``tempfile`` fails the
  second test.  The one admitted write is a command's own output file,
  listed by ``path::function`` in :data:`OUTPUT_FILE_WRITERS`.

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


def _package_of(path: Path) -> str:
    """The dotted package a module at *path* (under the repo root) belongs to."""
    parts = path.relative_to(_corpus.REPO_ROOT).with_suffix("").parts
    # ``a/b.py`` and ``a/__init__.py`` both belong to package ``a``.
    return ".".join(parts[:-1])


def _resolve(module: str, level: int, package: str) -> str:
    """The absolute module a ``from`` import names, resolving a relative one."""
    if level == 0:
        return module
    base = package.split(".")
    base = base[: len(base) - (level - 1)] if level > 1 else base
    return ".".join([*base, module] if module else base)


def _string_arg(call: ast.Call, position: int, keyword: str) -> str | None:
    """A string-literal argument of *call*, by keyword or position."""
    for kw in call.keywords:
        if kw.arg == keyword:
            value = kw.value
            break
    else:
        if len(call.args) <= position:
            return None
        value = call.args[position]
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _measure_imports(tree: ast.AST, package: str) -> list[int]:
    """Return the line of every import of the measure layer in *tree*.

    *package* is the dotted package of the scanned module, used to resolve
    relative imports.  Any call passed a module name that resolves to the
    layer counts, whatever the callee is called, so an aliased
    ``import_module`` does not slip through.
    """
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = _resolve(node.module or "", node.level, package)
            if _names_measure(module) or any(
                _names_measure(f"{module}.{alias.name}")
                for alias in node.names
            ):
                lines.append(node.lineno)
        elif isinstance(node, ast.Import):
            if any(_names_measure(alias.name) for alias in node.names):
                lines.append(node.lineno)
        elif isinstance(node, ast.Call):
            name = _string_arg(node, 0, "name")
            if name is None:
                continue
            anchor = _string_arg(node, 1, "package") or package
            level = len(name) - len(name.lstrip("."))
            if _names_measure(_resolve(name.lstrip("."), level, anchor)):
                lines.append(node.lineno)
    return lines


#: The package an inline sample is scanned as, so a relative import resolves.
_SAMPLE_PACKAGE = "vultron.core.sample"


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
        "from importlib import import_module as im\nim('vultron.measure')",
        "import importlib\nimportlib.import_module(name='vultron.measure')",
        "import importlib\nimportlib.import_module('.measure', 'vultron')",
        "from ... import measure",
        "from ...measure import ledger",
        "from ...measure.ledger import read_case_ledgers",
    ],
)
def test_the_import_detector_catches_each_shape(source):
    assert _measure_imports(_corpus.parse_inline(source), _SAMPLE_PACKAGE)


@pytest.mark.parametrize(
    "source",
    [
        "import vultron.measurement_other",
        "from vultron.core import measure_x",
        "x = 'vultron.measure'",
        "from .. import measure_other",
        "from . import measure",
        "import importlib\nimportlib.import_module('vultron.measurement')",
    ],
)
def test_the_import_detector_ignores_near_misses(source):
    assert not _measure_imports(_corpus.parse_inline(source), _SAMPLE_PACKAGE)


def test_a_module_package_is_its_directory():
    root = _corpus.REPO_ROOT
    assert _package_of(root / "vultron/core/a/b.py") == "vultron.core.a"
    assert _package_of(root / "vultron/core/a/__init__.py") == "vultron.core.a"


@pytest.mark.spec("CEH-01-001")
def test_no_protocol_path_module_imports_the_measure_layer():
    violations = sorted(
        f"{path.relative_to(_corpus.REPO_ROOT).as_posix()}:{line}"
        for root in _PROTOCOL_ROOTS
        for path, tree in _corpus.files_mentioning("measure", under=root)
        for line in _measure_imports(tree, _package_of(path))
    )
    assert not violations, (
        "The protocol path must not import the measurement layer "
        "(CEH-01-001):\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# CEH-01-002: the layer writes nothing
# ---------------------------------------------------------------------------

#: Attribute names that write to a store, a ledger or the file system: every
#: writing method of the DataLayer port (``vultron/core/ports/datalayer.py``),
#: and the ``Path`` and file-handle writes.  Matched on any attribute access, not
#: only a call, so ``w = path.write_text`` is caught too.  ``update`` is one of
#: them, so code here merges a dict with ``|`` rather than ``dict.update``.
_WRITE_ATTRIBUTES = frozenset(
    {
        "save",
        "save_many",
        "save_if_unchanged",
        "create",
        "update",
        "delete",
        "clear_all",
        "clear_table",
        "inbox_append",
        "inbox_pop",
        "outbox_append",
        "outbox_pop",
        "transaction",
        "write",
        "writelines",
        "write_text",
        "write_bytes",
        "touch",
        "mkdir",
        "makedirs",
        "unlink",
        "remove",
        "removedirs",
        "rmdir",
        "rename",
        "renames",
        "symlink_to",
        "hardlink_to",
        "dump",
    }
)

#: Modules whose only use here would be a write, a store or a temp file.
_WRITE_MODULES = frozenset(
    {
        "shutil",
        "sqlite3",
        "tempfile",
        "vultron.adapters",
        "vultron.core.ports.datalayer",
    }
)

#: ``os`` functions that write; a ``from os import`` of one is a write too.
_OS_WRITES = frozenset(
    {
        "remove",
        "replace",
        "rename",
        "renames",
        "makedirs",
        "mkdir",
        "rmdir",
        "removedirs",
        "unlink",
        "write",
        "truncate",
        "link",
        "symlink",
    }
)

#: Characters that make an ``open`` mode writable.
_WRITE_MODE_CHARS = frozenset("wax+")

#: ``path::function`` of each command that writes its own output file — the one
#: write CEH-01-002 admits.
OUTPUT_FILE_WRITERS: frozenset[str] = frozenset(
    {"vultron/measure/history/cli.py::_write_output"}
)


def _names_module(name: str, modules: frozenset[str]) -> bool:
    return any(name == m or name.startswith(m + ".") for m in modules)


def _open_mode(call: ast.Call, positional: int) -> ast.expr | None:
    """Return the mode argument of an ``open`` call, positional or keyword."""
    for keyword in call.keywords:
        if keyword.arg == "mode":
            return keyword.value
    if len(call.args) > positional:
        return call.args[positional]
    return None


def _is_write_open(call: ast.Call) -> bool:
    """Whether *call* is an ``open`` with a writable mode.

    ``open(f, mode)`` and a module's ``io.open`` / ``codecs.open`` /
    ``os.fdopen`` take the mode second; ``path.open(mode)`` takes it first.
    A mode that is not a string literal cannot be proved read-only, so it
    counts as a write.  ``os.open`` takes integer flags and always counts.
    """
    func = call.func
    if isinstance(func, ast.Name) and func.id in {"open", "fdopen"}:
        mode = _open_mode(call, positional=1)
    elif isinstance(func, ast.Attribute) and func.attr in {"open", "fdopen"}:
        owner = func.value
        if (
            isinstance(owner, ast.Name)
            and owner.id == "os"
            and func.attr == "open"
        ):
            return True
        module_level = isinstance(owner, ast.Name) and owner.id in {
            "io",
            "codecs",
            "os",
            "builtins",
        }
        mode = _open_mode(call, positional=1 if module_level else 0)
    else:
        return False
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return bool(_WRITE_MODE_CHARS & set(mode.value))
    return True


def _is_write_node(node: ast.AST) -> bool:
    """Whether *node* writes, or imports something only a write would need."""
    if isinstance(node, ast.Call) and _is_write_open(node):
        return True
    if isinstance(node, ast.Attribute):
        if node.attr in _WRITE_ATTRIBUTES:
            return True
        owner = node.value
        return (
            isinstance(owner, ast.Name)
            and owner.id == "os"
            and node.attr in _OS_WRITES
        )
    if isinstance(node, ast.Import):
        return any(_names_module(a.name, _WRITE_MODULES) for a in node.names)
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if _names_module(module, _WRITE_MODULES):
            return True
        if module == "os":
            return any(a.name in _OS_WRITES for a in node.names)
        return any(
            _names_module(f"{module}.{a.name}", _WRITE_MODULES)
            for a in node.names
        )
    return False


def _writes(tree: ast.AST) -> list[tuple[str, int]]:
    """Return ``(enclosing function, line)`` for every write in *tree*."""
    found: list[tuple[str, int]] = []

    def visit(node: ast.AST, function: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        if _is_write_node(node):
            found.append((function, getattr(node, "lineno", 0)))
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
        "dl.save_if_unchanged(obj, version)",
        "dl.update(obj)",
        "dl.clear_table('x')",
        "dl.clear_all()",
        "dl.inbox_append(item)",
        "dl.outbox_pop()",
        "write = path.write_text",
        "os.remove(p)",
        "os.replace(a, b)",
        "os.makedirs(p)",
        "os.open(p, os.O_RDONLY)",
        "from os import remove",
        "import shutil",
        "import sqlite3",
        "from tempfile import mkstemp",
        "from vultron.adapters.driven import datalayer_sqlite",
        "from vultron.core.ports.datalayer import DataLayer",
        "from vultron.core.ports import datalayer",
        "codecs.open(p, 'w')",
        "io.open(p, mode='a')",
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
        "codecs.open(p, 'r')",
        "io.open(p)",
        "os.path.join(a, b)",
        "from os import path",
        "import json",
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
