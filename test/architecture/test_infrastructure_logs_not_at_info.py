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

"""Ratchet: infrastructure log lines MUST NOT be emitted at INFO (SL-04-007).

Infrastructure chatter (persistence store/save/update, BT scaffolding dumps,
HTTP handler parsing echoes, pipeline completion repeats, per-recipient sync
queue entries, routine idempotency skips) drowns out the CVD protocol story on
the INFO channel.  ``specs/structured-logging.yaml`` SL-04-007 makes DEBUG-or-
lower mandatory for these patterns.

This test is the executable form of the grep check documented in
``notes/structured-logging.md`` § "Grep check after refactor": it walks the
``vultron/`` tree with ``ast`` and fails when any demoted message fragment
appears as the first argument of a ``logger.info(...)`` / ``self.logger.info(...)``
call.

Source concern: #1968.  Implementation: #1988.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_PACKAGE_ROOT = REPO_ROOT / "vultron"

#: Message fragments that MUST NOT appear in a ``logger.info()`` format string.
#:
#: Each entry corresponds to a row in the SL-04-007 demotion table in
#: ``notes/structured-logging.md``.
DEMOTED_FRAGMENTS: tuple[str, ...] = (
    "DataLayer stored",
    "DataLayer saved",
    "DataLayer updated",
    "BT structure",
    "Final BT state",
    "Parsing activity from",
    "Processing outbox for actor",
    "process_payload: outcome",
    "run_inbox_pipeline: status",
    "run_inbox_pipeline: replayed",
    "sync adapter: queued Announce(CaseLedgerEntry)",
    "store_embedded_participants: stored participant",
    "already exists locally",
    "already received by",
)


#: Coverage limits — deliberate, but worth knowing before trusting a green run:
#:
#: - Only receivers named ``logger`` / ``_LOGGER`` / ``log``, or attributes
#:   ``.logger`` / ``._logger``, are recognised. An inline
#:   ``logging.getLogger(__name__).info(...)`` is not matched.
#: - Only the *first* argument is inspected, so a message pre-built with ``%``
#:   or ``.format()`` and passed as a variable is not matched.
#:
#: Both patterns are absent from ``vultron/`` today. If one is introduced,
#: extend ``_is_logger_info_call`` / ``_format_string`` rather than assuming
#: this ratchet already covers it.


def _is_logger_info_call(node: ast.Call) -> bool:
    """Return True when *node* is a ``<something>.logger.info`` / ``logger.info`` call."""
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "info":
        return False
    receiver = func.value
    if isinstance(receiver, ast.Name):
        return receiver.id in {"logger", "_LOGGER", "log"}
    if isinstance(receiver, ast.Attribute):
        return receiver.attr in {"logger", "_logger"}
    return False


def _format_string(node: ast.Call) -> str:
    """Return the literal text of *node*'s first argument, or ``""``.

    Handles plain string literals, implicitly-concatenated literals (which
    ``ast`` folds into one ``Constant``), and f-strings, whose literal
    segments are concatenated so fragments spanning an interpolation are
    still detected.
    """
    if not node.args:
        return ""
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, ast.JoinedStr):
        return "".join(
            part.value
            for part in first.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    return ""


def _find_violations() -> list[str]:
    """Return ``"<path>:<line>: <fragment>"`` for every INFO-level violation."""
    violations: list[str] = []
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        # Cheap prefilter: only files that mention a demoted fragment at all
        # are worth parsing (keeps this well under the 5s per-test timeout).
        if not any(fragment in source for fragment in DEMOTED_FRAGMENTS):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_logger_info_call(
                node
            ):
                continue
            message = _format_string(node)
            for fragment in DEMOTED_FRAGMENTS:
                if fragment in message:
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{node.lineno}: {fragment!r}")
    return violations


def test_no_demoted_infrastructure_patterns_at_info() -> None:
    """No SL-04-007 demoted pattern is logged at INFO anywhere in vultron/."""
    violations = _find_violations()
    assert not violations, (
        "Infrastructure log lines MUST be DEBUG or lower (SL-04-007).\n"
        "Change logger.info(...) to logger.debug(...) at:\n  "
        + "\n  ".join(violations)
    )


def test_detector_recognises_a_violation() -> None:
    """The AST detector actually matches a logger.info call it should catch.

    Without this, a detector bug would make the ratchet above vacuously
    green.
    """
    source = 'logger.info("DataLayer stored %s", x)\n'
    tree = ast.parse(source)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert len(calls) == 1
    assert _is_logger_info_call(calls[0])
    assert "DataLayer stored" in _format_string(calls[0])


def test_detector_recognises_fstring_and_self_logger() -> None:
    """f-string messages on ``self.logger`` are matched too."""
    source = 'self.logger.info(f"BT structure:\\n{tree_repr}")\n'
    tree = ast.parse(source)
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    assert _is_logger_info_call(call)
    assert "BT structure" in _format_string(call)


def test_detector_ignores_debug_calls() -> None:
    """``logger.debug`` calls are not flagged."""
    source = 'logger.debug("DataLayer stored %s", x)\n'
    tree = ast.parse(source)
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    assert not _is_logger_info_call(call)
