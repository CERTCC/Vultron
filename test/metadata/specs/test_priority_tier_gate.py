"""Static gate: priority selection goes through the shared tier definition.

MS-02-004: code that selects spec requirements by priority obtains the
MS-02-003 tiering from ``RFC2119Priority.tier`` (or ``is_must_tier``), never
by comparing against individual enum members or priority strings. The literal
comparison is easy to write and fails silently — the prohibitions drop out and
nothing errors — so this test reads the Python under ``vultron/metadata/specs/``
and ``scripts/`` and fails on any comparison whose operand is a *priority
literal*:

- ``RFC2119Priority.<MEMBER>`` (through an import alias too), or the same
  member spelled ``RFC2119Priority("MUST")`` / ``RFC2119Priority["MUST"]``;
- a priority string (``"MUST"``, ``"SHOULD_NOT"``, ...);
- a tuple, list, set, or ``frozenset(...)``/``set(...)``/``tuple(...)``/
  ``list(...)`` of either;
- a name bound anywhere in the module to one of those containers, so
  ``_MUST_TIER = (RFC2119Priority.MUST, RFC2119Priority.MUST_NOT)`` followed
  by ``priority in _MUST_TIER`` is caught.

A comparison is an ``ast.Compare`` (``==``, ``!=``, ``is``, ``in``, ...) or a
``match``/``case`` arm whose pattern is a priority literal.

Display maps that label each member (``{RFC2119Priority.MUST: "..."}``) are
``Dict`` nodes, not comparisons, and are out of scope by construction.

Known gaps, on purpose: a *string-valued* comparison is judged by value, so
``x == "MAY"`` on a non-priority is flagged too (allowlist it if one ever
appears — none does today), and a method call such as
``priority.value.startswith("MUST")`` or ``_TIER.__contains__(priority)`` is
not a comparison node and is not seen.

The one allowlisted comparison is SR-11-003's selector, the recorded MS-02-003
exception. The allowlist is two-sided: an entry that no longer matches fails
too, so retiring the exception removes it here in the same change.

Requirements: specs/meta-specifications.yaml MS-02-004.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from vultron.metadata.specs.schema import RFC2119Priority

_REPO_ROOT = Path(__file__).parents[3]
_SCAN_ROOTS = (
    _REPO_ROOT / "vultron" / "metadata" / "specs",
    _REPO_ROOT / "scripts",
)

_PRIORITY_STRINGS = frozenset(p.value for p in RFC2119Priority)
_CONTAINER_BUILTINS = frozenset({"frozenset", "set", "tuple", "list"})

#: ``(repo-relative path, source text of the comparison)``. Exactly these hits
#: are permitted, and each MUST still be present (see the module docstring).
_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "vultron/metadata/specs/lint.py",
            "priority == RFC2119Priority.MUST",
        ),
    }
)


@dataclass
class _PriorityLiterals:
    """What counts as a priority literal in one module.

    ``enum_names`` is ``RFC2119Priority`` plus any import alias for it;
    ``container_names`` are names the module binds to a container of
    priority literals (resolved to a fixpoint so ``B = frozenset(A)`` follows
    ``A``).
    """

    enum_names: frozenset[str] = frozenset({RFC2119Priority.__name__})
    container_names: set[str] = field(default_factory=set)

    @classmethod
    def for_module(cls, tree: ast.Module) -> _PriorityLiterals:
        aliases = {RFC2119Priority.__name__}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if (
                        alias.name.rsplit(".", 1)[-1]
                        == RFC2119Priority.__name__
                        and alias.asname
                    ):
                        aliases.add(alias.asname)
        literals = cls(enum_names=frozenset(aliases))
        while True:
            before = len(literals.container_names)
            for node in ast.walk(tree):
                target, value = _binding(node)
                if (
                    target is not None
                    and value is not None
                    and literals.is_container(value)
                ):
                    literals.container_names.add(target)
            if len(literals.container_names) == before:
                return literals

    def is_member(self, node: ast.expr) -> bool:
        """``RFC2119Priority.MUST``, ``RFC2119Priority("MUST")``, ``RFC2119Priority["MUST"]``."""
        if isinstance(node, ast.Attribute):
            return (
                isinstance(node.value, ast.Name)
                and node.value.id in self.enum_names
                and node.attr in RFC2119Priority.__members__
            )
        if isinstance(node, ast.Call):
            return (
                isinstance(node.func, ast.Name)
                and node.func.id in self.enum_names
                and len(node.args) == 1
                and self.is_literal(node.args[0])
            )
        if isinstance(node, ast.Subscript):
            return (
                isinstance(node.value, ast.Name)
                and node.value.id in self.enum_names
                and self.is_literal(node.slice)
            )
        return False

    def is_container(self, node: ast.expr) -> bool:
        """A tuple/list/set display, or a container builtin call, holding one."""
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return any(self.is_literal(elt) for elt in node.elts)
        if isinstance(node, ast.Call):
            return (
                isinstance(node.func, ast.Name)
                and node.func.id in _CONTAINER_BUILTINS
                and any(self.is_literal(arg) for arg in node.args)
            )
        if isinstance(node, ast.Name):
            return node.id in self.container_names
        return False

    def is_literal(self, node: ast.expr) -> bool:
        """A member, a priority string, or a container of them (by value or name)."""
        if isinstance(node, ast.Constant):
            return (
                isinstance(node.value, str) and node.value in _PRIORITY_STRINGS
            )
        return self.is_member(node) or self.is_container(node)


def _binding(node: ast.AST) -> tuple[str | None, ast.expr | None]:
    """``(name, value)`` for a simple ``name = value`` / ``name: T = value``."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        if isinstance(target, ast.Name):
            return target.id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id, node.value
    return None, None


def find_priority_comparisons(
    source: str, filename: str
) -> list[tuple[int, str]]:
    """``(line, comparison text)`` for every comparison against a priority literal.

    Covers ``ast.Compare`` operands and ``match``/``case`` value patterns.
    """
    tree = ast.parse(source, filename=filename)
    literals = _PriorityLiterals.for_module(tree)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if any(
                literals.is_literal(n) for n in (node.left, *node.comparators)
            ):
                hits.append((node.lineno, ast.unparse(node)))
        elif isinstance(node, ast.MatchValue):
            if literals.is_literal(node.value):
                hits.append((node.lineno, f"case {ast.unparse(node)}"))
    return hits


def _scan() -> dict[tuple[str, str], list[int]]:
    """Every hit in the scanned trees, keyed like the allowlist."""
    found: dict[tuple[str, str], list[int]] = {}
    for root in _SCAN_ROOTS:
        for py_file in sorted(root.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            rel = py_file.relative_to(_REPO_ROOT).as_posix()
            source = py_file.read_text(encoding="utf-8")
            if RFC2119Priority.__name__ not in source and not any(
                f'"{p}"' in source or f"'{p}'" in source
                for p in _PRIORITY_STRINGS
            ):
                continue
            for line, text in find_priority_comparisons(source, rel):
                found.setdefault((rel, text), []).append(line)
    return found


@pytest.mark.spec("MS-02-004")
def test_no_priority_selection_compares_against_individual_members():
    found = _scan()
    offending = {
        key: lines for key, lines in found.items() if key not in _ALLOWLIST
    }
    assert not offending, (
        "Select by tier — `priority.is_must_tier` or `.tier` — not by "
        "comparing against RFC2119Priority members or "
        "priority strings (MS-02-004, MS-02-003):\n"
        + "\n".join(
            f"  {path}:{line}: {text}"
            for (path, text), lines in sorted(offending.items())
            for line in lines
        )
    )


@pytest.mark.spec("MS-02-004")
def test_allowlisted_exception_is_still_present_exactly_once():
    """Retiring the SR-11-003 exception must also delete its allowlist entry."""
    found = _scan()
    for key in _ALLOWLIST:
        assert (
            key in found
        ), f"allowlist entry no longer matches anything: {key}"
        assert (
            len(found[key]) == 1
        ), f"allowlist entry matched more than once: {key} at {found[key]}"


# ---------------------------------------------------------------------------
# The detector itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "snippet",
    [
        "ok = spec.priority == RFC2119Priority.MUST",
        "ok = spec.priority != RFC2119Priority.MUST_NOT",
        "ok = spec.priority is RFC2119Priority.MUST",
        "ok = spec.priority in (RFC2119Priority.SHOULD, RFC2119Priority.MAY)",
        'ok = spec.priority in ("MUST", "MUST_NOT")',
        'ok = spec.get("priority") == "MUST"',
        'ok = "SHOULD_NOT" == spec.priority.value',
        "ok = spec.priority.value in {'MAY'}",
        # the same member spelled through the enum's constructor or lookup
        'ok = spec.priority == RFC2119Priority("MUST")',
        'ok = spec.priority == RFC2119Priority["MUST_NOT"]',
        # a container bound to a name, then used for membership
        "_MUST_TIER = (RFC2119Priority.MUST, RFC2119Priority.MUST_NOT)\n"
        "ok = spec.priority in _MUST_TIER",
        "_MUST_TIER = frozenset({RFC2119Priority.MUST, RFC2119Priority.MUST_NOT})\n"
        "ok = spec.priority in _MUST_TIER",
        "_A = [RFC2119Priority.MUST]\n_B = frozenset(_A)\n"
        "ok = spec.priority not in _B",
        "_TIER: frozenset[str] = frozenset({'MUST', 'MUST_NOT'})\n"
        "ok = spec.priority in _TIER",
        # an import alias
        "from vultron.metadata.specs.schema import RFC2119Priority as P\n"
        "ok = spec.priority == P.MUST",
        # a match arm
        "match spec.priority:\n"
        "    case RFC2119Priority.MUST:\n"
        "        ok = True",
        "match spec.priority.value:\n"
        "    case 'MUST_NOT':\n"
        "        ok = True",
        # a same-valued non-priority string is flagged by value (known gap,
        # see the module docstring): allowlist it rather than weaken the gate
        'ok = x == "MAY"',
    ],
)
def test_detector_flags_member_and_string_comparisons(snippet):
    assert find_priority_comparisons(snippet, "<inline>") != []


@pytest.mark.parametrize(
    "snippet",
    [
        "ok = spec.priority.is_must_tier",
        "ok = not spec.priority.is_must_tier",
        "ok = spec.priority.tier is RFC2119Tier.MUST",
        'badge = {RFC2119Priority.MUST: "**MUST**"}',
        "ok = spec.priority.value != wanted",
        'ok = spec.get("kind") == "protocol"',
        # a conversion of a variable is not a literal
        'ok = RFC2119Priority(spec["priority"]) == wanted',
        "ok = RFC2119Priority[name] is wanted",
        # a name bound to something other than a priority container
        "_KINDS = ('protocol', 'process')\nok = spec.kind in _KINDS",
        # a match arm on something else
        "match spec.kind:\n    case 'protocol':\n        ok = True",
    ],
)
def test_detector_ignores_tier_selection_display_maps_and_variables(snippet):
    assert find_priority_comparisons(snippet, "<inline>") == []
