"""Import every ``vultron`` module as the first module of its import cycle.

Run as a script by ``test_every_module_imports_fresh.py``, so the interpreter
it runs in has loaded nothing under ``vultron`` when it starts.  (The test
imports it only to check ``_components``; importing it has no side effects.)  Its input on stdin is a JSON object mapping every
module name to the ``vultron`` modules its top-level code imports (the test
builds that graph from ``_corpus``).  Its output on stdout is a JSON object
mapping each module that failed to import to the formatted exception — ``{}``
when every module imports.

Why not one interpreter per module
----------------------------------
A deferred import that is hoisted (CS-05-002) can close an import cycle that
only resolves when the cycle is entered at one particular module, so pytest's
own collection order proves nothing.  Importing each module in its own new
interpreter would catch that, but every module would then re-import most of
the package and the check would take minutes.

Order only matters *inside* a strongly connected component of the import
graph.  Every module a component imports from outside it is fully initialized
before the component is entered, whichever member is entered first, and no
module outside it can be part-way through initializing — if such a module
imported the component and the component imported it back, it would be inside
the component.  So the driver walks the components dependencies-first (the
order Tarjan's algorithm emits them in), keeping everything already walked
loaded in this process.  Before loading a component with more than one member,
it forks one child per member, and each child imports that member first: from
the component's point of view, an interpreter that has never seen it.

The static graph can miss a runtime edge (``importlib``, a module-level call
into a function that imports).  Then a component is already loaded by the time
the driver reaches it, which would make its children vacuous.  The driver
checks for exactly that, and imports such a component's members in brand-new
interpreters instead, so a missed edge costs time, never coverage.
It does the same once a module has started a thread, since forking a
multi-threaded process is unsafe.
"""

import json
import os
import subprocess
import sys
import threading
import traceback

#: Third-party packages imported before the walk.  They are outside every
#: ``vultron`` cycle, and loading them once keeps each child cheap.
_PRELOAD = ("pydantic", "fastapi", "py_trees", "yaml", "httpx")

#: How many innermost frames of an import traceback to report.
_TRACEBACK_TAIL_FRAMES = 8


def _components(graph: dict[str, list[str]]) -> list[list[str]]:
    """Return the graph's strongly connected components, dependencies first.

    Tarjan's algorithm emits a component only after every component it has an
    edge into, which is exactly the order a dependency-first walk needs.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    components: list[list[str]] = []

    def visit(node: str) -> None:
        index[node] = low[node] = len(index)
        stack.append(node)
        for nxt in sorted(graph[node]):
            if nxt not in index:
                visit(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in stack:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            cut = stack.index(node)
            components.append(sorted(stack[cut:]))
            del stack[cut:]

    for root in sorted(graph):
        if root not in index:
            visit(root)
    return components


def _import(module: str) -> str | None:
    """Import *module* here; return the formatted failure, if any."""
    try:
        __import__(module)
    except BaseException:  # noqa: BLE001 - reported to the parent
        return traceback.format_exc(limit=-_TRACEBACK_TAIL_FRAMES)
    return None


def _forked_imports(members: list[str]) -> dict[str, str]:
    """Import each member first, each in a child forked from this process."""
    failures: dict[str, str] = {}
    max_children = os.cpu_count() or 1
    for start in range(0, len(members), max_children):
        children: list[tuple[str, int, int]] = []
        for module in members[start : start + max_children]:
            read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:  # child
                # A child must never return into the parent's loop, so every
                # path, including one that raises, ends in ``os._exit``.
                code = 1
                try:
                    os.close(read_fd)
                    error = _import(module) or ""
                    with os.fdopen(write_fd, "w") as out:
                        out.write(error)
                    code = 0
                finally:
                    os._exit(code)
            os.close(write_fd)
            children.append((module, pid, read_fd))
        for module, pid, read_fd in children:
            with os.fdopen(read_fd) as result:
                error = result.read()
            _, status = os.waitpid(pid, 0)
            if error:
                failures[module] = error
            elif status != 0:
                failures[module] = f"child exited with status {status}"
    return failures


def _fresh_imports(members: list[str]) -> dict[str, str]:
    """Import each member first, each in a brand-new interpreter."""
    failures: dict[str, str] = {}
    for module in members:
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            failures[module] = proc.stderr
    return failures


def main() -> int:
    """Walk the import graph on stdin and report every failing module."""
    graph: dict[str, list[str]] = json.load(sys.stdin)
    # ``_components`` recurses once per module on an import chain, and that
    # chain can be as deep as the package has modules.  Raised here, in the
    # driver's own process, never in a caller's: the limit is process-global.
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4 * len(graph) + 100))
    for name in _PRELOAD:
        try:
            __import__(name)
        except ImportError:
            pass
    failures: dict[str, str] = {}
    for component in _components(graph):
        if len(component) > 1:
            # Forking a process that runs other threads copies only the
            # forking thread, so a lock another thread held stays held in
            # the child forever; a module that started a thread on import
            # sends the rest of the walk to fresh interpreters instead.
            if threading.active_count() > 1 or any(
                m in sys.modules for m in component
            ):
                failures.update(_fresh_imports(component))
            else:
                failures.update(_forked_imports(component))
        for module in component:
            if module not in failures and (error := _import(module)):
                failures[module] = error
    print(json.dumps(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
