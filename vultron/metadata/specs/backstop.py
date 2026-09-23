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
"""Deterministic backstop for an agent's spec selection (``spec-backstop``).

From the changes on a branch, compute which spec groups plausibly govern the
changed code, and check them against the agent's Spec manifest::

    spec-backstop                                  # diff vs origin/main
    spec-backstop --base main --manifest manifest.txt
    spec-backstop --paths vultron/core/foo.py --json

Exit codes: 0 = no manifest given or every MUST-tier group resolved;
1 = unresolved MUST-tier groups; 2 = setup error.

Requirements: specs/spec-registry.yaml SR-12.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess  # nosec B404 - runs fixed git commands only
import sys
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from vultron.metadata.base import repo_root
from vultron.metadata.specs.registry import load_registry

SOURCE_PREFIX = "vultron/"
TEST_PREFIX = "test/"
MAX_EVIDENCE = 3
#: A changed symbol imported by more test files than this is a hub: its
#: import hits go to INFO, because nearly every test would otherwise be MUST.
HUB_THRESHOLD = 10

_HUNK_RE = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_CAMEL_RE = re.compile(r"[a-z][A-Z]")
_REQ_RE = re.compile(r"^[A-Z]+-\d\d-\d{3}$")
_GROUP_RE = re.compile(r"^[A-Z]+-\d\d$")
_ID_RUN_RE = re.compile(r"\s*((?:[A-Z]+(?:-\d\d(?:-\d{3})?)?\b\s*)+)")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
_HEADING_RE = re.compile(r"^(Loaded|Considered)\b[^:]*:(.*)$")

_BLOCK_FIELDS = ("body", "orelse", "finalbody", "handlers", "cases")

GitRunner = Callable[[Sequence[str]], str]


class BackstopError(Exception):
    """Setup failure: not a repository, bad ref, unreadable manifest."""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileChange:
    """A changed ``.py`` file; ``lines=None`` means the whole file changed."""

    path: str
    source: str | None
    lines: frozenset[int] | set[int] | None = None


@dataclass(frozen=True)
class TestFile:
    """What one ``test_*.py`` file imports from ``vultron`` and marks."""

    __test__ = False  # not a pytest class

    path: str
    modules: frozenset[str]
    names: frozenset[tuple[str, str]]
    spec_ids: frozenset[str]


@dataclass(frozen=True)
class Requirement:
    """One requirement, flattened for matching."""

    id: str
    group: str
    topic: str
    statement: str


@dataclass
class GroupHit:
    """The requirement IDs and evidence that put a group in a tier."""

    group: str
    topic: str
    reqs: set[str] = field(default_factory=set)
    evidence: set[str] = field(default_factory=set)


@dataclass
class BackstopReport:
    """Result of :func:`analyze`."""

    symbols: dict[str, set[str]]
    must: dict[str, GroupHit]
    info: dict[str, GroupHit]
    no_signal: list[str]
    hubs: dict[str, int] = field(default_factory=dict)
    hub_threshold: int = HUB_THRESHOLD


@dataclass
class Manifest:
    """IDs a Spec manifest lists as loaded or as considered and skipped."""

    loaded: set[str] = field(default_factory=set)
    dismissed: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Diff parsing (SR-12-001)
# ---------------------------------------------------------------------------


def _hunk_lines(line: str) -> set[int]:
    match = _HUNK_RE.match(line)
    if match is None:
        return set()
    start = int(match.group(1))
    count = int(match.group(2) or "1")
    if count == 0:  # pure deletion: mark the line it followed
        return {max(start, 1)}
    return set(range(start, start + count))


def parse_diff_hunks(diff: str) -> tuple[dict[str, set[int]], set[str]]:
    """Parse ``git diff -U0`` output into changed new-side lines per file.

    Returns:
        ``(changed, deleted)``: new-side line numbers per surviving ``.py``
        file, and the paths of deleted ``.py`` files.
    """
    changed: dict[str, set[int]] = {}
    deleted: set[str] = set()
    old_path = current = None
    for line in diff.splitlines():
        if line.startswith("--- "):
            old_path = line[6:] if line.startswith("--- a/") else None
        elif line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
            if current is None and old_path and old_path.endswith(".py"):
                deleted.add(old_path)
            if current is not None and not current.endswith(".py"):
                current = None
        elif current is not None and line.startswith("@@"):
            changed.setdefault(current, set()).update(_hunk_lines(line))
    return changed, deleted


def _run_git(root: Path) -> GitRunner:
    def run(args: Sequence[str]) -> str:
        proc = subprocess.run(  # nosec B603 B607 - fixed git argv
            ["git", *args], cwd=root, capture_output=True, text=True
        )
        if proc.returncode != 0:
            detail = proc.stderr.strip() or f"exit {proc.returncode}"
            raise BackstopError(f"git {' '.join(args)}: {detail}")
        return proc.stdout

    return run


def git_toplevel(cwd: Path) -> Path:
    """Return the git work-tree root containing *cwd*."""
    return Path(_run_git(cwd)(["rev-parse", "--show-toplevel"]).strip())


def collect_git_changes(
    git: GitRunner, root: Path, base: str
) -> list[FileChange]:
    """Collect committed, uncommitted, and untracked ``.py`` changes."""
    merge_base = git(["merge-base", base, "HEAD"]).strip()
    diff = git(
        ["diff", "-U0", "--no-color", "--no-ext-diff", "--no-renames"]
        + [merge_base, "--", "vultron", "test"]
    )
    changed, deleted = parse_diff_hunks(diff)
    changes = [
        FileChange(p, (root / p).read_text(encoding="utf-8"), frozenset(ls))
        for p, ls in changed.items()
    ]
    changes += [
        FileChange(p, git(["show", f"{merge_base}:{p}"])) for p in deleted
    ]
    untracked = git(
        ["ls-files", "--others", "--exclude-standard", "--", "vultron", "test"]
    )
    changes += [
        FileChange(p, (root / p).read_text(encoding="utf-8"))
        for p in untracked.splitlines()
        if p.endswith(".py")
    ]
    return sorted(changes, key=lambda c: c.path)


def changes_from_paths(root: Path, paths: Iterable[str]) -> list[FileChange]:
    """Treat each of *paths* as fully changed (``--paths`` mode)."""
    changes = []
    for raw in paths:
        full = (Path.cwd() / raw).resolve()
        try:
            rel = full.relative_to(root).as_posix()
            source = full.read_text(encoding="utf-8")
        except (ValueError, OSError) as exc:
            raise BackstopError(f"cannot read {raw}: {exc}") from exc
        changes.append(FileChange(rel, source))
    return changes


# ---------------------------------------------------------------------------
# Symbols and markers (SR-12-002)
# ---------------------------------------------------------------------------


def _symbol_names(node: ast.stmt) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names = [node.name]
    elif isinstance(node, ast.Assign):
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        names = [node.target.id]
    else:
        return []
    return [n for n in names if not (n.startswith("__") and n.endswith("__"))]


def _span(node: ast.stmt) -> range:
    decorators = getattr(node, "decorator_list", [])
    start = min([node.lineno] + [d.lineno for d in decorators])
    return range(start, (node.end_lineno or node.lineno) + 1)


def changed_nodes(
    tree: ast.Module, lines: frozenset[int] | set[int] | None
) -> list[ast.stmt]:
    """Top-level symbol nodes whose span intersects *lines* (all if None)."""
    return [
        node
        for node in tree.body
        if _symbol_names(node)
        and (lines is None or any(n in lines for n in _span(node)))
    ]


def changed_symbols(
    tree: ast.Module, lines: frozenset[int] | set[int] | None
) -> set[str]:
    """Names of the top-level symbols changed by *lines* (SR-12-002)."""
    return {
        n for node in changed_nodes(tree, lines) for n in _symbol_names(node)
    }


def _dotted(node: ast.expr) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _statements(body: Iterable[ast.AST]) -> Iterator[ast.AST]:
    """Yield statements in *body* and every nested block, expressions skipped.

    Walking statements only is several times faster than ``ast.walk`` over
    the whole test tree, and imports and markers only occur at this level.
    """
    for node in body:
        yield node
        for attr in _BLOCK_FIELDS:
            child = getattr(node, attr, None)
            if isinstance(child, list):
                yield from _statements(child)


def _marker_exprs(node: ast.AST) -> list[ast.expr]:
    """Decorators, and the value of a ``pytestmark = ...`` assignment."""
    exprs = list(getattr(node, "decorator_list", []))
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
    ):
        exprs.append(node.value)
    return exprs


def _call_spec_ids(expr: ast.expr) -> set[str]:
    return {
        arg.value
        for sub in ast.walk(expr)
        if isinstance(sub, ast.Call)
        and _dotted(sub.func).endswith("mark.spec")
        for arg in sub.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    }


def spec_ids_in(nodes: Iterable[ast.AST]) -> set[str]:
    """IDs in ``pytest.mark.spec(...)`` markers on or within *nodes*."""
    return {
        spec_id
        for node in _statements(nodes)
        for expr in _marker_exprs(node)
        for spec_id in _call_spec_ids(expr)
    }


# ---------------------------------------------------------------------------
# Test index (SR-12-003)
# ---------------------------------------------------------------------------


def _is_vultron(module: str | None) -> bool:
    return module is not None and (
        module == "vultron" or module.startswith("vultron.")
    )


def _vultron_imports(
    tree: ast.Module,
) -> tuple[set[str], set[tuple[str, str]]]:
    modules: set[str] = set()
    names: set[tuple[str, str]] = set()
    for node in _statements(tree.body):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names if _is_vultron(a.name))
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module is not None
            and _is_vultron(node.module)
        ):
            modules.add(node.module)
            for alias in node.names:
                names.add((node.module, alias.name))
                modules.add(f"{node.module}.{alias.name}")
    return modules, names


def index_test_file(path: str, source: str) -> TestFile | None:
    """Index one test file; ``None`` when it does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    modules, names = _vultron_imports(tree)
    return TestFile(
        path,
        frozenset(modules),
        frozenset(names),
        frozenset(spec_ids_in(tree.body)),
    )


def build_test_index(root: Path) -> dict[str, TestFile]:
    """Index every ``test/**/test_*.py`` file under *root*."""
    index = {}
    for file in sorted((root / "test").rglob("test_*.py")):
        rel = file.relative_to(root).as_posix()
        info = index_test_file(rel, file.read_text(encoding="utf-8"))
        if info is not None:
            index[rel] = info
    return index


def module_name(path: str) -> str:
    """Dotted module name for a repo-relative ``.py`` path."""
    parts = PurePosixPath(path).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _module_dir(path: str) -> PurePosixPath:
    """``a/b/c`` for ``vultron/a/b/c.py`` and ``vultron/a/b/c/__init__.py``."""
    rel = PurePosixPath(path).relative_to("vultron")
    return rel.parent if rel.name == "__init__.py" else rel.with_suffix("")


def mirror_tests(path: str, test_paths: Iterable[str]) -> list[str]:
    """Tests at the mirror path of a ``vultron/`` source file."""
    stem = _module_dir(path)
    if str(stem) == ".":
        return []
    flat = PurePosixPath("test") / stem.parent / f"test_{stem.name}.py"
    prefix = f"test/{stem}/"
    return sorted(
        t
        for t in test_paths
        if t == flat.as_posix()
        or (t.startswith(prefix) and "/" not in t[len(prefix) :])
    )


def _owner_modules(module: str) -> set[str]:
    """*module* and its ancestor packages below ``vultron`` (re-exports)."""
    parts = module.split(".")
    return {".".join(parts[:i]) for i in range(2, len(parts) + 1)}


def imported_symbols(
    test: TestFile, module: str, symbols: set[str]
) -> set[str]:
    """Changed *symbols* that *test* imports by name from *module*."""
    owners = _owner_modules(module)
    return {n for m, n in test.names if n in symbols and m in owners}


# ---------------------------------------------------------------------------
# Statement mentions (SR-12-003)
# ---------------------------------------------------------------------------


def _path_patterns(path: str) -> list[re.Pattern[str]]:
    stem = PurePosixPath(path).with_suffix("").as_posix()
    dotted = re.escape(module_name(path))
    slash = rf"(?<![\w/]){re.escape(stem)}(?:\.py)?(?![\w/]|\.\w)"
    return [
        re.compile(slash),
        re.compile(rf"(?<![\w.]){dotted}(?!\w|\.[a-z_])"),
    ]


def _mentionable(name: str) -> bool:
    return len(name) >= 6 or bool(_CAMEL_RE.search(name))


def _is_plain_word(name: str) -> bool:
    """``logger``, ``Report``: also ordinary English, so code-span only."""
    return name.isalpha() and name[1:].islower()


def mentions(req: Requirement, path: str, symbols: set[str]) -> set[str]:
    """Path, module, or symbol tokens of a change named in *req*.

    A plain lowercase word such as ``registry`` only counts inside a
    backtick code span, where it cannot be ordinary prose.
    """
    found = {
        m.group(0)
        for pattern in _path_patterns(path)
        for m in pattern.finditer(req.statement)
    }
    words = set(_WORD_RE.findall(req.statement))
    code = set(
        _WORD_RE.findall(" ".join(_CODE_SPAN_RE.findall(req.statement)))
    )
    found.update(
        s
        for s in symbols
        if _mentionable(s) and s in (code if _is_plain_word(s) else words)
    )
    return found


# ---------------------------------------------------------------------------
# Analysis (SR-12-003, SR-12-004, SR-12-007)
# ---------------------------------------------------------------------------


def _add(
    tier: dict[str, GroupHit],
    reqs: dict[str, Requirement],
    ids: Iterable[str],
    evidence: str,
) -> bool:
    added = False
    for rid in ids:
        req = reqs.get(rid)
        if req is None:
            continue
        hit = tier.setdefault(req.group, GroupHit(req.group, req.topic))
        hit.reqs.add(rid)
        hit.evidence.add(evidence)
        added = True
    return added


class _Analyzer:
    def __init__(
        self,
        tests: dict[str, TestFile],
        requirements: Sequence[Requirement],
        hub_threshold: int,
    ) -> None:
        self.tests = tests
        self.hub_threshold = hub_threshold
        self.requirements = requirements
        self.reqs = {r.id: r for r in requirements}
        self.report = BackstopReport({}, {}, {}, [])

    def must(self, ids: Iterable[str], evidence: str) -> bool:
        return _add(self.report.must, self.reqs, ids, evidence)

    def source_change(self, change: FileChange, symbols: set[str]) -> None:
        module = module_name(change.path)
        hit = self._importers(module, symbols)
        for test in mirror_tests(change.path, self.tests):
            hit |= self.must(self.tests[test].spec_ids, f"mirror {test}")
        for req in self.requirements:
            for token in sorted(mentions(req, change.path, symbols)):
                hit |= self.must([req.id], f"{req.id} names {token}")
        if not hit:
            self.report.no_signal.append(change.path)

    def info(self, ids: Iterable[str], evidence: str) -> None:
        _add(self.report.info, self.reqs, ids, evidence)

    def _hubs(self, imports: dict[str, set[str]]) -> set[str]:
        counts: dict[str, int] = {}
        for names in imports.values():
            for name in names:
                counts[name] = counts.get(name, 0) + 1
        hubs = {n for n, c in counts.items() if c > self.hub_threshold}
        self.report.hubs.update({n: counts[n] for n in hubs})
        return hubs

    def _importers(self, module: str, symbols: set[str]) -> bool:
        imports = {
            path: imported_symbols(test, module, symbols)
            for path, test in self.tests.items()
        }
        hubs = self._hubs(imports)
        hit = False
        for path, names in imports.items():
            ids = self.tests[path].spec_ids
            if names - hubs:
                shown = ", ".join(sorted(names - hubs))
                hit |= self.must(ids, f"{path} imports {shown}")
            elif names:
                self.info(
                    ids, f"{path} imports hub {', '.join(sorted(names))}"
                )
            elif module in self.tests[path].modules:
                self.info(ids, f"{path} imports {module}")
        return hit

    def test_change(self, change: FileChange, tree: ast.Module) -> None:
        ids = spec_ids_in(changed_nodes(tree, change.lines))
        self.must(ids, f"changed test {change.path}")


def _parse(change: FileChange) -> ast.Module | None:
    try:
        return ast.parse(change.source or "")
    except SyntaxError:
        return None


def analyze(
    changes: Iterable[FileChange],
    tests: dict[str, TestFile],
    requirements: Sequence[Requirement],
    hub_threshold: int = HUB_THRESHOLD,
) -> BackstopReport:
    """Compute MUST and INFO spec groups for *changes*."""
    analyzer = _Analyzer(tests, requirements, hub_threshold)
    for change in changes:
        tree = _parse(change) or ast.Module(body=[], type_ignores=[])
        if change.path.startswith(TEST_PREFIX):
            analyzer.test_change(change, tree)
        elif change.path.startswith(SOURCE_PREFIX):
            symbols = changed_symbols(tree, change.lines)
            analyzer.report.symbols[change.path] = symbols
            analyzer.source_change(change, symbols)
    report = analyzer.report
    report.hub_threshold = hub_threshold
    report.info = {
        g: h for g, h in report.info.items() if g not in report.must
    }
    return report


def load_requirements(spec_dir: Path) -> list[Requirement]:
    """Flatten the spec registry under *spec_dir*."""
    registry = load_registry(spec_dir)
    return [
        Requirement(
            spec.id, group.id, file.id, " ".join(spec.statement.split())
        )
        for file in registry.files
        for group in file.groups
        for spec in group.specs
    ]


# ---------------------------------------------------------------------------
# Manifest (SR-12-006)
# ---------------------------------------------------------------------------


def _leading_ids(text: str, topics: set[str]) -> set[str]:
    """IDs at the start of each ``;``/``,`` piece, before any reason text."""
    ids: set[str] = set()
    for piece in re.split(r"[;,]", text):
        match = _ID_RUN_RE.match(piece)
        if match is None:
            continue
        ids.update(
            token
            for token in match.group(1).split()
            if token in topics
            or _GROUP_RE.match(token)
            or _REQ_RE.match(token)
        )
    return ids


def _manifest_target(
    manifest: Manifest, line: str, current: set[str] | None
) -> tuple[set[str] | None, str]:
    """Return the ID set *line* feeds and the text to scan for IDs."""
    stripped = _BULLET_RE.sub("", line).replace("*", "").strip()
    heading = _HEADING_RE.match(stripped)
    if heading:
        kind, rest = heading.groups()
        target = manifest.loaded if kind == "Loaded" else manifest.dismissed
        return target, rest
    if stripped.startswith("Spec manifest"):
        return None, ""
    if _BULLET_RE.match(line) or line[:1].isspace() or not stripped:
        return current, _BULLET_RE.sub("", line)
    return None, ""


def parse_manifest(text: str, topics: set[str]) -> Manifest:
    """Extract loaded and dismissed IDs from a Spec manifest block."""
    manifest = Manifest()
    current: set[str] | None = None
    for line in text.splitlines():
        current, rest = _manifest_target(manifest, line, current)
        if current is not None:
            current.update(_leading_ids(rest, topics))
    return manifest


def is_resolved(hit: GroupHit, manifest: Manifest) -> bool:
    """Whether the manifest loads, dismisses, or itemises *hit*."""
    listed = manifest.loaded | manifest.dismissed
    return (
        hit.group in listed
        or hit.topic in manifest.loaded
        or hit.reqs <= listed
    )


def unresolved_groups(
    must: dict[str, GroupHit], manifest: Manifest
) -> list[GroupHit]:
    """MUST-tier groups the manifest does not resolve, sorted by group."""
    return [
        must[g] for g in sorted(must) if not is_resolved(must[g], manifest)
    ]


# ---------------------------------------------------------------------------
# Output (SR-12-005)
# ---------------------------------------------------------------------------


def _group_line(hit: GroupHit) -> str:
    evidence = sorted(hit.evidence)
    shown = "; ".join(evidence[:MAX_EVIDENCE])
    if len(evidence) > MAX_EVIDENCE:
        shown += f"; +{len(evidence) - MAX_EVIDENCE} more"
    return f"  {hit.group:<9} [{', '.join(sorted(hit.reqs))}] <- {shown}"


def render_text(
    report: BackstopReport, unresolved: list[GroupHit] | None = None
) -> str:
    """Compact human-readable report."""
    nsym = sum(len(s) for s in report.symbols.values())
    lines = [
        f"spec-backstop: {len(report.symbols)} changed source files, "
        f"{nsym} changed symbols",
    ]
    if report.hubs:
        hubs = ", ".join(f"{n} ({c})" for n, c in sorted(report.hubs.items()))
        lines.append(
            f"hub symbols (imported by >{report.hub_threshold} test files; "
            f"import hits shown as INFO): {hubs}"
        )
    lines.append(f"MUST ({len(report.must)} groups):")
    lines += [_group_line(report.must[g]) for g in sorted(report.must)]
    info = " ".join(
        f"{g}({len(report.info[g].reqs)})" for g in sorted(report.info)
    )
    lines.append(f"INFO ({len(report.info)} groups): {info}".rstrip())
    if unresolved is not None:
        lines.append(f"UNRESOLVED by manifest ({len(unresolved)} groups):")
        lines += [_group_line(hit) for hit in unresolved]
    return "\n".join(lines)


def _hit_dict(hit: GroupHit) -> dict[str, object]:
    return {
        "group": hit.group,
        "topic": hit.topic,
        "requirements": sorted(hit.reqs),
        "evidence": sorted(hit.evidence),
    }


def render_json(
    report: BackstopReport, unresolved: list[GroupHit] | None = None
) -> str:
    """Machine-readable report (``--json``)."""
    data: dict[str, object] = {
        "changed": [
            {"path": p, "symbols": sorted(s)}
            for p, s in sorted(report.symbols.items())
        ],
        "must": [_hit_dict(report.must[g]) for g in sorted(report.must)],
        "info": [_hit_dict(report.info[g]) for g in sorted(report.info)],
        "no_signal": report.no_signal,
        "hub_threshold": report.hub_threshold,
        "hubs": dict(sorted(report.hubs.items())),
    }
    if unresolved is not None:
        data["unresolved"] = [_hit_dict(hit) for hit in unresolved]
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec-backstop",
        description=(
            "List the spec groups that plausibly govern the changed code and "
            "check them against a Spec manifest."
        ),
    )
    parser.add_argument("--base", default="origin/main", help="base ref")
    parser.add_argument(
        "--manifest", help="Spec manifest file, or - for stdin"
    )
    parser.add_argument(
        "--paths", nargs="+", help="treat these files as fully changed"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--hub-threshold",
        type=int,
        default=HUB_THRESHOLD,
        metavar="N",
        help=(
            "demote import hits for symbols imported by more than N test "
            f"files to INFO (default {HUB_THRESHOLD})"
        ),
    )
    return parser


def _read_manifest(source: str, topics: set[str]) -> Manifest:
    if source == "-":
        return parse_manifest(sys.stdin.read(), topics)
    try:
        text = Path(source).read_text(encoding="utf-8")
    except OSError as exc:
        raise BackstopError(f"cannot read manifest {source}: {exc}") from exc
    return parse_manifest(text, topics)


def _collect(args: argparse.Namespace) -> tuple[Path, list[FileChange]]:
    if args.paths:
        root = repo_root().resolve()
        return root, changes_from_paths(root, args.paths)
    root = git_toplevel(Path.cwd()).resolve()
    return root, collect_git_changes(_run_git(root), root, args.base)


def _run(args: argparse.Namespace) -> int:
    root, changes = _collect(args)
    requirements = load_requirements(root / "specs")
    report = analyze(
        changes, build_test_index(root), requirements, args.hub_threshold
    )
    unresolved = None
    if args.manifest:
        topics = {r.topic for r in requirements}
        manifest = _read_manifest(args.manifest, topics)
        unresolved = unresolved_groups(report.must, manifest)
    render = render_json if args.json else render_text
    print(render(report, unresolved))
    if report.no_signal:
        print(
            "spec-backstop: no deterministic signal for: "
            f"{', '.join(report.no_signal)} — rely on manifest judgment",
            file=sys.stderr,
        )
    return 1 if unresolved else 0


def main() -> int:
    """CLI entry point for ``spec-backstop``."""
    args = _build_parser().parse_args()
    try:
        return _run(args)
    except (BackstopError, FileNotFoundError) as exc:
        print(f"spec-backstop: error: {exc}", file=sys.stderr)
        return 2
