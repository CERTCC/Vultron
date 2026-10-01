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

"""Architecture ratchet: the trigger driving port is one method (UCORG-05-006).

Two assertions, both over what exists rather than what is documented:

1. **One public method.**  ``TriggerDispatcher`` declares exactly ``trigger``.
   A second public method is a per-verb surface starting to grow back.
2. **No per-verb facade under ``vultron/core/``.**  A facade is a class with a
   method that constructs a ``Svc*UseCase`` and calls ``execute()`` on it —
   the shape ``TriggerService`` had 27 times over (ADR-0110).  The scan goes
   through ``_corpus`` (TB-13-001, TB-13-002), names each hit as
   ``file:Class.method``, and compares against ``KNOWN_VIOLATIONS`` with exact
   equality (ARCH-18-001) so neither a new facade nor a stale entry passes.
   The registry-backed dispatcher is not a facade: it constructs
   ``entry.use_case_class`` from a row, never a ``Svc*`` name.
"""

import ast
import re
from collections.abc import Iterator

import pytest

from test.architecture import _corpus
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher

_CORE_ROOT = _corpus.REPO_ROOT / "vultron" / "core"
_SVC_USE_CASE_RE = re.compile(r"^Svc\w+UseCase$")

#: Pre-existing facade methods.  Empty: ``TriggerService`` was the only one.
KNOWN_VIOLATIONS: frozenset[str] = frozenset()


@pytest.mark.spec("UCORG-05-006")
def test_trigger_dispatcher_declares_exactly_one_public_method() -> None:
    public = {
        name
        for name, value in vars(TriggerDispatcher).items()
        if not name.startswith("_") and callable(value)
    }
    assert public == {"trigger"}


def _svc_name(node: ast.expr) -> bool:
    """``Svc*UseCase`` spelled bare or as the attribute of a module."""
    if isinstance(node, ast.Name):
        return bool(_SVC_USE_CASE_RE.match(node.id))
    if isinstance(node, ast.Attribute):
        return bool(_SVC_USE_CASE_RE.match(node.attr))
    return False


def _constructs_and_executes_a_use_case(func: ast.AST) -> bool:
    """``Svc*UseCase(...).execute()`` anywhere in *func*'s body."""
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            and isinstance(node.func.value, ast.Call)
            and _svc_name(node.func.value.func)
        ):
            return True
    return False


def _facade_methods() -> Iterator[str]:
    for path, tree in _corpus.files_mentioning("UseCase(", under=_CORE_ROOT):
        assert isinstance(tree, ast.Module)
        for klass in tree.body:
            if not isinstance(klass, ast.ClassDef):
                continue
            for method in klass.body:
                if isinstance(
                    method, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and _constructs_and_executes_a_use_case(method):
                    rel = path.relative_to(_corpus.REPO_ROOT)
                    yield f"{rel}:{klass.name}.{method.name}"


@pytest.mark.spec("UCORG-05-006")
@pytest.mark.spec("ARCH-18-001")
def test_no_per_verb_trigger_facade_under_core() -> None:
    """No class under ``vultron/core/`` wraps a use case per method."""
    actual = frozenset(_facade_methods())
    assert actual == KNOWN_VIOLATIONS, (
        "per-verb facade methods changed.\n"
        f"  new:      {sorted(actual - KNOWN_VIOLATIONS)}\n"
        f"  resolved: {sorted(KNOWN_VIOLATIONS - actual)}"
    )


# ---------------------------------------------------------------------------
# Self-tests for the facade detector
# ---------------------------------------------------------------------------


def test_detector_sees_a_facade_method() -> None:
    tree = _corpus.parse_inline(
        "class Facade:\n"
        "    def engage_case(self, actor_id, case_id):\n"
        "        req = EngageCaseTriggerRequest(actor_id=actor_id)\n"
        "        return SvcEngageCaseUseCase(self._dl, req).execute()\n"
    )
    assert isinstance(tree, ast.Module)
    method = tree.body[0].body[0]  # type: ignore[attr-defined]
    assert _constructs_and_executes_a_use_case(method)


def test_detector_ignores_a_row_driven_dispatcher() -> None:
    tree = _corpus.parse_inline(
        "class Dispatcher:\n"
        "    def trigger(self, request, dl):\n"
        "        entry = self._entry_for(request)\n"
        "        use_case = entry.use_case_class(dl, request)\n"
        "        return use_case.execute()\n"
    )
    assert isinstance(tree, ast.Module)
    method = tree.body[0].body[0]  # type: ignore[attr-defined]
    assert not _constructs_and_executes_a_use_case(method)
