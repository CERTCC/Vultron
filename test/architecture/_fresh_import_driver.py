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

How many children at once
-------------------------
Both child routes run in batches of at most ``sys.argv[1]`` children, which
the caller sizes from the memory one xdist worker is budgeted
(``test.support.xdist_workers.child_process_budget``).  The bound is the
caller's because only the caller knows it is one of several workers spending
the same container; the driver's own default, used when it is run by hand, is
one child per CPU.  Sizing it here from ``os.cpu_count()`` ran as many children
as the host had cores no matter how little of the host this process could use,
and the brand-new-interpreter route ran strictly one at a time, which together
left the test both the heaviest process in the container and near its own
wall-clock ceiling (#5184).
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


def max_children(argv: list[str]) -> int:
    """How many children to run at once: the caller's bound, else one per CPU.

    The default is only for a hand run of the script; the test always states a
    bound (see "How many children at once" above, #5184).
    """
    if len(argv) > 1:
        return max(1, int(argv[1]))
    return os.cpu_count() or 1


def _forked_imports(members: list[str], at_once: int) -> dict[str, str]:
    """Import each member first, each in a child forked from this process."""
    failures: dict[str, str] = {}
    for start in range(0, len(members), at_once):
        children: list[tuple[str, int, int]] = []
        for module in members[start : start + at_once]:
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


def _fresh_imports(members: list[str], at_once: int) -> dict[str, str]:
    """Import each member first, each in a brand-new interpreter.

    Batched like the forked route, rather than one at a time: a brand-new
    interpreter re-imports pydantic and fastapi before it reaches the module,
    so this route cost ~2.7s per member and dominated the test's runtime at a
    third of its members, leaving almost no headroom under its own timeout
    (#5184).  Only ``at_once`` of them exist at any moment, so the bound this
    route gains is the same one the forked route loses.
    """
    failures: dict[str, str] = {}
    for start in range(0, len(members), at_once):
        batch = [
            (
                module,
                subprocess.Popen(
                    [sys.executable, "-c", f"import {module}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                ),
            )
            for module in members[start : start + at_once]
        ]
        # One ``communicate`` per child, in order.  A later child could in
        # principle fill its stderr pipe and block while an earlier one is
        # still being read, but the only thing written there is one traceback.
        for module, proc in batch:
            _, errors = proc.communicate()
            if proc.returncode != 0:
                failures[module] = errors
    return failures


def main() -> int:
    """Walk the import graph on stdin and report every failing module."""
    graph: dict[str, list[str]] = json.load(sys.stdin)
    # ``_components`` recurses once per module on an import chain, and that
    # chain can be as deep as the package has modules.  Raised here, in the
    # driver's own process, never in a caller's: the limit is process-global.
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4 * len(graph) + 100))
    at_once = max_children(sys.argv)
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
                failures.update(_fresh_imports(component, at_once))
            else:
                failures.update(_forked_imports(component, at_once))
        for module in component:
            if module not in failures and (error := _import(module)):
                failures[module] = error
    print(json.dumps(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
