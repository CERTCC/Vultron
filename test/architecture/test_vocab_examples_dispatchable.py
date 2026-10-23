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
"""Ratchet: every example activity must dispatch to exactly one registry entry.

The ``vocab_examples`` functions are the wire examples rendered on
``docs/reference/messages/*.md`` and written to ``docs/reference/examples/*.json``.
They are what an implementer copies.  Two existing gates check them and neither
asks the question that matters: ``test_vocab_utils.py`` asserts each one executes
and serializes, and ``test_vocab_examples_current.py`` asserts the committed
artifact file list is current.  An example can therefore be well-formed,
committed, rendered on a reference page — and undispatchable, because no
``SEMANTIC_REGISTRY`` entry's pattern matches it.

The match is counted against the registry's entries, not against every
``ActivityPattern`` in ``extractor/_instances.py``.  A pattern no entry uses
routes nothing, so an example matching only that pattern dispatches to
``UNKNOWN`` while a count over the module reads it as dispatchable:
``accept_actor_recommendation`` and ``reject_actor_recommendation`` passed
that way, matching the orphan ``Accept``/``RejectSuggestActorToCasePattern``,
until #4527 routed them.  ``test_every_pattern_instance_is_used_by_an_entry``
keeps the module free of such orphans.

Three defects found when this was first measured:

* ``remove_participant_from_case`` named the case in ``origin``.  ``ActivityPattern``
  has no ``origin_`` field, and ``RemoveCaseParticipantFromCasePattern``
  discriminates on ``target_``, so the example matched none of the patterns and
  ``docs/reference/messages/case_management.md`` documented the wrong field
  (fixed, #3438).
* ``read_report`` previously built ``Read(Report)`` while ``AckReportPattern``
  required ``Read(Offer(Report))`` — fixed in #3439/#3455.
* ``choose_preferred_embargo`` had a factory and a wire class but no registered
  pattern and no ``MessageSemantics``, so no peer could route it (#3433).  ADR-0100
  retired the poll rather than building it, and #3469 removed the class, the
  factory and the example, so the exemption that tracked it is gone too.

*Exactly* one match rather than at least one: two patterns matching the same
activity is the ambiguity SE-08-001 forbids, and it makes dispatch depend on
registry order.

The collector (``_vocab_example_corpus``, shared with the evidence gate) is
deliberately permissive about *shape*, because every way of
narrowing it has already hidden a target:

* Skipping any callable that declares a parameter dropped the four ``report.py``
  examples, which take a defaulted ``verbose``.  ``submit_report`` is among them,
  and it is the single most-copied example in the corpus.  The rule is therefore
  "no *required* parameters", not "no parameters".
* Requiring ``as_TransitiveActivity`` dropped ``choose_preferred_embargo``, an
  ``as_Question`` (since removed, #3469).  An intransitive activity is still an
  activity, and #3433 was exactly the undispatchable-example defect this gate
  exists to catch, so the check stays against ``as_Activity``.

A gate that silently resolves fewer targets than it claims produces a false clean
signal, which is worse than no gate (DF-09-009).

Source: ISSUE-3003.
"""

import pytest

from test.architecture._vocab_example_corpus import activity_examples
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.wire.as2.extractor import _instances
from vultron.wire.as2.extractor._pattern import ActivityPattern
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

# Examples that are not dispatchable, each with the reason that owns it.  An entry
# whose reason is an open issue is debt and goes when the issue closes; an entry
# whose reason is a *decision* is permanent and stays.  Two things keep an entry
# honest: the ``strict`` xfail below fails if one starts passing, and
# ``test_known_undispatchable_names_are_collected`` fails if one stops being
# collected at all — without that second check a renamed or deleted example would
# turn its exemption into a permanent ``KeyError``, which ``xfail`` records as a
# pass.
_KNOWN_UNDISPATCHABLE: dict[str, str] = {}


def _entry_patterns() -> list[tuple[str, ActivityPattern]]:
    """Every ``SEMANTIC_REGISTRY`` entry's pattern, by its semantics name.

    The dispatcher fallbacks carry no pattern and are skipped: an example that
    reaches one is undispatchable, which is what this gate exists to catch.
    """
    return [
        (entry.semantics.name, entry.pattern)
        for entry in SEMANTIC_REGISTRY
        if entry.pattern is not None
    ]


def _pattern_instances() -> list[tuple[str, ActivityPattern]]:
    """Every ``ActivityPattern`` in ``extractor/_instances.py``, by name.

    Read from the private module: ``extractor/__init__`` re-exports only a subset,
    so the public surface would leave the unexported patterns invisible here.
    """
    return [
        (name, value)
        for name, value in vars(_instances).items()
        if isinstance(value, ActivityPattern)
    ]


def _patterns_within(pattern: ActivityPattern) -> list[ActivityPattern]:
    """*pattern* and every pattern nested in its discriminator fields."""
    nested = [
        value
        for value in (
            pattern.to_,
            pattern.object_,
            pattern.target_,
            pattern.context_,
        )
        if isinstance(value, ActivityPattern)
    ]
    return [pattern, *(p for n in nested for p in _patterns_within(n))]


_ACTIVITY_EXAMPLES = activity_examples()


def _matching_pattern_names(activity: as_Activity) -> list[str]:
    return sorted(name for name, p in _entry_patterns() if p.match(activity))


def test_pattern_registry_is_not_empty():
    """A gate that resolves no patterns would pass vacuously (DF-09-009)."""
    assert len(_entry_patterns()) > 40, (
        f"Only {len(_entry_patterns())} SEMANTIC_REGISTRY entries carry a "
        "pattern. Either the registry shrank drastically or this test is no "
        "longer reading it."
    )
    assert len(_pattern_instances()) > 40, (
        f"Only {len(_pattern_instances())} ActivityPattern instances found in "
        "vultron/wire/as2/extractor/_instances.py; the orphan check below is "
        "no longer reading the module."
    )


def test_every_pattern_instance_is_used_by_an_entry():
    """A pattern no registry entry uses routes nothing.

    An activity matching only an orphan pattern dispatches to ``UNKNOWN``, so
    the orphan documents a wire form no receiver handles.  A pattern counts as
    used when an entry's pattern is it or nests it, as
    ``OfferActorToCasePattern`` is nested in the Accept and Reject entries.
    """
    used = {
        id(p)
        for _, entry_pattern in _entry_patterns()
        for p in _patterns_within(entry_pattern)
    }
    orphans = sorted(
        name for name, p in _pattern_instances() if id(p) not in used
    )
    assert not orphans, (
        f"{orphans} in vultron/wire/as2/extractor/_instances.py are used by "
        "no SEMANTIC_REGISTRY entry, so an activity matching one dispatches "
        "to UNKNOWN. Route it with an entry or delete it."
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

    An exempted name is excluded from the exactly-one-pattern test by name, so
    renaming or deleting the example — or giving it a required argument — would
    otherwise freeze its entry in place and the exemption would outlive the
    issue it names.
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
def test_example_activity_dispatches_to_one_registry_entry(example_name: str):
    """A rendered wire example must be dispatchable, and unambiguously so."""
    activity = _ACTIVITY_EXAMPLES[example_name]
    matches = _matching_pattern_names(activity)

    assert len(matches) == 1, (
        f"{example_name}() built a {type(activity).__name__} matching "
        f"{len(matches)} SEMANTIC_REGISTRY entry pattern(s): "
        f"{matches or 'none'}.\n"
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
        # that each xfail's own ``reason`` names its decision. A single shared
        # marker puts it in the parametrize id instead, where an audit of xfail
        # reasons does not read it.
        pytest.param(name, marks=pytest.mark.xfail(strict=True, reason=reason))
        for name, reason in sorted(_KNOWN_UNDISPATCHABLE.items())
    ],
)
def test_known_undispatchable_examples_still_fail(example_name: str):
    """Strict xfail: an exempted example that becomes dispatchable must leave."""
    activity = _ACTIVITY_EXAMPLES[example_name]
    assert len(_matching_pattern_names(activity)) == 1, _KNOWN_UNDISPATCHABLE[
        example_name
    ]
