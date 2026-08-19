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

"""Architecture ratchet: no demo_step/demo_check block may leave a variable
unbound for a later read (issue #2308).

``demo_step`` and ``demo_check`` swallow all exceptions by design: they record
the failure on ``_demo_failures`` and continue.  When a block's body raises,
any variable assigned *only* inside that block is left unbound — the next read
causes ``UnboundLocalError``, which propagates out of the demo function and
prevents ``assert_demo_success()`` from being reached.

The fix is always the same: pre-initialize the variable to a safe sentinel
(typically ``None``) *before* the ``with demo_step/demo_check`` block.

This test walks every ``*.py`` file under ``vultron/demo/`` with the Python
AST and fails if any function contains a variable that is:

1. Assigned for the first time inside a ``demo_step`` or ``demo_check`` block
   body (at the shallow / direct-child level of that block), AND
2. Used (read) after the block closes in the same function scope.

Once all 93 sites documented in issue #2308 are fixed this test becomes a
permanent ratchet — adding a new undefended site will cause the CI job to
fail.
"""

import ast
import pathlib

DEMO_DIR = pathlib.Path(__file__).parent.parent.parent / "vultron" / "demo"

_GUARDED_CMS = {"demo_step", "demo_check"}


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _cm_name(with_stmt: ast.With) -> str | None:
    """Return the guarded CM name if any with-item is a guarded CM, else None."""
    for item in with_stmt.items:
        ctx = item.context_expr
        if isinstance(ctx, ast.Call):
            fn = ctx.func
            name = (
                fn.id
                if isinstance(fn, ast.Name)
                else fn.attr if isinstance(fn, ast.Attribute) else None
            )
            if name in _GUARDED_CMS:
                return name
    return None


def _store_names(node: ast.expr) -> set:
    """All names in Store context inside an assignment target."""
    names: set = set()
    if isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            names.update(_store_names(elt))
    elif isinstance(node, ast.Starred):
        names.update(_store_names(node.value))
    return names


def _assigned_shallow(stmts: list) -> set:
    """Names directly assigned (not nested) in a flat statement list."""
    names: set = set()
    for stmt in stmts:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                names.update(_store_names(target))
        elif isinstance(stmt, ast.AugAssign):
            names.update(_store_names(stmt.target))
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            names.update(_store_names(stmt.target))
        elif isinstance(stmt, ast.For):
            names.update(_store_names(stmt.target))
        elif isinstance(stmt, ast.With):
            for item in stmt.items:
                if item.optional_vars:
                    names.update(_store_names(item.optional_vars))
    return names


def _load_names(stmts: list) -> set:
    """All Load-context Name ids anywhere within a statement list."""
    names: set = set()
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                names.add(node.id)
    return names


def _undefended_in_stmts(stmts: list) -> list:
    """Return ``(lineno, varname)`` pairs for every undefended site.

    Scans a flat list of statements (a function body) left-to-right,
    tracking which names have been assigned before each ``with`` block.
    """
    results = []
    pre: set = set()

    for i, stmt in enumerate(stmts):
        if not isinstance(stmt, ast.With):
            pre.update(_assigned_shallow([stmt]))
            continue

        cm = _cm_name(stmt)
        if cm not in _GUARDED_CMS:
            pre.update(_assigned_shallow([stmt]))
            continue

        block_assigned = _assigned_shallow(stmt.body)
        undefended = block_assigned - pre

        if undefended:
            post_used = _load_names(stmts[i + 1 :])
            for var in sorted(undefended & post_used):
                results.append((stmt.lineno, var))

        # After the block the var *might* exist; track it to avoid
        # double-reporting on a subsequent block that re-uses the same name.
        pre.update(block_assigned)

    return results


def _violations_in_file(path: pathlib.Path) -> list:
    source = path.read_text()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    found = []

    class _V(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            for lineno, var in _undefended_in_stmts(node.body):
                found.append((path, lineno, var))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            for lineno, var in _undefended_in_stmts(node.body):
                found.append((path, lineno, var))
            self.generic_visit(node)

    _V().visit(tree)
    return found


# ---------------------------------------------------------------------------
# The ratchet test
# ---------------------------------------------------------------------------


def test_no_undefended_demo_step_vars():
    """No demo_step/demo_check block may leave a variable unbound (issue #2308).

    Every variable whose first assignment lives inside a ``demo_step`` or
    ``demo_check`` block body *and* is read after the block closes must be
    pre-initialized to a safe sentinel (e.g. ``None``) before the block.
    """
    violations = []
    for path in sorted(DEMO_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for fpath, lineno, var in _violations_in_file(path):
            rel = fpath.relative_to(DEMO_DIR.parent.parent)
            violations.append(f"{rel}:{lineno}: undefended var '{var}'")

    assert violations == [], (
        "Variables assigned only inside demo_step/demo_check blocks "
        "and read afterward without prior initialization (issue #2308):\n"
        + "\n".join(violations)
    )
