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

Which calls count as log calls, and what that recognition cannot see, is
``test/architecture/_log_calls.py``.

Source concern: #1968.  Implementation: #1988.
"""

import ast

from test.architecture import _corpus
from test.architecture._log_calls import (
    first_argument_text,
    is_logger_info_call,
)

_PACKAGE_ROOT = _corpus.REPO_ROOT / "vultron"

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
    "already stored — skipping",
)


def _find_violations() -> list[str]:
    """Return ``"<path>:<line>: <fragment>"`` for every INFO-level violation."""
    violations: list[str] = []
    for path, tree in _corpus.files_mentioning(
        *DEMOTED_FRAGMENTS, under=_PACKAGE_ROOT
    ):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not is_logger_info_call(node):
                continue
            message = first_argument_text(node)
            for fragment in DEMOTED_FRAGMENTS:
                if fragment in message:
                    rel = path.relative_to(_corpus.REPO_ROOT)
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
    tree = _corpus.parse_inline(source)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert len(calls) == 1
    assert is_logger_info_call(calls[0])
    assert "DataLayer stored" in first_argument_text(calls[0])


def test_detector_recognises_fstring_and_self_logger() -> None:
    """f-string messages on ``self.logger`` are matched too."""
    source = 'self.logger.info(f"BT structure:\\n{tree_repr}")\n'
    tree = _corpus.parse_inline(source)
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    assert is_logger_info_call(call)
    assert "BT structure" in first_argument_text(call)


def test_detector_ignores_debug_calls() -> None:
    """``logger.debug`` calls are not flagged."""
    source = 'logger.debug("DataLayer stored %s", x)\n'
    tree = _corpus.parse_inline(source)
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    assert not is_logger_info_call(call)


def test_detector_recognises_inline_and_factory_loggers() -> None:
    """``getLogger(...).info`` and ``node_logger(...).info`` are matched too."""
    source = (
        'logging.getLogger(__name__).info("DataLayer stored %s", x)\n'
        'node_logger(node).info("Final BT state: %s", y)\n'
        'logging.info("Parsing activity from %s", z)\n'
    )
    tree = _corpus.parse_inline(source)
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "info"
    ]
    assert len(calls) == 3
    assert all(is_logger_info_call(call) for call in calls)
