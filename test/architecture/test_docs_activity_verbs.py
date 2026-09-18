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
"""Ratchet: the AS2 verb docs attribute to an activity must be the verb it has.

Documentation names activity/verb pairings in two shapes — a mermaid
``subgraph as:Verb`` block listing activity names, and inline prose of the form
``` `RmCloseReport` (`as:Reject`) ```.  Neither is checked by any other gate:
``mkdocs --strict`` validates links and nav, ``lint-docs`` checks prose style and
terminology, and MSM-06-002's ratchet asserts registry coverage of the
*reference* pages.  A wrong pairing therefore survives indefinitely, and three
did — ``RmInvalidateReport`` filed under ``as:Reject`` (it is
``as:TentativeReject``) and ``RmCloseReport`` filed under ``as:Leave`` (it is
``Reject(Offer(VulnerabilityReport))``), across five sites on three pages.

The pairing an implementer needs is already declared in code: each activity
class names its AS2 base, as in ``_RmCloseReportActivity(as_Reject)``.  This
ratchet derives the authoritative map from those declarations and compares every
pairing the docs assert against it.

An activity name appearing under no verb, or a verb naming no known activity, is
not a finding — only a pairing that contradicts the code is.  That keeps prose
mentioning a verb for unrelated reasons from producing noise.

Source: ISSUE-3402, prompted by the defects fixed in ISSUE-3395.
"""

import re

from test.architecture import _corpus

_ACTIVITIES_ROOT = (
    _corpus.REPO_ROOT / "vultron" / "wire" / "as2" / "vocab" / "activities"
)

# ``class _RmCloseReportActivity(as_Reject):`` -> ("_RmCloseReportActivity", "as_Reject")
_CLASS_DECL = re.compile(r"^class (\w+Activity)\((as_\w+)\)", re.MULTILINE)

# A mermaid ``subgraph as:Verb`` block, up to its matching ``end``.
_MERMAID_SUBGRAPH = re.compile(r"subgraph (as:\w+)\s*\n((?:.*\n)*?)\s*end\b")

# Inline prose: `ActivityName` (`as:Verb`)
_INLINE_PAIRING = re.compile(r"`(\w+)`\s*\(`(as:\w+)`\)")

# Bare CamelCase tokens inside a mermaid block, which is how activities appear
# as node names there.
_MERMAID_TOKEN = re.compile(r"\b([A-Z]\w+)\b")

#: Substrings that mark a page as possibly asserting a pairing. Used to
#: prefilter the docs corpus; both syntaxes this ratchet understands contain one.
_PAIRING_MARKERS = ("subgraph as:", "(`as:")


def _authoritative_verbs() -> dict[str, str]:
    """Map the doc-facing activity name to the ``as:Verb`` its class subclasses.

    Docs name activities without the private-module underscore and without the
    ``Activity`` suffix: ``_RmCloseReportActivity`` is written ``RmCloseReport``.
    """
    verbs: dict[str, str] = {}
    for path, source in _corpus.sources_mentioning(
        "(as_", under=_ACTIVITIES_ROOT
    ):
        del path
        for class_name, base in _CLASS_DECL.findall(source):
            doc_name = class_name.lstrip("_").removesuffix("Activity")
            verbs[doc_name] = base.replace("as_", "as:")
    return verbs


def _asserted_pairings(text: str) -> list[tuple[str, str]]:
    """Return every (activity_name, asserted_verb) pair a page claims."""
    pairings: list[tuple[str, str]] = []
    for verb, block in _MERMAID_SUBGRAPH.findall(text):
        pairings.extend((name, verb) for name in _MERMAID_TOKEN.findall(block))
    pairings.extend(_INLINE_PAIRING.findall(text))
    return pairings


def test_authoritative_verb_map_is_populated():
    """The activity/verb map must be non-empty, or the ratchet checks nothing.

    A refactor that moves or renames ``vocab/activities/`` would otherwise make
    this file silently vacuous (DF-09-009 applies the same reasoning to docs
    gates that resolve an empty target set).
    """
    verbs = _authoritative_verbs()
    assert len(verbs) > 40, (
        "Derived suspiciously few activity/verb pairings from "
        f"{_ACTIVITIES_ROOT.relative_to(_corpus.REPO_ROOT)} (got {len(verbs)}). "
        "Has the activity vocabulary moved, or the class declaration style "
        "changed? Update _CLASS_DECL rather than lowering this floor."
    )


def test_docs_assert_pairings_that_exist_to_check():
    """The docs scan must find pairings, or a passing run proves nothing."""
    verbs = _authoritative_verbs()
    checked = sum(
        1
        for _, text in _corpus.docs_mentioning(*_PAIRING_MARKERS)
        for name, _ in _asserted_pairings(text)
        if name in verbs
    )
    assert checked > 20, (
        f"Found only {checked} activity/verb pairings across docs/. The mermaid "
        "or inline syntax the docs use has probably changed; update "
        "_MERMAID_SUBGRAPH or _INLINE_PAIRING."
    )


def test_docs_activity_verbs_match_wire_classes():
    """Every AS2 verb docs attribute to an activity must match its wire class.

    Source: ISSUE-3402, prompted by ISSUE-3395.
    """
    verbs = _authoritative_verbs()
    mismatches: list[str] = []

    for doc_file, text in _corpus.docs_mentioning(*_PAIRING_MARKERS):
        for name, asserted in _asserted_pairings(text):
            actual = verbs.get(name)
            if actual is not None and actual != asserted:
                mismatches.append(
                    f"{doc_file.relative_to(_corpus.REPO_ROOT)}: {name} is "
                    f"documented as {asserted} but subclasses {actual}"
                )

    assert sorted(set(mismatches)) == [], (
        "Documentation attributes the wrong ActivityStreams verb to these "
        "activities. The wire class is authoritative — correct the docs, or "
        "correct the class if the docs describe the intended design:\n"
        + "\n".join(f"  {m}" for m in sorted(set(mismatches)))
    )
