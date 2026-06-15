"""Structural enforcement tests for BTND-07 BT module layout.

Implements CI enforcement for the following spec requirements:

- BTND-07-001: BT-bearing areas MUST use a ``nodes/`` subpackage for leaf
  nodes; a flat ``nodes.py`` at the area root is non-compliant.
- BTND-07-003: Tree composition files MUST be root-level ``*_tree.py``
  modules inside the BT area (not inside ``nodes/``).
- BTND-07-004: ``nodes/`` leaf modules MUST NOT exceed 500 lines.

A **BT-bearing area** is any direct subdirectory of
``vultron/core/behaviors/`` that contains at least one ``*_tree.py`` file.
Helper-only areas (no ``*_tree.py`` files) are exempt from these checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
BEHAVIORS_ROOT = REPO_ROOT / "vultron" / "core" / "behaviors"

_MAX_LEAF_LINES = 500


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def _bt_bearing_areas() -> list[Path]:
    """Return subdirectories of behaviors/ that have at least one *_tree.py.

    Areas without any ``*_tree.py`` files are treated as helper-only and are
    exempt from BTND-07 structure checks.
    """
    if not BEHAVIORS_ROOT.is_dir():
        return []
    areas = []
    for child in sorted(BEHAVIORS_ROOT.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_") or child.name == "__pycache__":
            continue
        if any(child.rglob("*_tree.py")):
            areas.append(child)
    return areas


def _leaf_modules(area: Path) -> list[Path]:
    """Return non-init .py files inside the nodes/ subpackage of an area.

    ``__init__.py`` files are excluded because they serve as re-export
    facades whose size is proportional to the number of public names, not
    implementation complexity.
    """
    nodes_dir = area / "nodes"
    if not nodes_dir.is_dir():
        return []
    return sorted(
        p
        for p in nodes_dir.rglob("*.py")
        if p.name != "__init__.py" and "__pycache__" not in p.parts
    )


# ---------------------------------------------------------------------------
# Collected parametrize inputs (evaluated once at collection time)
# ---------------------------------------------------------------------------

_BT_AREAS: list[Path] = _bt_bearing_areas()
_AREA_IDS: list[str] = [a.name for a in _BT_AREAS]

_LEAF_PARAMS = [
    pytest.param(
        area,
        mod,
        id=f"{area.name}/{mod.relative_to(area / 'nodes')}",
    )
    for area in _BT_AREAS
    for mod in _leaf_modules(area)
]


# ---------------------------------------------------------------------------
# Sanity / discovery tests
# ---------------------------------------------------------------------------


def test_behaviors_root_exists() -> None:
    """The behaviors root directory must exist for BTND-07 checks to run."""
    assert BEHAVIORS_ROOT.is_dir(), (
        f"BEHAVIORS_ROOT not found: {BEHAVIORS_ROOT}. "
        "Check that the repository layout has not changed."
    )


def test_bt_bearing_areas_detected() -> None:
    """At least one BT-bearing area must be discovered.

    Guards against the discovery helper silently returning an empty list
    if BEHAVIORS_ROOT is wrong or the layout has been moved.
    """
    assert _BT_AREAS, (
        f"No BT-bearing areas found under {BEHAVIORS_ROOT}. "
        "Check that BEHAVIORS_ROOT is correct and that at least one "
        "subdirectory contains a *_tree.py file."
    )


# ---------------------------------------------------------------------------
# BTND-07-001: nodes/ subpackage required; flat nodes.py prohibited
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("area", _BT_AREAS, ids=_AREA_IDS)
def test_bt_area_has_nodes_subpackage(area: Path) -> None:
    """BTND-07-001: BT-bearing area MUST have a nodes/ subpackage.

    The ``nodes/`` directory must exist and contain an ``__init__.py`` so
    that leaf node modules can be imported as a package.
    """
    nodes_dir = area / "nodes"
    init_py = nodes_dir / "__init__.py"

    assert nodes_dir.is_dir(), (
        f"{area.name}: missing nodes/ subpackage directory (BTND-07-001). "
        f"Create {nodes_dir.relative_to(REPO_ROOT)}/ and add __init__.py."
    )
    assert init_py.is_file(), (
        f"{area.name}/nodes/: directory exists but is missing __init__.py "
        f"(BTND-07-001). "
        f"Add {init_py.relative_to(REPO_ROOT)}."
    )


@pytest.mark.parametrize("area", _BT_AREAS, ids=_AREA_IDS)
def test_bt_area_has_no_flat_nodes_module(area: Path) -> None:
    """BTND-07-001: BT-bearing area MUST NOT have a flat nodes.py module.

    A flat ``nodes.py`` at the area root is non-compliant regardless of
    size. All leaf nodes must live under the ``nodes/`` subpackage.
    """
    flat_nodes = area / "nodes.py"
    assert not flat_nodes.exists(), (
        f"{area.name}: flat nodes.py is non-compliant (BTND-07-001). "
        "Convert it to a nodes/ subpackage with a __init__.py re-export."
    )


# ---------------------------------------------------------------------------
# BTND-07-003: tree composition files belong at the area root
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("area", _BT_AREAS, ids=_AREA_IDS)
def test_tree_files_not_inside_nodes(area: Path) -> None:
    """BTND-07-003: *_tree.py files MUST NOT appear inside nodes/.

    Tree composition belongs at the top level of the BT area. Leaf nodes
    in ``nodes/`` implement atomic behaviors; they do not compose trees.
    """
    nodes_dir = area / "nodes"
    if not nodes_dir.is_dir():
        return  # caught by test_bt_area_has_nodes_subpackage

    misplaced = sorted(nodes_dir.rglob("*_tree.py"))
    if misplaced:
        paths = "\n".join(f"  {p.relative_to(REPO_ROOT)}" for p in misplaced)
        raise AssertionError(
            f"{area.name}: *_tree.py files found inside nodes/ "
            f"(BTND-07-003). Move them to "
            f"{area.relative_to(REPO_ROOT)}/:\n{paths}"
        )


# ---------------------------------------------------------------------------
# BTND-07-004: leaf module line-count limit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("area,module", _LEAF_PARAMS)
def test_leaf_module_line_count(area: Path, module: Path) -> None:
    """BTND-07-004: nodes/ leaf modules MUST NOT exceed 500 lines.

    Any module under ``nodes/`` (or its sub-packages) that grows beyond
    500 lines is a candidate for further decomposition by semantic concern
    (e.g., conditions.py, lifecycle.py, actions.py).
    """
    line_count = len(module.read_text(encoding="utf-8").splitlines())
    rel = module.relative_to(REPO_ROOT)
    assert line_count <= _MAX_LEAF_LINES, (
        f"{rel}: {line_count} lines exceeds the {_MAX_LEAF_LINES}-line "
        "limit (BTND-07-004). Decompose into smaller submodules grouped "
        "by semantic concern."
    )
