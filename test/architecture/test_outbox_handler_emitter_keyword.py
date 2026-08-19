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
"""Architecture invariant: ``outbox_handler``'s emitter is passed by keyword.

``outbox_handler(actor_id, dl, emitter=None)`` used to be
``outbox_handler(actor_id, dl, shared_dl, emitter)``.  When ADR-0066 deleted the
shared DataLayer, the third *positional* slot changed meaning from "a store" to
"the emitter" while every call site kept passing a store — so ``emitter`` became
a ``SqliteDataLayer`` and ``await emitter.emit(...)`` raised ``AttributeError``
on the first outbox item that actually had a recipient.  30 call sites across the
five trigger routers were affected, and unit tests missed all of them because a
route with nothing to deliver returns before touching the emitter.

This ratchet removes the shape rather than the instance: a positional third
argument to ``outbox_handler`` is forbidden outright, so a store can never slide
into the emitter slot again.  Callers that need to name an emitter pass
``emitter=``, which cannot be mistaken for a store at a glance or by a type
checker.

Issue: #2238
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
_SEARCH_ROOTS = (REPO_ROOT / "vultron", REPO_ROOT / "test")


def _label(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _is_outbox_handler_ref(node: ast.expr) -> bool:
    """True for ``outbox_handler`` and ``<module>.outbox_handler``."""
    return (isinstance(node, ast.Name) and node.id == "outbox_handler") or (
        isinstance(node, ast.Attribute) and node.attr == "outbox_handler"
    )


def _positional_args_to_outbox_handler(tree: ast.AST):
    """Yield (node, positional_args) for every call that runs outbox_handler.

    Two shapes reach it: a direct call, and scheduling it as a background task
    via ``background_tasks.add_task(outbox_handler, ...)``, where add_task
    forwards its remaining positional arguments.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_outbox_handler_ref(node.func):
            yield node, node.args
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_task"
            and node.args
            and _is_outbox_handler_ref(node.args[0])
        ):
            yield node, node.args[1:]


def _iter_sources():
    for root in _SEARCH_ROOTS:
        for path in sorted(root.rglob("*.py")):
            yield path


def test_outbox_handler_never_takes_a_positional_emitter():
    """No call site passes outbox_handler a third positional argument."""
    violations: list[str] = []

    for path in _iter_sources():
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - not expected in-tree
            continue
        for node, args in _positional_args_to_outbox_handler(tree):
            if len(args) > 2:
                violations.append(
                    f"{_label(path)}:{node.lineno}: outbox_handler receives"
                    f" {len(args)} positional arguments"
                    f" ({ast.unparse(args[2])!r} in the emitter slot);"
                    " pass the emitter as emitter=..."
                )

    assert not violations, (
        "outbox_handler must not be given a positional emitter — the slot used"
        " to hold the shared DataLayer, so a store passed here becomes the"
        " emitter and delivery fails at await emitter.emit(). Offenders:\n"
        + "\n".join(violations)
    )


def test_ratchet_detects_a_positional_emitter():
    """The ratchet fires on the shape it exists to forbid.

    Without this, a change that broke ``_positional_args_to_outbox_handler``
    would make the ratchet above pass vacuously.
    """
    regressed = ast.parse(
        "background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)\n"
        "outbox_handler(actor_id, actor_dl, shared_dl)\n"
    )
    found = [
        args for _node, args in _positional_args_to_outbox_handler(regressed)
    ]
    assert len(found) == 2, "both call shapes must be recognised"
    assert all(len(args) == 3 for args in found)


def test_ratchet_accepts_the_corrected_shapes():
    """Two-positional calls and keyword emitters do not trip the ratchet."""
    ok = ast.parse(
        "background_tasks.add_task(outbox_handler, actor_id, actor_dl)\n"
        "background_tasks.add_task("
        "    outbox_handler, actor_id, actor_dl, emitter=emitter)\n"
        "await outbox_handler(actor_id, actor_dl, emitter=emitter)\n"
        "asyncio.run(outbox_handler(actor_id, actor_dl))\n"
    )
    for _node, args in _positional_args_to_outbox_handler(ok):
        assert len(args) <= 2, ast.unparse(_node)
