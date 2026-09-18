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
"""Ratchet: every example activity must be dispatchable by exactly one pattern.

The ``vocab_examples`` functions are the wire examples rendered on
``docs/reference/messages/*.md`` and written to ``docs/reference/examples/*.json``.
They are what an implementer copies.  Two existing gates check them and neither
asks the question that matters: ``test_vocab_utils.py`` asserts each one executes
and serializes, and ``test_vocab_examples_current.py`` asserts the committed
artifact file list is current.  An example can therefore be well-formed,
committed, rendered on a reference page — and undispatchable, because no
registered ``ActivityPattern`` matches it.

Two defects found when this was first measured:

* ``remove_participant_from_case`` named the case in ``origin``.  ``ActivityPattern``
  has no ``origin_`` field, and ``RemoveCaseParticipantFromCasePattern``
  discriminates on ``target_``, so the example matched none of the patterns and
  ``docs/reference/messages/case_management.md`` documented the wrong field
  (fixed, #3438).
* ``read_report`` builds ``Read(Report)`` while ``AckReportPattern`` requires
  ``Read(Offer(Report))`` — the emit path and the receive path disagree about the
  ``RK`` wire form (#3439, the ``xfail`` below).

*Exactly* one match rather than at least one: two patterns matching the same
activity is the ambiguity SE-08-001 forbids, and it makes dispatch depend on
registry order.

Source: ISSUE-3003.
"""

import inspect

import pytest

from vultron.wire.as2.extractor import _instances
from vultron.wire.as2.extractor._pattern import ActivityPattern
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.examples import vocab_examples

# Helpers and module plumbing reachable from ``vocab_examples``' star-imports that
# are not example factories.
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

# Examples whose shape is known-wrong, each with the issue that owns the fix.
# Remove the entry when the issue closes; the ``strict`` xfail below fails if one
# starts passing, so a stale exemption cannot linger.
_KNOWN_UNDISPATCHABLE = {
    "read_report": "#3439 — emit builds Read(Report), AckReportPattern requires Read(Offer(Report))",
}


def _patterns() -> list[tuple[str, ActivityPattern]]:
    """Every registered ``ActivityPattern``, by attribute name.

    Read from the private module: ``extractor/__init__`` re-exports only a subset,
    so the public surface would leave the unexported patterns invisible here.
    """
    return [
        (name, value)
        for name, value in vars(_instances).items()
        if isinstance(value, ActivityPattern)
    ]


def _activity_examples() -> dict[str, as_TransitiveActivity]:
    """Build every zero-argument example that returns a transitive activity.

    Object examples (``vendor()``, ``case_participant()``, …) are skipped: a
    pattern matches an activity, so an object has nothing to dispatch.
    """
    built: dict[str, as_TransitiveActivity] = {}
    for name, value in vars(vocab_examples).items():
        if name.startswith("_") or name in _NOT_EXAMPLES:
            continue
        if not callable(value):
            continue
        if not getattr(value, "__module__", "").startswith(_EXAMPLES_PACKAGE):
            continue
        try:
            if len(inspect.signature(value).parameters) != 0:
                continue
        except (TypeError, ValueError):
            continue
        result = value()
        if isinstance(result, as_TransitiveActivity):
            built[name] = result
    return built


_ACTIVITY_EXAMPLES = _activity_examples()


def _matching_pattern_names(activity: as_TransitiveActivity) -> list[str]:
    return sorted(name for name, p in _patterns() if p.match(activity))


def test_pattern_registry_is_not_empty():
    """A gate that resolves no patterns would pass vacuously (DF-09-009)."""
    assert len(_patterns()) > 40, (
        f"Only {len(_patterns())} ActivityPattern instances found in "
        "vultron/wire/as2/extractor/_instances.py. Either the registry shrank "
        "drastically or this test is no longer reading it."
    )


def test_activity_examples_were_collected():
    """The collector must find examples, or a passing run proves nothing."""
    assert len(_ACTIVITY_EXAMPLES) > 40, (
        f"Only {len(_ACTIVITY_EXAMPLES)} activity examples collected from "
        "vocab_examples. The example module layout or the transitive-activity "
        "base class has probably changed; update _activity_examples()."
    )


@pytest.mark.parametrize(
    "example_name",
    sorted(
        name
        for name in _ACTIVITY_EXAMPLES
        if name not in _KNOWN_UNDISPATCHABLE
    ),
)
def test_example_activity_matches_exactly_one_pattern(example_name: str):
    """A rendered wire example must be dispatchable, and unambiguously so."""
    activity = _ACTIVITY_EXAMPLES[example_name]
    matches = _matching_pattern_names(activity)

    assert len(matches) == 1, (
        f"{example_name}() built a {type(activity).__name__} matching "
        f"{len(matches)} registered ActivityPattern(s): {matches or 'none'}.\n"
        "An example matching none is undispatchable — a receiver drops it — and "
        "the reference page rendering it documents a wire form that does not "
        "work. An example matching several makes dispatch depend on registry "
        "order (SE-08-001).\n"
        "Check the discriminator fields the pattern requires (object_, target_, "
        "context_); note that ActivityPattern has no origin_ field, so `origin` "
        "is never consulted for dispatch."
    )


@pytest.mark.parametrize(
    "example_name,reason", sorted(_KNOWN_UNDISPATCHABLE.items())
)
@pytest.mark.xfail(
    strict=True, reason="tracked defect; see _KNOWN_UNDISPATCHABLE"
)
def test_known_undispatchable_examples_still_fail(
    example_name: str, reason: str
):
    """Strict xfail: closing the tracked issue must also remove the exemption."""
    activity = _ACTIVITY_EXAMPLES[example_name]
    assert len(_matching_pattern_names(activity)) == 1, reason
