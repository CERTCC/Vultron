"""Import every ``vultron`` module as the first module of its import cycle.

Run as a script by ``test_every_module_imports_fresh.py``, so the interpreter
it runs in has loaded nothing under ``vultron`` when it starts.  (The test
imports it only to check ``_components``; importing it has no side effects.)
Its input on stdin is a JSON object mapping every module name to the
``vultron`` modules its top-level code imports (the test builds that graph
from ``_corpus``).  Its output on stdout is a JSON object
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
order Tarjan's algorithm emits them in).  Before it loads a component with more
than one member, it loads the modules that component imports, directly or not,
and nothing else; then it forks one child per member, and each child imports
that member first: from the component's point of view, an interpreter that has
never seen it.  Every module no cycle imports waits for a last pass at the end,
after the last cycle is checked.

The static graph can miss a runtime edge (``importlib``, a module-level call
into a function that imports).  Then a component is already loaded by the time
the driver reaches it, which would make its children vacuous.  The driver
checks for exactly that, and checks such a component again in the recheck pass
below, so a missed edge costs time, never coverage.  Once a module has started
a thread, it imports each member in a brand-new interpreter instead, since
forking a multi-threaded process is unsafe.

The recheck pass
----------------
A brand-new interpreter costs tens of times what a fork does per member,
because it imports pydantic, fastapi and the cycle's dependencies all over
again.  In plain walk order, ``vultron.demo.cli`` (which the fuzzer's cycle
imports) loaded the demo helpers' cycles through the scenario registry before
the walk reached them, and brand-new interpreters took over half the run
(#5932).  So the driver
defers each cycle it finds already loaded.  After the walk, it runs itself once
more as a recheck pass (``--recheck`` and the first member of each deferred
cycle).  That pass loads only those cycles and their own dependencies, so a
module some other cycle needed does not load them first, and it forks each
cycle's children as usual.  Only a cycle that its own dependencies load at
runtime is still loaded there, and only then does each of its members get a
brand-new interpreter.

How many children at once
-------------------------
Both child routes keep at most ``sys.argv[1]`` children running, which
the caller sizes from the memory one xdist worker is budgeted
(``test.support.xdist_workers.child_process_budget``).  The bound is the
caller's because only the caller knows it is one of several workers spending
the same container; the driver's own default, used when it is run by hand, is
one child per CPU.  Sizing it here from ``os.cpu_count()`` ran as many children
as the host had cores no matter how little of the host this process could use,
and the brand-new-interpreter route ran strictly one at a time, which together
left the test both the heaviest process in the container and near its own
wall-clock ceiling (#5184).  A new child starts as soon as one ends, rather
than in batches that wait for their slowest member: with batches, a slot sat
idle whenever one member of a cycle imported slower than the rest (#5932).
The recheck pass is one more driver with the package loaded, alive beside
this one while its children run, so it is given one child fewer than this
driver was.
"""

import json
import os
import selectors
import subprocess
import sys
import threading
import traceback
from collections.abc import Callable

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


#: A started child: the read end of its report pipe, and a call that reaps it
#: and returns its failure, if any, given everything it wrote to that pipe.
_Child = tuple[int, Callable[[str], str | None]]


def _run_children(
    members: list[str], at_once: int, start: Callable[[str], _Child]
) -> dict[str, str]:
    """Run ``start(member)`` for every member, at most *at_once* at a time.

    Each child's pipe is read as it writes, so none blocks on a full pipe, and
    a child is reaped once its pipe closes.  The next member starts as soon as
    a child ends.
    """
    failures: dict[str, str] = {}
    waiting = list(reversed(members))
    reports: dict[int, list[bytes]] = {}
    with selectors.DefaultSelector() as selector:
        while waiting or reports:
            while waiting and len(reports) < at_once:
                module = waiting.pop()
                read_fd, reap = start(module)
                reports[read_fd] = []
                selector.register(
                    read_fd, selectors.EVENT_READ, (module, reap)
                )
            for key, _ in selector.select():
                chunk = os.read(key.fd, 65536)
                if chunk:
                    reports[key.fd].append(chunk)
                    continue
                selector.unregister(key.fd)
                os.close(key.fd)
                module, reap = key.data
                report = b"".join(reports.pop(key.fd)).decode(errors="replace")
                if (error := reap(report)) is not None:
                    failures[module] = error
    return failures


def _fork_child(module: str) -> _Child:
    """Import *module* first in a child forked from this process."""
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

    def reap(report: str) -> str | None:
        _, status = os.waitpid(pid, 0)
        if report:
            return report
        return f"child exited with status {status}" if status != 0 else None

    return read_fd, reap


def _forked_imports(members: list[str], at_once: int) -> dict[str, str]:
    """Import each member first, each in a child forked from this process."""
    return _run_children(members, at_once, _fork_child)


def _interpreter_child(module: str) -> _Child:
    """Import *module* in a brand-new interpreter; its report is its stderr."""
    proc = subprocess.Popen(
        [sys.executable, "-c", f"import {module}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert proc.stderr is not None
    # The selector owns the descriptor from here; the file object must not
    # close it a second time.
    read_fd = os.dup(proc.stderr.fileno())
    proc.stderr.close()

    def reap(report: str) -> str | None:
        return report if proc.wait() != 0 else None

    return read_fd, reap


def _fresh_imports(members: list[str], at_once: int) -> dict[str, str]:
    """Import each member first, each in a brand-new interpreter.

    Run under the same bound as the forked route, rather than one at a time:
    a brand-new interpreter re-imports pydantic and fastapi before it reaches
    the module, so this route cost ~2.7s per member and dominated the test's
    runtime at a third of its members, leaving almost no headroom under its
    own timeout (#5184).  Only ``at_once`` of them exist at any moment, so the
    bound this route gains is the same one the forked route loses.
    """
    return _run_children(members, at_once, _interpreter_child)


def _unloaded_dependencies(
    graph: dict[str, list[str]], component: list[str], order: dict[str, int]
) -> list[str]:
    """The modules *component* imports, directly or not, that are not loaded.

    Dependencies first, in walk *order*, so each one is imported after the
    modules it imports.  A loaded module is not searched past: Python loaded
    what it imports along with it.
    """
    members = set(component)
    found: set[str] = set()
    todo = [d for m in component for d in graph[m]]
    while todo:
        module = todo.pop()
        if module in members or module in found or module in sys.modules:
            continue
        found.add(module)
        todo.extend(graph[module])
    return sorted(found, key=order.__getitem__)


#: The flag that makes the driver a recheck pass, followed by the first
#: member of each cycle it is to check (see "The recheck pass" above).
_RECHECK = "--recheck"


def _must_not_fork() -> bool:
    """Whether a module has started a thread, which makes forking unsafe.

    Forking a process that runs other threads copies only the forking thread,
    so a lock another thread held stays held in the child forever.
    """
    return threading.active_count() > 1


def _recheck(
    graph: dict[str, list[str]], cycles: list[list[str]], at_once: int
) -> dict[str, str]:
    """Check *cycles* in a recheck pass: a new driver that loaded nothing."""
    proc = subprocess.run(
        [sys.executable, __file__, str(at_once), _RECHECK]
        + [cycle[0] for cycle in cycles],
        input=json.dumps(graph),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {c[0]: f"recheck pass failed:\n{proc.stderr}" for c in cycles}
    failures: dict[str, str] = json.loads(proc.stdout.strip().splitlines()[-1])
    return failures


class _Walk:
    """One pass over the import graph, and the failures it has found."""

    def __init__(self, graph: dict[str, list[str]], at_once: int) -> None:
        self.graph = graph
        self.at_once = at_once
        self.components = _components(graph)
        self.order = {
            m: i for i, m in enumerate(m for c in self.components for m in c)
        }
        self.failures: dict[str, str] = {}

    def load(self, module: str) -> None:
        """Import *module* here, recording a failure."""
        if module not in self.failures and (error := _import(module)):
            self.failures[module] = error

    def check(self, cycle: list[str], last_chance: bool) -> bool:
        """Enter *cycle* at each member; ``False`` if it was deferred.

        Its dependencies are loaded first, and its members after.  A cycle
        found already loaded is deferred to the recheck pass, unless this is
        that pass (*last_chance*), which uses brand-new interpreters instead.
        """
        for module in _unloaded_dependencies(self.graph, cycle, self.order):
            self.load(module)
        loaded = any(m in sys.modules for m in cycle)
        if loaded and not last_chance and not _must_not_fork():
            return False
        if loaded or _must_not_fork():
            self.failures.update(_fresh_imports(cycle, self.at_once))
        else:
            self.failures.update(_forked_imports(cycle, self.at_once))
        for module in cycle:
            self.load(module)
        return True


def _preload() -> None:
    for name in _PRELOAD:
        try:
            __import__(name)
        except ImportError:
            pass


def main() -> int:
    """Walk the import graph on stdin and report every failing module."""
    graph: dict[str, list[str]] = json.load(sys.stdin)
    # ``_components`` recurses once per module on an import chain, and that
    # chain can be as deep as the package has modules.  Raised here, in the
    # driver's own process, never in a caller's: the limit is process-global.
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4 * len(graph) + 100))
    _preload()
    walk = _Walk(graph, max_children(sys.argv))
    cycles = [c for c in walk.components if len(c) > 1]
    if sys.argv[2:3] == [_RECHECK]:
        for cycle in cycles:
            if cycle[0] in sys.argv[3:]:
                walk.check(cycle, last_chance=True)
    else:
        deferred = [c for c in cycles if not walk.check(c, last_chance=False)]
        for module in walk.order:
            walk.load(module)
        if deferred:
            # The recheck pass is itself a driver that stays in memory beside
            # this one, so it takes one child slot (see "How many children at
            # once" above).
            at_once = max(1, walk.at_once - 1)
            walk.failures.update(_recheck(graph, deferred, at_once))
    print(json.dumps(walk.failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
