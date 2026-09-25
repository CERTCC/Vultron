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
"""The example activities an implementer copies, built once for every gate.

Every ``vocab_examples`` function that returns an activity and needs no
arguments, plus the examples ``docs/`` renders from elsewhere.  Shared by the
gates that ask different questions of the same corpus — is each example
dispatchable (``test_vocab_examples_dispatchable``), and is each one's received
evidence out of reach of the objects parsed from it
(``test_wire_artifact_immutability``) — so they can never disagree about what
the corpus is.  Why the collector is as permissive as it is is recorded in
``test_vocab_examples_dispatchable``'s module docstring.
"""

import inspect
from typing import Any

from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.examples import (
    submit_report_tutorial,
    vocab_examples,
)

# Helpers and module plumbing reachable from ``vocab_examples``' star-imports that
# are not example factories.
#
# ``main`` is load-bearing here, not belt-and-braces: its only parameter is
# ``outdir=None``, so under the "no *required* parameters" rule it is callable, and
# calling it writes all 60 artifacts into the repo's ``docs/reference/examples/``.
_NOT_EXAMPLES = frozenset(
    {
        "main",
        "cast",
        "obj_to_file",
        "json2md",
        "print_obj",
        "case",
        "gen_report",
    }
)

_EXAMPLES_PACKAGE = "vultron.wire.as2.vocab.examples"

# Activity examples rendered under ``docs/`` that ``vocab_examples`` does not
# re-export, so scanning that module alone cannot see them.  Keyed by the name the
# test parametrization reports.
_EXTRA_SOURCES = {
    "submit_report_tutorial.create_report_activity": (
        submit_report_tutorial.create_report_activity
    ),
}


def _takes_no_required_arguments(value: object) -> bool:
    """Whether ``value`` can be called with no arguments.

    Not "declares no parameters": the four ``report.py`` examples take a defaulted
    ``verbose``, and testing for an empty parameter list skipped all of them.
    """
    try:
        parameters = inspect.signature(value).parameters.values()  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return all(
        p.default is not inspect.Parameter.empty
        or p.kind
        in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for p in parameters
    )


def activity_examples() -> dict[str, as_Activity]:
    """Build every example that returns an activity and needs no arguments.

    Object examples (``vendor()``, ``case_participant()``, …) are skipped: a
    pattern matches an activity, so an object has nothing to dispatch.  Activities
    are *not* narrowed to the transitive ones — see
    ``test_vocab_examples_dispatchable``'s module docstring.
    """
    built: dict[str, as_Activity] = {}
    candidates: list[tuple[str, object]] = list(vars(vocab_examples).items())
    candidates += list(_EXTRA_SOURCES.items())
    for name, value in candidates:
        if name.startswith("_") or name in _NOT_EXAMPLES:
            continue
        if not callable(value):
            continue
        if not getattr(value, "__module__", "").startswith(_EXAMPLES_PACKAGE):
            continue
        if not _takes_no_required_arguments(value):
            continue
        result = value()
        if isinstance(result, as_Activity):
            built[name] = result
    return built


def wire_body(activity: as_Activity) -> dict[str, Any]:
    """The JSON body a sender delivers for *activity*.

    Dumped as ``outbox_delivery`` dumps it.  ``serialize_as_any`` matters: without
    it a field typed as a parent class dumps only the parent's fields, so an inline
    ``CaseProposal`` loses the ``object``/``target`` a receiver requires and the
    body no longer parses.
    """
    return activity.model_dump(
        mode="json", by_alias=True, exclude_none=True, serialize_as_any=True
    )
