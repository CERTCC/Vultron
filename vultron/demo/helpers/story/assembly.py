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
"""Assemble a story: fragments, props, choices and named prefixes.

:data:`Fragment`, :class:`StoryProp`, :func:`choose` and :func:`story`, the
parts a scenario writes its story from (:mod:`vultron.demo.helpers.story`),
and :func:`fragment_name` and :func:`fragment_sentence`, how a fragment is
named and how it says what it does once it is written down.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vultron.demo.helpers.cast import ALL_SLOTS
from vultron.demo.scenario.branch_points import validate_path
from vultron.demo.scenario.tree import PathStep
from vultron.errors import DemoStoryError

if TYPE_CHECKING:
    from vultron.demo.helpers.story.state import StoryState


#: One step of a story: a callable run against the story's state.  Named
#: rather than inlined because it is also what a named prefix is made of, and
#: what a scenario reads top to bottom.
Fragment = Callable[["StoryState"], None]


def _unstable_name_reason(module: object, qualname: object) -> str | None:
    """Return why ``module``/``qualname`` is not a stable name, or ``None``."""
    if (
        not isinstance(module, str)
        or not module
        or not isinstance(qualname, str)
        or not qualname
    ):
        return (
            "it has no __module__ and __qualname__ pair, so there is no name "
            "to write; a functools.partial and a callable instance are the "
            "usual causes"
        )
    if "<" in qualname:
        return (
            f"its qualified name {qualname!r} holds a synthetic segment such "
            "as '<lambda>' or '<locals>', which names no step and changes "
            "when its enclosing function is renamed"
        )
    return None


def fragment_name(fragment: object, *, scenario: str) -> str:
    """Return *fragment*'s qualified name: ``module.qualname``.

    Every story item is a :class:`Choose` or a **named module-level**
    fragment — a parameterized helper is called from inside one — so this
    name is stable, and the committed plot manifest records a fragment by it
    (DEMOCI-11-034).

    Args:
        fragment: The story item, a :data:`Fragment`. Typed as an opaque
            object because deciding whether it *has* a stable name is this
            function's whole job: a ``functools.partial`` and a callable
            instance are both assignable to :data:`Fragment` and neither
            carries a ``__qualname__``, so the narrower annotation would
            promise a check the type system does not make.
        scenario: The scenario whose story holds it, for the message.

    Returns:
        ``f"{fragment.__module__}.{fragment.__qualname__}"``.

    Raises:
        DemoStoryError: When that name would not be stable. Refusing beats
            recording it: a manifest row that moves on an unrelated rename
            makes every later diff unreadable, which is the one thing the
            artifact exists to keep legible.
    """
    module = getattr(fragment, "__module__", None)
    qualname = getattr(fragment, "__qualname__", None)
    reason = _unstable_name_reason(module, qualname)
    if reason is not None:
        raise DemoStoryError(
            f"scenario {scenario!r} has a story item {fragment!r} that the "
            f"plot manifest cannot name: {reason} (DEMOCI-11-034). Give the "
            "step a module-level function in the scenario's module or under "
            "vultron/demo/helpers/, and call any parameterized helper from "
            "inside it."
        )
    return f"{module}.{qualname}"


#: Every word that names a container rather than the case: each container's
#: own slug, read from :data:`~vultron.demo.helpers.cast.ALL_SLOTS` so a sixth
#: slot cannot be added without joining this check, and the bare word
#: ``container`` itself.  A container is *where* a step runs, never what it
#: does, so naming one in a fragment's opening sentence tells a reader of the
#: story nothing about the case (DEMOCI-11-066).
_CONTAINER_WORDS: frozenset[str] = frozenset(
    [*(slot.name for slot in ALL_SLOTS), "container", "containers"]
)

#: A code identifier spelled as words joined by underscores:
#: ``add_note_to_case``, ``CASE_OWNER``.  It is the one spelling a sentence
#: about coordinated disclosure never needs — the domain terms are "the case
#: note" and "the Case Owner" — so it is the mechanical signal that a
#: docstring opened in code rather than in domain terms (DEMOCI-11-066).
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b")

#: A code identifier spelled in dotted notation: ``CS.P``, ``EM.ACTIVE``,
#: ``CVDRole.COORDINATOR``.  One side has to start with a capital, which is
#: what keeps a sentence's own full stop out of it: ``"Acme Inc. engages"``
#: has a space after the stop and does not match, and a lowercase pair such
#: as ``e.g`` is not a name.
_DOTTED_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*"
    r"|[A-Za-z][A-Za-z0-9_]*\.[A-Z][A-Za-z0-9_]*)\b"
)

#: A demo milestone marker opening the sentence: ``M1:``, ``M2:``.  The
#: markers are the harness's own bookkeeping for which checkpoint a run
#: reached; they say nothing to the CVD reader the story is rendered for
#: (DEMOCI-11-065), so they belong in the docstring's body.
_MILESTONE_RE = re.compile(r"^M\d+:")

#: Punctuation that may close a sentence after its full stop, stripped before
#: the full-stop test so a quoted or parenthesised ending is not refused.
_CLOSERS = "\"'’”)]"

#: Abbreviations whose own full stop is not the end of a sentence.  Kept short
#: and extended only when a real fragment needs one: every entry weakens the
#: one-sentence check for every sentence.
_ABBREVIATIONS: tuple[str, ...] = (
    "e.g.",
    "i.e.",
    "etc.",
    "cf.",
    "vs.",
    "Inc.",
    "Ltd.",
    "Co.",
)

#: A sentence ending followed by more text: the signal that the summary holds
#: more than one sentence.  Covers ``?`` and ``!`` as well as the full stop,
#: because a question a step asks is still a whole sentence.
_SENTENCE_BREAK_RE = re.compile(r"[.!?]\s+\S")


def _opening_paragraph(fragment: object) -> str:
    """Return *fragment*'s docstring up to its first blank line, as one line.

    The docstring's summary, not its first physical line: a summary long
    enough to wrap is still one sentence, and reading only the first line
    would cut it in half.  Everything after the blank line is the body, which
    a story never shows.
    """
    doc = inspect.getdoc(fragment)
    if not doc:
        return ""
    summary: list[str] = []
    for line in doc.splitlines():
        if not line.strip():
            break
        summary.append(line.strip())
    return " ".join(summary)


def _holds_two_sentences(sentence: str) -> bool:
    """Whether *sentence* ends one sentence and starts another.

    The abbreviations of :data:`_ABBREVIATIONS` are blanked out first, so
    their full stops are not read as endings and the author is not told to
    move a remainder that does not exist.
    """
    scanned = sentence
    for abbreviation in _ABBREVIATIONS:
        scanned = scanned.replace(abbreviation, "_" * len(abbreviation))
    return _SENTENCE_BREAK_RE.search(scanned) is not None


def _sentence_violations(sentence: str) -> list[str]:
    """Return every way *sentence* is not one sentence in CVD domain terms.

    Every violation is reported, not the first: the sentence is refused as a
    unit, so an author told one reason at a time gains nothing from the round
    trip (EH-07-001).  Each kind is reported once however often it occurs, so
    a sentence naming one identifier twice does not print the same line twice.
    """
    violations: list[str] = []
    if not sentence.rstrip(_CLOSERS).endswith("."):
        violations.append(
            "it does not end in a full stop, so where the sentence ends is a "
            "guess"
        )
    if _holds_two_sentences(sentence):
        violations.append(
            "it holds more than one sentence; the opening sentence is the "
            "whole of what a story shows for the step, so put the rest in "
            "the docstring's body"
        )
    if "`" in sentence:
        violations.append(
            "it holds a backtick, which marks code rather than domain prose"
        )
    if _MILESTONE_RE.match(sentence):
        violations.append(
            "it opens with a demo milestone marker, which is the harness's "
            "bookkeeping rather than anything the case did; move it to the "
            "docstring's body"
        )
    violations.extend(
        f"it names the code identifier {match!r}"
        for match in sorted(
            set(_IDENTIFIER_RE.findall(sentence))
            | set(_DOTTED_RE.findall(sentence))
        )
    )
    lowered = sentence.lower()
    violations.extend(
        f"it names the container {word!r}"
        for word in sorted(_CONTAINER_WORDS)
        if re.search(rf"\b{re.escape(word)}\b", lowered)
    )
    return violations


def fragment_sentence(fragment: object, *, scenario: str) -> str:
    """Return *fragment*'s opening sentence: what the step does, in domain terms.

    The plot manifest names a fragment by code (:func:`fragment_name`), which
    a CVD domain expert cannot review.  One domain sentence per fragment is
    what lets each scenario's plot render as a numbered story on its narrative
    page (DEMOCI-11-065, DEMOCI-11-067).

    What "a code identifier" is read as, which DEMOCI-11-066 leaves wider
    than the check: a backtick, a name spelled as words joined by
    underscores or in dotted notation, a demo milestone marker, and any word
    that names a container rather than the case.  A *requirement or decision id*
    in parentheses — ``(CSB-15-002)``, ``(DEMOMA-14-004)`` — is a citation,
    not a code identifier, and is left alone: the narrative pages these
    sentences render into cite requirements in prose themselves, and the
    citation is how a reader checks the step against the spec.

    A step that cannot be named cannot be read either, so this starts from
    :func:`fragment_name`.  That is not only for the message: a
    ``functools.partial`` and a callable instance both answer ``__doc__``
    with a docstring their *class* owns — ``functools.partial``'s own reads
    "Create a new function with partial application ..." — which says nothing
    about the step and would pass every check below.

    Args:
        fragment: The story item, a :data:`Fragment`.  Typed as an opaque
            object for the same reason as in :func:`fragment_name`: whether it
            carries a usable docstring at all is part of what is being
            decided.
        scenario: The scenario whose story holds it, for the message.

    Returns:
        The docstring's summary — its text up to the first blank line, joined
        into one line.

    Raises:
        DemoStoryError: As :func:`fragment_name`, and when the summary is
            missing, is more than one sentence, or is written in code rather
            than in domain terms (DEMOCI-11-066).  Refusing beats rendering
            it: a story line holding a backtick or a ``snake_case`` name is
            the manifest's code name again, which is what the rendering
            exists to replace.
    """
    name = fragment_name(fragment, scenario=scenario)
    sentence = _opening_paragraph(fragment)
    violations = (
        _sentence_violations(sentence)
        if sentence
        else [
            "it has no docstring, so there is no sentence to open with; "
            "every fragment the plot manifest names has one"
        ]
    )
    if violations:
        raise DemoStoryError(
            f"scenario {scenario!r} has a story fragment "
            f"{name} whose opening sentence cannot be "
            f"told as a story: {'; '.join(violations)} (DEMOCI-11-065, "
            "DEMOCI-11-066). Open the docstring with one sentence saying "
            "what the step does in CVD domain terms, naming roles and acts "
            "rather than identifiers, helpers or containers."
        )
    return sentence


@dataclass(frozen=True)
class StoryProp[PropT]:
    """One artifact a story carries from the fragment that makes it onward.

    :class:`StoryState` names the artifacts *every* story has — the case, the
    report, the Offer, the delivered Invites.  A family's own artifacts are
    declared as props beside the fragments that pass them: the embargo in
    force in the Reporter → Coordinator → Vendor embargo pair, the note a
    later poster replies to.  A prop rather than a field on the state, and
    rather than a per-family subclass, because a fragment is typed
    ``Callable[[StoryState], None]`` and a ``Callable[[Subclass], None]`` is
    not assignable to it (``notes/demo-scenario-tree.md`` § "Composition").

    Declare one at module level, where the fragments that share it can see it::

        EMBARGO_IN_FORCE: StoryProp[str] = StoryProp("embargo in force", str)

    Attributes:
        name: What the artifact is, in the words the error message uses.
        type_: What :meth:`StoryState.keep` accepts and
            :meth:`StoryState.kept` returns.  Checked on the way in, so a
            reader never has to.
    """

    name: str
    type_: type[PropT]


@dataclass(frozen=True, slots=True)
class Choose:
    """One declared decision of a story (DEMOCI-11-013, DEMOCI-11-019).

    Frozen: the item is read by the registry at import time to derive the
    scenario's path and again by :func:`run_story` to record the step mark, and
    the two must be the same fact.
    """

    #: The branch point decided here; an entry of
    #: :data:`~vultron.demo.scenario.branch_points.BRANCH_POINTS`.
    branch_point: str
    #: The choice this story takes there.
    choice: str
    #: The cast member that decides, by the name its scenario seats it under
    #: (:class:`~vultron.demo.helpers.actor_roles.ActorRole`), not its actor
    #: id: a story is written before the run that draws the ids.
    by: str

    def __post_init__(self) -> None:
        # Validated here rather than when the registry merges the tree, so an
        # unknown branch point or choice fails where it is written.
        validate_path(((self.branch_point, self.choice),))
        if not isinstance(self.by, str) or not self.by:
            raise DemoStoryError(
                f"choice {self.branch_point}:{self.choice} names "
                f"{self.by!r} as the actor that decides it; the name is the "
                "one its scenario's ROLES seats the actor under, and the "
                "harness reads that actor's role from the canonical case "
                "(DEMOCI-11-013, DEMOCI-11-047)."
            )

    @property
    def step(self) -> PathStep:
        """This choice as one step of a scenario's path."""
        return (self.branch_point, self.choice)


def choose(branch_point: str, choice: str, *, by: str) -> Choose:
    """Declare that the story decides *branch_point* by taking *choice*.

    Args:
        branch_point: The branch point decided here.
        choice: The choice this story takes.
        by: The deciding cast member's name in this scenario.

    Returns:
        The story item. ``by`` is keyword-only: the first two arguments are a
        pair read from the branch-point table, and a third positional string
        beside them would be trivially swappable with either.

    Raises:
        DemoScenarioRegistryError: When the branch point or the choice is not
            in the branch-point table.
        DemoStoryError: When ``by`` is not a cast member's name.
    """
    return Choose(branch_point=branch_point, choice=choice, by=by)


@dataclass(frozen=True, slots=True)
class Story:
    """A scenario's story, or a named prefix several scenarios start with.

    Build one with :func:`story`, which is where prefixes are concatenated and
    the items are checked.
    """

    #: The story's items in order: fragments and declared choices.
    items: tuple[Choose | Fragment, ...]

    @property
    def path(self) -> tuple[PathStep, ...]:
        """The path this story walks: its choices, in order (DEMOCI-11-019).

        This is what ``@scenario(story=...)`` registers as the scenario's
        path, so the tree, the generated index and the step marks in the
        recordings all come from the code that runs.
        """
        return tuple(
            item.step for item in self.items if isinstance(item, Choose)
        )


def story(*parts: Story | Choose | Fragment) -> Story:
    """Assemble one story from named prefixes, choices and fragments.

    A :class:`Story` part is spliced in rather than nested, so a scenario that
    starts with a named prefix has one flat sequence: the path is the choices
    of the whole, and :func:`run_story` plays the items in the order written.

    Args:
        parts: Named prefixes, :func:`choose` items and fragments, in order.

    Returns:
        The assembled story.

    Raises:
        DemoStoryError: When no part is given, or a part is neither a story,
            a choice nor a callable fragment.
    """
    items: list[Choose | Fragment] = []
    for part in parts:
        if isinstance(part, Story):
            items.extend(part.items)
        elif isinstance(part, Choose) or callable(part):
            items.append(part)
        else:
            raise DemoStoryError(
                f"story item {part!r} is neither a named prefix, a "
                "choose(...) nor a fragment taking the story's state; a "
                "story is a flat sequence of those three."
            )
    if not items:
        raise DemoStoryError(
            "a story has at least one item; an empty one would register a "
            "scenario with no path and no steps to run."
        )
    return Story(items=tuple(items))
