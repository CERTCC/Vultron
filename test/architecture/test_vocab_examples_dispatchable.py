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

Three defects found when this was first measured:

* ``remove_participant_from_case`` named the case in ``origin``.  ``ActivityPattern``
  has no ``origin_`` field, and ``RemoveCaseParticipantFromCasePattern``
  discriminates on ``target_``, so the example matched none of the patterns and
  ``docs/reference/messages/case_management.md`` documented the wrong field
  (fixed, #3438).
* ``read_report`` builds ``Read(Report)`` while ``AckReportPattern`` requires
  ``Read(Offer(Report))`` — the emit path and the receive path disagree about the
  ``RK`` wire form (#3439, an ``xfail`` below).
* ``choose_preferred_embargo`` has a factory and a wire class but no registered
  pattern and no ``MessageSemantics``, so no peer can route it (#3433, an ``xfail``
  below).

*Exactly* one match rather than at least one: two patterns matching the same
activity is the ambiguity SE-08-001 forbids, and it makes dispatch depend on
registry order.

The collector is deliberately permissive about *shape*, because every way of
narrowing it has already hidden a target:

* Skipping any callable that declares a parameter dropped the four ``report.py``
  examples, which take a defaulted ``verbose``.  ``submit_report`` is among them,
  and it is the single most-copied example in the corpus.  The rule is therefore
  "no *required* parameters", not "no parameters".
* Requiring ``as_TransitiveActivity`` dropped ``choose_preferred_embargo``, an
  ``as_Question``.  An intransitive activity is still an activity, and #3433 is
  exactly the undispatchable-example defect this gate exists to catch, so the
  check is against ``as_Activity``.

A gate that silently resolves fewer targets than it claims produces a false clean
signal, which is worse than no gate (DF-09-009).

Source: ISSUE-3003.
"""

import inspect

import pytest

from vultron.wire.as2.extractor import _instances
from vultron.wire.as2.extractor._pattern import ActivityPattern
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

# Examples whose shape is known-wrong, each with the issue that owns the fix.
# Remove the entry when the issue closes.  Two things keep an entry honest: the
# ``strict`` xfail below fails if one starts passing, and
# ``test_known_undispatchable_names_are_collected`` fails if one stops being
# collected at all — without that second check a renamed or deleted example would
# turn its exemption into a permanent ``KeyError``, which ``xfail`` records as a
# pass.
_KNOWN_UNDISPATCHABLE = {
    "read_report": "#3439 — emit builds Read(Report), AckReportPattern requires Read(Offer(Report))",
    "choose_preferred_embargo": "#3433 — factory and wire class exist, but no ActivityPattern and no MessageSemantics",
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


def _activity_examples() -> dict[str, as_Activity]:
    """Build every example that returns an activity and needs no arguments.

    Object examples (``vendor()``, ``case_participant()``, …) are skipped: a
    pattern matches an activity, so an object has nothing to dispatch.  Activities
    are *not* narrowed to the transitive ones — see the module docstring.
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


_ACTIVITY_EXAMPLES = _activity_examples()


def _matching_pattern_names(activity: as_Activity) -> list[str]:
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
    assert len(_ACTIVITY_EXAMPLES) > 50, (
        f"Only {len(_ACTIVITY_EXAMPLES)} activity examples collected from "
        "vocab_examples. The example module layout or the as_Activity base class "
        "has probably changed; update _activity_examples(). A narrowed collector "
        "still passes every assertion below, so this count is the only thing "
        "standing between a skipped example and a green run (DF-09-009)."
    )


def test_known_undispatchable_names_are_collected():
    """An exemption for an example nobody collects is a permanently green lie.

    ``_ACTIVITY_EXAMPLES[name]`` raises ``KeyError`` for an uncollected name, and
    an exception inside the ``strict`` xfail below is recorded as XFAIL rather
    than a failure.  So without this check, renaming or deleting an exempted
    example — or giving it a required argument — freezes its entry in place and
    the exemption outlives the issue it names.
    """
    missing = sorted(set(_KNOWN_UNDISPATCHABLE) - set(_ACTIVITY_EXAMPLES))
    assert not missing, (
        f"_KNOWN_UNDISPATCHABLE names {missing}, which the collector does not "
        "find. Either the example was renamed or removed — in which case delete "
        "the entry — or the collector has stopped reaching it, in which case the "
        "exemption is hiding an unchecked example rather than tracking a known "
        "defect."
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
    "example_name",
    [
        # The mark is built per-parameter rather than applied to the whole test so
        # that each xfail's own ``reason`` names its issue. A single shared marker
        # puts the issue number in the parametrize id instead, where the
        # every-xfail-cites-a-live-issue audit does not read it.
        pytest.param(name, marks=pytest.mark.xfail(strict=True, reason=reason))
        for name, reason in sorted(_KNOWN_UNDISPATCHABLE.items())
    ],
)
def test_known_undispatchable_examples_still_fail(example_name: str):
    """Strict xfail: closing the tracked issue must also remove the exemption."""
    activity = _ACTIVITY_EXAMPLES[example_name]
    assert len(_matching_pattern_names(activity)) == 1, _KNOWN_UNDISPATCHABLE[
        example_name
    ]
