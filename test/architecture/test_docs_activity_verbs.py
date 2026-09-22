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
"""Ratchet: the AS2 form and verb docs attribute to an activity must be its own.

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

Since ISSUE-3456 the activity guides name activities by their **formal protocol
message paired with the AS2 wire form** — "Report Valid (RV) is implemented in
ActivityStreams as ``Accept(Offer(VulnerabilityReport))``" — and drop the prototype
class name, because an implementer building a conformant peer in another language
has no ``RmValidateReport``.  The wire form alone would not do: ``Accept(Offer(…))``,
``TentativeReject(Offer(…))`` and ``Reject(Offer(…))`` are *valid*, *invalid* and
*closed*, and nothing in the wire form says which, so replacing the protocol name
with it deletes a layer rather than translating one.  That moved the reader-facing
name out of the mermaid node *id* and into its *label*, which this module tracks in
two ways:

* ``_MERMAID_DECL`` accepts both the bare and the labelled spelling, so the verb
  checks keep reading the id, which is still what identifies the activity.
* ``test_mermaid_labels_are_the_canonical_as2_form`` checks the label against the
  form derived from the registered ``ActivityPattern``.  That is a strictly
  stronger assertion than the verb pairing: it compares the whole object
  composition, so it catches ``Read(VulnerabilityReport)`` where the pattern
  requires ``Read(Offer(VulnerabilityReport))``.

The convention change is itself the cautionary tale.  Relabelling the nodes made
``_MERMAID_DECL`` stop matching them, and the pairing count fell from 21 to 1 —
caught only because ``test_docs_assert_pairings_that_exist_to_check`` asserts a
floor.  Any future change to the node spelling must move that guard with it, or the
suite goes green over an unchecked corpus (DF-09-009).

The convention this module enforces is specified as DF-09-010 (ADR-0083, "Which
name the reader gets"): reader-facing docs pair the formal protocol message name
and code with the AS2 wire form, and the prototype class name survives only as a
non-rendered identifier.

Source: ISSUE-3402, prompted by the defects fixed in ISSUE-3395; extended by
ISSUE-3456.
"""

import functools
import re
from types import MappingProxyType

# The complete pattern set lives in the private module.  ``extractor/__init__``
# re-exports only 48 of the 51, so importing the public surface would leave the
# unexported patterns invisible to this ratchet — the same silent gap a
# class-only map produced.
from vultron.semantic_registry import SEMANTIC_REGISTRY
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

# A node declaration inside a mermaid block.  Matching whole lines rather than
# bare tokens keeps edge declarations (``RmCreateReport --> RmSubmitReport``)
# from being read as membership claims — the target of an edge is not a member of
# the subgraph that draws it.
#
# Two forms are accepted.  A bare CamelCase token is the older spelling, where
# the node id was also the rendered text.  Since ISSUE-3456 the activity guides
# render the AS2 wire form instead, so the id survives only as an edge handle and
# the label carries the reader-facing name:
#
#     RmReadReport["Read(Offer(VulnerabilityReport))"]
#
# The id is still what identifies the activity, so it is what the verb check
# reads; ``test_mermaid_labels_are_the_canonical_as2_form`` checks the label.
_MERMAID_DECL = re.compile(r'^\s*([A-Z]\w+)(?:\["[^"]*"\])?\s*$', re.MULTILINE)

# The same declaration, keeping the label. Only labelled nodes match.
_MERMAID_LABELLED = re.compile(
    r'^\s*([A-Z]\w+)\["([^"]*)"\]\s*$', re.MULTILINE
)

#: The base class of the activity vocabulary. It subclasses an AS2 type like
#: any activity does, but it is not itself a documentable activity.
_VOCAB_BASE_NAME = "VultronAS2"

#: Substrings that mark a page as possibly asserting a pairing. Used to
#: prefilter the docs corpus; both syntaxes this ratchet understands contain one.
_PAIRING_MARKERS = ("subgraph as:", "(`as:")

#: The activity guides. Scanned directly rather than through
#: ``_PAIRING_MARKERS``, because that prefilter only finds pages carrying a
#: mermaid ``subgraph as:`` block or an inline ``(`as:Verb`)`` parenthetical —
#: and ISSUE-3456 removed the latter (AC-4) from pages that never had the
#: former, dropping ``acknowledge.md`` out of the target set entirely while it
#: gained five hand-typed wire forms.  A wire form in prose is a claim about
#: the JSON an implementer must emit, so it needs a gate whether or not the
#: page happens to draw a diagram (DF-09-009).
_GUIDES_ROOT = (
    _corpus.REPO_ROOT / "docs" / "howto" / "activitypub" / "activities"
)

#: An inline wire form in prose: a backticked ``Verb(...)`` token.
_INLINE_WIRE_FORM = re.compile(r"`([A-Z][A-Za-z]+\([^`]*\))`")

#: Lowest number of labelled mermaid nodes the guides are known to carry.
#: A floor generous enough to lose nodes silently is not a gate: with 52 nodes
#: present, a ``> 30`` floor tolerated 19 disappearing while every test stayed
#: green.  Pin it at the real count so losing even one is loud, and raise it
#: when nodes are added (MS-11 ratchet discipline, DF-09-009).
_MIN_LABELLED_NODES = 52

#: Node ids whose wire form no registry entry carries on its own, mapped to the
#: pattern that does carry it.  ``ActivateEmbargo`` shares
#: ``AddEmbargoEventToCasePattern`` with ``AddEmbargoToCase`` — the activation
#: form is the same ``Add(Event)`` distinguished only by ``inReplyTo`` — so it
#: has no ``SEMANTIC_REGISTRY`` entry of its own and would otherwise be skipped
#: unchecked, which is precisely the node ISSUE-3456 AC-6 was about.
_FORM_ALIASES = MappingProxyType({"ActivateEmbargo": "AddEmbargoToCase"})

#: The qualifier each node id is allowed to carry after its wire form, naming
#: the field that tells two activities sharing one form apart.  Checked rather
#: than stripped: the qualifier is the *only* thing distinguishing these two, so
#: discarding it would let a label assert the exact opposite of the truth.
#: A node id absent here may carry no qualifier at all.
_EXPECTED_QUALIFIER = MappingProxyType(
    {
        "ActivateEmbargo": "inReplyTo: Invite(Event)",
        "AddEmbargoToCase": "no inReplyTo",
    }
)

#: Wire forms the guides state deliberately even though no pattern produces
#: them, each because the page's subject *is* that mismatch.  Every entry needs
#: a reason; this is not a place to park an unexplained failure.
_UNREGISTERED_FORMS_BY_DESIGN = MappingProxyType(
    {
        # establish_embargo.md: polling across candidate embargoes has a
        # factory but no registered pattern, so no receiver dispatches it.
        "Question(anyOf=[Event])": "no registered pattern (#3433)",
        # acknowledge.md: named as the form that matches nothing, to warn an
        # implementer off sending the bare report instead of its Offer.
        "Read(VulnerabilityReport)": "counter-example (MSM-01-008)",
    }
)


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


def _render_as2_form(pattern: ActivityPattern) -> str:
    """The canonical AS2 wire form of a pattern, e.g. ``Read(Offer(Report))``.

    ``object_`` is either an object type or a nested pattern, which is what makes
    the composite forms — ``Accept(Invite(Event))`` is an ``Accept`` whose object
    is an ``Invite``.  ``target_`` and ``context_`` are deliberately *not* folded
    in: they are per-activity qualifiers the prose states, and including them
    would make the inline form too long to read in a sentence or a diagram node.
    """
    verb = getattr(pattern.activity_, "value", pattern.activity_)
    obj = pattern.object_
    if obj is None:
        return str(verb)
    if isinstance(obj, ActivityPattern):
        inner = _render_as2_form(obj)
    else:
        inner = str(getattr(obj, "value", obj))
    return f"{verb}({inner})"


@functools.cache
def _canonical_forms() -> MappingProxyType[str, str]:
    """Map the doc-facing activity name to its canonical AS2 wire form.

    Derived rather than hand-listed, from the same two sources as the verb map:
    ``SEMANTIC_REGISTRY`` pairs each ``wire_activity_class`` with the pattern that
    dispatches it, and the pattern instances cover the names that have a pattern
    but no dedicated class.  A hand-maintained table here would be one more thing
    to drift, which is the defect this module exists to catch.
    """
    forms: dict[str, str] = {}
    for name, pattern in vars(_instances).items():
        if isinstance(pattern, ActivityPattern):
            forms[re.sub(r"(Activity)?Pattern$", "", name)] = _render_as2_form(
                pattern
            )
    # The class->pattern pairing wins where both exist: it is the mapping a
    # reader of the class name cares about.
    for entry in SEMANTIC_REGISTRY:
        cls = entry.wire_activity_class
        if cls is not None and entry.pattern is not None:
            forms[_doc_name(cls.__name__)] = _render_as2_form(entry.pattern)
    # Names that share another activity's pattern and so have no entry of their
    # own.  Resolved last so an alias can never shadow a real derivation.
    for alias, target in _FORM_ALIASES.items():
        if alias not in forms and target in forms:
            forms[alias] = forms[target]
    return MappingProxyType(forms)


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


def _labelled_nodes() -> list[tuple[str, str, str]]:
    """Every ``(page, node_id, label)`` a mermaid block declares with a label."""
    found: list[tuple[str, str, str]] = []
    for doc_file, text in _corpus.docs_mentioning(*_PAIRING_MARKERS):
        page = str(doc_file.relative_to(_corpus.REPO_ROOT))
        for node_id, label in _MERMAID_LABELLED.findall(text):
            found.append((page, node_id, label))
    return found


def test_mermaid_labels_are_the_canonical_as2_form():
    """A labelled activity node must render that activity's real AS2 wire form.

    Since ISSUE-3456 the activity guides name activities by wire form rather than
    by prototype class name, so the label is what the reader sees and the id is
    only an edge handle.  A hand-typed label can therefore be wrong in a way no
    other gate notices: ``mkdocs --strict`` does not parse mermaid, and the verb
    check above reads the id.

    This is a stronger check than the verb pairing it complements — it compares
    the whole object composition, so it catches ``Read(VulnerabilityReport)``
    where the pattern requires ``Read(Offer(VulnerabilityReport))``.

    Labels carry two lines separated by ``<br/>``: the protocol act first, the wire
    form last (ISSUE-3456). Only the last line is compared. The first is the
    semantic name, which is not derivable from the registry — for the 22 activities
    the formal protocol never names it comes from the reference tree's own heading,
    so asserting it here would only re-state a hand-maintained list.

    The wire line may carry a trailing ``, <qualifier>`` naming the field that
    distinguishes two activities sharing one wire form. ``ActivateEmbargo`` and
    ``AddEmbargoToCase`` are both ``Add(Event)`` and are told apart by
    ``inReplyTo``, so the qualifier is *checked* against
    ``_EXPECTED_QUALIFIER`` rather than stripped — it is the only thing
    distinguishing them, and discarding it let a label assert the exact opposite
    of the truth while this test passed.

    An unresolvable node id is a failure, not a skip.  Skipping it silently is
    the same false-clean signal DF-09-009 forbids, and it hid ``ActivateEmbargo``
    — the one node ISSUE-3456 AC-6 singled out — behind a green run.
    """
    forms = _canonical_forms()
    wrong: list[str] = []
    unmapped: list[str] = []
    for page, node_id, label in _labelled_nodes():
        expected = forms.get(node_id)
        if expected is None:
            unmapped.append(f"  {page}: {node_id}")
            continue
        wire_line = label.split("<br/>")[-1].strip()
        actual, _, qualifier = (x.strip() for x in wire_line.partition(","))
        want_qualifier = _EXPECTED_QUALIFIER.get(node_id, "")
        if actual != expected:
            wrong.append(
                f"  {page}: {node_id} labelled {actual!r}, is {expected!r}"
            )
        elif qualifier != want_qualifier:
            wrong.append(
                f"  {page}: {node_id} qualified {qualifier!r}, "
                f"expected {want_qualifier!r}"
            )

    assert wrong == [], (
        "These mermaid nodes render an AS2 wire form, or a distinguishing "
        "qualifier, that is not what their activity actually has. The form is "
        "derived from the registered ActivityPattern, so the label is what is "
        "wrong, not the expectation:\n" + "\n".join(wrong)
    )
    assert unmapped == [], (
        "These labelled mermaid nodes name no activity this ratchet can resolve "
        "to a wire form, so their labels went unchecked. Either the id is wrong, "
        "or the activity shares another's pattern and needs a documented "
        "_FORM_ALIASES entry:\n" + "\n".join(unmapped)
    )


def test_labelled_node_scan_finds_targets():
    """The label scan must keep finding every node, or a passing run proves less.

    If a future edit changes the node spelling, ``_MERMAID_LABELLED`` stops
    matching and every label goes unchecked while the suite stays green — the
    DF-09-009 false-clean signal, and the exact failure this module's own
    convention change would have caused had
    ``test_docs_assert_pairings_that_exist_to_check`` not been here to catch it.

    The count is pinned at ``_MIN_LABELLED_NODES`` rather than set to a round
    number below it.  A floor with slack is not a ratchet: the original ``> 30``
    against 52 real nodes let 19 vanish undetected, including by the legal
    mermaid round shape ``Node(("label"))``, which ``_MERMAID_LABELLED`` does not
    match.  Raise the constant when you add nodes.
    """
    labelled = _labelled_nodes()
    assert len(labelled) >= _MIN_LABELLED_NODES, (
        f"Found only {len(labelled)} labelled activity nodes, expected at least "
        f"{_MIN_LABELLED_NODES}. _MERMAID_LABELLED probably no longer matches "
        "the node spelling the docs use — check for a shape other than "
        'Id["label"]. If nodes were deliberately removed, lower the constant '
        "in the same change."
    )


def test_inline_wire_forms_in_guides_are_registered():
    """A wire form stated in guide prose must be one a pattern actually produces.

    The mermaid label check above only sees pages that draw a diagram. Seven of
    the thirteen activity guides state their wire forms in prose alone, and
    ISSUE-3456 moved the reader-facing name *into* those forms — so a typo there
    now misleads an implementer about the JSON to emit, where before it only
    named an internal class wrongly. ``acknowledge.md`` is the cautionary case:
    AC-4 removed its inline ``(`as:Verb`)`` parentheticals, which were its only
    ``_PAIRING_MARKERS`` match, so it left the ratchet's target set in the same
    change that gave it five hand-typed wire forms.

    Deliberate exceptions live in ``_UNREGISTERED_FORMS_BY_DESIGN`` with a reason
    each, because a page whose subject is a form that dispatches nowhere has to
    be able to name it.
    """
    forms = set(_canonical_forms().values())
    unknown: list[str] = []
    checked = 0
    for doc_file, text in _corpus.all_docs():
        if _GUIDES_ROOT not in doc_file.parents:
            continue
        page = str(doc_file.relative_to(_corpus.REPO_ROOT))
        in_fence = False
        for lineno, line in enumerate(text.split("\n"), 1):
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for token in _INLINE_WIRE_FORM.findall(line):
                checked += 1
                if token in forms or token in _UNREGISTERED_FORMS_BY_DESIGN:
                    continue
                unknown.append(f"  {page}:{lineno}: {token}")

    assert unknown == [], (
        "These wire forms appear in activity-guide prose but no registered "
        "ActivityPattern produces them. Either the form is mistyped, or it is a "
        "deliberate counter-example and needs an "
        "_UNREGISTERED_FORMS_BY_DESIGN entry with a reason:\n"
        + "\n".join(unknown)
    )
    assert checked > 100, (
        f"Only {checked} inline wire forms found across the activity guides. "
        "_INLINE_WIRE_FORM probably no longer matches the spelling the guides "
        "use, so this gate is checking almost nothing (DF-09-009)."
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
