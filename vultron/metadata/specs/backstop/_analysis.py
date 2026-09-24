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
"""Statement mentions and tier analysis (SR-12-003, SR-12-004, SR-12-007)."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath

from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.backstop._model import (
    SOURCE_PREFIX,
    TEST_PREFIX,
    HUB_THRESHOLD,
    MONOLITH_GROUP_SPAN,
    FileChange,
    TestFile,
    Requirement,
    GroupHit,
    BackstopReport,
    _ADVISORY,
)

from vultron.metadata.specs.backstop._symbols import (
    changed_symbols,
    changed_nodes,
    spec_ids_in,
    mirror_tests,
    imported_symbols,
    module_name,
)

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_CAMEL_RE = re.compile(r"[a-z][A-Z]")


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
        """Record *ids* as MUST, routing advisory requirements to INFO.

        A group whose only matched requirements are SHOULD or MAY cannot
        block, or a SHOULD-only group such as TRIG-05 forces a load with no
        obligation behind it.
        """
        ids = list(ids)
        mandatory = [i for i in ids if self.reqs.get(i, _ADVISORY).mandatory]
        advisory = [i for i in ids if i not in set(mandatory)]
        if advisory:
            self.info(advisory, f"{evidence} (advisory: SHOULD/MAY only)")
        return _add(self.report.must, self.reqs, mandatory, evidence)

    def source_change(self, change: FileChange, symbols: set[str]) -> None:
        module = module_name(change.path)
        hit = self._importers(module, symbols)
        for test in mirror_tests(change.path, self.tests):
            hit |= self._from_test(test, f"mirror {test}")
        # Hub demotion deliberately does not apply here. ``mentions`` only
        # matches symbols *defined* in the changed file, so a requirement
        # naming ``BTBridge`` is a requirement about the contract of the file
        # that defines it — the strongest signal available, not the weakest.
        for req in self.requirements:
            for token in sorted(mentions(req, change.path, symbols)):
                hit |= self.must([req.id], f"{req.id} names {token}")
        if not hit:
            self.report.no_signal.append(change.path)

    def _from_test(self, test: str, evidence: str) -> bool:
        """Promote *test*'s markers, unless it is a catch-all test file.

        A file carrying markers for more than ``MONOLITH_GROUP_SPAN`` groups
        is a whole-subsystem suite (the median here is 2), so importing any
        one symbol from it says nothing about which of its groups apply.
        """
        ids = self.tests[test].spec_ids
        groups = {self.reqs[i].group for i in ids if i in self.reqs}
        if len(groups) > MONOLITH_GROUP_SPAN:
            self.report.monoliths[test] = len(groups)
            self.info(
                ids, f"{evidence} (catch-all suite, {len(groups)} groups)"
            )
            return False
        return self.must(ids, evidence)

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
                hit |= self._from_test(path, f"{path} imports {shown}")
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
        else:
            analyzer.report.ignored.append(change.path)
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
            spec.id,
            group.id,
            file.id,
            " ".join(spec.statement.split()),
            spec.priority.value,
        )
        for file in registry.files
        for group in file.groups
        for spec in group.specs
    ]
