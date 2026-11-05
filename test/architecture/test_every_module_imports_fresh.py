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

from test.architecture import _corpus, _fresh_import_driver
from test.architecture._fresh_import_driver import _components
from test.support.child_env import child_env
from test.support.xdist_workers import child_process_budget

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
    graph: dict[str, list[str]],
    extra_path: Path | None = None,
    at_once: int | None = None,
) -> dict[str, str]:
    """Run the driver on *graph* and return its failures.

    The child bound is passed in, not left to the driver: this process is one
    xdist worker among several spending the same container, so the fan-out is
    sized from the memory one worker is budgeted rather than from the host's
    cores (#5184).
    """
    bound = child_process_budget() if at_once is None else at_once
    extra = () if extra_path is None else (extra_path,)
    proc = subprocess.run(
        [sys.executable, str(_DRIVER), str(bound)],
        input=json.dumps(graph),
        capture_output=True,
        text=True,
        cwd=_corpus.REPO_ROOT,
        env=child_env(*extra),
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


def test_driver_imports_this_checkouts_vultron_whatever_pythonpath_names(
    tmp_path, monkeypatch
):
    """An inherited ``PYTHONPATH`` naming another checkout never wins (#5456).

    The driver runs as a script, so its first ``sys.path`` entry is its own
    directory, not the repository root; a ``vultron`` on the inherited path
    would shadow this checkout's and fail every module the other one lacks.
    """
    other = tmp_path / "other-checkout" / "vultron"
    other.mkdir(parents=True)
    (other / "__init__.py").write_text(
        "raise ImportError('imported another checkout')\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(other.parent))

    assert _run_driver({"vultron": []}) == {}


def test_max_children_takes_the_bound_the_caller_states():
    """The caller's bound wins, and a bound below one is still one child."""
    assert _fresh_import_driver.max_children(["driver", "3"]) == 3
    assert _fresh_import_driver.max_children(["driver", "0"]) == 1


def test_max_children_falls_back_to_one_per_cpu_for_a_hand_run():
    """Run by hand with no bound, the driver sizes itself from the CPUs."""
    assert _fresh_import_driver.max_children(["driver"]) == (
        os.cpu_count() or 1
    )


#: How long each probe module stays "being imported".  Long enough that two
#: children forked back to back overlap on any machine, short enough that the
#: whole probe fits the unit tier's 30s ceiling.
_PROBE_SECONDS = 0.2

#: Members of the probe cycle.  More than the largest bound under test, so a
#: bound that is ignored shows up as a wider overlap rather than one batch.
_PROBE_MEMBERS = ("m0", "m1", "m2", "m3", "m4", "m5")


def _write_concurrency_probe(root: Path, log: Path) -> dict[str, list[str]]:
    """A declared cycle whose members record when each was being imported.

    Returns the graph to hand the driver.  The edges are the driver's input
    data, so the modules need not import one another to be one strongly
    connected component — which keeps each member's body nothing but the
    record-sleep-record the probe measures.
    """
    package = root / "probe"
    package.mkdir()
    (package / "__init__.py").write_text("")
    body = (
        "import os, time\n"
        "\n"
        "\n"
        "def _mark(edge):\n"
        "    with open(os.environ['PROBE_LOG'], 'a') as out:\n"
        "        out.write(f'{time.monotonic_ns()} {edge}\\n')\n"
        "\n"
        "\n"
        "_mark('enter')\n"
        f"time.sleep({_PROBE_SECONDS})\n"
        "_mark('leave')\n"
    )
    for member in _PROBE_MEMBERS:
        (package / f"{member}.py").write_text(body)
    log.write_text("")
    ring = list(_PROBE_MEMBERS)
    graph: dict[str, list[str]] = {"probe": []}
    for index, member in enumerate(ring):
        following = ring[(index + 1) % len(ring)]
        graph[f"probe.{member}"] = ["probe", f"probe.{following}"]
    return graph


def _peak_overlap(log: Path) -> int:
    """The most probe modules that were being imported at the same moment."""
    events = sorted(
        (int(stamp), edge)
        for stamp, edge in (
            line.split() for line in log.read_text().splitlines() if line
        )
    )
    running = peak = 0
    for _, edge in events:
        running += 1 if edge == "enter" else -1
        peak = max(peak, running)
    return peak


@pytest.mark.parametrize("at_once", [1, 2])
def test_the_driver_forks_no_more_children_than_the_bound(
    tmp_path, monkeypatch, at_once
):
    """The bound holds, and it is reached (#5184).

    Before the fix the fan-out was ``os.cpu_count()``, so a sixteen-core host
    ran sixteen children beside its sixteen xdist workers however little of
    that host the container allowed.  Both halves are asserted: a bound that
    is ignored shows a wider overlap, and a driver that lost its concurrency
    altogether shows a narrower one.
    """
    log = tmp_path / "probe.log"
    graph = _write_concurrency_probe(tmp_path, log)
    monkeypatch.setenv("PROBE_LOG", str(log))

    assert _run_driver(graph, extra_path=tmp_path, at_once=at_once) == {}

    assert _peak_overlap(log) == at_once


# Integration tier: one fork per member of every import cycle in vultron/
# costs tens of seconds (about 30s measured on a loaded 12-core machine), too
# much for the unit suite's ~1 minute budget; the CI full suite (`-m ""`) runs
# it.  The ceiling is explicit because the cost is dominated by child process
# start-up, which a loaded or small CI runner stretches well past the measured
# figure; the fan-out itself is bounded by `child_process_budget` (#5184).
@pytest.mark.integration
@pytest.mark.timeout(240)
def test_every_vultron_module_imports_in_a_fresh_interpreter():
    """No module raises when it is the first of its import cycle to load."""
    failures = _run_driver(_import_graph())
    assert not failures, "\n\n".join(
        f"{module} does not import when loaded first:\n{error}"
        for module, error in sorted(failures.items())
    )
