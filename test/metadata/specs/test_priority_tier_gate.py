"""Static gate: priority selection goes through the shared tier definition.

MS-02-004: code that selects spec requirements by priority obtains the
MS-02-003 tiering from ``RFC2119Priority.tier`` (or ``is_must_tier``), never
by comparing against individual enum members or priority strings. The literal comparison is easy to write and fails silently —
the prohibitions drop out and nothing errors — so this test reads the Python
under ``vultron/metadata/specs/`` and ``scripts/`` and fails on any
``Compare`` node whose operands include an ``RFC2119Priority.<MEMBER>``
attribute, a priority string, or a tuple/list/set of either.

Display maps that label each member (``{RFC2119Priority.MUST: "..."}``) are
``Dict`` nodes, not comparisons, and are out of scope by construction.

The one allowlisted comparison is SR-11-003's selector, the recorded MS-02-003
exception. The allowlist is two-sided: an entry that no longer matches fails
too, so retiring the exception removes it here in the same change.

Requirements: specs/meta-specifications.yaml MS-02-004.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from vultron.metadata.specs.schema import RFC2119Priority

_REPO_ROOT = Path(__file__).parents[3]
_SCAN_ROOTS = (
    _REPO_ROOT / "vultron" / "metadata" / "specs",
    _REPO_ROOT / "scripts",
)

_PRIORITY_STRINGS = frozenset(p.value for p in RFC2119Priority)

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


def _is_priority_literal(node: ast.expr) -> bool:
    """An ``RFC2119Priority.<MEMBER>``, a priority string, or a container of them."""
    if isinstance(node, ast.Attribute):
        return (
            isinstance(node.value, ast.Name)
            and node.value.id == RFC2119Priority.__name__
            and node.attr in RFC2119Priority.__members__
        )
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and node.value in _PRIORITY_STRINGS
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return any(_is_priority_literal(elt) for elt in node.elts)
    return False


def find_priority_comparisons(
    source: str, filename: str
) -> list[tuple[int, str]]:
    """``(line, comparison text)`` for every comparison against a priority literal."""
    tree = ast.parse(source, filename=filename)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if any(
            _is_priority_literal(n) for n in (node.left, *node.comparators)
        ):
            hits.append((node.lineno, ast.unparse(node)))
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
        "ok = spec.priority in (RFC2119Priority.SHOULD, RFC2119Priority.MAY)",
        'ok = spec.priority in ("MUST", "MUST_NOT")',
        'ok = spec.get("priority") == "MUST"',
        'ok = "SHOULD_NOT" == spec.priority.value',
        "ok = spec.priority.value in {'MAY'}",
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
    ],
)
def test_detector_ignores_tier_selection_display_maps_and_variables(snippet):
    assert find_priority_comparisons(snippet, "<inline>") == []
