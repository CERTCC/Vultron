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


def _discovers_submodules(tree: ast.Module) -> bool:
    """Whether a package's code calls ``pkgutil.iter_modules`` anywhere.

    The ``vocab`` packages import every submodule at import time this way, so
    no static import names the edge.  The call may sit in a function the
    package body calls, so the whole tree is searched; a package that only
    calls it later costs a merged cycle, never coverage.
    """
    return any(
        isinstance(node, ast.Attribute) and node.attr == "iter_modules"
        for node in ast.walk(tree)
    )


def _import_graph() -> dict[str, list[str]]:
    """Map each ``vultron`` module to the ``vultron`` modules it imports.

    An over-approximation is safe — it only merges cycles the driver then
    checks more thoroughly.  A module's parent package counts as an edge,
    because Python initializes ``a.b`` before it runs ``a.b.c``.  A package
    that discovers its submodules (:func:`_discovers_submodules`) has an edge
    to each of them.  Without it, the walk loads a cycle under that package
    before it reaches the cycle, and the driver checks every member of that
    cycle in a brand-new interpreter, tens of times the cost of a fork
    (#5932).
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
        if is_package and _discovers_submodules(tree):
            edges.update(
                module
                for module in modules
                if module.rpartition(".")[0] == name
            )
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


def test_import_graph_sees_a_package_that_discovers_its_submodules():
    """A package that imports its submodules at runtime shares their cycle.

    ``vultron.wire.as2.vocab.activities`` imports every submodule through
    ``pkgutil.iter_modules``.  Without that edge the ``case`` cycle under it
    is already loaded when the walk reaches it, and each of its members costs
    a brand-new interpreter instead of a fork (#5932).
    """
    package = "vultron.wire.as2.vocab.activities"
    (cycle,) = [c for c in _components(_import_graph()) if package in c]
    assert f"{package}.case" in cycle


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


#: A frame only a brand-new ``python -c`` interpreter's traceback carries.
_FRESH_FRAME = 'File "<string>"'

#: A module that loads the probe cycle through ``importlib``, which no static
#: scan sees.
_LOADER = "import importlib\n\nimportlib.import_module('cyc.a')\n"


def test_driver_still_checks_a_cycle_an_unseen_edge_preloaded(tmp_path):
    """A runtime import the graph misses costs time, never coverage.

    ``cyc.c`` loads the cycle through ``importlib``.  The graph says ``cyc.a``
    imports ``cyc.c``, so the driver loads ``cyc.c`` before it enters the
    cycle, and finds the cycle already loaded; only a brand-new interpreter
    can still enter it at ``b``, and that route's traceback says so.
    """
    _write_cycle_package(tmp_path, {"c.py": _LOADER})
    graph = {
        "cyc": [],
        "cyc.a": ["cyc", "cyc.b", "cyc.c"],
        "cyc.b": ["cyc", "cyc.a"],
        "cyc.c": ["cyc"],
    }

    failures = _run_driver(graph, extra_path=tmp_path)

    assert set(failures) == {"cyc.b"}
    assert _FRESH_FRAME in failures["cyc.b"]


def test_a_module_no_cycle_imports_waits_until_the_cycles_are_checked(
    tmp_path,
):
    """A module that loads a cycle at runtime cannot preload it (#5932).

    ``cyc._loader`` sorts before the cycle and no cycle member imports it, so
    a walk that loaded every module in order ran it first, found the cycle
    loaded, and paid a brand-new interpreter per member.  Loaded last, it
    leaves the cycle to forked children.
    """
    _write_cycle_package(tmp_path, {"_loader.py": _LOADER})
    graph = {
        "cyc": [],
        "cyc._loader": ["cyc"],
        "cyc.a": ["cyc", "cyc.b"],
        "cyc.b": ["cyc", "cyc.a"],
    }

    failures = _run_driver(graph, extra_path=tmp_path)

    assert set(failures) == {"cyc.b"}
    assert _FRESH_FRAME not in failures["cyc.b"]


def test_a_cycle_another_cycles_dependency_loaded_is_forked_on_recheck(
    tmp_path,
):
    """The recheck pass forks a cycle the walk found loaded (#5932).

    The ``_p``/``_q`` cycle sorts first and imports ``cyc.loader``, which
    loads the ``a``/``b`` cycle at runtime, so the walk finds that cycle
    already loaded.  It is not one of that cycle's own dependencies, so the
    recheck pass, which loads only those, enters the cycle in forked children
    rather than one brand-new interpreter per member.
    """
    _write_cycle_package(
        tmp_path, {"_p.py": "", "_q.py": "", "loader.py": _LOADER}
    )
    graph = {
        "cyc": [],
        "cyc._p": ["cyc", "cyc._q", "cyc.loader"],
        "cyc._q": ["cyc", "cyc._p"],
        "cyc.loader": ["cyc"],
        "cyc.a": ["cyc", "cyc.b"],
        "cyc.b": ["cyc", "cyc.a"],
    }

    failures = _run_driver(graph, extra_path=tmp_path)

    assert set(failures) == {"cyc.b"}
    assert _FRESH_FRAME not in failures["cyc.b"]


def test_a_recheck_pass_that_crashes_fails_each_cycle_it_held():
    """A crashed recheck pass fails its cycles; it never passes them unchecked.

    The graph names a module it has no entry for, so the recheck pass dies
    building its components.
    """
    failures = _fresh_import_driver._recheck({"m": ["n"]}, [["m", "n"]], 1)

    assert list(failures) == ["m"]
    assert failures["m"].startswith("recheck pass failed:")
    assert "KeyError" in failures["m"]


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

#: How long the one slow probe member is "being imported": long enough that
#: the other slot imports several fast members meanwhile.
_SLOW_PROBE_SECONDS = 1.5


def _write_concurrency_probe(
    root: Path, log: Path, slow: str | None = None
) -> dict[str, list[str]]:
    """A declared cycle whose members record when each was being imported.

    Returns the graph to hand the driver.  The edges are the driver's input
    data, so the modules need not import one another to be one strongly
    connected component — which keeps each member's body nothing but the
    record-sleep-record the probe measures.  The *slow* member, if named,
    sleeps :data:`_SLOW_PROBE_SECONDS` instead.
    """
    package = root / "probe"
    package.mkdir()
    (package / "__init__.py").write_text("")
    for member in _PROBE_MEMBERS:
        seconds = _SLOW_PROBE_SECONDS if member == slow else _PROBE_SECONDS
        body = (
            "import os, time\n"
            "\n"
            "\n"
            "def _mark(edge):\n"
            "    with open(os.environ['PROBE_LOG'], 'a') as out:\n"
            "        out.write(f'{time.monotonic_ns()} {edge} {__name__}\\n')\n"
            "\n"
            "\n"
            "_mark('enter')\n"
            f"time.sleep({seconds})\n"
            "_mark('leave')\n"
        )
        (package / f"{member}.py").write_text(body)
    log.write_text("")
    ring = list(_PROBE_MEMBERS)
    graph: dict[str, list[str]] = {"probe": []}
    for index, member in enumerate(ring):
        following = ring[(index + 1) % len(ring)]
        graph[f"probe.{member}"] = ["probe", f"probe.{following}"]
    return graph


def _probe_events(log: Path) -> list[tuple[int, str, str]]:
    """The probe log's ``(stamp, edge, module)`` records, oldest first."""
    return sorted(
        (int(stamp), edge, module)
        for stamp, edge, module in (
            line.split() for line in log.read_text().splitlines() if line
        )
    )


def _peak_overlap(log: Path) -> int:
    """The most probe modules that were being imported at the same moment."""
    running = peak = 0
    for _, edge, _ in _probe_events(log):
        running += 1 if edge == "enter" else -1
        peak = max(peak, running)
    return peak


def _overlapping(log: Path, module: str) -> set[str]:
    """The other probe modules a child imported while *module*'s child did.

    Only each module's first span counts: that is its child's.  The driver
    imports the whole cycle itself afterwards, one module at a time.
    """
    spans: dict[str, list[int]] = {}
    for stamp, _, name in _probe_events(log):
        spans.setdefault(name, []).append(stamp)
    start, end = spans[module][:2]
    return {
        name
        for name, (enter, leave, *_) in spans.items()
        if name != module and enter < end and leave > start
    }


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


def test_a_slow_child_does_not_hold_the_other_slots_idle(
    tmp_path, monkeypatch
):
    """A slot that frees starts the next member at once (#5932).

    Run in batches, the slow first member shared its time with one batch-mate
    only, and the other slot sat idle until the slow one ended.  With the
    slots kept full, several fast members import while the slow one does.
    """
    log = tmp_path / "probe.log"
    graph = _write_concurrency_probe(tmp_path, log, slow="m0")
    monkeypatch.setenv("PROBE_LOG", str(log))

    assert _run_driver(graph, extra_path=tmp_path, at_once=2) == {}

    assert _peak_overlap(log) == 2
    assert len(_overlapping(log, "probe.m0")) >= 2


# Integration tier: one fork per member of every import cycle in vultron/
# costs minutes on a small host, too much for the unit suite's ~1 minute
# budget; the CI full suite (`-m ""`) runs it.  Measured in a 6-CPU slot on a
# shared 16-core host (#5932): 125s alone, and 148s beside the rest of
# `test/architecture/` and `test/metadata/` under `-n auto`.  Before #5932 it
# took 245s alone, over half of that in brand-new interpreters for cycles the
# walk had already loaded, and it hit this ceiling under load every time.  The
# ceiling is explicit because the cost is child import time, which a loaded
# or small CI runner stretches; the fan-out is bounded by
# `child_process_budget` (#5184).
@pytest.mark.integration
@pytest.mark.timeout(240)
def test_every_vultron_module_imports_in_a_fresh_interpreter():
    """No module raises when it is the first of its import cycle to load."""
    failures = _run_driver(_import_graph())
    assert not failures, "\n\n".join(
        f"{module} does not import when loaded first:\n{error}"
        for module, error in sorted(failures.items())
    )
