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

The pairing an implementer needs is already declared in code, in two places, and
this ratchet reads both:

* Each activity class names its AS2 base, as in
  ``_RmCloseReportActivity(as_Reject)``.
* Each registered ``ActivityPattern`` names its verb, as in
  ``CreateNotePattern(activity_=TAtype.CREATE)``.

Both are needed because the docs draw names from both systems.  ``CreateNote``
and ``CreateParticipantStatus`` are registry patterns with no dedicated class;
``CreateStatusForParticipant`` is a class whose pattern carries a different
name.  A class-only map makes the first kind invisible, which is how
``CreateStatus`` — a name belonging to neither system — survived review.  The
two sources agree wherever they overlap, and a disagreement is itself a finding.

A verb naming no known activity is not a finding: prose mentions a verb for
plenty of unrelated reasons.  But a name *declared as a member* of an
``as:Verb`` subgraph is an assertion that the activity exists and has that verb,
so an unknown name there is a finding.

Source: ISSUE-3402, prompted by the defects fixed in ISSUE-3395.
"""

import functools
import re
from types import MappingProxyType

# The complete pattern set lives in the private module.  ``extractor/__init__``
# re-exports only 48 of the 51, so importing the public surface would leave the
# unexported patterns invisible to this ratchet — the same silent gap a
# class-only map produced.
from vultron.wire.as2.extractor import _instances
from vultron.wire.as2.extractor._pattern import ActivityPattern

from test.architecture import _corpus

_ACTIVITIES_ROOT = (
    _corpus.REPO_ROOT / "vultron" / "wire" / "as2" / "vocab" / "activities"
)

# ``class _RmCloseReportActivity(as_Reject):`` -> ("_RmCloseReportActivity", "as_Reject")
_CLASS_DECL = re.compile(r"^class (\w+Activity)\((as_\w+)\)", re.MULTILINE)

# Every activity class declaration, whatever its bases. Used to prove
# _CLASS_DECL did not silently skip one (a mixin, or a black-wrapped
# declaration, would not match the single-base form above).
_ANY_CLASS_DECL = re.compile(r"^class (\w+Activity)\(", re.MULTILINE)

# A mermaid ``subgraph as:Verb`` block, up to its matching ``end``.
_MERMAID_SUBGRAPH = re.compile(r"subgraph (as:\w+)\s*\n((?:.*\n)*?)\s*end\b")

# Inline prose: `ActivityName` (`as:Verb`)
_INLINE_PAIRING = re.compile(r"`(\w+)`\s*\(`(as:\w+)`\)")

# A node declaration inside a mermaid block: a bare CamelCase token alone on its
# line.  Matching whole lines rather than bare tokens keeps edge declarations
# (``RmCreateReport --> RmSubmitReport``) from being read as membership claims —
# the target of an edge is not a member of the subgraph that draws it.
_MERMAID_DECL = re.compile(r"^\s*([A-Z]\w+)\s*$", re.MULTILINE)

#: The base class of the activity vocabulary. It subclasses an AS2 type like
#: any activity does, but it is not itself a documentable activity.
_VOCAB_BASE_NAME = "VultronAS2"

#: Substrings that mark a page as possibly asserting a pairing. Used to
#: prefilter the docs corpus; both syntaxes this ratchet understands contain one.
_PAIRING_MARKERS = ("subgraph as:", "(`as:")


def _doc_name(class_name: str) -> str:
    """Strip a class name down to the name docs use for it.

    Docs name activities without the private-module underscore and without the
    ``Activity`` suffix: ``_RmCloseReportActivity`` is written ``RmCloseReport``.
    """
    return class_name.lstrip("_").removesuffix("Activity")


def _class_verbs() -> dict[str, str]:
    """Map the doc-facing activity name to the ``as:Verb`` its class subclasses."""
    verbs: dict[str, str] = {}
    for _, source in _corpus.sources_mentioning(
        "(as_", under=_ACTIVITIES_ROOT
    ):
        for class_name, base in _CLASS_DECL.findall(source):
            verbs[_doc_name(class_name)] = base.replace("as_", "as:")
    verbs.pop(_VOCAB_BASE_NAME, None)
    return verbs


def _pattern_verbs() -> dict[str, str]:
    """Map the doc-facing activity name to the ``as:Verb`` its pattern matches.

    ``CreateNotePattern`` and ``AddNoteToCaseActivityPattern`` are written
    ``CreateNote`` and ``AddNoteToCase``.
    """
    return {
        re.sub(r"(Activity)?Pattern$", "", name): f"as:{value.activity_}"
        for name, value in vars(_instances).items()
        if isinstance(value, ActivityPattern)
    }


@functools.cache
def _authoritative_verbs() -> MappingProxyType[str, str]:
    """The merged class and pattern verb map.

    Cached: building it costs ~50 ms, almost all of it in the corpus scan, and
    every test in this module needs the same result.  Returned read-only so the
    shared value cannot be mutated by a caller.
    """
    verbs = _pattern_verbs()
    verbs.update(_class_verbs())
    return MappingProxyType(verbs)


def _asserted_pairings(text: str) -> list[tuple[str, str]]:
    """Return every (activity_name, asserted_verb) pair a page claims."""
    pairings: list[tuple[str, str]] = []
    for verb, block in _MERMAID_SUBGRAPH.findall(text):
        pairings.extend((name, verb) for name in _MERMAID_DECL.findall(block))
    pairings.extend(_INLINE_PAIRING.findall(text))
    return pairings


def test_class_and_pattern_verbs_agree():
    """Where a name is both a class and a pattern, both must name the same verb.

    A disagreement means one of the two declarations is wrong, and this ratchet
    would then be merging a contradiction into a single map rather than
    reporting it.
    """
    classes = _class_verbs()
    patterns = _pattern_verbs()
    conflicts = {
        name: (classes[name], patterns[name])
        for name in sorted(classes.keys() & patterns.keys())
        if classes[name] != patterns[name]
    }
    assert conflicts == {}, (
        "The activity class and its registered ActivityPattern name different "
        "verbs for the same activity (name: (class verb, pattern verb)):\n"
        + "\n".join(f"  {n}: {v}" for n, v in conflicts.items())
    )


def test_class_verb_map_covers_every_activity_class():
    """Every activity class declaration must land in the map.

    ``_CLASS_DECL`` matches only a single ``(as_X)`` base on one physical line.
    A mixin (``class _FooActivity(as_Create, SomeMixin)``) or a black-wrapped
    declaration would not match, dropping that activity from the map — and,
    because an unmapped name is skipped rather than reported, silently
    unchecking every pairing the docs assert for it.  Asserting equality rather
    than a floor makes that loss loud (DF-09-009 applies the same reasoning to
    docs gates that resolve an empty target set).
    """
    declared = {
        _doc_name(name)
        for _, source in _corpus.sources_mentioning(
            "class ", under=_ACTIVITIES_ROOT
        )
        for name in _ANY_CLASS_DECL.findall(source)
    } - {_VOCAB_BASE_NAME}

    missing = sorted(declared - _class_verbs().keys())
    assert missing == [], (
        "These activity classes are declared under "
        f"{_ACTIVITIES_ROOT.relative_to(_corpus.REPO_ROOT)} but did not match "
        "_CLASS_DECL, so the verbs docs attribute to them go unchecked. Update "
        "_CLASS_DECL to handle their declaration form:\n"
        + "\n".join(f"  {m}" for m in missing)
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
        "_MERMAID_SUBGRAPH, _MERMAID_DECL or _INLINE_PAIRING."
    )


def test_mermaid_as_subgraphs_are_not_nested():
    """No ``as:Verb`` subgraph may contain a nested subgraph.

    ``_MERMAID_SUBGRAPH`` closes on the first ``end``, which for a nested block
    is the inner one — every member after it would be dropped from the scan with
    no diagnostic.  Nesting is legal mermaid and is already used elsewhere in
    this tree, so fail loudly here rather than under-check quietly.
    """
    nested: list[str] = []
    for doc_file, text in _corpus.docs_mentioning(*_PAIRING_MARKERS):
        for verb, block in _MERMAID_SUBGRAPH.findall(text):
            if "subgraph" in block:
                nested.append(
                    f"{doc_file.relative_to(_corpus.REPO_ROOT)}: {verb}"
                )

    assert nested == [], (
        "These `subgraph as:Verb` blocks contain a nested subgraph, which this "
        "ratchet cannot read — it would stop at the inner `end` and silently "
        "skip the rest. Flatten the diagram, or teach _MERMAID_SUBGRAPH to "
        "balance nesting:\n" + "\n".join(f"  {n}" for n in nested)
    )


def test_docs_declare_only_known_activities():
    """A name declared inside an ``as:Verb`` subgraph must be a real activity.

    Declaring ``CreateStatus`` under ``subgraph as:Create`` asserts that an
    activity by that name exists.  When it does not, an implementer following
    the diagram emits something no ``ActivityPattern`` matches, which dispatches
    as unrecognized — the failure mode of ISSUE-3395.  Prose that merely
    mentions a name is left alone; only a subgraph membership claim is checked.
    """
    verbs = _authoritative_verbs()
    unknown: list[str] = []

    for doc_file, text in _corpus.docs_mentioning(*_PAIRING_MARKERS):
        for verb, block in _MERMAID_SUBGRAPH.findall(text):
            for name in _MERMAID_DECL.findall(block):
                if name not in verbs:
                    unknown.append(
                        f"{doc_file.relative_to(_corpus.REPO_ROOT)}: {name} is "
                        f"declared under {verb} but is neither an activity "
                        "class nor a registered pattern"
                    )

    assert sorted(set(unknown)) == [], (
        "Documentation declares activities that do not exist. Use the name of "
        "the activity class or of its registered ActivityPattern:\n"
        + "\n".join(f"  {u}" for u in sorted(set(unknown)))
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
