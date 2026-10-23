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

HP-01-001 / HP-01-002 (``specs/handler-protocol.yaml``) ride on the same scan:
a handler's ``execute()`` takes no arguments — everything it needs arrived
through ``__init__(dl, request)`` — so any parameter beyond ``self``
(positional, ``*args``, keyword-only, or ``**kwargs``) fails here too, and the
received-side return type is ``HandlerResult``, a ``UseCaseResult`` subtype.

The scan is two-stage:

1. **Static** — the AST (via ``_corpus``, TB-13-003) finds every top-level
   class that defines ``execute`` and reads its return annotation. A missing
   annotation fails here, before anything is imported.
2. **Resolved** — ``typing.get_type_hints`` resolves the annotation on the
   imported class, which must be a class that subclasses ``UseCaseResult``. "Registered
   subtype" in UCORG-05-004 means exactly this: the subtype relation is the
   registry, so a new result type needs no list edit here. A generic base
   whose ``execute()`` returns a ``TypeVar`` conforms when that variable is
   *bound* to a ``UseCaseResult`` subtype (``SvcBTTriggerBase[TriggerResultT]``,
   ADR-0110): every concrete binding is then a subtype, and an unbound
   variable — which would admit anything — still fails.

The scan covers every package under ``use_cases/`` — received, query and
trigger alike. The trigger side once carried a named exclusion (UCORG-05-004b,
retired with #3831 when ``TriggerResult`` became a ``UseCaseResult`` subtype);
a new directory of use cases conforms from the start.
"""

import ast
import importlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, NamedTuple, TypeVar, get_type_hints

import pytest

from test.architecture import _corpus
from vultron.core.models.use_case_result import UseCaseResult

_USE_CASES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "use_cases"


class _ExecuteSignature(NamedTuple):
    """What the static pass reads off one top-level ``execute`` definition."""

    class_name: str
    #: Return annotation source, ``None`` when absent; used only in messages.
    annotation: str | None
    #: Every parameter beyond the first (``self``), as written — HP-01-001.
    extra_params: tuple[str, ...]


def _extra_params(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[str, ...]:
    """Parameter names of *fn* beyond the receiver, in declaration order.

    A ``@staticmethod`` has no receiver, so every positional parameter counts.
    """
    args = fn.args
    is_static = any(
        isinstance(d, ast.Name) and d.id == "staticmethod"
        for d in fn.decorator_list
    )
    positional = [*args.posonlyargs, *args.args][0 if is_static else 1 :]
    names = [a.arg for a in positional]
    if args.vararg is not None:
        names.append(f"*{args.vararg.arg}")
    names.extend(a.arg for a in args.kwonlyargs)
    if args.kwarg is not None:
        names.append(f"**{args.kwarg.arg}")
    return tuple(names)


def _execute_annotations(tree: ast.AST) -> Iterator[_ExecuteSignature]:
    """Yield one :class:`_ExecuteSignature` per top-level ``execute``."""
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
                yield _ExecuteSignature(
                    cls.name,
                    None if returns is None else ast.unparse(returns),
                    _extra_params(fn),
                )


def _violations_in(
    tree: ast.AST, resolve: Callable[[str], object]
) -> list[str]:
    """Return ``"Class: problem"`` strings for non-conforming ``execute``s.

    *resolve* maps a class name to the resolved return type of its
    ``execute``; it may raise if the annotation names something unknown.
    """
    problems: list[str] = []
    for class_name, annotation, extra_params in _execute_annotations(tree):
        if extra_params:
            problems.append(
                f"{class_name}: execute() takes arguments "
                f"({', '.join(extra_params)}) — it must take none (HP-01-001)"
            )
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
        if not _is_use_case_result_type(resolved):
            problems.append(
                f"{class_name}: execute() -> {annotation} is not a "
                "UseCaseResult subtype"
            )
    return problems


def _is_use_case_result_type(resolved: object) -> bool:
    """True for a ``UseCaseResult`` subclass or a ``TypeVar`` bound to one."""
    if isinstance(resolved, TypeVar):
        resolved = resolved.__bound__
    return isinstance(resolved, type) and issubclass(resolved, UseCaseResult)


def _return_hint(namespace: dict[str, object], class_name: str) -> object:
    """Return the resolved ``execute`` return type of *class_name*."""
    cls = namespace[class_name]
    # The namespace is typed ``object``; getattr keeps the type checker out.
    return get_type_hints(getattr(cls, "execute"))["return"]  # noqa: B009


def _module_resolver(path: Path) -> Callable[[str], object]:
    """Return a resolver over the classes of *path*'s imported module."""
    dotted = ".".join(
        path.relative_to(_corpus.REPO_ROOT).with_suffix("").parts
    )

    def _resolve(class_name: str) -> object:
        return _return_hint(vars(importlib.import_module(dotted)), class_name)

    return _resolve


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
        if any(True for _ in _execute_annotations(tree)):
            scanned.add(path.relative_to(_USE_CASES_ROOT).parts[0])
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        violations.extend(
            f"{rel}: {v}" for v in _violations_in(tree, _module_resolver(path))
        )
    return scanned, violations


def test_every_use_case_execute_returns_a_use_case_result() -> None:
    """UCORG-05-004, HP-01-001, HP-01-002: ``execute()`` takes no arguments and
    is annotated with a ``UseCaseResult`` type."""
    scanned, violations = _collect()
    # Guard against a vacuous pass: a broken prefilter or root would scan
    # nothing, or lose a whole package, and still report no violations.
    assert {
        "received",
        "query",
        "triggers",
    } <= scanned, (
        "expected execute() methods in received/, query/ and triggers/; "
        f"scanned {scanned}"
    )
    assert not violations, (
        "execute() must return UseCaseResult or a subtype (UCORG-05-004, "
        "ADR-0095):\n" + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests
# ---------------------------------------------------------------------------


class _SampleResult(UseCaseResult):
    pass


_BoundT = TypeVar("_BoundT", bound=_SampleResult)
_UnboundT = TypeVar("_UnboundT")


def _check(source: str) -> list[str]:
    """Run the detector over inline *source*, executed as a sample module."""
    namespace: dict[str, object] = {
        "Any": Any,
        "_SampleResult": _SampleResult,
        "UseCaseResult": UseCaseResult,
        "_BoundT": _BoundT,
        "_UnboundT": _UnboundT,
    }
    # Executes the test's own inline sample source, never external input.
    exec(compile(source, "<sample>", "exec"), namespace)  # noqa: S102
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


def test_detector_accepts_a_type_variable_bound_to_a_result() -> None:
    """A generic base binding its result TypeVar conforms (ADR-0110)."""
    assert _check("class U:\n    def execute(self) -> _BoundT: ...\n") == []


@pytest.mark.parametrize(
    "annotation", ["None", "dict", "Any", "_SampleResult | None", "_UnboundT"]
)
def test_detector_flags_a_non_result_annotation(annotation: str) -> None:
    [problem] = _check(
        f"class U:\n    def execute(self) -> {annotation}: ...\n"
    )
    assert "not a UseCaseResult subtype" in problem


@pytest.mark.parametrize(
    "params",
    [
        "self, request",
        "self, *args",
        "self, *, dry_run=False",
        "self, **kwargs",
    ],
)
def test_detector_flags_an_execute_that_takes_arguments(params: str) -> None:
    """HP-01-001: any parameter beyond ``self`` is a violation."""
    [problem] = _check(
        f"class U:\n    def execute({params}) -> _SampleResult: ...\n"
    )
    assert "takes arguments" in problem


def test_detector_flags_a_staticmethod_execute_with_a_parameter() -> None:
    """A ``@staticmethod`` has no receiver to skip, so its one parameter counts."""
    [problem] = _check(
        "class U:\n"
        "    @staticmethod\n"
        "    def execute(request) -> _SampleResult: ...\n"
    )
    assert "takes arguments" in problem


def test_detector_reports_arguments_and_return_type_separately() -> None:
    """Both defects on one ``execute()`` are both reported."""
    problems = _check(
        "class U:\n    def execute(self, request) -> None: ...\n"
    )
    assert len(problems) == 2
    assert any("takes arguments" in p for p in problems)
    assert any("not a UseCaseResult subtype" in p for p in problems)


def test_detector_flags_a_missing_annotation() -> None:
    [problem] = _check("class U:\n    def execute(self): ...\n")
    assert "no return annotation" in problem


def test_detector_flags_an_unresolvable_annotation() -> None:
    [problem] = _check("class U:\n    def execute(self) -> 'Missing': ...\n")
    assert "cannot resolve" in problem


def test_detector_ignores_classes_without_execute() -> None:
    assert _check("class U:\n    def run(self) -> None: ...\n") == []
