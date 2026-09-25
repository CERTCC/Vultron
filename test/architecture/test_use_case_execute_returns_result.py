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

"""Architecture ratchet: every use-case ``execute()`` returns a ``UseCaseResult``.

UCORG-05-004 (``specs/use-case-organization.yaml``): every concrete use-case
class in ``vultron/core/use_cases/`` declares an ``execute()`` return
annotation of ``UseCaseResult`` or a subtype of it. A missing annotation,
``-> None``, ``-> dict`` and ``-> Any`` all fail — each lets a use case report
nothing typed, which is the ambiguity ADR-0095 removes (UCORG-05-001).

The scan is two-stage:

1. **Static** — the AST (via ``_corpus``, TB-13-003) finds every top-level
   class that defines ``execute`` and reads its return annotation. A missing
   annotation fails here, before anything is imported.
2. **Resolved** — ``typing.get_type_hints`` resolves the annotation on the
   imported class, which must be a class that subclasses ``UseCaseResult``. "Registered
   subtype" in UCORG-05-004 means exactly this: the subtype relation is the
   registry, so a new result type needs no list edit here.

**Exclusion (UCORG-05-004b):** ``vultron/core/use_cases/triggers/`` is not
scanned. Trigger ``execute()`` methods still return a ``dict`` or a
``TriggerResult`` that does not yet inherit ``UseCaseResult``; #3354 migrates
them and MUST delete ``_EXCLUDED_DIRS`` when it lands.
"""

import ast
import importlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, get_type_hints

import pytest

from test.architecture import _corpus
from vultron.core.models.use_case_result import UseCaseResult

_USE_CASES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "use_cases"

# Retired by #3354 (trigger-side result types, UCORG-05-004b). Do not add to
# this tuple: a new directory of use cases conforms from the start.
_EXCLUDED_DIRS: tuple[Path, ...] = (_USE_CASES_ROOT / "triggers",)


def _execute_annotations(tree: ast.AST) -> Iterator[tuple[str, str | None]]:
    """Yield ``(class_name, annotation_source)`` per top-level ``execute``.

    ``annotation_source`` is ``None`` when ``execute`` has no return
    annotation, and is otherwise used only in messages.
    """
    assert isinstance(tree, ast.Module)
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if (
                isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                and fn.name == "execute"
            ):
                returns = fn.returns
                yield cls.name, (
                    None if returns is None else ast.unparse(returns)
                )


def _violations_in(
    tree: ast.AST, resolve: Callable[[str], object]
) -> list[str]:
    """Return ``"Class: problem"`` strings for non-conforming ``execute``s.

    *resolve* maps a class name to the resolved return type of its
    ``execute``; it may raise if the annotation names something unknown.
    """
    problems: list[str] = []
    for class_name, annotation in _execute_annotations(tree):
        if annotation is None:
            problems.append(
                f"{class_name}: execute() has no return annotation"
            )
            continue
        try:
            resolved = resolve(class_name)
        except Exception as exc:  # noqa: BLE001 — reported, not swallowed
            problems.append(
                f"{class_name}: cannot resolve -> {annotation} ({exc!r})"
            )
            continue
        if not (
            isinstance(resolved, type) and issubclass(resolved, UseCaseResult)
        ):
            problems.append(
                f"{class_name}: execute() -> {annotation} is not a "
                "UseCaseResult subtype"
            )
    return problems


def _return_hint(namespace: dict[str, object], class_name: str) -> object:
    """Return the resolved ``execute`` return type of *class_name*."""
    cls = namespace[class_name]
    return get_type_hints(getattr(cls, "execute"))["return"]


def _module_resolver(path: Path) -> Callable[[str], object]:
    """Return a resolver over the classes of *path*'s imported module."""
    dotted = ".".join(
        path.relative_to(_corpus.REPO_ROOT).with_suffix("").parts
    )

    def _resolve(class_name: str) -> object:
        return _return_hint(vars(importlib.import_module(dotted)), class_name)

    return _resolve


def _is_excluded(path: Path) -> bool:
    return any(path.is_relative_to(d) for d in _EXCLUDED_DIRS)


def _collect() -> tuple[set[str], list[str]]:
    """Return ``(scanned_packages, violations)`` over the use-case corpus.

    ``scanned_packages`` names the first directory under ``use_cases/`` of
    every file that contributed at least one ``execute()``.
    """
    scanned: set[str] = set()
    violations: list[str] = []
    for path, tree in _corpus.files_mentioning(
        "def execute", under=_USE_CASES_ROOT
    ):
        if _is_excluded(path):
            continue
        if any(True for _ in _execute_annotations(tree)):
            scanned.add(path.relative_to(_USE_CASES_ROOT).parts[0])
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        violations.extend(
            f"{rel}: {v}" for v in _violations_in(tree, _module_resolver(path))
        )
    return scanned, violations


def test_every_use_case_execute_returns_a_use_case_result() -> None:
    """UCORG-05-004: ``execute()`` is annotated with a ``UseCaseResult`` type."""
    scanned, violations = _collect()
    # Guard against a vacuous pass: a broken prefilter or root would scan
    # nothing, or lose a whole package, and still report no violations.
    assert {
        "received",
        "query",
    } <= scanned, f"expected execute() methods in received/ and query/; scanned {scanned}"
    assert not violations, (
        "execute() must return UseCaseResult or a subtype (UCORG-05-004, "
        "ADR-0095):\n" + "\n".join(f"  {v}" for v in violations)
    )


def test_triggers_exclusion_is_still_needed() -> None:
    """UCORG-05-004b: the exclusion stays only while triggers fail the rule.

    When #3354 migrates the trigger side, this fails and ``_EXCLUDED_DIRS``
    MUST be deleted rather than left as a silent, unexplained carve-out.
    """
    still_failing = []
    for excluded in _EXCLUDED_DIRS:
        for path, tree in _corpus.files_mentioning(
            "def execute", under=excluded
        ):
            if _violations_in(tree, _module_resolver(path)):
                still_failing.append(path)
    assert still_failing, (
        "every use case under the excluded directories now conforms; delete "
        "_EXCLUDED_DIRS (#3354)"
    )


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests
# ---------------------------------------------------------------------------


class _SampleResult(UseCaseResult):
    pass


def _check(source: str) -> list[str]:
    """Run the detector over inline *source*, executed as a sample module."""
    namespace: dict[str, object] = {
        "Any": Any,
        "_SampleResult": _SampleResult,
        "UseCaseResult": UseCaseResult,
    }
    exec(compile(source, "<sample>", "exec"), namespace)
    return _violations_in(
        _corpus.parse_inline(source),
        lambda class_name: _return_hint(namespace, class_name),
    )


@pytest.mark.parametrize("annotation", ["_SampleResult", "UseCaseResult"])
def test_detector_accepts_a_use_case_result_annotation(
    annotation: str,
) -> None:
    assert (
        _check(f"class U:\n    def execute(self) -> {annotation}: ...\n") == []
    )


def test_detector_accepts_a_forward_reference() -> None:
    assert (
        _check("class U:\n    def execute(self) -> '_SampleResult': ...\n")
        == []
    )


@pytest.mark.parametrize(
    "annotation", ["None", "dict", "Any", "_SampleResult | None"]
)
def test_detector_flags_a_non_result_annotation(annotation: str) -> None:
    [problem] = _check(
        f"class U:\n    def execute(self) -> {annotation}: ...\n"
    )
    assert "not a UseCaseResult subtype" in problem


def test_detector_flags_a_missing_annotation() -> None:
    [problem] = _check("class U:\n    def execute(self): ...\n")
    assert "no return annotation" in problem


def test_detector_flags_an_unresolvable_annotation() -> None:
    [problem] = _check("class U:\n    def execute(self) -> 'Missing': ...\n")
    assert "cannot resolve" in problem


def test_detector_ignores_classes_without_execute() -> None:
    assert _check("class U:\n    def run(self) -> None: ...\n") == []
