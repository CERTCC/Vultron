"""Architecture ratchet: delegated ``attributed_to`` comes from the shared helper.

CM-24-005: every path that emits an Activity on another participant's behalf
obtains ``actor`` and ``attributed_to`` from
:func:`vultron.core.behaviors.delegated_authorship.delegated_authorship`.  No
callsite may reconstruct the pattern.

A core function that hands an ``attributed_to`` keyword to a trigger-activity
factory method — the ports that build the activities a CASE_MANAGER authors —
must derive that value from a ``delegated_authorship()`` result bound in the
same function, unless the value is the literal
``None`` (the manager's own ask) or ``self.actor_id`` (a note the actor itself
authors — attribution to the author, not delegation).  The set is exact: there is no allowlist.

Specs: CM-24-005 (``specs/case-management.yaml``).
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"
_HELPER = _CORE / "behaviors" / "delegated_authorship.py"
_HELPER_NAME = "delegated_authorship"
_FACTORY_MARKER = "trigger_activity_factory"


def _attribute_chain(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _is_not_delegated(value: ast.AST) -> bool:
    """``None`` (the manager's own ask) or ``self.actor_id`` (self-authored)."""
    if isinstance(value, ast.Constant):
        return value.value is None
    return _attribute_chain(value) == "self.actor_id"


def _is_delegated_factory_call(call: ast.Call) -> bool:
    if not isinstance(call.func, ast.Attribute):
        return False
    if _FACTORY_MARKER not in _attribute_chain(call.func.value):
        return False
    return any(
        kw.arg == "attributed_to" and not _is_not_delegated(kw.value)
        for kw in call.keywords
    )


def _is_helper_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and (
        getattr(node.func, "id", None) == _HELPER_NAME
        or getattr(node.func, "attr", None) == _HELPER_NAME
    )


def _helper_result_names(fn: ast.AST) -> set[str]:
    """Names bound to a ``delegated_authorship()`` result inside *fn*."""
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and any(
            _is_helper_call(n) for n in ast.walk(node.value)
        ):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _derives_from(value: ast.AST, names: set[str]) -> bool:
    return any(
        isinstance(n, ast.Name) and n.id in names for n in ast.walk(value)
    )


def _violations(path: Path, tree: ast.AST) -> list[str]:
    found: list[str] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        results = _helper_result_names(fn)
        for call in ast.walk(fn):
            if not (
                isinstance(call, ast.Call) and _is_delegated_factory_call(call)
            ):
                continue
            for kw in call.keywords:
                if kw.arg != "attributed_to" or _is_not_delegated(kw.value):
                    continue
                if not _derives_from(kw.value, results):
                    rel = path.relative_to(_corpus.REPO_ROOT)
                    found.append(f"{rel}:{call.lineno} in {fn.name}()")
    return found


@pytest.mark.spec("CM-24-005")
def test_attributed_to_on_factory_calls_comes_from_the_helper() -> None:
    violations: list[str] = []
    for path, tree in _corpus.files_mentioning("attributed_to", under=_CORE):
        if path == _HELPER:
            continue
        violations.extend(_violations(path, tree))
    assert not violations, (
        "attributed_to passed to a trigger-activity factory without calling "
        "delegated_authorship() (CM-24-005):\n" + "\n".join(violations)
    )


@pytest.mark.spec("CM-24-005")
def test_ratchet_detects_a_hand_built_attribution() -> None:
    tree = _corpus.parse_inline(
        "def f(self):\n"
        "    return self.trigger_activity_factory.propose_embargo(\n"
        "        attributed_to=self.proposer)\n"
    )
    assert _violations(_HELPER, tree)


@pytest.mark.spec("CM-24-005")
def test_ratchet_accepts_helper_and_literal_none() -> None:
    tree = _corpus.parse_inline(
        "def f(self):\n"
        "    a = delegated_authorship(doing_actor_id=1, requesting_actor_id=2)\n"
        "    self.trigger_activity_factory.x(attributed_to=a.attributed_to)\n"
        "def h(self):\n"
        "    a = delegated_authorship(doing_actor_id=1, requesting_actor_id=2)\n"
        "    self.trigger_activity_factory.x(\n"
        "        attributed_to=a.attributed_to if self.p else None)\n"
        "def g(self):\n"
        "    self.trigger_activity_factory.x(attributed_to=None)\n"
    )
    assert not _violations(_HELPER, tree)


@pytest.mark.spec("CM-24-005")
def test_ratchet_rejects_a_bypassed_helper_result() -> None:
    tree = _corpus.parse_inline(
        "def f(self):\n"
        "    a = delegated_authorship(doing_actor_id=1, requesting_actor_id=2)\n"
        "    self.trigger_activity_factory.x(attributed_to=self.proposer)\n"
    )
    assert _violations(_HELPER, tree)
