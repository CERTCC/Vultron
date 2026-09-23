#!/usr/bin/env python

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
"""Ratchets: loader failure attribution stays in one tooling-layer helper.

MS-17-003 — no module under ``vultron/metadata/`` other than
``file_loading.py`` may re-raise a caught exception as a path-prefixed
``ValueError``: ``except ...: raise ValueError(f"{path}: ...")``. That is the
shape every hand-written copy took before the shared helper existed. The
ratchet looks for that shape rather than for a caught YAML exception, because
every copy caught bare ``Exception`` — a YAML-specific check passes with all of
the duplication still in place.

MS-17-004 — no module under ``vultron/metadata/`` may import from
``vultron/errors.py``. The ``VultronError`` hierarchy is the protocol's, and
extending it here would break the ``ValueError`` contract these loaders
document.
"""

import ast

import pytest

from test.architecture import _corpus

_METADATA_ROOT = _corpus.REPO_ROOT / "vultron" / "metadata"
_HELPER = _METADATA_ROOT / "file_loading.py"


def _metadata_trees():
    """Parsed modules under ``vultron/metadata/``; never empty.

    Both ratchets pass vacuously over an empty scan, so a path or corpus-cache
    change that finds nothing fails here instead.
    """
    trees = list(_corpus.all_trees(under=_METADATA_ROOT))
    assert _HELPER in {
        path for path, _ in trees
    }, f"corpus scan of {_METADATA_ROOT} did not reach {_HELPER.name}"
    return trees


def _path_prefixed_reraises(tree: ast.AST) -> list[int]:
    """Return line numbers of ``raise ValueError(f"{x}...")`` in an except body.

    "Path-prefixed" means the f-string *opens* with an interpolation — the
    ``f"{path}: ..."`` / ``f"{key}: ..."`` form. A message that opens with
    literal text (``f"README generation failed: {exc}"``) is a caller adding
    context, not a private attribution wrapper.
    """
    lines: list[int] = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler):
            continue
        for node in ast.walk(handler):
            if not (isinstance(node, ast.Raise) and node.exc is not None):
                continue
            call = node.exc
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "ValueError"
                and call.args
                and isinstance(call.args[0], ast.JoinedStr)
                and call.args[0].values
                and isinstance(call.args[0].values[0], ast.FormattedValue)
            ):
                continue
            lines.append(node.lineno)
    return lines


@pytest.mark.spec("MS-17-003")
def test_no_private_attribution_wrapper_outside_the_helper():
    """Every loader obtains file attribution from ``file_loading.py``."""
    violations = [
        f"{path.relative_to(_corpus.REPO_ROOT)}:{line}"
        for path, tree in _metadata_trees()
        if path != _HELPER
        for line in _path_prefixed_reraises(tree)
    ]

    assert violations == [], (
        "These re-raise a caught exception as a path-prefixed ValueError — a "
        "private copy of the attribution wrapper (MS-17-003). Route the parse "
        "through file_loading.load_yaml / load_frontmatter and the model "
        "through file_loading.validate instead:\n  " + "\n  ".join(violations)
    )


@pytest.mark.spec("MS-17-003")
@pytest.mark.parametrize(
    "source",
    [
        # adr/loader.py's load_adr_post, as it was.
        "try:\n    f()\nexcept Exception as exc:\n"
        '    raise ValueError(f"{path}: malformed YAML: {exc}") from exc\n',
        # adr/loader.py's model_validate guard, as it was.
        "try:\n    f()\nexcept Exception as exc:\n"
        '    raise ValueError(f"{key}: {exc}") from exc\n',
    ],
    ids=["parse-wrapper", "validate-wrapper"],
)
def test_the_ratchet_detects_the_removed_copies(source):
    """Guard against a vacuous pass: the shapes it replaced still match."""
    assert _path_prefixed_reraises(_corpus.parse_inline(source)) == [4]


@pytest.mark.spec("MS-17-003")
def test_the_ratchet_ignores_context_added_by_a_caller():
    """A message opening with literal text is not an attribution wrapper."""
    source = (
        "try:\n    f()\nexcept Exception as exc:\n"
        '    raise ValueError(f"README generation failed: {exc}") from exc\n'
    )

    assert _path_prefixed_reraises(_corpus.parse_inline(source)) == []


@pytest.mark.spec("MS-17-004")
def test_metadata_does_not_import_the_protocol_error_hierarchy():
    """``vultron/errors.py`` belongs to the protocol domain, not tooling."""
    violations: list[str] = []
    for path, tree in _metadata_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # ``from vultron import errors`` names the module as an alias.
                modules = [node.module or ""] + [
                    f"{node.module}.{alias.name}" for alias in node.names
                ]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            if any(
                m == "vultron.errors" or m.startswith("vultron.errors.")
                for m in modules
            ):
                violations.append(
                    f"{path.relative_to(_corpus.REPO_ROOT)}:{node.lineno}"
                )

    assert violations == [], (
        "vultron/metadata/ must not import vultron.errors (MS-17-004); raise "
        "file_loading.MetadataLoadError, a ValueError subclass:\n  "
        + "\n  ".join(violations)
    )
