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

"""Every module under ``vultron/`` imports cleanly, whatever it is imported after.

CS-05-005 makes a function-local import in ``vultron/`` legal only as a marked
cycle break, so every other one is hoisted to module level.  A hoist that closes
an import cycle fails only when the cycle is entered at one particular module —
pytest's collection order, or any one process's import order, can hide it.  This
test imports every module in an interpreter that has loaded nothing under
``vultron`` (``_fresh_import_driver.py``, run as a subprocess), and every member
of an import cycle as the first member of that cycle to load, so such a hoist
fails here, loudly, instead of in one deployment's start-up order.

The driver needs the import graph; this module builds it from ``_corpus``.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test.architecture import _corpus
from test.architecture._fresh_import_driver import _components

_VULTRON = _corpus.REPO_ROOT / "vultron"
_DRIVER = Path(__file__).with_name("_fresh_import_driver.py")


def _module_name(path: Path) -> tuple[str, bool]:
    """Return the dotted module name for *path* and whether it is a package."""
    parts = list(path.relative_to(_corpus.REPO_ROOT).with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _import_time_statements(body: list[ast.stmt]) -> list[ast.stmt]:
    """Statements that run when the module body runs.

    Function bodies are skipped, because they run only when called; a
    ``TYPE_CHECKING`` branch is skipped, because it never runs.  Class bodies,
    ``if``/``try``/``with`` blocks and ``else`` branches all run at import time.
    """
    out: list[ast.stmt] = []
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(stmt, ast.If) and _is_type_checking(stmt.test):
            out.extend(_import_time_statements(stmt.orelse))
            continue
        out.append(stmt)
        for field in ("body", "orelse", "finalbody"):
            nested = getattr(stmt, field, None)
            if isinstance(nested, list):
                out.extend(_import_time_statements(nested))
        for handler in getattr(stmt, "handlers", []):
            out.extend(_import_time_statements(handler.body))
    return out


def _prefixes(dotted: str) -> list[str]:
    parts = dotted.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


def _import_graph() -> dict[str, list[str]]:
    """Map each ``vultron`` module to the ``vultron`` modules it imports.

    An over-approximation is safe — it only merges cycles the driver then
    checks more thoroughly.  A module's parent package counts as an edge,
    because Python initializes ``a.b`` before it runs ``a.b.c``.
    """
    trees = {
        _module_name(path): tree for path, tree in _corpus.all_trees(_VULTRON)
    }
    modules = {name for name, _ in trees}
    graph: dict[str, list[str]] = {}
    for (name, is_package), tree in trees.items():
        assert isinstance(tree, ast.Module)
        parent = name.rpartition(".")[0]
        package = name if is_package else parent
        edges = {parent} if parent else set()
        for stmt in _import_time_statements(tree.body):
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    edges.update(_prefixes(alias.name))
            elif isinstance(stmt, ast.ImportFrom):
                if stmt.level:
                    base = package.split(".")[
                        : len(package.split(".")) - stmt.level + 1
                    ]
                    target = ".".join(
                        [*base, *([stmt.module] if stmt.module else [])]
                    )
                else:
                    target = stmt.module or ""
                edges.update(_prefixes(target))
                edges.update(f"{target}.{alias.name}" for alias in stmt.names)
        graph[name] = sorted((edges & modules) - {name})
    return graph


def test_import_graph_finds_a_known_cycle():
    """The graph carries real edges, so the driver has cycles to enter.

    With no edges every module would be a component of one, no child would
    be forked, and the fresh-import test would pass having checked nothing.
    A package that re-exports a submodule and the submodule it re-exports
    (which initializes the package first) are the simplest real cycle.
    """
    package = "vultron.core.behaviors.inbox"
    (cycle,) = [c for c in _components(_import_graph()) if package in c]
    assert f"{package}._process_payload" in cycle


def _run_driver(
    graph: dict[str, list[str]], extra_path: Path | None = None
) -> dict[str, str]:
    """Run the driver on *graph* and return its failures."""
    env = dict(os.environ)
    if extra_path is not None:
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in (str(extra_path), env.get("PYTHONPATH", "")) if p
        )
    proc = subprocess.run(
        [sys.executable, str(_DRIVER)],
        input=json.dumps(graph),
        capture_output=True,
        text=True,
        cwd=_corpus.REPO_ROOT,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    failures: dict[str, str] = json.loads(proc.stdout.strip().splitlines()[-1])
    return failures


def _write_cycle_package(root: Path, extra: dict[str, str]) -> None:
    """A package whose ``a``/``b`` cycle imports only when entered at ``a``.

    Entered at ``b``, ``b`` imports ``a``, which asks the half-initialized
    ``b`` for ``B`` before ``b`` has defined it.
    """
    package = root / "cyc"
    package.mkdir()
    files = {
        "__init__.py": "",
        "a.py": "from cyc.b import B\n\nA = 1\n",
        "b.py": "from cyc import a\n\nB = 1\n",
        **extra,
    }
    for name, text in files.items():
        (package / name).write_text(text)


def test_driver_reports_a_cycle_that_fails_only_from_one_entry(tmp_path):
    """The driver enters a cycle at each member, not once in walk order."""
    _write_cycle_package(tmp_path, {})
    graph = {"cyc": [], "cyc.a": ["cyc", "cyc.b"], "cyc.b": ["cyc", "cyc.a"]}

    failures = _run_driver(graph, extra_path=tmp_path)

    assert set(failures) == {"cyc.b"}
    assert "partially initialized module 'cyc.b'" in failures["cyc.b"]


def test_driver_still_checks_a_cycle_an_unseen_edge_preloaded(tmp_path):
    """A runtime import the graph misses costs time, never coverage.

    ``cyc.c`` loads the cycle through ``importlib``, which no static scan sees,
    and it is walked first — so the cycle is already loaded when the driver
    reaches it, and only a brand-new interpreter can still enter it at ``b``.
    """
    _write_cycle_package(
        tmp_path,
        {"c.py": "import importlib\n\nimportlib.import_module('cyc.a')\n"},
    )
    graph = {
        "cyc": [],
        "cyc.a": ["cyc", "cyc.b"],
        "cyc.b": ["cyc", "cyc.a"],
        "cyc.c": ["cyc"],
    }

    failures = _run_driver(graph, extra_path=tmp_path)

    assert set(failures) == {"cyc.b"}


# Integration tier: one fork per member of every import cycle in vultron/
# costs tens of seconds (about 30s measured on a loaded 12-core machine), too
# much for the unit suite's ~1 minute budget; the CI full suite (`-m ""`) runs
# it.  The explicit ceiling exists because the fork fan-out scales with core
# count, and a 4-core CI runner can take several times as long as that.
@pytest.mark.integration
@pytest.mark.timeout(240)
def test_every_vultron_module_imports_in_a_fresh_interpreter():
    """No module raises when it is the first of its import cycle to load."""
    failures = _run_driver(_import_graph())
    assert not failures, "\n\n".join(
        f"{module} does not import when loaded first:\n{error}"
        for module, error in sorted(failures.items())
    )
