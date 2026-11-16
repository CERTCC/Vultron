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

"""Ratchet: no log call passes a correlation id through ``extra=`` (SL-02-003).

``activity_id`` and ``actor_id`` reach a record as attributes copied from
ambient context by :class:`vultron.logging_correlation.CorrelationFilter`,
never per call: a per-call ``extra=`` repeats the value at every site, and a
site that omits it writes a record with no correlation.

The scan walks ``vultron/`` with ``ast`` and flags a log call (as
``test/architecture/_log_calls.py`` recognises one) whose ``extra=`` names a
correlation field as a key of a dict literal (beside any ``**spread``) or a
keyword of a ``dict(...)`` call.  An ``extra=`` built elsewhere and passed as a
variable, or a key that only a ``**spread`` brings in, is not seen.
"""

import ast

from test.architecture import _corpus
from test.architecture._log_calls import is_log_call
from vultron.logging_correlation import CORRELATION_FIELDS

_PACKAGE_ROOT = _corpus.REPO_ROOT / "vultron"


def _extra_keys(value: ast.expr) -> set[str]:
    """Return the literal keys an ``extra=`` expression visibly sets."""
    if isinstance(value, ast.Dict):
        return {
            key.value
            for key in value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "dict"
    ):
        return {kw.arg for kw in value.keywords if kw.arg is not None}
    return set()


def _correlation_fields_in_extra(node: ast.Call) -> set[str]:
    """Return the correlation fields *node* passes through ``extra=``."""
    if not is_log_call(node):
        return set()
    fields: set[str] = set()
    for keyword in node.keywords:
        if keyword.arg == "extra":
            fields |= _extra_keys(keyword.value) & set(CORRELATION_FIELDS)
    return fields


def _violations_in(path_label: str, tree: ast.AST) -> list[str]:
    return [
        f"{path_label}:{node.lineno}: {field}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for field in sorted(_correlation_fields_in_extra(node))
    ]


def test_no_log_call_passes_correlation_ids_through_extra() -> None:
    """No log call in vultron/ sets activity_id or actor_id via extra= (SL-02-003)."""
    violations: list[str] = []
    for path, tree in _corpus.files_mentioning(
        *CORRELATION_FIELDS, under=_PACKAGE_ROOT
    ):
        rel = str(path.relative_to(_corpus.REPO_ROOT))
        violations.extend(_violations_in(rel, tree))
    assert not violations, (
        "Correlation ids MUST come from vultron.logging_correlation's ambient "
        "context, not per-call extra= (SL-02-003). Enter "
        "correlation_context(...) at the processing boundary instead, at:\n  "
        + "\n  ".join(violations)
    )


def test_detector_flags_dict_literal_and_dict_call() -> None:
    """Both spellings of ``extra=`` and every log method are caught.

    Without this, a detector bug would make the ratchet above vacuously
    green.
    """
    source = (
        'logger.info("x", extra={"activity_id": a})\n'
        'self.logger.warning("x", extra=dict(actor_id=b))\n'
        'logging.getLogger(__name__).log(10, "x", extra={"actor_id": b, '
        '"activity_id": a})\n'
    )
    assert _violations_in("<inline>", _corpus.parse_inline(source)) == [
        "<inline>:1: activity_id",
        "<inline>:2: actor_id",
        "<inline>:3: activity_id",
        "<inline>:3: actor_id",
    ]


def test_detector_ignores_other_extra_keys_and_non_log_calls() -> None:
    """Unrelated ``extra=`` keys and non-logger calls are not flagged."""
    source = (
        'logger.info("x", extra={"case_id": c})\n'
        'logger.info("actor %s", actor_id)\n'
        'build(extra={"actor_id": b})\n'
    )
    assert _violations_in("<inline>", _corpus.parse_inline(source)) == []


def test_detector_sees_keys_beside_a_spread_but_not_through_a_variable() -> (
    None
):
    """The documented limits: a ``**spread`` hides only its own keys."""
    source = (
        'logger.info("x", extra={**base, "actor_id": b})\n'
        'logger.info("x", extra={**base})\n'
        'logger.info("x", extra=fields)\n'
    )
    assert _violations_in("<inline>", _corpus.parse_inline(source)) == [
        "<inline>:1: actor_id",
    ]
